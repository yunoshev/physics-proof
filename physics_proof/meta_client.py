"""Meta Model API client (SPEC.md M1).

One place for every call to ``https://api.meta.ai/v1``: the Responses API
for Spark (text, images, video input, strict JSON schema output, tool
calling, ``web_search``, reasoning effort), the Files API (upload with
expiry, delete), and SAM 3.1 streaming segmentation.

Wire facts below were measured against the live API on 2026-10-27 and are
also recorded in ``tasks/M1.md``. The SAM text lines are parsed with Meta's
``meta-sam-parser`` package; this module only pairs its records with video
frames and rasterises full-frame masks.

The API key comes only from ``META_API_KEY`` and is never logged, saved, or
put into an exception message.
"""

from __future__ import annotations

import base64
import json
import os
import random
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import httpx
import numpy as np
from meta_sam_parser import (
    CompletedOutcome,
    SegmentationBoxRecord,
    SegmentationMaskRecord,
    decode_mask_to_raster,
    video_segmentation_format,
)

from .config import MAX_DATA_URL_BYTES, Settings
from .ledger import Ledger, Usage, load_prices


class ApiError(Exception):
    """A non-retryable Meta API failure."""

    def __init__(self, status: int, message: str, param: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.param = param

    def __str__(self) -> str:
        text = f"Meta API error {self.status}: {self.message}"
        if self.param:
            text += f" (param: {self.param})"
        return text


class BillingError(ApiError):
    """HTTP 402: billing is not configured. Never retried."""


class StreamError(Exception):
    """The SSE stream was truncated or malformed."""


class TruncatedStreamError(StreamError):
    """The SSE stream ended before its completion event.

    A subclass of StreamError, so old ``except StreamError`` handling still
    applies. Only this failure mode is retried: the request itself was fine
    and a fresh attempt may get a complete stream. Malformed or empty
    streams fail fast instead.
    """


class ResponseFailedError(ApiError, StreamError):
    """The stream ended with ``response.failed`` or a bare ``error`` event.

    A subclass of both ApiError and StreamError, so old ``except`` handling
    for either still applies. Carries the server's message in ``message``
    and its code in ``code``. Never retried: the request itself was
    rejected or failed server-side.
    """

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(0, message, code)
        self.code = code

    def __str__(self) -> str:
        text = f"Meta API response failed: {self.message}"
        if self.code:
            text += f" (code: {self.code})"
        return text


class IncompleteResponseError(StreamError):
    """A terminal but incomplete response (e.g. ``max_output_tokens``).

    Raised only by callers that need a complete answer (search, the
    blindness classifier, mask check). The agent loop instead returns the
    partial response and retries with a larger limit. Carries the billed
    cost of the cut-off call so wrappers can account for it.
    """

    def __init__(
        self,
        reason: str,
        *,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        super().__init__(
            "response incomplete (%s): %d output tokens billed; "
            "raise max_output_tokens or shorten the request" % (reason, output_tokens)
        )
        self.reason = reason
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd


#: HTTP statuses worth another attempt (plus cut streams, resets, timeouts).
#: Other 4xx (including 402 billing and 400 validation errors) never retry.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass
class FunctionCall:
    """One parsed function call from a Spark turn."""

    id: str
    call_id: str
    name: str
    arguments: dict[str, Any]
    status: str


@dataclass
class UsageStats:
    """Token usage from ``response.completed`` (the source of truth)."""

    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass
class SparkResponse:
    """One finished Spark turn.

    ``incomplete_reason`` is None for complete responses; otherwise it is
    the server's ``incomplete_details.reason`` (usually
    ``"max_output_tokens"``). Incomplete turns still bill their usage.
    """

    id: str
    model: str
    status: str
    text: str
    output: list[dict[str, Any]]
    function_calls: list[FunctionCall]
    usage: UsageStats
    cost_usd: float
    raw: bytes = b""
    incomplete_reason: str | None = None


@dataclass
class SamObject:
    """One segmented object in one frame.

    ``box`` is half-open ``(x1, y1, x2, y2)`` in source pixels; ``mask`` is a
    boolean full-frame ``(H, W)`` array with True only inside the box.
    """

    id: str
    box: tuple[int, int, int, int]
    confidence: float | None
    mask: np.ndarray = field(repr=False)


@dataclass
class SamResult:
    """Decoded SAM 3.1 segmentation of a video."""

    frames: dict[int, list[SamObject]]
    frames_processed: int
    cost_usd: float
    model: str = "sam-3.1"
    raw: bytes = b""


def _mime_for(path: Path, kind: str) -> str:
    suffix = path.suffix.lower()
    if kind == "video":
        return {".mp4": "video/mp4", ".mov": "video/quicktime"}.get(suffix, "video/mp4")
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")


def _data_url(path: Path, kind: str) -> str:
    mime = _mime_for(path, kind)
    blob = path.read_bytes()
    encoded = base64.b64encode(blob).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def text_part(text: str) -> dict[str, Any]:
    """Build an ``input_text`` content part."""
    return {"type": "input_text", "text": text}


def iter_sse_events(raw: bytes) -> Iterator[tuple[str | None, str]]:
    """Yield ``(event_name, data)`` pairs from a raw SSE body.

    Raises StreamError on undecodable bytes. Multi-line ``data:`` fields are
    joined with newlines; ``:`` comment lines are skipped.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StreamError(f"SSE stream is not valid UTF-8: {exc}") from exc
    event_name: str | None = None
    data_lines: list[str] = []
    lines = text.split("\n")

    def dispatch() -> tuple[str | None, str] | None:
        if not data_lines:
            return None
        return (event_name, "\n".join(data_lines))

    for line in lines:
        if line == "" or line == "\r":
            item = dispatch()
            event_name = None
            data_lines = []
            if item is not None:
                yield item
        elif line.startswith(":"):
            continue
        elif line.startswith("data:"):
            # One optional leading space is SSE framing, the rest is payload.
            payload_text = line[5:]
            if payload_text.startswith(" "):
                payload_text = payload_text[1:]
            if payload_text.endswith("\r"):
                payload_text = payload_text[:-1]
            data_lines.append(payload_text)
        elif line.startswith("event:"):
            event_name = line[6:].strip()
    tail = dispatch()
    if tail is not None:
        yield tail


def incomplete_reason_of(response: dict[str, Any]) -> str | None:
    """The server's ``incomplete_details.reason``, or None when complete."""
    details = response.get("incomplete_details") or {}
    if isinstance(details, dict):
        reason = details.get("reason")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
    if response.get("status") == "incomplete":
        return "incomplete"
    return None


def _failed_error(payload: dict[str, Any]) -> ResponseFailedError:
    """Build the error for a ``response.failed`` or ``error`` event."""
    response = payload.get("response")
    error: Any = payload.get("error")
    if isinstance(response, dict) and isinstance(response.get("error"), dict):
        error = response["error"]
    if isinstance(error, dict):
        message = str(error.get("message") or "response failed")
        code = error.get("code")
        code = str(code) if code is not None else None
    else:
        message = str(payload.get("message") or "response failed")
        code_raw = payload.get("code")
        code = str(code_raw) if code_raw is not None else None
    return ResponseFailedError(" ".join(message.split()), code)


def raise_if_incomplete(response: SparkResponse) -> None:
    """Raise IncompleteResponseError when a turn was cut off; else no-op."""
    reason = getattr(response, "incomplete_reason", None)
    if reason:
        usage = getattr(response, "usage", None)
        raise IncompleteResponseError(
            str(reason),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            cost_usd=float(getattr(response, "cost_usd", 0.0) or 0.0),
        )


def parse_response_body(raw: bytes) -> tuple[str, dict[str, Any]]:
    """Parse a full SSE body into ``(delta_text, terminal_response)``.

    ``terminal_response`` is the ``response`` object from the terminal
    event: ``response.completed`` as before, or ``response.incomplete``
    (returned, not raised — its usage is billed; check
    ``incomplete_reason_of``). ``response.failed`` and bare ``error``
    events raise ResponseFailedError with the server's message and code.
    Only a stream with no terminal event at all raises
    TruncatedStreamError (the retryable cut-stream case).
    """
    delta_texts: list[str] = []
    completed: dict[str, Any] | None = None
    incomplete: dict[str, Any] | None = None
    saw_event = False
    for _name, data in iter_sse_events(raw):
        if data == "":
            continue
        saw_event = True
        if data.strip() == "[DONE]":
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            snippet = data[:120].replace("\n", " ")
            raise StreamError(f"malformed SSE data line: {snippet!r}") from exc
        if not isinstance(payload, dict) or "type" not in payload:
            raise StreamError("SSE data line is not a Responses event object")
        event_type = payload["type"]
        if event_type == "response.output_text.delta":
            delta = payload.get("delta", "")
            if isinstance(delta, str):
                delta_texts.append(delta)
        elif event_type == "response.completed":
            response = payload.get("response", payload)
            if isinstance(response, dict):
                completed = response
        elif event_type == "response.incomplete":
            response = payload.get("response", payload)
            if isinstance(response, dict):
                incomplete = response
        elif event_type in ("response.failed", "error"):
            raise _failed_error(payload)
    if not saw_event:
        raise StreamError("empty SSE stream: no events received")
    if completed is not None:
        return "".join(delta_texts), completed
    if incomplete is not None:
        return "".join(delta_texts), incomplete
    raise TruncatedStreamError("truncated SSE stream: no response.completed event")


def _message_text(output: list[dict[str, Any]]) -> str:
    texts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if isinstance(part, dict) and part.get("type") == "output_text":
                text = part.get("text", "")
                if isinstance(text, str):
                    texts.append(text)
    return "".join(texts)


def _function_calls(output: list[dict[str, Any]]) -> list[FunctionCall]:
    calls: list[FunctionCall] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        raw_args = item.get("arguments", "{}")
        if not isinstance(raw_args, str):
            raise StreamError("function_call arguments are not a JSON string")
        try:
            arguments = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            snippet = raw_args[:120].replace("\n", " ")
            raise StreamError(f"function_call arguments are not valid JSON: {snippet!r}") from exc
        if not isinstance(arguments, dict):
            raise StreamError("function_call arguments JSON is not an object")
        calls.append(
            FunctionCall(
                id=str(item.get("id", "")),
                call_id=str(item.get("call_id", "")),
                name=str(item.get("name", "")),
                arguments=arguments,
                status=str(item.get("status", "")),
            )
        )
    return calls


def _usage_of(completed: dict[str, Any]) -> UsageStats:
    usage = completed.get("usage", {}) or {}
    input_details = usage.get("input_tokens_details", {}) or {}
    output_details = usage.get("output_tokens_details", {}) or {}
    return UsageStats(
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        cached_tokens=int(input_details.get("cached_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
        reasoning_tokens=int(output_details.get("reasoning_tokens", 0) or 0),
    )


def decode_sam_text(
    full_text: str, width: int, height: int
) -> dict[int, list[SamObject]]:
    """Decode SAM 3.1 output text into per-frame objects with full-frame masks.

    Uses Meta's ``meta-sam-parser`` for the line grammar and mask codec; this
    function only pairs box/mask records and places each box-sized raster at
    its box origin in an ``(H, W)`` frame. Frames without objects are absent.
    """
    parser = video_segmentation_format().create_parser()
    parser.push(full_text)
    result = parser.finish(CompletedOutcome()).result
    boxes: dict[tuple[int, str], SegmentationBoxRecord] = {}
    masks: dict[tuple[int, str], SegmentationMaskRecord] = {}
    for record in result.records:
        frame_index = record.frame.frame_index if record.frame is not None else None
        if frame_index is None:
            continue
        key = (frame_index, record.object_id)
        if isinstance(record, SegmentationBoxRecord):
            boxes[key] = record
        elif isinstance(record, SegmentationMaskRecord):
            masks[key] = record
    frames: dict[int, list[SamObject]] = {}
    for key in sorted(boxes):
        if key not in masks:
            continue
        frame_index, object_id = key
        box = boxes[key]
        mask_record = masks[key]
        left, top = int(box.left), int(box.top)
        right, bottom = int(box.right), int(box.bottom)
        raster = decode_mask_to_raster(mask_record.mask)
        crop = np.frombuffer(raster, dtype=np.uint8).reshape(
            mask_record.mask.height, mask_record.mask.width
        )
        full = np.zeros((height, width), dtype=bool)
        bottom_clip = min(top + crop.shape[0], height)
        right_clip = min(left + crop.shape[1], width)
        if top < height and left < width and bottom_clip > top and right_clip > left:
            patch = crop[: bottom_clip - top, : right_clip - left].astype(bool)
            full[top:bottom_clip, left:right_clip] = patch
        confidence = box.confidence
        if confidence is None:
            confidence = mask_record.confidence
        frames.setdefault(frame_index, []).append(
            SamObject(
                id=object_id,
                box=(left, top, right, bottom),
                confidence=confidence,
                mask=full,
            )
        )
    for objects in frames.values():
        objects.sort(key=lambda item: item.id)
    return frames


def video_dimensions(path: str | Path) -> tuple[int, int]:
    """Return ``(width, height)`` of a video via ffprobe."""
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe is required for video dimensions") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {completed.stderr.strip()}")
    parts = completed.stdout.strip().split(",")
    if len(parts) != 2:
        raise RuntimeError(f"ffprobe gave unexpected output for {path}: {completed.stdout!r}")
    return int(parts[0]), int(parts[1])


class MetaClient:
    """All HTTP calls to the Meta Model API, plus one ledger line per call."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        settings: Settings | None = None,
        ledger: Ledger | None = None,
        run: str = "m1",
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("META_API_KEY", "")
        if not key:
            raise ApiError(0, "META_API_KEY environment variable is not set")
        self._api_key = key
        self.settings = settings or Settings.from_env()
        self.ledger = ledger
        self.run = run
        self._prices: dict[str, Any] | None = None

    def __repr__(self) -> str:
        return f"MetaClient(model={self.settings.model!r}, run={self.run!r})"

    @property
    def prices(self) -> dict[str, Any]:
        """Price table, loaded once from the configured path."""
        if self._prices is None:
            self._prices = load_prices(self.settings.prices_path)
        return self._prices

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Accept": "text/event-stream"}

    def _record(
        self,
        *,
        kind: str,
        model: str,
        input_tokens: int = 0,
        cached_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
        frames: int = 0,
        searches: int = 0,
        note: str = "",
    ) -> float:
        if self.ledger is None:
            from .ledger import compute_cost_usd

            return compute_cost_usd(
                Usage(
                    run=self.run,
                    model=model,
                    kind=kind,
                    input_tokens=input_tokens,
                    cached_tokens=cached_tokens,
                    output_tokens=output_tokens,
                    reasoning_tokens=reasoning_tokens,
                    frames=frames,
                    searches=searches,
                    note=note,
                ),
                self.prices,
            )
        record = self.ledger.add(
            Usage(
                run=self.run,
                model=model,
                kind=kind,
                input_tokens=input_tokens,
                cached_tokens=cached_tokens,
                output_tokens=output_tokens,
                reasoning_tokens=reasoning_tokens,
                frames=frames,
                searches=searches,
                note=note,
            )
        )
        return float(record["usd"])

    def _check_status(self, response: httpx.Response) -> None:
        """Raise BillingError/ApiError for a finished non-2xx response."""
        if 200 <= response.status_code < 300:
            return
        try:
            response.read()
        except Exception:
            pass
        try:
            body = response.json()
        except ValueError:
            body = {}
        error = body.get("error", {}) if isinstance(body, dict) else {}
        if not isinstance(error, dict):
            error = {"message": str(error)}
        message = str(error.get("message") or body.get("message") or response.text[:200] or "request failed")
        message = " ".join(message.split())
        param = error.get("param")
        param = str(param) if param is not None else None
        code = str(error.get("code") or "")
        if response.status_code == 402:
            raise BillingError(
                response.status_code,
                f"Meta API billing is not configured ({code}): "
                "add a payment method on the Billing page, then retry.",
            )
        raise ApiError(response.status_code, message, param)

    def _sleep_before_retry(self, attempt: int, response: httpx.Response | None) -> None:
        """Wait before the next attempt: Retry-After wins, else backoff+jitter.

        Backoff is ``backoff_base_s * 2**attempt`` (1 s, 2 s, 4 s by default)
        plus up to one more base of jitter. A zero base (tests) sleeps zero.
        """
        wait_s: float | None = None
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after is not None:
                try:
                    wait_s = max(0.0, float(retry_after))
                except ValueError:
                    wait_s = None
        if wait_s is None:
            base = self.settings.backoff_base_s
            wait_s = base * (2.0**attempt) + random.uniform(0.0, base)
        time.sleep(min(wait_s, 60.0))

    def _log_retry(
        self,
        *,
        kind: str,
        model: str,
        attempt: int,
        attempts: int,
        reason: str,
        note: str = "",
    ) -> None:
        """Log one zero-cost ledger line for a failed attempt that retries.

        A cut stream carries no usage, so the line records zeros; the reason
        goes in the note. Partial usage, if a future failure mode ever has
        some, is recorded once on this line via explicit counts.
        """
        label = "retry %d/%d after %s" % (attempt + 1, attempts - 1, reason)
        if note:
            label += " (" + " ".join(str(note).split()) + ")"
        self._record(kind=kind, model=model, note=label)

    def _post_responses_stream(
        self,
        body: dict[str, Any],
        *,
        budget_check: Callable[[], None] | None = None,
        retry_kind: str = "spark",
        retry_model: str = "",
        retry_note: str = "",
    ) -> tuple[bytes, str, dict[str, Any]]:
        """POST /responses with stream=true; return (raw, delta_text, terminal).

        Retries transient failures — HTTP 429/500/502/503/504, a stream cut
        before any terminal event, connection resets and timeouts — until
        ``settings.max_attempts`` attempts are spent (3 retries by default).
        Other 4xx, billing errors, malformed streams, ``response.failed``
        and ``error`` events raise at once; a terminal ``response.incomplete``
        is returned (its usage is billed). Each failed attempt that will be
        retried is logged to the ledger as a zero-cost line with its reason.
        ``budget_check``, when given, runs before every attempt and aborts
        the loop when it raises.
        """
        attempts = max(1, self.settings.max_attempts)
        last_error: Exception | None = None
        url = self.settings.base_url.rstrip("/") + "/responses"
        for attempt in range(attempts):
            if budget_check is not None:
                budget_check()
            try:
                with httpx.Client(timeout=self.settings.timeout_s) as client:
                    with client.stream(
                        "POST", url, headers=self._headers(), json=body
                    ) as response:
                        if response.status_code in _RETRYABLE_STATUS:
                            reason = "HTTP %d" % response.status_code
                            try:
                                response.read()
                            finally:
                                response.close()
                            last_error = ApiError(
                                response.status_code, "transient Meta API failure"
                            )
                            if attempt < attempts - 1:
                                self._log_retry(
                                    kind=retry_kind,
                                    model=retry_model,
                                    attempt=attempt,
                                    attempts=attempts,
                                    reason=reason,
                                    note=retry_note,
                                )
                                self._sleep_before_retry(attempt, response)
                                continue
                            self._check_status(response)
                        self._check_status(response)
                        raw = b"".join(response.iter_bytes())
            except httpx.TransportError as exc:
                reason = "connection error (%s)" % type(exc).__name__
                last_error = exc
                if attempt < attempts - 1:
                    self._log_retry(
                        kind=retry_kind,
                        model=retry_model,
                        attempt=attempt,
                        attempts=attempts,
                        reason=reason,
                        note=retry_note,
                    )
                    self._sleep_before_retry(attempt, None)
                    continue
                raise
            try:
                _deltas, completed = parse_response_body(raw)
            except TruncatedStreamError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    self._log_retry(
                        kind=retry_kind,
                        model=retry_model,
                        attempt=attempt,
                        attempts=attempts,
                        reason=str(exc),
                        note=retry_note,
                    )
                    self._sleep_before_retry(attempt, None)
                    continue
                raise
            return raw, _deltas, completed
        assert last_error is not None
        raise last_error

    def respond(
        self,
        input: str | list[dict[str, Any]],
        *,
        model: str | None = None,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
        effort: str | None = None,
        web_search: bool = False,
        previous_response_id: str | None = None,
        store: bool = False,
        include: list[str] | None = None,
        max_output_tokens: int | None = None,
        note: str = "",
        budget_check: Callable[[], None] | None = None,
    ) -> SparkResponse:
        """Run one Spark turn and return the parsed response plus cost.

        Transient failures (HTTP 429/500/502/503/504, streams cut before
        any terminal event, resets, timeouts) retry up to 3 times with
        backoff; ``budget_check`` runs before every attempt. A terminal
        ``response.incomplete`` is returned with ``incomplete_reason`` set
        (usage is billed as usual); ``response.failed`` and ``error``
        events raise ResponseFailedError.
        """
        used_model = model or self.settings.model
        if isinstance(input, str):
            messages: list[dict[str, Any]] = [
                {"role": "user", "content": [text_part(input)]}
            ]
        else:
            messages = input
        body: dict[str, Any] = {
            "model": used_model,
            "input": messages,
            "stream": True,
            "store": store,
            "max_output_tokens": max_output_tokens or self.settings.max_output_tokens,
        }
        if instructions is not None:
            body["instructions"] = instructions
        merged_tools = list(tools) if tools else []
        if web_search:
            merged_tools.append({"type": "web_search"})
        if merged_tools:
            body["tools"] = merged_tools
            body["tool_choice"] = "auto"
        if json_schema is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "result",
                    "schema": json_schema,
                    "strict": True,
                }
            }
        if effort or self.settings.effort:
            body["reasoning"] = {"effort": effort or self.settings.effort}
        if previous_response_id is not None:
            body["previous_response_id"] = previous_response_id
        if include is not None:
            body["include"] = include
        raw, _deltas, completed = self._post_responses_stream(
            body,
            budget_check=budget_check,
            retry_kind="spark",
            retry_model=used_model,
            retry_note=note,
        )
        output = completed.get("output", [])
        if not isinstance(output, list):
            raise StreamError("response.completed output is not a list")
        text = _message_text(output) or _deltas
        usage = _usage_of(completed)
        reason = incomplete_reason_of(completed)
        cost = self._record(
            kind="spark",
            model=used_model,
            input_tokens=usage.input_tokens,
            cached_tokens=usage.cached_tokens,
            output_tokens=usage.output_tokens,
            reasoning_tokens=usage.reasoning_tokens,
            searches=1 if web_search else 0,
            note=note,
        )
        return SparkResponse(
            id=str(completed.get("id", "")),
            model=used_model,
            status=str(completed.get("status", "")),
            text=text,
            output=output,
            function_calls=_function_calls(output),
            usage=usage,
            cost_usd=cost,
            raw=raw,
            incomplete_reason=reason,
        )

    def image_part(self, path: str | Path) -> dict[str, Any]:
        """Build an ``input_image`` part, inlined as a data URL."""
        resolved = Path(path)
        return {"type": "input_image", "image_url": _data_url(resolved, "image")}

    def video_part(self, path: str | Path) -> dict[str, Any]:
        """Build an ``input_video`` part: data URL, or upload + file_id."""
        resolved = Path(path)
        if resolved.stat().st_size <= MAX_DATA_URL_BYTES:
            return {"type": "input_video", "video_url": _data_url(resolved, "video")}
        file_id = self.upload_file(resolved)
        return {"type": "input_video", "file_id": file_id}

    def _post_files(self, path: Path, expires_s: int) -> dict[str, Any]:
        attempts = max(1, self.settings.max_attempts)
        last_error: Exception | None = None
        url = self.settings.base_url.rstrip("/") + "/files"
        for attempt in range(attempts):
            with httpx.Client(timeout=self.settings.timeout_s) as client:
                with open(path, "rb") as handle:
                    files = {"file": (path.name, handle, "application/octet-stream")}
                    data = {
                        "purpose": "user_data",
                        "expires_after[anchor]": "created_at",
                        "expires_after[seconds]": str(expires_s),
                    }
                    response = client.post(
                        url,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        files=files,
                        data=data,
                    )
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    last_error = ApiError(response.status_code, "transient Meta API failure")
                    if attempt < attempts - 1:
                        self._sleep_before_retry(attempt, response)
                        continue
                self._check_status(response)
                payload = response.json()
                if not isinstance(payload, dict) or "id" not in payload:
                    raise StreamError("file upload response has no file id")
                return payload
        assert last_error is not None
        raise last_error

    def upload_file(self, path: str | Path, expires_s: int = 3600) -> str:
        """Upload a file for video input; returns the file id."""
        payload = self._post_files(Path(path), expires_s)
        self._record(kind="upload", model="files", note=str(path))
        return str(payload["id"])

    def delete_file(self, file_id: str) -> None:
        """Delete an uploaded file (HTTP 200 expected)."""
        attempts = max(1, self.settings.max_attempts)
        last_error: Exception | None = None
        url = self.settings.base_url.rstrip("/") + f"/files/{file_id}"
        for attempt in range(attempts):
            with httpx.Client(timeout=self.settings.timeout_s) as client:
                response = client.delete(
                    url, headers={"Authorization": f"Bearer {self._api_key}"}
                )
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    last_error = ApiError(response.status_code, "transient Meta API failure")
                    if attempt < attempts - 1:
                        self._sleep_before_retry(attempt, response)
                        continue
                self._check_status(response)
                self._record(kind="delete", model="files", note=file_id)
                return
        assert last_error is not None
        raise last_error

    def sam_video(
        self,
        video_path: str | Path,
        phrase: str,
        *,
        mask_encoding: str = "lossless",
        note: str = "",
        budget_check: Callable[[], None] | None = None,
    ) -> SamResult:
        """Segment one noun phrase in a video; always deletes the upload.

        The SAM stream shares the Spark retry policy: transient failures
        retry up to 3 times with backoff; ``budget_check`` runs before
        every attempt.
        """
        resolved = Path(video_path)
        width, height = video_dimensions(resolved)
        file_id = self.upload_file(resolved)
        try:
            body: dict[str, Any] = {
                "model": "sam-3.1",
                "input": [
                    {
                        "role": "user",
                        "content": [
                            text_part(phrase),
                            {"type": "input_video", "file_id": file_id},
                        ],
                    }
                ],
                "metadata": {
                    "include_confidence": "true",
                    "mask_encoding": mask_encoding,
                },
                "stream": True,
                "store": False,
            }
            raw, deltas, completed = self._post_responses_stream(
                body,
                budget_check=budget_check,
                retry_kind="sam",
                retry_model="sam-3.1",
                retry_note=note or phrase,
            )
            output = completed.get("output", [])
            full_text = _message_text(output) or deltas
            frames = decode_sam_text(full_text, width, height)
            usage = completed.get("usage", {}) or {}
            try:
                frames_processed = int(usage.get("video_frames_processed", 0) or 0)
            except (TypeError, ValueError):
                frames_processed = 0
            if frames_processed <= 0 and frames:
                frames_processed = max(frames) + 1
            cost = self._record(
                kind="sam",
                model="sam-3.1",
                frames=frames_processed,
                note=note or f"{resolved.name}: {phrase}",
            )
            return SamResult(
                frames=frames,
                frames_processed=frames_processed,
                cost_usd=cost,
                raw=raw,
            )
        finally:
            try:
                self.delete_file(file_id)
            except Exception:
                pass

# generated from brief/04 · part 04 owns this file
"""Shared HTTP, SSE and retry mechanics (part 04 §6).

``skills/meta-api.md`` literally: ``POST {base}/responses`` with
``stream:true``; blocks separated by blank lines with ``event:`` and
``data:`` lines; ``:`` comment lines and the final ``data: [DONE]``
skipped; dispatch on the JSON ``type``, not the ``event:`` name.
Exactly one terminal event ends a response (``response.completed``,
``response.incomplete``, ``response.failed``); a stream that ends
with none is truncated and retried. The error body is
``{"error": {"code", "message", "type", "param"}}``.

Retry policy: 429/500/502/503/504, transport errors and truncated
streams retry (4 attempts in all, backoff ``2**attempt + U(0,1)`` s,
a numeric ``Retry-After`` wins, any wait capped at 60 s). Other 4xx
(402 included) never retry: they raise :class:`FailedCallError`,
which the loop does not retry as network (a 400 is a bug in our
request; retrying it would hide it). The key never appears in any
error text.
"""

from __future__ import annotations

import json
import random
import time

from src import config as _config
from src.accounting import FailedCallError, NetworkError

__all__ = [
    "RETRYABLE_STATUSES",
    "FailedCallError",
    "NetworkError",
    "auth_headers",
    "backoff_s",
    "error_message",
    "parse_sse_terminal",
    "post_stream",
    "request_with_retries",
    "retry_after_s",
]


#: Statuses retried with backoff (everything else 4xx is final).
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def _default_sleep(seconds: float) -> None:
    time.sleep(float(seconds))


def auth_headers(api_key: str) -> dict:
    """Request headers. The key travels here and nowhere else."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "text/event-stream",
    }


def backoff_s(attempt: int) -> float:
    """Backoff before retry ``attempt`` (1-based), capped at 60 s."""
    return min(float(2 ** int(attempt)) + random.uniform(0.0, 1.0),
               float(_config.RETRY_AFTER_CAP_S))


def retry_after_s(headers) -> float | None:
    """Numeric ``Retry-After`` in seconds (capped), else None."""
    try:
        raw = (headers or {}).get("retry-after")
    except AttributeError:
        try:
            raw = headers.get("retry-after")
        except Exception:  # noqa: BLE001 — no usable header
            return None
    if raw is None:
        return None
    try:
        return min(max(0.0, float(str(raw).strip())), float(
            _config.RETRY_AFTER_CAP_S))
    except (TypeError, ValueError):
        return None


def error_message(status: int, body: bytes) -> str:
    """``HTTP {status}: {message}`` from an error body (no key)."""
    try:
        payload = json.loads((body or b"").decode("utf-8", "replace"))
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return f"HTTP {int(status)}: {error['message']}"
        if isinstance(payload.get("message"), str):
            return f"HTTP {int(status)}: {payload['message']}"
    text = (body or b"").decode("utf-8", "replace").strip()
    return f"HTTP {int(status)}: {text[:300]}" if text else (
        f"HTTP {int(status)}")


def parse_sse_terminal(body: bytes):
    """The terminal event of one SSE stream, or ``(None, None)``.

    Returns ``(terminal, error_text)`` where ``terminal`` is the
    ``response.completed`` / ``response.incomplete`` /
    ``response.failed`` event dict when one arrived, else None. A
    bare ``error`` event maps to ``(None, text)``. Dispatch is on the
    JSON ``type``; ``:`` comments and ``data: [DONE]`` are skipped.
    """
    terminal = None
    error_text = None
    for block in (body or b"").split(b"\n\n"):
        data_lines = []
        for line in block.split(b"\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith(b":"):
                continue
            if stripped.startswith(b"data:"):
                data_lines.append(stripped[len(b"data:"):].strip())
        if not data_lines:
            continue
        raw = b"\n".join(data_lines).strip()
        if raw == b"[DONE]":
            continue
        try:
            event = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind in ("response.completed", "response.incomplete",
                    "response.failed"):
            if terminal is None:
                terminal = event
        elif kind == "error" and error_text is None:
            detail = event.get("error") or event.get("message")
            error_text = (json.dumps(detail, default=str)[:500]
                          if detail is not None else "error event")
    return terminal, error_text


def post_stream(url: str, headers: dict, payload: dict,
                timeout: float):
    """One raw ``POST`` returning ``(status, headers, body)``.

    Never raises for an HTTP status: statuses are classified by the
    caller. Transport deaths raise the httpx error for the caller to
    class as network.
    """
    import httpx  # noqa: PLC0415 — the one HTTP library (part 04 §6)

    with httpx.Client(timeout=float(timeout)) as client:
        response = client.post(url, headers=headers, json=payload)
        return (int(response.status_code), response.headers,
                response.content)


def request_with_retries(url: str, headers: dict, payload: dict, *,
                         timeout: float | None = None,
                         sleep=None):
    """POST ``payload`` under the retry policy; return ``(terminal,
    error_text)`` from :func:`parse_sse_terminal`.

    Raises :class:`NetworkError` when every attempt dies on transport,
    a retryable status, or a truncated stream; raises
    :class:`FailedCallError` on a non-retryable 4xx (never retried —
    a 400 is a bug in our request).
    """
    pause = sleep if sleep is not None else _default_sleep
    limit = float(timeout if timeout is not None
                  else _config.API_TIMEOUT_S)
    attempts = int(_config.API_MAX_ATTEMPTS)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            status, headers_out, body = post_stream(
                url, headers, payload, limit)
        except Exception as exc:  # noqa: BLE001 — transport death
            last_error = exc
            if attempt >= attempts:
                break
            pause(backoff_s(attempt))
            continue
        if status in RETRYABLE_STATUSES:
            wait = retry_after_s(headers_out)
            last_error = NetworkError(
                f"HTTP {status} (retryable)")
            if attempt >= attempts:
                break
            pause(backoff_s(attempt) if wait is None else wait)
            continue
        if 400 <= status < 500:
            raise FailedCallError(error_message(status, body))
        if status >= 500:
            last_error = NetworkError(error_message(status, body))
            if attempt >= attempts:
                break
            pause(backoff_s(attempt))
            continue
        terminal, error_text = parse_sse_terminal(body)
        if terminal is None:
            last_error = NetworkError(
                "stream ended with no terminal event"
                + (f": {error_text}" if error_text else ""))
            if attempt >= attempts:
                break
            pause(backoff_s(attempt))
            continue
        return terminal, error_text
    raise NetworkError(
        f"request failed after {attempts} attempts: {last_error}")

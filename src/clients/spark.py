# generated from brief/04 · part 04 owns this file
"""The Spark agent-turn client (part 04 §6).

Implements the loop's ``spark_client`` injection exactly as
:func:`src.loop.run.run_loop` defines it: ``(request) ->
response`` with ``request`` ``{"model", "messages",
"max_output_tokens"}`` plus an optional ``"reasoning_effort"``
(the :class:`src.loop.history.History` snapshot; the effort is one
of ``"low"``, ``"medium"``, ``"high"``, ``"max"`` and anything else
falls back to the configured default) and ``response``
``{"terminal", "text", "tool_calls", "usage"}``.

History follows ``skills/meta-api.md`` (stateless turns): the
previous responses' output items — commentary plus every
``function_call`` item — are replayed, and each call is paired with
its ``function_call_output`` by ``call_id``. Part types follow the
skill's role table: user messages carry ``input_text`` /
``input_image`` / ``input_video`` parts, assistant messages carry
``output_text`` only (the first live run died on turn 2 with
``HTTP 400: content type input_text is not valid on assistant
messages`` because the client converted assistant history into
``input_text``). Tool images ride in a separate following user
message. System text travels as ``instructions``, never as a
message.

The tool definitions sent are the ones this client is given
(defaulting to part 07's export); the client keeps no copy of its
own. A 4xx other than 429 is returned as a ``response.failed``
terminal — never raised as transport, so the loop does not retry it
as network.
"""

from __future__ import annotations

import base64
import copy
import json
from pathlib import Path

from src import config as _config
from src.accounting import FailedCallError, NetworkError

from ._http import auth_headers, request_with_retries

__all__ = [
    "ClientBugError",
    "convert_messages",
    "make_spark_client",
    "to_api_tools",
]


class ClientBugError(Exception):
    """Our request could not be built (missing artifact, bad block).

    A bug in our request, never transport: the caller surfaces it as
    a ``response.failed`` terminal instead of retrying it.
    """


def to_api_tools(tool_schemas) -> list:
    """Part-07 tool definitions in API function-tool shape.

    The shape is ``{"type": "function", "name", "description",
    "parameters", "strict": true}`` verbatim from the given export —
    the client adds nothing and keeps no copy of its own.
    """
    converted = []
    for schema in tool_schemas or []:
        converted.append({
            "type": "function",
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": copy.deepcopy(schema.get("parameters", {})),
            "strict": True,
        })
    return converted


def _mime_for(path: str) -> str:
    lowered = str(path).lower()
    if lowered.endswith(".png"):
        return "image/png"
    return "image/jpeg"


def _read_artifact(run_dir, artifact: str) -> bytes:
    """Image bytes for a run-relative artifact path (or raise)."""
    if not isinstance(artifact, str) or not artifact.strip():
        raise ClientBugError("tool result names no image artifact")
    candidate = artifact.strip()
    if Path(candidate).is_absolute() or ".." in Path(candidate).parts:
        raise ClientBugError(
            f"image artifact {candidate!r} is not run-relative")
    if run_dir is None:
        path = Path(candidate)
    else:
        path = Path(str(run_dir)) / candidate
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ClientBugError(
            f"image artifact {candidate!r} is unreadable: {exc}") from exc
    if not data:
        raise ClientBugError(f"image artifact {candidate!r} is empty")
    return data


def convert_messages(messages, run_dir=None):
    """Split a loop snapshot into ``(instructions, input)``.

    ``instructions`` concatenates every system-role text (the stable
    prefix plus loop notices); ``input`` carries user messages
    (``input_text``/``input_image``), assistant messages
    (``output_text`` only) with their ``function_call`` items replayed
    alongside, and one ``function_call_output`` per tool message with
    tool images in a separate following user message.
    """
    instructions: list[str] = []
    api_input: list = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content") or []
        texts = [str(b.get("text", "")) for b in content
                 if isinstance(b, dict) and b.get("type") == "text"
                 and str(b.get("text", ""))]
        if role == "system":
            if texts:
                instructions.append("\n".join(texts))
            continue
        if role == "assistant":
            # Output parts only: input_text on an assistant message
            # is a live-API 400 (first live run, turn 2).
            api_input.append({
                "role": "assistant",
                "content": [{"type": "output_text",
                             "text": "\n".join(texts)}],
            })
            for call in message.get("function_calls") or []:
                if not isinstance(call, dict):
                    continue
                arguments = call.get("arguments")
                if isinstance(arguments, dict):
                    arguments = json.dumps(arguments)
                elif not isinstance(arguments, str):
                    arguments = json.dumps(arguments or {})
                api_input.append({
                    "type": "function_call",
                    "call_id": str(call.get("call_id") or call.get("name")),
                    "name": str(call.get("name")),
                    "arguments": arguments,
                })
            continue
        if role == "tool":
            output_text = "\n".join(texts)
            api_input.append({
                "type": "function_call_output",
                "call_id": str(message.get("call_id") or ""),
                "output": output_text,
            })
            images = [b for b in content
                      if isinstance(b, dict) and b.get("type") == "image"]
            if images:
                parts: list = [{
                    "type": "input_text",
                    "text": (f"Output image(s) from tool "
                             f"{message.get('tool', '')}:"),
                }]
                for block in images:
                    if block.get("image_url"):
                        parts.append({
                            "type": "input_image",
                            "image_url": block["image_url"],
                        })
                        continue
                    data = _read_artifact(run_dir, block.get("artifact"))
                    parts.append({
                        "type": "input_image",
                        "image_url": (
                            f"data:{_mime_for(block.get('artifact', ''))}"
                            f";base64,{base64.b64encode(data).decode()}"),
                    })
                api_input.append({"role": "user", "content": parts})
            continue
        # User (and any notice): input parts only.
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and str(
                    block.get("text", "")):
                parts.append({"type": "input_text",
                              "text": str(block["text"])})
            elif block.get("type") == "image":
                if block.get("image_url"):
                    parts.append({"type": "input_image",
                                  "image_url": block["image_url"]})
                else:
                    data = _read_artifact(run_dir, block.get("artifact"))
                    parts.append({
                        "type": "input_image",
                        "image_url": (
                            f"data:{_mime_for(block.get('artifact', ''))}"
                            f";base64,{base64.b64encode(data).decode()}"),
                    })
        if parts:
            api_input.append({"role": role or "user", "content": parts})
    return "\n\n".join(instructions), api_input


def _response_output(response: dict):
    """The terminal ``response`` object of an SSE terminal event."""
    if not isinstance(response, dict):
        return {}
    inner = response.get("response")
    return inner if isinstance(inner, dict) else response


def _extract_usage(response: dict) -> dict | None:
    """Terminal-event usage as the ledger's four ints (or None)."""
    usage = _response_output(response).get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
    except (TypeError, ValueError):
        return None
    details_in = usage.get("input_tokens_details") or {}
    details_out = usage.get("output_tokens_details") or {}
    try:
        cached = int(details_in.get("cached_tokens", 0))
        reasoning = int(details_out.get("reasoning_tokens", 0))
    except (TypeError, ValueError):
        cached, reasoning = 0, 0
    if min(input_tokens, output_tokens, cached, reasoning) < 0:
        return None
    return {
        "input_tokens": input_tokens,
        "cached_tokens": min(cached, input_tokens),
        "output_tokens": output_tokens,
        "reasoning_tokens": min(reasoning, output_tokens),
    }


def _extract_text_and_calls(response: dict):
    """``(text, tool_calls)`` from the terminal output items."""
    output = _response_output(response).get("output") or []
    texts: list[str] = []
    calls: list = []
    for item in output:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind == "message":
            for part in item.get("content") or []:
                if (isinstance(part, dict)
                        and part.get("type") == "output_text"
                        and part.get("text")):
                    texts.append(str(part["text"]))
        elif kind == "function_call":
            arguments = item.get("arguments", "{}")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments) if arguments else {}
                except ValueError:
                    arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            calls.append({
                "call_id": str(item.get("call_id") or item.get("name")),
                "name": str(item.get("name")),
                "arguments": arguments,
            })
    return "".join(texts), calls


def _incomplete_reason(response: dict) -> str:
    details = _response_output(response).get("incomplete_details") or {}
    if isinstance(details, dict) and details.get("reason"):
        return str(details["reason"])
    return "unknown"


def _failed_error(response: dict, fallback: str = "") -> str:
    inner = _response_output(response)
    error = inner.get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])[:500]
    if isinstance(error, str) and error:
        return error[:500]
    return fallback or "response.failed"


def make_spark_client(api_key, *, base_url=None, run_dir=None,
                      tools=None, model=None, timeout=None,
                      sleep=None):
    """The loop's agent callable (part 04 §6).

    ``tools`` defaults to part 07's export (single source; the loop's
    prompt prefix uses the same export). ``run_dir`` resolves
    tool-result image artifacts to bytes.
    """
    key = str(api_key)
    base = str(base_url or _config.API_BASE_URL)

    def _tool_defs():
        if tools is not None:
            return to_api_tools(tools)
        from src.tools.schemas import (  # noqa: PLC0415 — single source
            TOOL_SCHEMAS,
        )
        return to_api_tools(TOOL_SCHEMAS)

    def spark_client(request) -> dict:
        """Send one agent turn; never raise a 4xx as transport."""
        if not isinstance(request, dict):
            return {"terminal": "response.failed", "text": "",
                    "tool_calls": [], "usage": None,
                    "error": "spark request must be a dict"}
        try:
            instructions, api_input = convert_messages(
                request.get("messages"), run_dir)
        except ClientBugError as exc:
            return {"terminal": "response.failed", "text": "",
                    "tool_calls": [], "usage": None,
                    "error": f"client bug: {exc}"}
        except Exception as exc:  # noqa: BLE001 — our bug, not transport
            return {"terminal": "response.failed", "text": "",
                    "tool_calls": [], "usage": None,
                    "error": f"client bug: {type(exc).__name__}: {exc}"}
        requested_effort = request.get("reasoning_effort")
        if requested_effort not in ("low", "medium", "high", "max"):
            requested_effort = _config.SPARK_REASONING_EFFORT
        body: dict = {
            "model": (request.get("model") or model
                      or _config.SPARK_MODEL),
            "input": api_input,
            "stream": True,
            "store": False,
            "max_output_tokens": int(
                request.get("max_output_tokens")
                or _config.MAX_OUTPUT_TOKENS),
            # Max effort where judgment is made (addenda 2026-11-01,
            # 2026-11-04): the loop may name its effort per request;
            # anything else falls back to the configured default.
            "reasoning": {"effort": requested_effort},
            "tools": _tool_defs(),
            "tool_choice": "auto",
        }
        if instructions:
            body["instructions"] = instructions
        try:
            terminal, _ = request_with_retries(
                f"{base}/responses", auth_headers(key), body,
                timeout=(float(timeout) if timeout is not None
                         else _config.API_TIMEOUT_S),
                sleep=sleep)
        except FailedCallError as exc:
            # A 4xx other than 429 is a bug in our request: surface it
            # as a failed terminal the loop does not retry as network.
            return {"terminal": "response.failed", "text": "",
                    "tool_calls": [], "usage": None,
                    "error": str(exc)[:500]}
        kind = (terminal or {}).get("type")
        usage = _extract_usage(terminal or {})
        if kind == "response.completed":
            text, calls = _extract_text_and_calls(terminal or {})
            return {"terminal": "response.completed", "text": text,
                    "tool_calls": calls, "usage": usage}
        if kind == "response.incomplete":
            return {"terminal": "response.incomplete", "text": "",
                    "tool_calls": [],
                    "usage": usage,
                    "incomplete_reason": _incomplete_reason(
                        terminal or {})}
        error = _failed_error(terminal or {})
        return {"terminal": "response.failed", "text": "",
                "tool_calls": [], "usage": usage, "error": error}

    return spark_client

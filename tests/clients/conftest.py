# generated from brief/04 · part 04 owns this file
"""Shared stub HTTP server for the part-04 client tests.

The stub serves synthetic SSE streams built from the skills' grammar
(``skills/meta-api.md``, ``skills/sam-3-1.md``) — and, since the
2026-10-28 addendum, it validates like the live API, rejecting with
the live API's 400 messages:

- role/part-type mismatches (skill: "Part types by role");
- a ``function_call_output`` whose ``call_id`` was never issued;
- strict tools lacking ``additionalProperties:false`` or a complete
  ``required``;
- any ``tool_choice`` other than ``"auto"``;
- a missing ``stream:true``.

Helpers here are a pytest fixture (factory where a test needs
arguments); no test module imports this file by name.
"""

from __future__ import annotations

import json
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

__all__ = [
    "VALIDATION_ERROR",
    "StubServer",
    "sse_block",
    "sse_completed_text",
    "sse_completed_call",
    "sse_incomplete",
    "sse_failed",
    "sse_truncated",
]

#: Marker tests look for on stub validation failures.
VALIDATION_ERROR = "stub-validation"

_USER_PARTS = {"input_text", "input_image", "input_video"}
_ASSISTANT_PARTS = {"output_text"}


def _strict_params_ok(node) -> bool:
    """Every object level closed with a complete ``required``."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            props = node.get("properties")
            required = node.get("required")
            if not isinstance(props, dict):
                return False
            if (node.get("additionalProperties") is not False
                    or sorted(required or []) != sorted(props)):
                return False
            return all(_strict_params_ok(v) for v in props.values())
        if node.get("type") == "array" and "items" in node:
            return _strict_params_ok(node["items"])
        for keyword in ("anyOf", "oneOf", "allOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                if not all(_strict_params_ok(b) for b in branches):
                    return False
    elif isinstance(node, list):
        return all(_strict_params_ok(v) for v in node)
    return True


def validate_body(body) -> tuple | None:
    """``(status, error_dict)`` when the live API would 400, else None."""
    if not isinstance(body, dict):
        return None
    if body.get("stream") is not True:
        return (400, {"code": "invalid_request",
                      "message": "stream must be true",
                      "type": "invalid_request_error",
                      "param": "stream"})
    if "tool_choice" in body and body.get("tool_choice") != "auto":
        return (400, {"code": "invalid_request",
                      "message": 'tool_choice must be "auto"',
                      "type": "invalid_request_error",
                      "param": "tool_choice"})
    for tool in body.get("tools") or []:
        if not isinstance(tool, dict) or tool.get("type") != "function":
            continue
        params = tool.get("parameters") or {}
        if tool.get("strict") is not True or not _strict_params_ok(params):
            return (400, {"code": "invalid_request",
                          "message": ("strict tools must set "
                                      "additionalProperties:false with a "
                                      "complete required list"),
                          "type": "invalid_request_error",
                          "param": "parameters"})
    issued: set[str] = set()
    for item in body.get("input") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function_call":
            if item.get("call_id"):
                issued.add(str(item["call_id"]))
            continue
        if item.get("type") == "function_call_output":
            call_id = str(item.get("call_id") or "")
            if call_id not in issued:
                return (400, {"code": "invalid_request",
                              "message": (
                                  f"function_call_output call_id {call_id!r} "
                                  f"has no matching function_call"),
                              "type": "invalid_request_error",
                              "param": "input"})
            continue
        role = item.get("role")
        parts = item.get("content") or []
        if role == "assistant":
            for part in parts:
                kind = part.get("type") if isinstance(part, dict) else None
                if kind not in _ASSISTANT_PARTS:
                    return (400, {"code": "invalid_request",
                                  "message": (
                                      f"content type {kind} is not valid "
                                      f"on assistant messages"),
                                  "type": "invalid_request_error",
                                  "param": "input"})
        elif role == "user":
            for part in parts:
                kind = part.get("type") if isinstance(part, dict) else None
                if kind not in _USER_PARTS:
                    return (400, {"code": "invalid_request",
                                  "message": (
                                      f"content type {kind} is not valid "
                                      f"on user messages"),
                                  "type": "invalid_request_error",
                                  "param": "input"})
    return None


def sse_block(payload: dict, event: str = "response") -> bytes:
    """One SSE block for ``payload`` (dispatched on JSON ``type``)."""
    return (f"event: {event}\ndata: {json.dumps(payload)}\n\n").encode()


def _usage(input_tokens=100, cached_tokens=10, output_tokens=50,
           reasoning_tokens=5, **extra) -> dict:
    usage = {
        "input_tokens": input_tokens,
        "input_tokens_details": {"cached_tokens": cached_tokens},
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
    }
    usage.update(extra)
    return usage


def _terminal_event(kind: str, response: dict, seq: int = 1) -> bytes:
    out = sse_block({"type": "response.created",
                     "sequence_number": seq - 1 or 0})
    out += sse_block({"type": kind, "sequence_number": seq,
                      "response": response})
    out += b"data: [DONE]\n\n"
    return out


def sse_completed_text(text: str, **usage_kwargs) -> bytes:
    """A plain assistant answer (no tool call)."""
    return _terminal_event("response.completed", {
        "id": "resp_stub",
        "output": [{
            "type": "message", "id": "msg_1", "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
        }],
        "usage": _usage(**usage_kwargs),
    })


def sse_completed_call(text: str, *, call_id: str, name: str,
                       arguments: dict, **usage_kwargs) -> bytes:
    """Commentary plus one ``function_call`` (skill §Output items)."""
    return _terminal_event("response.completed", {
        "id": "resp_stub",
        "output": [
            {"type": "reasoning", "encrypted_content": "opaque"},
            {"type": "message", "id": "msg_1", "role": "assistant",
             "phase": "commentary",
             "content": [{"type": "output_text", "text": text}]},
            {"type": "function_call", "call_id": call_id, "name": name,
             "arguments": json.dumps(arguments)},
        ],
        "usage": _usage(**usage_kwargs),
    })


def sse_incomplete(reason: str = "max_output_tokens") -> bytes:
    return _terminal_event("response.incomplete", {
        "id": "resp_stub",
        "output": [],
        "usage": _usage(),
        "incomplete_details": {"reason": reason},
    })


def sse_failed(message: str = "boom") -> bytes:
    return _terminal_event("response.failed", {
        "id": "resp_stub",
        "output": [],
        "error": {"message": message},
    })


def sse_truncated() -> bytes:
    """A stream that dies with no terminal event (must be retried)."""
    return (sse_block({"type": "response.created", "sequence_number": 0})
            + sse_block({"type": "response.in_progress",
                         "sequence_number": 1})
            + b"data: [DONE]\n\n")


class StubServer:
    """A scripted stub of ``POST /responses``, ``/files`` (part 04 §6).

    ``script`` is a deque of ``(status, headers, body)`` tuples served
    in order to ``POST /responses``; ``FILES`` uploads/deletes are
    answered automatically. Every ``/responses`` request is validated
    like the live API first (a 400 there records the body and does
    not consume the script). ``log`` holds all decoded request
    bodies; ``hits`` counts ``/responses`` posts.
    """

    def __init__(self):
        self.script: deque = deque()
        self.log: list = []
        self.hits = 0
        self.rejections: list = []
        self.uploads: list = []
        self.deletes: list = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None, "stub is not running"
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def enqueue(self, body: bytes, status: int = 200,
                headers: dict | None = None) -> None:
        self.script.append((status, dict(headers or {}), body))

    def start(self) -> "StubServer":
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: D102 — quiet
                pass

            def _send(self, status, headers, body):
                self.send_response(status)
                self.send_header("Content-Type", "text/event-stream")
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = (self.rfile.read(length) if length else b"")
                if self.path == "/files":
                    stub.uploads.append(
                        {"size": len(raw),
                         "content_type": self.headers.get("Content-Type")})
                    payload = json.dumps(
                        {"id": f"file_{len(stub.uploads)}",
                         "bytes": len(raw), "created_at": 1,
                         "expires_at": 3601,
                         "status": "uploaded"}).encode()
                    self._send(200, {}, payload)
                    return
                if self.path != "/responses":
                    self._send(404, {}, b"{}")
                    return
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except ValueError:
                    body = {}
                stub.hits += 1
                stub.log.append(body)
                rejection = validate_body(body)
                if rejection is not None:
                    status, error = rejection
                    stub.rejections.append(body)
                    self._send(status, {},
                               json.dumps({"error": error}).encode())
                    return
                if stub.script:
                    status, headers, payload = stub.script.popleft()
                else:
                    status, headers, payload = (
                        200, {}, sse_completed_text("default reply"))
                self._send(status, headers, payload)

            def do_DELETE(self):
                if self.path.startswith("/files/"):
                    stub.deletes.append(self.path)
                    self._send(200, {}, b"{}")
                    return
                self._send(404, {}, b"{}")

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None


@pytest.fixture
def stub_server():
    """A running validating stub (factory: ``enqueue`` scripts it)."""
    server = StubServer().start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def make_clients():
    """Factory: live clients pointed at a stub base URL, no sleeping."""
    from src.clients import build_clients

    def _make(stub, **overrides):
        sleeps: list = []
        kwargs = {"base_url": stub.base_url, "timeout": 10,
                  "sleep": sleeps.append}
        kwargs.update(overrides)
        clients = build_clients("test-key", **kwargs)
        clients["sleeps"] = sleeps
        return clients

    return _make

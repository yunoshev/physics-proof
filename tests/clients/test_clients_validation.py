# generated from brief/04 · part 04 owns this file
"""Stub-validation tests (part 04 addendum 2026-10-28).

The first live run died on turn 2 with ``HTTP 400: content type
input_text is not valid on assistant messages`` while the offline
tests passed — the stub accepted anything. The stub now validates
like the live API, and the client must never produce what the stub
rejects. Each test below fails on the pre-fix client.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _post(base_url, body):
    with httpx.Client(timeout=10) as client:
        return client.post(f"{base_url}/responses", json=body)


def test_stub_rejects_assistant_input_text(stub_server):
    response = _post(stub_server.base_url, {
        "model": "m", "stream": True,
        "input": [{"role": "assistant",
                   "content": [{"type": "input_text", "text": "hi"}]}],
    })
    assert response.status_code == 400
    assert ("content type input_text is not valid on assistant messages"
            in response.text)


def test_stub_rejects_unknown_call_id(stub_server):
    response = _post(stub_server.base_url, {
        "model": "m", "stream": True,
        "input": [{"type": "function_call_output", "call_id": "call_x",
                   "output": "result"}],
    })
    assert response.status_code == 400
    assert "call_x" in response.text


def test_stub_rejects_open_strict_tools(stub_server):
    response = _post(stub_server.base_url, {
        "model": "m", "stream": True, "input": [],
        "tools": [{"type": "function", "name": "f", "description": "d",
                   "parameters": {"type": "object",
                                  "properties": {"a": {"type": "string"}},
                                  "required": ["a"]},
                   "strict": True}],
        "tool_choice": "auto",
    })
    assert response.status_code == 400
    assert json.loads(response.text)["error"]["param"] == "parameters"


def test_stub_rejects_bad_tool_choice(stub_server):
    response = _post(stub_server.base_url, {
        "model": "m", "stream": True, "input": [],
        "tool_choice": "required",
    })
    assert response.status_code == 400


def test_stub_rejects_missing_stream(stub_server):
    response = _post(stub_server.base_url, {
        "model": "m", "input": []})
    assert response.status_code == 400


def test_client_never_sends_assistant_input_text(stub_server,
                                                 make_clients):
    """The turn-2 regression: replayed history stays output_text."""
    from src.clients.spark import convert_messages

    history = [
        {"role": "system",
         "content": [{"type": "text", "text": "prefix"}]},
        {"role": "user",
         "content": [{"type": "text", "text": "analyse"}]},
        {"role": "assistant",
         "content": [{"type": "text", "text": "looking at frames"}],
         "function_calls": [{"type": "function_call",
                             "call_id": "call_1",
                             "name": "view_frames",
                             "arguments": {"frame_start": 0,
                                           "frame_end": 3}}]},
        {"role": "tool", "call_id": "call_1", "tool": "view_frames",
         "content": [{"type": "text",
                      "text": "[view_frames result]\nok"}]},
    ]
    instructions, api_input = convert_messages(history)
    assert instructions == "prefix"
    assistant = [i for i in api_input if i.get("role") == "assistant"]
    assert len(assistant) == 1
    assert assistant[0]["content"] == [
        {"type": "output_text", "text": "looking at frames"}]
    calls = [i for i in api_input if i.get("type") == "function_call"]
    assert [c["call_id"] for c in calls] == ["call_1"]
    outputs = [i for i in api_input
               if i.get("type") == "function_call_output"]
    assert [o["call_id"] for o in outputs] == ["call_1"]
    # And the stub accepts the real request built from it.
    from tests.clients.conftest import sse_completed_text

    stub_server.enqueue(sse_completed_text("ok"))
    clients = make_clients(stub_server)
    response = clients["spark_client"]({
        "model": "muse-spark-1.3-contributor", "messages": history,
        "max_output_tokens": 32768})
    assert response["terminal"] == "response.completed"
    assert stub_server.rejections == []


def test_client_400_is_failed_not_retried(stub_server, make_clients):
    """A 400 is a bug in our request: one hit, failed terminal."""
    from tests.clients.conftest import sse_completed_text

    stub_server.enqueue(sse_completed_text("unused"))
    clients = make_clients(stub_server, tools=[
        {"name": "bad", "description": "open schema",
         "parameters": {"type": "object",
                        "properties": {"a": {"type": "string"}},
                        "required": ["a"]}}])
    response = clients["spark_client"]({
        "model": "muse-spark-1.3-contributor",
        "messages": [{"role": "user",
                      "content": [{"type": "text", "text": "go"}]}],
        "max_output_tokens": 32})
    assert response["terminal"] == "response.failed"
    assert stub_server.hits == 1
    assert len(stub_server.script) == 1, "the script must be untouched"

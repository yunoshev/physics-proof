# generated from brief/04 · part 04 owns this file
"""Spark agent-turn client tests (part 04 §6, offline, stubbed)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.accounting import NetworkError

from tests.clients.conftest import (
    sse_completed_call,
    sse_completed_text,
    sse_failed,
    sse_incomplete,
    sse_truncated,
)

MODEL = "muse-spark-1.3-contributor"


def _request(text="go", **overrides):
    request = {
        "model": MODEL,
        "messages": [
            {"role": "system",
             "content": [{"type": "text", "text": "You are Spark."}]},
            {"role": "user",
             "content": [{"type": "text", "text": text}]},
        ],
        "max_output_tokens": 32768,
    }
    request.update(overrides)
    return request


def test_completed_text_and_request_shape(stub_server, make_clients):
    stub_server.enqueue(sse_completed_text("hello"))
    clients = make_clients(stub_server)
    response = clients["spark_client"](_request())
    assert response["terminal"] == "response.completed"
    assert response["text"] == "hello"
    assert response["tool_calls"] == []
    assert stub_server.rejections == []
    body = stub_server.log[-1]
    assert body["model"] == MODEL
    assert body["stream"] is True
    assert body["store"] is False
    assert body["max_output_tokens"] == 32768
    # The agent thinks at max effort (part 04 addendum 2026-11-01):
    # the request carries the configured effort, read from the
    # constant rather than spelled out here.
    from src import config as _config

    assert body["reasoning"] == {"effort": _config.SPARK_REASONING_EFFORT}
    assert body["max_output_tokens"] == _config.MAX_OUTPUT_TOKENS
    assert body["tool_choice"] == "auto"
    assert body["instructions"] == "You are Spark."
    # The system prompt travels as instructions, never as a message.
    assert [m.get("role") for m in body["input"]] == ["user"]
    assert body["input"][0]["content"] == [
        {"type": "input_text", "text": "go"}]
    # Part-07 tools travel verbatim (no client copy of its own).
    from src.tools.schemas import TOOL_SCHEMAS

    assert {t["name"] for t in body["tools"]} == {
        t["name"] for t in TOOL_SCHEMAS}
    for tool in body["tools"]:
        assert tool["type"] == "function"
        assert tool["strict"] is True


def test_function_call_round_trip(stub_server, make_clients):
    args = {"frame_start": 0, "frame_end": 3}
    stub_server.enqueue(sse_completed_call("looking", call_id="call_1",
                                           name="view_frames",
                                           arguments=args))
    clients = make_clients(stub_server)
    response = clients["spark_client"](_request())
    assert response["terminal"] == "response.completed"
    assert response["text"] == "looking"
    assert response["tool_calls"] == [{
        "call_id": "call_1", "name": "view_frames", "arguments": args}]


def test_incomplete_is_returned_not_retried(stub_server, make_clients):
    stub_server.enqueue(sse_incomplete("max_output_tokens"))
    clients = make_clients(stub_server)
    response = clients["spark_client"](_request())
    assert response["terminal"] == "response.incomplete"
    assert response["incomplete_reason"] == "max_output_tokens"
    assert stub_server.hits == 1
    # Incomplete turns with usage are still billed (loop debits them).
    assert response["usage"]["output_tokens"] > 0


def test_failed_terminal_is_returned(stub_server, make_clients):
    stub_server.enqueue(sse_failed("engine blew up"))
    clients = make_clients(stub_server)
    response = clients["spark_client"](_request())
    assert response["terminal"] == "response.failed"
    assert "engine blew up" in response["error"]
    assert stub_server.hits == 1


def test_truncated_stream_retried_then_raises(stub_server, make_clients):
    stub_server.enqueue(sse_truncated())
    stub_server.enqueue(sse_truncated())
    stub_server.enqueue(sse_truncated())
    stub_server.enqueue(sse_truncated())
    clients = make_clients(stub_server)
    try:
        clients["spark_client"](_request())
    except NetworkError:
        pass
    else:  # pragma: no cover — the client must not swallow this
        raise AssertionError("truncated stream must raise NetworkError")
    assert stub_server.hits == 4


def test_truncated_then_completed_recovers(stub_server, make_clients):
    stub_server.enqueue(sse_truncated())
    stub_server.enqueue(sse_completed_text("recovered"))
    clients = make_clients(stub_server)
    response = clients["spark_client"](_request())
    assert response["text"] == "recovered"
    assert stub_server.hits == 2


def test_429_retry_after_honoured(stub_server, make_clients):
    stub_server.enqueue(b"{}", status=429,
                        headers={"Retry-After": "2"})
    stub_server.enqueue(sse_completed_text("after backoff"))
    clients = make_clients(stub_server)
    response = clients["spark_client"](_request())
    assert response["text"] == "after backoff"
    assert clients["sleeps"] == [2.0]


def test_agent_turn_carries_config_reasoning_effort(
        stub_server, make_clients):
    """Every agent-turn body carries the configured reasoning effort
    (part 04 addendum 2026-11-01). Fails without the fix: the old
    body carries no ``reasoning`` key at all, so the run silently
    thinks below max."""
    from src import config as _config

    stub_server.enqueue(sse_completed_text("ok"))
    clients = make_clients(stub_server)
    clients["spark_client"](_request())
    body = stub_server.log[-1]
    assert body["reasoning"] == {"effort": _config.SPARK_REASONING_EFFORT}


def test_request_reasoning_effort_names_effort(
        stub_server, make_clients):
    """A request may name its reasoning effort (part 04 addendum
    2026-11-04). Fails without the fix: the body always carries the
    configured default, so a named effort is ignored."""
    from src import config as _config

    stub_server.enqueue(sse_completed_text("one"))
    stub_server.enqueue(sse_completed_text("two"))
    stub_server.enqueue(sse_completed_text("three"))
    clients = make_clients(stub_server)
    named = dict(_request())
    named["reasoning_effort"] = "high"
    clients["spark_client"](named)
    assert stub_server.log[-1]["reasoning"] == {"effort": "high"}
    clients["spark_client"](_request())
    assert stub_server.log[-1]["reasoning"] == {
        "effort": _config.SPARK_REASONING_EFFORT}
    unknown = dict(_request())
    unknown["reasoning_effort"] = "fast"
    clients["spark_client"](unknown)
    assert stub_server.log[-1]["reasoning"] == {
        "effort": _config.SPARK_REASONING_EFFORT}


def test_no_client_request_uses_low_effort(stub_server, make_clients):
    """No request body in ``src/clients/`` asks for low effort
    (part 04 addendum 2026-11-01). Fails without the fix: the four
    blind bodies all asked for low."""
    from src import config as _config

    stub_server.enqueue(sse_completed_text("ok"))
    stub_server.enqueue(sse_completed_text(
        '{"description": "d", "alternatives": []}'))
    stub_server.enqueue(sse_completed_text(
        '{"descriptions": [{"description": "a span", "view": "side",'
        ' "dimension": "depth"}]}'))
    stub_server.enqueue(sse_completed_text(
        '{"results": [{"agrees": true, "why": "match"}]}'))
    stub_server.enqueue(sse_completed_text('{"verdict": "no"}'))
    clients = make_clients(stub_server)
    clients["spark_client"](_request())
    clients["blind_spark_client"]({"image": b"x", "extents": {},
                                   "question": "q"})
    clients["blind_spark_client"]({"kind": "line_look", "image": b"x",
                                   "question": "q", "n_lines": 1})
    clients["blind_spark_client"]({"kind": "line_match",
                                   "descriptions": ["a span"],
                                   "claims": ["a claim"],
                                   "question": "q"})
    clients["classifier"]("a generic query")
    for body in stub_server.log:
        assert isinstance(body, dict)
        reasoning = body.get("reasoning")
        if isinstance(reasoning, dict):
            assert reasoning.get("effort") != "low", body
    # The bodies that must carry an effort do carry the configured one.
    assert stub_server.log[0]["reasoning"] == {
        "effort": _config.SPARK_REASONING_EFFORT}
    for body in stub_server.log[1:5]:
        assert body["reasoning"] == {
            "effort": _config.BLIND_REASONING_EFFORT}
        assert body["max_output_tokens"] == (
            _config.BLIND_MAX_OUTPUT_TOKENS)


def test_402_not_retried(stub_server, make_clients):
    payload = json.dumps({"error": {
        "code": "billing_not_configured",
        "message": "no payment method", "type": "auth_error",
    }}).encode()
    stub_server.enqueue(payload, status=402)
    clients = make_clients(stub_server)
    response = clients["spark_client"](_request())
    # A 4xx is a failed terminal, never transport: one hit, no retry.
    assert response["terminal"] == "response.failed"
    assert "no payment method" in response["error"]
    assert stub_server.hits == 1
    assert clients["sleeps"] == []


def test_client_test_basenames_unique_across_tests():
    """Test basenames are unique across tests/ (part 04 §3).

    Test directories are not packages and pytest's default import
    mode needs unique basenames: a second ``test_contract.py`` once
    stopped the whole suite at collection. Fails if any file added
    here reuses a basename owned by another part.
    """
    from pathlib import Path

    roots = Path("tests")
    assert roots.is_dir(), "run from the repo root"
    seen: dict[str, str] = {}
    for path in sorted(roots.rglob("test_*.py")):
        if ".venv" in path.parts:
            continue
        if path.name in seen:
            raise AssertionError(
                f"duplicate test module basename {path.name}: "
                f"{seen[path.name]} and {path}")
        seen[path.name] = str(path)
    mine = sorted(p.name for p in (roots / "clients").glob("test_*.py"))
    assert mine, "part 04 owns tests/clients/"
    assert len(set(mine)) == len(mine)


def test_usage_extraction_without_double_counting(stub_server,
                                                  make_clients):
    stub_server.enqueue(sse_completed_text(
        "priced", input_tokens=1000, cached_tokens=200,
        output_tokens=500, reasoning_tokens=100))
    clients = make_clients(stub_server)
    usage = clients["spark_client"](_request())["usage"]
    assert usage == {"input_tokens": 1000, "cached_tokens": 200,
                     "output_tokens": 500, "reasoning_tokens": 100}
    # The ledger's subset formula, never a sum of all four fields.
    from src.accounting import price_call

    assert price_call(usage["input_tokens"], usage["cached_tokens"],
                      usage["output_tokens"]) == pytest.approx(
                          (800 * 0.10 + 200 * 0.002 + 500 * 0.20)
                          / 1_000_000)

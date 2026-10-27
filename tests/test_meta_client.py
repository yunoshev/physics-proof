"""Offline probes 1-3: errors, retries, broken streams (fake server)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from physics_proof.config import Settings
from physics_proof.ledger import Ledger
from physics_proof.meta_client import (
    ApiError,
    BillingError,
    MetaClient,
    StreamError,
)

from fake_server import FakeMetaHandler, start_fake_server

COMPLETED_SSE = (
    b'data: {"type": "response.output_text.delta", "delta": "hi"}\n'
    b"\n"
    b'data: {"type": "response.completed", "response": {"id": "resp_1", '
    b'"status": "completed", "output": [{"type": "message", "id": "m1", '
    b'"role": "assistant", "content": [{"type": "output_text", "text": "hi"}]}], '
    b'"usage": {"input_tokens": 5, "input_tokens_details": {"cached_tokens": 1}, '
    b'"output_tokens": 3, "output_tokens_details": {"reasoning_tokens": 0}}}}\n'
    b"\n"
)


def make_client(base_url: str, **kwargs) -> MetaClient:
    settings = Settings(
        base_url=base_url,
        backoff_base_s=kwargs.pop("backoff_base_s", 0.0),
        **kwargs,
    )
    return MetaClient(api_key="test-fake-key", settings=settings)


def test_billing_error_exactly_one_request():
    body = json.dumps(
        {
            "error": {
                "code": "billing_not_configured",
                "message": "Add a card.",
                "type": "billing_error",
            }
        }
    ).encode()
    server, base_url = start_fake_server([(402, {"Content-Type": "application/json"}, body)])
    try:
        client = make_client(base_url)
        with pytest.raises(BillingError) as excinfo:
            client.respond("hello")
        message = str(excinfo.value)
    finally:
        server.shutdown()
    from fake_server import FakeMetaHandler

    assert len(FakeMetaHandler.requests) == 1
    assert "\n" not in message
    assert "Billing page" in message


def test_retry_after_429_then_success():
    script = [
        (429, {"Retry-After": "0", "Content-Type": "application/json"}, b'{"error": {"message": "slow"}}'),
        (200, {"Content-Type": "text/event-stream"}, COMPLETED_SSE),
    ]
    server, base_url = start_fake_server(script)
    try:
        client = make_client(base_url)
        response = client.respond("hello")
    finally:
        server.shutdown()
    from fake_server import FakeMetaHandler

    assert len(FakeMetaHandler.requests) == 2
    assert response.status == "completed"
    assert response.text == "hi"
    assert response.usage.input_tokens == 5
    assert response.usage.cached_tokens == 1
    assert response.usage.output_tokens == 3


def test_500s_raise_after_3_retries():
    body = b'{"error": {"message": "boom"}}'
    script = [(500, {"Content-Type": "application/json"}, body)] * 5
    server, base_url = start_fake_server(script)
    try:
        client = make_client(base_url)
        with pytest.raises(ApiError) as excinfo:
            client.respond("hello")
    finally:
        server.shutdown()
    from fake_server import FakeMetaHandler

    assert len(FakeMetaHandler.requests) == 4
    assert excinfo.value.status == 500


def test_400_error_carries_message_and_param():
    body = json.dumps(
        {"error": {"message": "bad schema", "param": "tools[0].parameters"}}
    ).encode()
    server, base_url = start_fake_server(
        [(400, {"Content-Type": "application/json"}, body)]
    )
    try:
        client = make_client(base_url)
        with pytest.raises(ApiError) as excinfo:
            client.respond("hello")
    finally:
        server.shutdown()
    assert excinfo.value.status == 400
    assert "bad schema" in excinfo.value.message
    assert excinfo.value.param == "tools[0].parameters"


@pytest.mark.parametrize(
    "body",
    [
        b'data: {"type": "response.output_text.delta", "delta": "hi"}\n\n',
        b'data: {"type": "oops", \n\n',
        b"",
        b"this is not sse at all\n\n",
    ],
)
def test_broken_stream_raises_stream_error(body):
    server, base_url = start_fake_server(
        [(200, {"Content-Type": "text/event-stream"}, body)]
    )
    try:
        client = make_client(base_url)
        with pytest.raises(StreamError):
            client.respond("hello")
    finally:
        server.shutdown()


def test_request_shape_defaults():
    server, base_url = start_fake_server(
        [(200, {"Content-Type": "text/event-stream"}, COMPLETED_SSE)]
    )
    try:
        client = make_client(base_url)
        client.respond("hello")
    finally:
        server.shutdown()
    from fake_server import FakeMetaHandler

    assert len(FakeMetaHandler.requests) == 1
    sent = FakeMetaHandler.requests[0]["json"]
    assert sent["stream"] is True
    assert sent["model"] == "muse-spark-1.3-contributor"
    assert sent["max_output_tokens"] == 4096
    assert sent["reasoning"] == {"effort": "low"}
    assert sent["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "hello"}]}
    ]


def test_upload_and_delete_roundtrip():
    upload_body = json.dumps(
        {"id": "file_1", "bytes": 10, "status": "ready"}
    ).encode()
    script = [
        (200, {"Content-Type": "application/json"}, upload_body),
        (200, {"Content-Type": "application/json"}, b"{}"),
    ]
    server, base_url = start_fake_server(script)
    try:
        client = make_client(base_url)
        file_id = client.upload_file(__file__)
        client.delete_file(file_id)
    finally:
        server.shutdown()
    from fake_server import FakeMetaHandler

    assert file_id == "file_1"
    assert FakeMetaHandler.requests[0]["method"] == "POST"
    assert FakeMetaHandler.requests[0]["path"] == "/files"
    assert FakeMetaHandler.requests[1]["method"] == "DELETE"
    assert FakeMetaHandler.requests[1]["path"] == "/files/file_1"


CUT_SSE = b'data: {"type": "response.output_text.delta", "delta": "hi"}\n\n'


def make_ledger_client(base_url: str, tmp_path, **kwargs) -> tuple[MetaClient, Path]:
    run_path = Path(str(tmp_path)) / "run.jsonl"
    global_path = Path(str(tmp_path)) / "global.jsonl"
    settings = Settings(
        base_url=base_url,
        backoff_base_s=kwargs.pop("backoff_base_s", 0.0),
        **kwargs,
    )
    ledger = Ledger(run_path, global_path)
    return MetaClient(api_key="test-fake-key", settings=settings, ledger=ledger), run_path


def read_ledger_lines(run_path) -> list:
    text = run_path.read_text(encoding="utf-8").strip() if run_path.exists() else ""
    return [json.loads(line) for line in text.split("\n")] if text else []


def test_cut_stream_once_then_complete_logs_one_retry(tmp_path):
    script = [
        (200, {"Content-Type": "text/event-stream"}, CUT_SSE),
        (200, {"Content-Type": "text/event-stream"}, COMPLETED_SSE),
    ]
    server, base_url = start_fake_server(script)
    try:
        client, run_path = make_ledger_client(base_url, tmp_path)
        response = client.respond("hello", note="probe")
    finally:
        server.shutdown()

    assert len(FakeMetaHandler.requests) == 2
    assert response.status == "completed"
    assert response.text == "hi"
    lines = read_ledger_lines(run_path)
    assert len(lines) == 2
    retry, success = lines
    assert retry["usd"] == 0.0
    assert "retry 1/3" in retry["note"]
    assert "truncated SSE stream" in retry["note"]
    assert success["usd"] > 0.0


def test_cut_stream_four_times_raises_after_3_retries(tmp_path):
    script = [(200, {"Content-Type": "text/event-stream"}, CUT_SSE)] * 5
    server, base_url = start_fake_server(script)
    try:
        client, run_path = make_ledger_client(base_url, tmp_path)
        with pytest.raises(StreamError, match="truncated SSE stream"):
            client.respond("hello")
    finally:
        server.shutdown()

    assert len(FakeMetaHandler.requests) == 4
    lines = read_ledger_lines(run_path)
    assert len(lines) == 3
    assert [line["note"] for line in lines] == [
        "retry 1/3 after truncated SSE stream: no response.completed event",
        "retry 2/3 after truncated SSE stream: no response.completed event",
        "retry 3/3 after truncated SSE stream: no response.completed event",
    ]
    assert all(line["usd"] == 0.0 for line in lines)


def test_400_never_retried(tmp_path):
    body = json.dumps({"error": {"message": "bad schema"}}).encode()
    script = [
        (400, {"Content-Type": "application/json"}, body),
        (200, {"Content-Type": "text/event-stream"}, COMPLETED_SSE),
    ]
    server, base_url = start_fake_server(script)
    try:
        client, run_path = make_ledger_client(base_url, tmp_path)
        with pytest.raises(ApiError) as excinfo:
            client.respond("hello")
    finally:
        server.shutdown()

    assert excinfo.value.status == 400
    assert len(FakeMetaHandler.requests) == 1
    assert read_ledger_lines(run_path) == []


def test_retry_after_wait_is_honoured(monkeypatch, tmp_path):
    waits: list = []
    monkeypatch.setattr(time, "sleep", waits.append)
    script = [
        (429, {"Retry-After": "2", "Content-Type": "application/json"}, b'{"error": {}}'),
        (200, {"Content-Type": "text/event-stream"}, COMPLETED_SSE),
    ]
    server, base_url = start_fake_server(script)
    try:
        client, run_path = make_ledger_client(base_url, tmp_path, backoff_base_s=1.0)
        response = client.respond("hello")
    finally:
        server.shutdown()

    assert response.status == "completed"
    assert len(waits) == 1
    assert waits[0] >= 2.0
    lines = read_ledger_lines(run_path)
    assert len(lines) == 2
    assert lines[0]["usd"] == 0.0
    assert "HTTP 429" in lines[0]["note"]


def test_budget_check_runs_before_each_attempt(tmp_path):
    calls: list = []

    class CapReached(RuntimeError):
        pass

    def check() -> None:
        calls.append(1)
        if len(calls) >= 3:
            raise CapReached("dollar cap reached")

    script = [(200, {"Content-Type": "text/event-stream"}, CUT_SSE)] * 5
    server, base_url = start_fake_server(script)
    try:
        client, _ = make_ledger_client(base_url, tmp_path)
        with pytest.raises(CapReached):
            client.respond("hello", budget_check=check)
    finally:
        server.shutdown()

    assert len(calls) == 3
    assert len(FakeMetaHandler.requests) == 2


def test_sam_stream_cut_once_then_complete(tmp_path, fixtures_dir):
    sam_sse = (fixtures_dir / "sam_red_square.sse").read_bytes()
    upload_body = json.dumps({"id": "file_9", "bytes": 10, "status": "ready"}).encode()
    script = [
        (200, {"Content-Type": "application/json"}, upload_body),
        (200, {"Content-Type": "text/event-stream"}, CUT_SSE),
        (200, {"Content-Type": "text/event-stream"}, sam_sse),
        (200, {"Content-Type": "application/json"}, b"{}"),
    ]
    server, base_url = start_fake_server(script)
    try:
        client, run_path = make_ledger_client(base_url, tmp_path)
        result = client.sam_video(fixtures_dir / "sam_clip.mp4", "red square")
    finally:
        server.shutdown()

    assert [item["path"] for item in FakeMetaHandler.requests] == [
        "/files",
        "/responses",
        "/responses",
        "/files/file_9",
    ]
    assert result.frames, "SAM retry should still decode masks"
    assert result.frames_processed > 0
    lines = read_ledger_lines(run_path)
    retries = [line for line in lines if "retry" in line["note"]]
    assert len(retries) == 1
    assert retries[0]["usd"] == 0.0
    assert "retry 1/3" in retries[0]["note"]
    assert "truncated SSE stream" in retries[0]["note"]

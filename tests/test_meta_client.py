"""Offline probes 1-3: errors, retries, broken streams (fake server)."""

from __future__ import annotations

import json

import pytest

from physics_proof.config import Settings
from physics_proof.meta_client import (
    ApiError,
    BillingError,
    MetaClient,
    StreamError,
)

from fake_server import start_fake_server

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


def test_four_500s_raise_after_3_attempts():
    body = b'{"error": {"message": "boom"}}'
    script = [(500, {"Content-Type": "application/json"}, body)] * 4
    server, base_url = start_fake_server(script)
    try:
        client = make_client(base_url)
        with pytest.raises(ApiError) as excinfo:
            client.respond("hello")
    finally:
        server.shutdown()
    from fake_server import FakeMetaHandler

    assert len(FakeMetaHandler.requests) == 3
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

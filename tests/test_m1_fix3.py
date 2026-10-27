"""M1-fix3 probes: incomplete/failed/error terminal events, agent retry (offline)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fake_server import FakeMetaHandler, start_fake_server
from physics_proof.agent import run_analysis
from physics_proof.blocks import load_masks
from physics_proof.config import DEFAULT_AGENT_MAX_OUTPUT_TOKENS, Settings
from physics_proof.ledger import Ledger
from physics_proof.mask_check import MaskCheck
from physics_proof.meta_client import (
    ApiError,
    FunctionCall,
    IncompleteResponseError,
    MetaClient,
    ResponseFailedError,
    SparkResponse,
    StreamError,
    TruncatedStreamError,
    UsageStats,
    incomplete_reason_of,
    parse_response_body,
)
from physics_proof.search_tool import SearchTool, classify_with_cost

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIP = FIXTURES / "sam_clip.mp4"


def _event(payload: dict[str, Any]) -> bytes:
    """One SSE data frame for a Responses event payload."""
    return b"data: " + json.dumps(payload).encode() + b"\n\n"


INCOMPLETE_RESPONSE = {
    "id": "resp_x",
    "status": "incomplete",
    "incomplete_details": {"reason": "max_output_tokens"},
    "output": [
        {
            "type": "message",
            "id": "m1",
            "role": "assistant",
            "status": "incomplete",
            "content": [{"type": "output_text", "text": "partial answer"}],
        }
    ],
    "usage": {
        "input_tokens": 100,
        "input_tokens_details": {"cached_tokens": 10},
        "output_tokens": 4096,
        "output_tokens_details": {"reasoning_tokens": 3000},
    },
}

INCOMPLETE_SSE = _event(
    {"type": "response.output_text.delta", "delta": "partial"}
) + _event({"type": "response.incomplete", "response": INCOMPLETE_RESPONSE})

FAILED_SSE = _event(
    {
        "type": "response.failed",
        "response": {
            "id": "resp_y",
            "status": "failed",
            "error": {"message": "server exploded", "code": "server_error"},
        },
    }
)

ERROR_SSE = _event(
    {"type": "error", "message": "upstream blew up", "code": "upstream_5xx"}
)

CUT_SSE = _event({"type": "response.output_text.delta", "delta": "hi"})

COMPLETED_SSE = _event(
    {
        "type": "response.completed",
        "response": {
            "id": "resp_z",
            "status": "completed",
            "output": [],
            "usage": {
                "input_tokens": 5,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 3,
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        },
    }
)


def _client(base_url: str, ledger_path: Path | None = None) -> MetaClient:
    settings = Settings(base_url=base_url, backoff_base_s=0.0)
    if ledger_path is None:
        return MetaClient(api_key="test-fake-key", settings=settings)
    ledger = Ledger(str(ledger_path), str(ledger_path) + ".global")
    return MetaClient(api_key="test-fake-key", settings=settings, ledger=ledger)


def test_incomplete_body_returned_with_reason_and_usage() -> None:
    """Probe 1a: an incomplete body parses; reason and usage are readable."""
    deltas, terminal = parse_response_body(INCOMPLETE_SSE)
    assert terminal["status"] == "incomplete"
    assert incomplete_reason_of(terminal) == "max_output_tokens"
    assert terminal["usage"]["output_tokens"] == 4096
    assert terminal["usage"]["output_tokens_details"]["reasoning_tokens"] == 3000
    assert "partial" in deltas


def test_completed_body_has_no_incomplete_reason() -> None:
    """A normal completed body still parses with no incomplete reason."""
    _deltas, terminal = parse_response_body(COMPLETED_SSE)
    assert terminal["status"] == "completed"
    assert incomplete_reason_of(terminal) is None


def test_incomplete_respond_bills_usage(tmp_path: Path) -> None:
    """Probe 1b: respond returns the incomplete turn and ledgers its tokens."""
    server, base_url = start_fake_server(
        [(200, {"Content-Type": "text/event-stream"}, INCOMPLETE_SSE)]
    )
    run_ledger = tmp_path / "run.jsonl"
    try:
        client = _client(base_url, run_ledger)
        response = client.respond("hello")
    finally:
        server.shutdown()
    assert len(FakeMetaHandler.requests) == 1
    assert response.status == "incomplete"
    assert response.incomplete_reason == "max_output_tokens"
    assert response.text == "partial answer"
    assert response.usage.output_tokens == 4096
    assert response.usage.reasoning_tokens == 3000
    lines = [
        json.loads(line)
        for line in run_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["usd"] > 0.0
    assert lines[0]["output_tokens"] == 4096


def test_failed_body_raises_with_server_message() -> None:
    """Probe 2a: response.failed raises once (no retry) with message and code."""
    server, base_url = start_fake_server(
        [(200, {"Content-Type": "text/event-stream"}, FAILED_SSE)]
    )
    try:
        client = _client(base_url)
        with pytest.raises(ResponseFailedError) as excinfo:
            client.respond("hello")
    finally:
        server.shutdown()
    assert len(FakeMetaHandler.requests) == 1
    assert "server exploded" in str(excinfo.value)
    assert excinfo.value.code == "server_error"
    assert isinstance(excinfo.value, ApiError)
    assert isinstance(excinfo.value, StreamError)


def test_error_event_raises_with_server_message() -> None:
    """Probe 2b: a bare error event raises with the server's message."""
    server, base_url = start_fake_server(
        [(200, {"Content-Type": "text/event-stream"}, ERROR_SSE)]
    )
    try:
        client = _client(base_url)
        with pytest.raises(ResponseFailedError, match="upstream blew up"):
            client.respond("hello")
    finally:
        server.shutdown()
    assert len(FakeMetaHandler.requests) == 1


def test_no_terminal_event_is_truncated() -> None:
    """Probe 2c: a stream with no terminal event is still a retryable cut."""
    with pytest.raises(TruncatedStreamError, match="truncated SSE stream"):
        parse_response_body(CUT_SSE)


def test_agent_default_limit_is_generous_and_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent default is at least 32k and honours the env override."""
    assert DEFAULT_AGENT_MAX_OUTPUT_TOKENS >= 32000
    assert Settings.from_env().agent_max_output_tokens >= 32000
    monkeypatch.setenv("META_AGENT_MAX_OUTPUT_TOKENS", "12345")
    assert Settings.from_env().agent_max_output_tokens == 12345


class _IncompleteClassifierClient:
    """Classifier stub that always comes back cut off."""

    def respond(self, query: str, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            text="{}", cost_usd=0.0004, incomplete_reason="max_output_tokens"
        )


def test_classifier_incomplete_is_an_error() -> None:
    """The blindness classifier surfaces a cut-off turn instead of guessing."""
    with pytest.raises(IncompleteResponseError, match="max_output_tokens"):
        classify_with_cost(_IncompleteClassifierClient(), ["mass of a steel hammer"])


class _IncompleteSearchClient:
    """Classifier says reference; the web search itself comes back cut off."""

    def respond(self, query: str, **kwargs: Any) -> SimpleNamespace:
        if kwargs.get("web_search") is True:
            return SimpleNamespace(
                text="{}",
                cost_usd=0.0025,
                incomplete_reason="max_output_tokens",
            )
        texts = json.loads(query.split("TEXTS:\n", 1)[1])
        items = [{"kind": "reference", "reason": "fake reference"} for _ in texts]
        return SimpleNamespace(
            text=json.dumps({"items": items}), cost_usd=0.0004
        )


def test_search_incomplete_is_a_clear_refusal(tmp_path: Path) -> None:
    """A cut-off search is refused with the incomplete reason, not silence."""
    tool = SearchTool(_IncompleteSearchClient(), tmp_path / "ws")
    result = tool.run("standard gravity value in m/s^2")
    assert result.allowed is False
    assert "incomplete" in result.reason
    assert "max_output_tokens" in result.reason


class _IncompleteMaskClient:
    """Mask-check stub that always comes back cut off."""

    def image_part(self, path: Path) -> dict[str, str]:
        return {"type": "input_image", "image_url": "data:image/png;base64,FAKE"}

    def respond(self, messages: Any, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            text="{}",
            cost_usd=0.001,
            usage=SimpleNamespace(output_tokens=4096),
            incomplete_reason="max_output_tokens",
        )


def test_mask_check_incomplete_raises(tmp_path: Path) -> None:
    """A cut-off mask check raises instead of judging from a partial answer."""
    mask_set = load_masks(FIXTURES / "maskcheck_a.npz")
    oid = int(mask_set.ids[0])
    frames = [int(mask_set.frames[0])]
    tool = MaskCheck(
        _IncompleteMaskClient(), tmp_path / "ws", FIXTURES / "maskcheck_clip.mp4"
    )
    with pytest.raises(IncompleteResponseError, match="max_output_tokens"):
        tool.run(FIXTURES / "maskcheck_a.npz", oid, frames, "the mask covers the box")


def _complete_call(name: str, args: dict[str, Any]) -> SparkResponse:
    """One finished fake Spark turn carrying a single tool call."""
    call = FunctionCall(
        id="fc-1", call_id="call-1", name=name, arguments=args, status="completed"
    )
    return SparkResponse(
        id="resp-fake",
        model="fake-spark",
        status="completed",
        text="calling " + name,
        output=[],
        function_calls=[call],
        usage=UsageStats(),
        cost_usd=0.001,
        raw=b"",
    )


def _incomplete_turn(reason: str = "max_output_tokens") -> SparkResponse:
    """One fake Spark turn cut off by the output limit."""
    return SparkResponse(
        id="resp-fake",
        model="fake-spark",
        status="incomplete",
        text="partial script",
        output=[],
        function_calls=[],
        usage=UsageStats(input_tokens=50, output_tokens=4096, reasoning_tokens=4000),
        cost_usd=0.001,
        raw=b"",
        incomplete_reason=reason,
    )


class FlakySpark:
    """Scripted provider: replays SparkResponses, records respond kwargs."""

    def __init__(self, script: list[SparkResponse]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []
        self.model = "fake-spark"

    def video_part(self, path: str | Path) -> dict[str, str]:
        return {"type": "input_video", "video_url": "data:video/mp4;base64,FAKE"}

    def image_part(self, path: str | Path) -> dict[str, str]:
        return {"type": "input_image", "image_url": "data:image/png;base64,FAKE"}

    def respond(self, messages: Any, **kwargs: Any) -> SparkResponse:
        self.calls.append(dict(kwargs))
        if self.script:
            return self.script.pop(0)
        return SparkResponse(
            id="resp-fake",
            model="fake-spark",
            status="completed",
            text="thinking",
            output=[],
            function_calls=[],
            usage=UsageStats(),
            cost_usd=0.001,
            raw=b"",
        )


def _limits(spark: FlakySpark) -> list[Any]:
    """The max_output_tokens of every agent turn in order."""
    return [call.get("max_output_tokens") for call in spark.calls]


def _turns(run_dir: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_dir / "turns").glob("turn*.json"))
    ]


def test_agent_retries_once_with_doubled_limit(tmp_path: Path) -> None:
    """Probe 4a: a cut-off turn retries once at 2x and the run continues."""
    spark = FlakySpark(
        [_incomplete_turn(), _complete_call("video_info", {}), _incomplete_turn()]
    )
    run_dir = tmp_path / "run"
    summary = run_analysis(CLIP, run_dir, spark=spark, max_turns=2)
    assert _limits(spark)[:3] == [32768, 65536, 32768]
    assert summary.status == "undetermined: budget"
    turns = _turns(run_dir)
    assert "The clip:" in turns[0]["result_text"]


def test_agent_gives_spark_a_short_reply_when_still_cut(tmp_path: Path) -> None:
    """Probe 4b: two cut-offs in a row become a short reply, not an error."""
    spark = FlakySpark([_incomplete_turn(), _incomplete_turn()])
    run_dir = tmp_path / "run"
    summary = run_analysis(
        CLIP, run_dir, spark=spark, max_turns=1, agent_max_output_tokens=100
    )
    assert _limits(spark) == [100, 200]
    assert summary.status == "undetermined: budget"
    turns = _turns(run_dir)
    assert len(turns) == 1
    assert "cut off at 4096 output tokens" in turns[0]["result_text"]
    assert "smaller steps" in turns[0]["result_text"]


def test_agent_other_incomplete_reason_is_an_error(tmp_path: Path) -> None:
    """A non-limit incomplete (e.g. content filter) ends the run clearly."""
    spark = FlakySpark([_incomplete_turn(reason="content_filter")])
    summary = run_analysis(CLIP, tmp_path / "run", spark=spark, max_turns=5)
    assert summary.status.startswith("error: spark call failed: ")
    assert "content_filter" in summary.status
    assert len(spark.calls) == 1

# generated from brief/06 · part 06 owns this file
"""Core loop behaviour: limits, context, history, retries, isolation."""

from __future__ import annotations

import json

import pytest

from src import config
from src.loop import run_loop


def test_loop_max_output_tokens_32k_config(script_spark, stub_responses,
                                           drive_loop, make_run,
                                           accepting_validator):
    """Every agent call requests the named 32k output limit (§3)."""
    assert config.MAX_OUTPUT_TOKENS == 32768
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"]("hello"),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1},
                           "evidence_path": None,
                           "dry_run": False}, "call-s")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert len(spark.requests) >= 2
    for request in spark.requests:
        assert request["max_output_tokens"] == 32768
        assert (request["max_output_tokens"]
                == config.MAX_OUTPUT_TOKENS)


def test_loop_stable_prefix_byte_identical_across_turns(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """Two consecutive requests carry the identical prefix (§1)."""
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"]("one"),
        stub_responses["completed"]("two"),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "dry_run": False},
                "call-s")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    first = spark.requests[0]["messages"][0]
    for request in spark.requests[1:]:
        assert request["messages"][0] == first


def test_loop_incomplete_is_reprompted_not_retried_as_network(
        script_spark, stub_responses, drive_loop, make_run, make_ledger,
        accepting_validator):
    """``incomplete`` is discarded and re-prompted once, never a stream
    error: the run continues and the billed usage still counts (§3)."""
    from src.accounting import Ledger
    run_dir = make_run()
    ledger = Ledger(run_id=run_dir.name, run_dir=str(run_dir))
    sleeps: list = []
    script = [
        {"terminal": "response.incomplete", "text": "half a thought",
         "tool_calls": [],
         "usage": {"input_tokens": 100, "cached_tokens": 90,
                   "output_tokens": 50, "reasoning_tokens": 10}},
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "dry_run": False},
                "call-s")]),
    ]
    spark = script_spark(script)
    out = run_loop(str(run_dir), run_dir.name, spark_client=spark,
                   ledger=ledger, sleep=sleeps.append, clock=None,
                   validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert len(spark.requests) == 2
    assert sleeps == []
    second_texts = [b.get("text", "") for m in spark.requests[1]["messages"]
                    for b in m.get("content", [])]
    assert any("cut off" in t for t in second_texts)
    assert any(entry.get("usage", {}).get("output_tokens") == 50
               for entry in ledger.entries)
    assert any(entry.get("usage", {}).get("cached_tokens") == 90
               for entry in ledger.entries)


def test_loop_dying_stream_retried_with_backoff_then_tool_error(
        drive_loop, make_run, make_ledger, stub_responses,
        accepting_validator):
    """A dying stream sleeps with backoff and retries; exhausted, the
    run ends undetermined with valid files — never a hang (§6)."""
    from src.accounting import NetworkError
    run_dir = make_run()
    sleeps: list = []

    def _dead(request):
        raise NetworkError("died")

    out = drive_loop(run_dir, _dead, ledger=make_ledger("r", run_dir),
                     sleep=sleeps.append)
    assert out["status"] == "undetermined"
    assert len(sleeps) == config.RETRY_MAX_ATTEMPTS - 1
    assert sleeps[1] > sleeps[0] >= 2.0
    assert (run_dir / "result.json").is_file()
    assert (run_dir / "summary.json").is_file()

    run_dir2 = make_run("run2")
    attempts = {"n": 0}

    def _flaky(request):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise NetworkError("blip")
        return stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "dry_run": False},
                "call-s")])

    sleeps2: list = []
    out2 = drive_loop(run_dir2, _flaky,
                      ledger=make_ledger("r2", run_dir2),
                      sleep=sleeps2.append,
                      validator=accepting_validator(run_dir2))
    assert out2["status"] == "submitted"
    assert len(sleeps2) == 2


def test_loop_history_replays_calls_with_paired_outputs(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """The second request replays the first response's ``function_call``
    and pairs it with its ``function_call_output`` (§3rd-run)."""
    import src.tools.view_frames as view_frames_mod
    seen: list = []

    def _fake_view(run_dir, turn, **kwargs):
        seen.append(dict(kwargs))
        return {"ok": True, "summary": "saw frames", "files": [],
                "metrics": {"cells": 2}}

    monkeypatch.setattr(view_frames_mod, "view_frames", _fake_view)
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"](
            "looking", [stub_responses["call"](
                "view_frames", {"frame_start": 0, "frame_end": 3},
                "call-1")]),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "dry_run": False},
                "call-2")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert seen and seen[0].get("frame_start") == 0
    messages = spark.requests[1]["messages"]
    assistants = [m for m in messages if m.get("role") == "assistant"
                  and m.get("function_calls")]
    assert any(call.get("call_id") == "call-1"
               for m in assistants for call in m["function_calls"])
    tools = [m for m in messages if m.get("role") == "tool"]
    assert any(m.get("call_id") == "call-1" for m in tools)


def test_loop_budget_line_on_every_tool_result(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """Every tool result ends with the informational budget line (§5)."""
    import src.tools.view_frames as view_frames_mod

    def _fake_view(run_dir, turn, **kwargs):
        return {"ok": True, "summary": "saw frames", "files": [],
                "metrics": {}}

    monkeypatch.setattr(view_frames_mod, "view_frames", _fake_view)
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"](
            "a", [stub_responses["call"]("view_frames", {}, "call-1")]),
        stub_responses["completed"](
            "b", [stub_responses["call"]("view_frames", {}, "call-2")]),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "dry_run": False},
                "call-3")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    rendered = [tc.get("rendered", "")
                for entry in (json.loads(line) for line in lines)
                for tc in entry.get("tool_calls", [])
                if tc.get("rendered")]
    assert len(rendered) == 2
    for text in rendered:
        last = text.splitlines()[-1]
        assert "turns left" in last
        assert "min left" in last


def test_loop_context_keeps_last_two_images(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """Only the last two tool results' images stay; older ones become a
    placeholder naming the artifact file (§4)."""
    import src.tools.view_frames as view_frames_mod

    def _fake_view(run_dir, turn, **kwargs):
        name = f"artifacts/t{turn}_view_frames_0.png"
        return {"ok": True, "summary": "sheet", "files": [name],
                "metrics": {}}

    monkeypatch.setattr(view_frames_mod, "view_frames", _fake_view)
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"](
            "a", [stub_responses["call"]("view_frames", {}, "call-1")]),
        stub_responses["completed"](
            "b", [stub_responses["call"]("view_frames", {}, "call-2")]),
        stub_responses["completed"](
            "c", [stub_responses["call"]("view_frames", {}, "call-3")]),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "dry_run": False},
                "call-4")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    messages = spark.requests[3]["messages"]
    tools = [m for m in messages if m.get("role") == "tool"]
    assert len(tools) == 3
    first_text = "\n".join(b.get("text", "") for b in tools[0]["content"]
                           if b.get("type") == "text")
    assert "[image omitted; see artifacts/t1_view_frames_0.png]" in first_text
    assert not [b for b in tools[0]["content"]
                if b.get("type") == "image"]
    for message in tools[1:]:
        assert [b for b in message["content"]
                if b.get("type") == "image"]


def test_loop_identical_call_flagged_with_earlier_turn(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """A repeated identical call still runs but is marked with the
    earlier turn; the third identical call gets the notice (§3rd-run)."""
    import src.tools.view_frames as view_frames_mod

    def _fake_view(run_dir, turn, **kwargs):
        return {"ok": True, "summary": "sheet", "files": [],
                "metrics": {}}

    monkeypatch.setattr(view_frames_mod, "view_frames", _fake_view)
    run_dir = make_run()
    args = {"frame_start": 0, "frame_end": 3}
    spark = script_spark([
        stub_responses["completed"](
            "a", [stub_responses["call"]("view_frames", args, "call-1")]),
        stub_responses["completed"](
            "b", [stub_responses["call"]("view_frames", args, "call-2")]),
        stub_responses["completed"](
            "c", [stub_responses["call"]("view_frames", args, "call-3")]),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "dry_run": False},
                "call-4")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    rendered = [tc.get("rendered", "")
                for entry in (json.loads(line) for line in lines)
                for tc in entry.get("tool_calls", [])
                if tc.get("rendered") and tc.get("name") == "view_frames"]
    assert len(rendered) == 3
    assert not rendered[0].startswith("same call as turn")
    assert rendered[1].startswith("same call as turn 1")
    assert rendered[2].startswith("same call as turn 1")
    assert "stop calling it" in rendered[2]


def test_loop_no_cross_run_state(script_spark, stub_responses, drive_loop,
                                 make_run, accepting_validator):
    """The loop passes no state from any other run: fresh conversation
    per run (§6)."""
    run_dir = make_run("first")
    spark_a = script_spark([
        stub_responses["completed"](
            "a", [stub_responses["call"]("view_frames", {}, "call-A")]),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "dry_run": False},
                "call-B")]),
    ])
    out_a = drive_loop(run_dir, spark_a,
                       validator=accepting_validator(run_dir))
    assert out_a["status"] == "submitted"
    run_dir2 = make_run("second")
    spark_b = script_spark([
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "dry_run": False},
                "call-C")]),
    ])
    out_b = drive_loop(run_dir2, spark_b,
                       validator=accepting_validator(run_dir2))
    assert out_b["status"] == "submitted"
    first_messages = spark_b.requests[0]["messages"]
    assert [m for m in first_messages if m.get("role") in ("assistant",
                                                           "tool")] == []
    blob = json.dumps(first_messages)
    assert "call-A" not in blob


def test_loop_prompt_has_no_never_watch_budget(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """The prompt plans the finish; it never says 'never watch the
    budget' (sixth live run)."""
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "dry_run": False},
                "call-s")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    prefix = (run_dir / "logs" / "prefix.txt").read_text(encoding="utf-8")
    assert "never watch the budget" not in prefix
    for request in spark.requests:
        for message in request["messages"]:
            for block in message.get("content", []):
                assert "never watch the budget" not in block.get(
                    "text", "")

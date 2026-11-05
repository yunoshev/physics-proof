# generated from brief/06 · part 06 owns this file
"""Prompt prefix: helper docs in the prefix, stable bytes, replayable
logs (part 06 addenda, run 12/3 and §6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.loop.prefix import (
    INITIAL_TASK,
    helper_module_names,
    initial_task,
)


def _submit_call(stub_responses, call_id="call-submit"):
    return stub_responses["call"](
        "submit", {"evidence": {"a": 1}, "evidence_path": None,
                   "dry_run": False}, call_id)


def test_loop_prefix_has_helpers_docs_and_modules(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """``build_prefix`` carries the helper docs verbatim (first heading
    plus every public module), identically across turns (run 12/3)."""
    docs = Path("src/helpers/HELPERS_DOCS.md").read_text(encoding="utf-8")
    first_heading = next(line for line in docs.splitlines()
                         if line.startswith("# "))
    modules = helper_module_names(docs)
    assert len(modules) >= 3
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"]("one"),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses)]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    prefix = spark.requests[0]["messages"][0]["content"][0]["text"]
    assert first_heading in prefix
    for module in modules:
        assert module in prefix
    assert (spark.requests[1]["messages"][0]["content"][0]["text"]
            == prefix)


def test_loop_prefix_identical_across_requests(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """Two consecutive requests carry the identical prefix, matching the
    operator-side copy in ``logs/``."""
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"]("one"),
        stub_responses["completed"]("two"),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses)]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    first = spark.requests[0]["messages"][0]
    for request in spark.requests[1:]:
        assert request["messages"][0] == first
    logged = (run_dir / "logs" / "prefix.txt").read_text(encoding="utf-8")
    assert logged == first["content"][0]["text"]


def test_loop_initial_task_names_no_source_reading(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """The initial task points at the in-prefix helper docs instead of
    source reading (run 12/3)."""
    assert "helper docs as needed" not in INITIAL_TASK
    assert "do not read its source" in INITIAL_TASK
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"](
            "done", [_submit_call(stub_responses)]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    initial = spark.requests[0]["messages"][1]
    assert initial["role"] == "user"
    blob = json.dumps(initial)
    assert "helper docs as needed" not in blob
    assert "do not read its source" in blob


def test_loop_initial_task_names_dry_run_by_one_third(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """The initial task ends with the dry-run-early rule: a first dry
    run by one third of the budget (Moon run 15)."""
    assert "by one third of the budget" in INITIAL_TASK
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"](
            "done", [_submit_call(stub_responses)]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    initial = spark.requests[0]["messages"][1]
    assert initial["role"] == "user"
    assert "by one third of the budget" in json.dumps(initial)


def test_loop_initial_task_builds_checks_with_library():
    """Range checks and the clock are built with the helper library:
    the initial task names the builders with and without a plan."""
    wonder = {
        "question": "Could a person really run straight up a wall?",
        "checks": [
            {"what": "ascent speed", "kind": "range",
             "why": "answers it", "how": "measure it",
             "compare_with": "records"},
            {"what": "step rate", "kind": "clock",
             "why": "tempo", "how": "count steps",
             "compare_with": "norms"},
        ],
    }
    for task in (INITIAL_TASK, initial_task(wonder)):
        assert "ranges.mask_extent" in task
        assert "ranges.print_check" in task
        assert "clock.clock_evidence" in task


def test_loop_logs_replayable_for_leak_test(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """Every turn appends prompt hash, tool calls, results and a ledger
    snapshot to ``logs/`` — enough to replay the run (§6)."""
    import src.tools.view_frames as view_frames_mod

    def _fake_view(run_dir, turn, **kwargs):
        return {"ok": True, "summary": "sheet", "files": [],
                "metrics": {}}

    monkeypatch.setattr(view_frames_mod, "view_frames", _fake_view)
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"](
            "look", [stub_responses["call"]("view_frames", {},
                                            "call-1")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-2")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        entry = json.loads(line)
        assert entry["prompt_hash"]
        assert isinstance(entry["tool_calls"], list)
        assert "ledger" in entry
        assert entry["ledger"]["totals"]["turns"] >= entry["turn"]
    first, second = (json.loads(line) for line in lines)
    assert first["tool_calls"][0]["name"] == "view_frames"
    assert "rendered" in first["tool_calls"][0]
    assert second["tool_calls"][0]["name"] == "submit"

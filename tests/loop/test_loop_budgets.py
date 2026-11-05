# generated from brief/06 · part 06 owns this file
"""Budget enforcement: halfway/finishing notices, closings, caps, and
the clean-dry-run last resort (part 06 §5 and the live-run addenda).

Caps always come from :mod:`src.config`; the suite pins no literal cap.
"""

from __future__ import annotations

import json

import pytest

from src import config
from src.loop import run_loop


#: Dry runs carry a real measurement (a segment with frames): the
#: loop refuses a placeholder dry run (part 06 addendum 2026-10-31),
#: so a test that needs a dry run to reach the validator submits
#: this. Real submits keep the bare ``{"a": 1}`` — the refusal is
#: dry-run-only.
_MEASURED_DRY_EVIDENCE = {"segments": [{"frames": {"start": 1, "apex": 5,
                                                   "end": 9}}]}


def _submit_call(stub_responses, dry_run=False, call_id="call-submit",
                evidence=None):
    if evidence is None:
        evidence = (dict(_MEASURED_DRY_EVIDENCE) if dry_run else {"a": 1})
    return stub_responses["call"](
        "submit", {"evidence": evidence, "evidence_path": None,
                   "dry_run": dry_run}, call_id)


def _rendered_of(run_dir, name):
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    return [tc.get("rendered", "")
            for entry in (json.loads(line) for line in lines)
            for tc in entry.get("tool_calls", [])
            if tc.get("rendered") and tc.get("name") == name]


def _thinking(stub_responses, n, prefix="thinking"):
    return [stub_responses["completed"](f"{prefix} {n}-{i}")
            for i in range(n)]


def test_loop_halfway_notice_once_at_turn_30(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """A stub that never submits gets the half-way notice exactly once,
    at half the configured turns (sixth live run read 30 of 60). The
    run then ends four turns into the finishing phase with no evidence
    file (wall run 7: the loop finishes the run)."""
    from src.loop.budgets import FINISHING_TURNS
    halfway = config.MAX_TURNS // 2
    start = next(turn for turn in range(1, config.MAX_TURNS + 1)
                 if turn / config.MAX_TURNS >= config.WARN_RATIO)
    run_dir = make_run()
    spark = script_spark([])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "undetermined"
    assert "budget" in out["reason"]
    assert out["turns"] == start + FINISHING_TURNS
    hits = [i for i, request in enumerate(spark.requests)
            if "nothing has been submitted" in json.dumps(
                request["messages"])]
    assert hits[0] == halfway - 1
    last = spark.requests[-1]["messages"]
    injected = [m for m in last
                if m.get("role") == "user"
                and "nothing has been submitted" in json.dumps(m)]
    assert len(injected) == 1


def test_loop_halfway_follows_wall_clock(
        script_spark, stub_responses, drive_loop, make_run, fake_clock,
        accepting_validator):
    """The half-way notice follows the first run-level budget to cross
    half — here wall time at low turn counts — and names it (run 10)."""
    run_dir = make_run()

    def _tenth(request):
        fake_clock.advance(config.HARD_CAP_WALL_S / 2 + 1)
        return stub_responses["completed"]("still looking")

    script = _thinking(stub_responses, 9) + [_tenth]
    script.append(stub_responses["completed"](
        "done", [_submit_call(stub_responses, call_id="call-submit")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    blobs = [json.dumps(request["messages"]) for request in spark.requests]
    assert not any("nothing has been submitted" in blob
                   for blob in blobs[:10])
    assert "Half the time" in blobs[10]
    last = spark.requests[-1]["messages"]
    injected = [m for m in last
                if m.get("role") == "user"
                and "nothing has been submitted" in json.dumps(m)]
    assert len(injected) == 1


def test_loop_hard_cap_synthesises_budget_undetermined(
        script_spark, stub_responses, drive_loop, make_run, fake_clock):
    """At a run-level cap with no clean dry run, the loop stops calling
    Spark and synthesises a valid budget undetermined file (§5)."""
    from src.contract import validate_result, validate_summary
    run_dir = make_run()

    def _first(request):
        fake_clock.advance(config.HARD_CAP_WALL_S + 5)
        return stub_responses["completed"]("looking")

    spark = script_spark([_first,
                          stub_responses["completed"]("never sent")])
    out = drive_loop(run_dir, spark, clock=fake_clock, validator=None)
    assert out["status"] == "undetermined"
    assert "budget" in out["reason"]
    assert len(spark.requests) == 1
    result = json.loads((run_dir / "result.json").read_text(
        encoding="utf-8"))
    assert validate_result(result) == []
    assert result["verdict"]["kind"] == "undetermined"
    summary = json.loads((run_dir / "summary.json").read_text(
        encoding="utf-8"))
    assert validate_summary(summary) == []
    assert summary["budget_outcome"] == "budget_undetermined"


def test_loop_near_limit_leaves_segment_open(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """Near the turn limit with SAM unused, segment stays open: the
    near-limit closing is per budget (run 3). The dry run first reopens
    exploration (one-third rule), and the call lands below the
    finishing phase, so only segment's own SAM budget could close it."""
    run_dir = make_run()
    seg_turn = int(config.MAX_TURNS * config.WARN_RATIO) - 1
    script = [stub_responses["completed"](
        "early dry", [_submit_call(stub_responses, dry_run=True,
                                   call_id="call-dry")])]
    script += _thinking(stub_responses, seg_turn - 2)
    script.append(stub_responses["completed"](
        "segment now", [stub_responses["call"](
            "segment", {"phrase": "the wall", "frame_start": 0,
                        "frame_end": 7, "confirm_small_range": True},
            "call-seg")]))
    script.append(stub_responses["completed"](
        "done", [_submit_call(stub_responses, call_id="call-submit")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert out["turns"] == seg_turn + 1
    rendered = _rendered_of(run_dir, "segment")
    assert len(rendered) == 1
    assert "closed" not in rendered[0]
    assert "sam_unavailable" in rendered[0]
    seg_request = spark.requests[seg_turn - 1]["messages"]
    assert "finishing phase" not in json.dumps(seg_request)


def test_loop_exploration_closes_until_first_dry_run(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        rejecting_validator):
    """Once the first run-level budget reaches one third with no submit,
    exploration closes; the first dry run reopens it (Moon run 15)."""
    import src.tools.run_python as run_python_mod
    third = config.MAX_TURNS // 3

    def _fake_python(run_dir, turn, **kwargs):
        return {"ok": True, "summary": "ran", "files": [],
                "metrics": {}}

    monkeypatch.setattr(run_python_mod, "run_python", _fake_python)
    run_dir = make_run()
    validator = rejecting_validator(
        run_dir, [[{"code": "E1", "field": "evidence", "detail": "fix"}]])
    script = _thinking(stub_responses, third - 1)
    script.append(stub_responses["completed"](
        "explore", [stub_responses["call"](
            "segment", {"phrase": "the wall", "frame_start": 0,
                        "frame_end": 7, "confirm_small_range": True},
            "call-seg"),
            stub_responses["call"]("run_python", {"code": "print(1)"},
                                   "call-py")]))
    script.append(stub_responses["completed"](
        "dry", [_submit_call(stub_responses, dry_run=True,
                             call_id="call-dry")]))
    script.append(stub_responses["completed"](
        "explore again", [stub_responses["call"](
            "segment", {"phrase": "the wall", "frame_start": 0,
                        "frame_end": 7, "confirm_small_range": True},
            "call-seg-2")]))
    script.append(stub_responses["completed"](
        "done", [_submit_call(stub_responses, call_id="call-submit")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark, validator=validator)
    assert out["status"] == "submitted"
    segments = _rendered_of(run_dir, "segment")
    assert len(segments) == 2
    assert segments[0].startswith("closed until your first dry run")
    assert "closed until your first dry run" not in segments[1]
    pythons = _rendered_of(run_dir, "run_python")
    assert len(pythons) == 1
    assert "closed" not in pythons[0]


def test_loop_finishing_phase_closes_at_wall_80(
        script_spark, stub_responses, drive_loop, make_run, fake_clock,
        monkeypatch, accepting_validator):
    """At 80% of wall time the finishing phase closes exploration while
    run_python stays open (run 13/4)."""
    import src.tools.run_python as run_python_mod

    def _fake_python(run_dir, turn, **kwargs):
        return {"ok": True, "summary": "ran", "files": [],
                "metrics": {}}

    monkeypatch.setattr(run_python_mod, "run_python", _fake_python)
    run_dir = make_run()

    def _first(request):
        fake_clock.advance(config.HARD_CAP_WALL_S * config.WARN_RATIO + 1)
        return stub_responses["completed"]("warming up")

    spark = script_spark([
        _first,
        stub_responses["completed"](
            "finish", [stub_responses["call"](
                "segment", {"phrase": "the wall", "frame_start": 0,
                            "frame_end": 7, "confirm_small_range": True},
                "call-seg"),
                stub_responses["call"]("run_python",
                                       {"code": "print(1)"},
                                       "call-py")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-submit")]),
    ])
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    segments = _rendered_of(run_dir, "segment")
    assert len(segments) == 1
    assert segments[0].startswith("finishing phase:")
    pythons = _rendered_of(run_dir, "run_python")
    assert len(pythons) == 1
    assert "closed" not in pythons[0]
    blob = json.dumps(spark.requests[1]["messages"])
    assert "finishing phase" in blob


def test_loop_per_tool_budget_closes_only_that_tool(
        script_spark, stub_responses, drive_loop, make_run, make_ledger,
        rejecting_validator):
    """A spent SAM budget closes segment with a one-line notice while
    the run goes on (fifth live run)."""
    run_dir = make_run()
    ledger = make_ledger("r", run_dir)
    ledger.sam_frames_billed = config.MAX_SAM_FRAMES
    validator = rejecting_validator(
        run_dir, [[{"code": "E1", "field": "evidence", "detail": "fix"}]])
    spark = script_spark([
        stub_responses["completed"](
            "try", [stub_responses["call"](
                "segment", {"phrase": "the wall", "frame_start": 0,
                            "frame_end": 7, "confirm_small_range": True},
                "call-seg"),
                _submit_call(stub_responses, dry_run=True,
                             call_id="call-dry")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-submit")]),
    ])
    out = drive_loop(run_dir, spark, ledger=ledger, validator=validator)
    assert out["status"] == "submitted"
    segments = _rendered_of(run_dir, "segment")
    assert len(segments) == 1
    assert "closed" in segments[0]
    assert "SAM" in segments[0]


def test_loop_budget_line_shows_last_dry_run(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        rejecting_validator):
    """After a rejected dry run with 2 errors, the next budget line ends
    with the dry-run suffix (run 13/4)."""
    import src.tools.view_frames as view_frames_mod

    def _fake_view(run_dir, turn, **kwargs):
        return {"ok": True, "summary": "sheet", "files": [],
                "metrics": {}}

    monkeypatch.setattr(view_frames_mod, "view_frames", _fake_view)
    run_dir = make_run()
    validator = rejecting_validator(run_dir, [[
        {"code": "E1", "field": "a", "detail": "first"},
        {"code": "E2", "field": "b", "detail": "second"}]])
    spark = script_spark([
        stub_responses["completed"](
            "dry", [_submit_call(stub_responses, dry_run=True,
                                 call_id="call-dry")]),
        stub_responses["completed"](
            "look", [stub_responses["call"]("view_frames", {},
                                            "call-view")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-submit")]),
    ])
    out = drive_loop(run_dir, spark, validator=validator)
    assert out["status"] == "submitted"
    rendered = _rendered_of(run_dir, "view_frames")
    assert len(rendered) == 1
    assert rendered[0].splitlines()[-1].endswith(
        "last dry run: 2 errors (turn 1)")


def test_loop_clean_dry_run_wins_at_wall_cap(
        script_spark, stub_responses, drive_loop, make_run, fake_clock):
    """At a run-level cap, a clean last dry run is submitted for real
    instead of ending budget (run 10)."""
    from src.contract import validate_result
    run_dir = make_run()

    def _validator(evidence, run_context=None, dry_run=False):
        if dry_run:
            return {"accepted": True, "errors": []}
        from src.validate.synthesis import (
            synthesize_undetermined as _synth,
        )
        from src.validate.synthesis import write_result as _write
        result = _synth(str(run_dir), run_dir.name, "budget",
                        detail="wall_time cap")
        path = _write(str(run_dir), result)
        _validator.calls.append(bool(dry_run))
        return {"accepted": True, "errors": [], "result": result,
                "result_path": path}

    _validator.calls = []

    def _first(request):
        fake_clock.advance(config.HARD_CAP_WALL_S + 5)
        return stub_responses["completed"](
            "dry", [_submit_call(stub_responses, dry_run=True,
                                 call_id="call-dry")])

    spark = script_spark([_first])
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     validator=_validator)
    assert out["status"] == "submitted"
    assert _validator.calls == [False]
    result = json.loads((run_dir / "result.json").read_text(
        encoding="utf-8"))
    assert validate_result(result) == []
    names = [a.get("name", "") for a in
             result["provenance"]["artifacts"]]
    assert any("submitted at the budget limit from the last clean dry "
               "run" in name for name in names)


def test_loop_rejected_dry_run_ends_budget(
        script_spark, stub_responses, drive_loop, make_run, fake_clock,
        rejecting_validator):
    """A rejected last dry run still ends budget at the cap (run 10)."""
    run_dir = make_run()
    validator = rejecting_validator(
        run_dir, [[{"code": "E1", "field": "evidence",
                    "detail": "broken"}]])

    def _first(request):
        fake_clock.advance(config.HARD_CAP_WALL_S + 5)
        return stub_responses["completed"](
            "dry", [_submit_call(stub_responses, dry_run=True,
                                 call_id="call-dry")])

    spark = script_spark([_first])
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     validator=validator)
    assert out["status"] == "undetermined"
    assert "budget" in out["reason"]
    assert len(validator.calls) == 1


def test_loop_push_codes_count_as_clean_at_cap(
        script_spark, stub_responses, drive_loop, make_run, fake_clock,
        rejecting_validator):
    """A dry run failing only with push codes counts as clean, so the
    capped run ends with that measured result (run 10, part 11 §16)."""
    from src.validate import PUSH_CODES
    run_dir = make_run()
    push_error = {"code": PUSH_CODES[0], "field": "references",
                  "detail": "only one reference so far"}
    validator = rejecting_validator(run_dir, [[push_error]])

    def _first(request):
        fake_clock.advance(config.HARD_CAP_WALL_S + 5)
        return stub_responses["completed"](
            "dry", [_submit_call(stub_responses, dry_run=True,
                                 call_id="call-dry")])

    spark = script_spark([_first])
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     validator=validator)
    assert out["status"] == "submitted"
    assert [c["dry_run"] for c in validator.calls] == [True, False]

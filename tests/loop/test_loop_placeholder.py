# generated from brief/06 · part 06 owns this file
"""Placeholder refusal and plan progress (part 06 addenda 2026-10-31).

Hand run 7 dry-ran a placeholder and never wrote a measurement into
``workspace/evidence.json``; wall run 12 did the same twice. The loop
now refuses a placeholder dry run — without calling the validator
and without counting it as a dry run — and every turn's status line
shows the Wonder plan's progress.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.loop.plan import (
    PLACEHOLDER_REFUSAL,
    evidence_has_measurement,
    plan_progress_line,
)

PLACEHOLDER = {"references": [], "range_checks": [], "segments": []}


def _submit_call(stub_responses, evidence, dry_run, call_id):
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


def _wonder_answer():
    return {
        "claim": "the clip shows a person running up a tall wall",
        "question": "could a person really run straight up a wall",
        "world": "Earth",
        "checks": [
            {"kind": "gravity",
             "what": "wall-run ascent",
             "why": "free vertical motion must match the world's g",
             "how": "segment the climber and fit a parabola",
             "compare_with": "the world's gravity"},
            {"kind": "range",
             "what": "wall height vs runner",
             "why": "answers whether the wall is taller than reachable",
             "how": "measure the wall and the runner against a known size",
             "compare_with": "adult body norms"},
            {"kind": "clock",
             "what": "step rate of the climb",
             "why": "shows whether the clip plays at real speed",
             "how": "count steps across frames",
             "compare_with": "natural human step-rate range"},
        ],
        "realistic_if": "the fit matches within sigma",
        "not_realistic_if": "the fit misses by several sigma",
    }


@pytest.mark.parametrize("evidence, expected", [
    ({}, False),
    ({"references": [], "range_checks": [], "segments": []}, False),
    ({"references": [{"name": "r"}], "range_checks": [],
      "segments": []}, False),
    ({"range_checks": [{"id": "c", "extents": []}]}, False),
    ({"segments": [{"id": "s"}]}, False),
    ({"references": [{"name": "r", "extent_px": {"x1": 0}}]}, True),
    ({"range_checks": [{"id": "c",
                        "extents": [{"name": "w"}]}]}, True),
    ({"segments": [{"id": "s", "frames": {"start": 1, "apex": 5,
                                          "end": 9}}]}, True),
    ([], False),
    (None, False),
])
def test_loop_evidence_has_measurement_cases(evidence, expected):
    """Only a reference with ``extent_px``, a range check with an
    extent, or a segment with frames counts as a measurement."""
    assert evidence_has_measurement(evidence) is expected


def test_loop_placeholder_dry_run_refused(
        script_spark, stub_responses, drive_loop, make_run,
        measured_evidence, rejecting_validator):
    """A placeholder dry run returns the refusal message, never calls
    the validator, never advances the dry-run count — and the run
    goes on (hand run 7, wall run 12)."""
    run_dir = make_run()
    validator = rejecting_validator(
        run_dir, [[{"code": "E1", "field": "evidence",
                    "detail": "fix"}],
                  [{"code": "E1", "field": "evidence",
                    "detail": "fix"}]])
    measured = measured_evidence()
    spark = script_spark([
        stub_responses["completed"](
            "placeholder", [_submit_call(stub_responses, PLACEHOLDER,
                                         True, "call-dry")]),
        stub_responses["completed"](
            "measured", [_submit_call(stub_responses, measured, False,
                                      "call-real")]),
        stub_responses["completed"](
            "measured again", [_submit_call(stub_responses, measured,
                                            False, "call-real-2")]),
    ])
    out = drive_loop(run_dir, spark, validator=validator)
    assert out["status"] == "submitted"
    # The validator never saw the placeholder. Each early real submit
    # carries its extra dry-run probe, so two reals mean two
    # probe-plus-real pairs.
    assert [call["dry_run"] for call in validator.calls] == [True,
                                                             False,
                                                             True,
                                                             False]
    # The dry-run budget never advanced: the submit tool was refused
    # before it could bump its operator-only counter.
    assert not (run_dir / "logs" / "dry_runs.json").exists()
    rendered = _rendered_of(run_dir, "submit")
    # Two rendered results: the refusal, then the first real
    # rejection (an accepted submit ends the run with no rendered
    # text of its own).
    assert len(rendered) == 2
    assert PLACEHOLDER_REFUSAL in rendered[0]
    # The refusal recorded nothing: no last dry run rides the status.
    assert "last dry run" not in rendered[0]
    assert "E1" in rendered[1]


def test_loop_placeholder_via_evidence_path_refused(
        script_spark, stub_responses, drive_loop, make_run,
        measured_evidence, accepting_validator):
    """A placeholder reached through ``evidence_path`` is refused the
    same way: the file the agent must keep current is read, not the
    inline argument alone."""
    run_dir = make_run()
    (run_dir / "workspace" / "evidence.json").write_text(
        json.dumps(PLACEHOLDER), encoding="utf-8")
    measured = measured_evidence()
    spark = script_spark([
        stub_responses["completed"](
            "placeholder", [stub_responses["call"](
                "submit", {"evidence": None,
                           "evidence_path": "workspace/evidence.json",
                           "dry_run": True}, "call-dry")]),
        stub_responses["completed"](
            "measured", [_submit_call(stub_responses, measured, False,
                                      "call-real")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    rendered = _rendered_of(run_dir, "submit")
    # Only the refusal renders: the accepted submit ends the run
    # with no rendered text of its own.
    assert len(rendered) == 1
    assert PLACEHOLDER_REFUSAL in rendered[0]


def test_loop_refused_placeholder_does_not_reopen_exploration(
        script_spark, stub_responses, drive_loop, make_run, fake_clock,
        measured_evidence, rejecting_validator):
    """Past one third of the budget a refused placeholder keeps
    exploration closed; the first measured dry run reopens it."""
    from src import config
    from src.loop.run import EXPLORATION_CLOSED_LINE
    run_dir = make_run()
    validator = rejecting_validator(
        run_dir, [[{"code": "E1", "field": "evidence",
                    "detail": "fix"}]])
    measured = measured_evidence()

    def _segment(call_id):
        return stub_responses["call"](
            "segment", {"phrase": "the wall", "frame_start": 0,
                        "frame_end": 7, "confirm_small_range": True},
            call_id)

    def _advance(request):
        fake_clock.advance(config.HARD_CAP_WALL_S / 3.0 + 10)
        return stub_responses["completed"]("warming up")

    spark = script_spark([
        _advance,
        stub_responses["completed"]("explore", [_segment("call-seg-1")]),
        stub_responses["completed"](
            "placeholder", [_submit_call(stub_responses, PLACEHOLDER,
                                         True, "call-dry")]),
        stub_responses["completed"]("explore", [_segment("call-seg-2")]),
        stub_responses["completed"](
            "measured", [_submit_call(stub_responses, measured, True,
                                      "call-dry-2")]),
        stub_responses["completed"]("explore", [_segment("call-seg-3")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, measured, False,
                                  "call-real")]),
    ])
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     validator=validator)
    assert out["status"] == "submitted"
    # The placeholder never reached the validator: one measured dry
    # run plus the real submit's extra dry-run probe plus the real
    # submit.
    assert [call["dry_run"] for call in validator.calls] == [
        True, True, False]
    segments = _rendered_of(run_dir, "segment")
    assert len(segments) == 3
    assert segments[0].startswith(EXPLORATION_CLOSED_LINE)
    assert segments[1].startswith(EXPLORATION_CLOSED_LINE)
    assert "sam_unavailable" in segments[2]


def test_loop_status_line_shows_plan_progress(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        measured_evidence, accepting_validator):
    """Every turn's status line names each Wonder check and whether
    ``workspace/evidence.json`` holds it now — re-read every turn."""
    import src.loop.run as run_mod
    import src.tools.view_frames as view_frames_mod

    wonder = _wonder_answer()
    monkeypatch.setattr(run_mod, "run_preplan",
                        lambda *args, **kwargs: (wonder, None, None))

    def _fake_view(run_dir, turn, **kwargs):
        return {"ok": True, "summary": "sheet", "files": [],
                "metrics": {}}

    def _fake_python(run_dir, turn, **kwargs):
        (Path(str(run_dir)) / "workspace" / "evidence.json").write_text(
            json.dumps({
                "segments": [{"id": "hop_a",
                              "frames": {"start": 1, "apex": 5,
                                         "end": 9}}],
                "clock": {"signal_description": "steps",
                          "measured_rate_hz": 2.0},
                "first_look": {"overview": {
                    "artifact": "artifacts/t0_segment_0.npz",
                    "object_id": "1",
                    "tool_result": "artifacts/t0_motion_overview_0.json",
                    "candidates": [
                        {"id": "F1", "frame_start": 1, "frame_end": 9,
                         "airtime_s": 0.8, "peak_rise_px": 20.0,
                         "decision": "measured", "segment_id": "hop_a",
                         "reason": None},
                        {"id": "F2", "frame_start": 20,
                         "frame_end": 24, "airtime_s": 0.4,
                         "peak_rise_px": 4.0,
                         "decision": "not_a_flight",
                         "segment_id": None,
                         "reason": "walking step, rise 4 px"},
                    ],
                    "first_check": {"segment_id": "hop_a",
                                    "why": "most frames"},
                }},
            }), encoding="utf-8")
        return {"ok": True, "summary": "ran", "files": [],
                "metrics": {}}

    import src.tools.run_python as run_python_mod
    monkeypatch.setattr(view_frames_mod, "view_frames", _fake_view)
    monkeypatch.setattr(run_python_mod, "run_python", _fake_python)
    run_dir = make_run()
    (run_dir / "workspace" / "evidence.json").write_text(
        json.dumps({"range_checks": [{"id": "wall",
                                      "extents": [{"name": "w"}]}]}),
        encoding="utf-8")
    measured = measured_evidence()
    spark = script_spark([
        stub_responses["completed"](
            "look", [stub_responses["call"]("view_frames", {},
                                            "call-view-1")]),
        stub_responses["completed"](
            "measure", [stub_responses["call"](
                "run_python", {"code": "print(1)"}, "call-py")]),
        stub_responses["completed"](
            "look", [stub_responses["call"]("view_frames", {},
                                            "call-view-2")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, measured, False,
                                  "call-real")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    views = _rendered_of(run_dir, "view_frames")
    assert len(views) == 2
    first = views[0].splitlines()
    assert "turns left" in first[-2] and "min left" in first[-2]
    assert first[-1] == (
        "plan: 1 gravity: wall-run ascent \u2014 not in evidence.json; "
        "2 range: wall height vs runner \u2014 in evidence.json; "
        "3 clock: step rate of the climb \u2014 not in evidence.json")
    last = views[1].splitlines()
    assert last[-1] == (
        "plan: 1 gravity: wall-run ascent \u2014 in evidence.json; "
        "2 range: wall height vs runner \u2014 not in evidence.json; "
        "3 clock: step rate of the climb \u2014 in evidence.json")


def test_loop_status_line_absent_without_plan(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """With no Wonder plan the status line is the budget line alone."""
    import src.loop.run as run_mod
    import src.tools.view_frames as view_frames_mod

    monkeypatch.setattr(run_mod, "run_preplan",
                        lambda *args, **kwargs: (None, None, None))

    def _fake_view(run_dir, turn, **kwargs):
        return {"ok": True, "summary": "sheet", "files": [],
                "metrics": {}}

    monkeypatch.setattr(view_frames_mod, "view_frames", _fake_view)
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"](
            "look", [stub_responses["call"]("view_frames", {},
                                            "call-view")]),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1}, "evidence_path": None,
                           "dry_run": False}, "call-real")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    views = _rendered_of(run_dir, "view_frames")
    assert len(views) == 1
    assert "plan:" not in views[0]
    assert plan_progress_line(None, run_dir) is None
    assert plan_progress_line({}, run_dir) is None

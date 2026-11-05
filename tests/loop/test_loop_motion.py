# generated from brief/06 · part 06 owns this file
"""``motion_overview`` in the loop (part 06 addendum 2026-11-01).

The loop dispatches ``motion_overview`` like the other tools: its
schema is already in the tool list Spark receives, its result is
logged with its files named, and its chart and strip images ride
back to Spark as images the way ``view_frames`` sheets do. The
prefix says when to use it, and the plan's progress line counts a
motion check as done only once the overview decides every
candidate and every measured candidate flies as a segment.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def _wonder_one_gravity():
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
        ],
        "realistic_if": "the fit matches within sigma",
        "not_realistic_if": "the fit misses by several sigma",
    }


def _write_evidence(run_dir, evidence):
    (Path(str(run_dir)) / "workspace" / "evidence.json").write_text(
        json.dumps(evidence), encoding="utf-8")


def _overview(*candidates):
    return {
        "artifact": "artifacts/t0_segment_0.npz",
        "object_id": "1",
        "tool_result": "artifacts/t0_motion_overview_0.json",
        "candidates": list(candidates),
        "first_check": {"segment_id": "hop_a",
                        "why": "most frames"},
    }


def _measured_candidate(cid="F1", segment_id="hop_a", **extra):
    record = {"id": cid, "frame_start": 1, "frame_end": 9,
              "airtime_s": 0.8, "peak_rise_px": 20.0,
              "decision": "measured", "segment_id": segment_id,
              "reason": None}
    record.update(extra)
    return record


def _dismissed_candidate(cid="F2"):
    return {"id": cid, "frame_start": 20, "frame_end": 24,
            "airtime_s": 0.4, "peak_rise_px": 4.0,
            "decision": "not_a_flight", "segment_id": None,
            "reason": "walking step, rise 4 px"}


def test_loop_prefix_says_when_to_use_motion_overview():
    """The prefix carries one short paragraph on the motion survey."""
    from src.loop.prefix import MOTION_PARAGRAPH, build_prefix

    blob = build_prefix()
    assert MOTION_PARAGRAPH.strip() in blob
    assert "\n" not in MOTION_PARAGRAPH.strip()
    for phrase in ("whole clip in one", "motion_overview",
                   "chart and strips", "decide every candidate",
                   "one first", "confirmations", "short segments"):
        assert phrase in blob, phrase


def test_loop_plan_progress_motion_check_needs_decided_overview(
        make_run):
    """A motion check is done only via a decided overview whose
    measured candidates each fly as a segment with frames."""
    from src.loop.plan import plan_progress_line

    wonder = _wonder_one_gravity()
    run_dir = make_run()
    frames = {"start": 1, "apex": 5, "end": 9}

    def _line():
        return plan_progress_line(wonder, run_dir)

    # Segments alone are not enough: no overview, no decision.
    _write_evidence(run_dir, {"segments": [{"id": "hop_a",
                                            "frames": dict(frames)}]})
    assert _line() == (
        "plan: 1 gravity: wall-run ascent \u2014 not in evidence.json")

    # An undecided candidate keeps the check open.
    pending = _measured_candidate()
    del pending["decision"]
    _write_evidence(run_dir, {
        "segments": [{"id": "hop_a", "frames": dict(frames)}],
        "first_look": {"overview": _overview(pending)}})
    assert _line().endswith("not in evidence.json")

    # Decided, and the measured candidate flies: done.
    _write_evidence(run_dir, {
        "segments": [{"id": "hop_a", "frames": dict(frames)}],
        "first_look": {"overview": _overview(
            _measured_candidate(), _dismissed_candidate())}})
    assert _line() == (
        "plan: 1 gravity: wall-run ascent \u2014 in evidence.json")

    # A measured candidate with no segment with frames: not done.
    _write_evidence(run_dir, {
        "segments": [{"id": "hop_a"}],
        "first_look": {"overview": _overview(
            _measured_candidate(), _dismissed_candidate())}})
    assert _line().endswith("not in evidence.json")

    # Every candidate dismissed with a reason is also decided: done.
    _write_evidence(run_dir, {
        "segments": [],
        "first_look": {"overview": _overview(
            _dismissed_candidate("F1"), _dismissed_candidate("F2"))}})
    assert _line() == (
        "plan: 1 gravity: wall-run ascent \u2014 in evidence.json")


def test_loop_motion_overview_dispatches_names_files_and_rides_as_image(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        measured_evidence, accepting_validator):
    """A scripted run calling ``motion_overview`` on the fake-1 masks
    gets a result naming the chart and the strips, and the next
    request to the client carries the chart as an image."""
    import src.loop.run as run_mod

    monkeypatch.setattr(run_mod, "run_preplan",
                        lambda *args, **kwargs: (None, None, None))
    source = Path("fixtures/source/fake-1")
    run_dir = make_run()
    shutil.copy(source / "input" / "timing.json",
                run_dir / "input" / "timing.json")
    shutil.copy(source / "input" / "clip.mp4",
                run_dir / "input" / "clip.mp4")
    shutil.copy(source / "artifacts" / "t9_segment_0.npz",
                run_dir / "artifacts" / "t9_segment_0.npz")
    spark = script_spark([
        stub_responses["completed"](
            "survey", [stub_responses["call"](
                "motion_overview",
                {"masks_artifact": "artifacts/t9_segment_0.npz",
                 "object_ids": ["1"]}, "call-overview")]),
        stub_responses["completed"]("noted"),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": measured_evidence(),
                           "evidence_path": None, "dry_run": False},
                "call-real")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"

    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    overviews = [tc
                 for entry in (json.loads(line) for line in lines)
                 for tc in entry.get("tool_calls", [])
                 if tc.get("name") == "motion_overview"
                 and tc.get("rendered")]
    assert len(overviews) == 1
    rendered = overviews[0]["rendered"]
    assert "motion_overview_chart" in rendered
    assert "motion_overview_strip" in rendered
    charts = sorted((run_dir / "artifacts").glob(
        "*motion_overview_chart*.png"))
    assert len(charts) == 1 and charts[0].stat().st_size > 0
    assert sorted((run_dir / "artifacts").glob(
        "*motion_overview_strip*.png"))

    assert len(spark.requests) == 3
    images = [str(block.get("artifact", ""))
              for message in spark.requests[1].get("messages", [])
              for block in message.get("content", [])
              if isinstance(block, dict)
              and block.get("type") == "image"]
    assert any("motion_overview_chart" in name for name in images), images

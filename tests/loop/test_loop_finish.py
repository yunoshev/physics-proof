# generated from brief/06 · part 06 owns this file
"""Wall run 7 (part 06 addendum 2026-10-30): check kinds, shape-only
examples, and the loop finishing the run.

Caps always come from :mod:`src.config`; the suite pins no literal cap.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import config
from src.loop.budgets import FINISHING_TURNS
from src.loop.prefix import OWN_CLIP_LINE, build_prefix, initial_task
from src.loop.preplan import (
    CHECK_KINDS,
    CHECK_REQUIRED,
    validate_wonder,
    wonder_prompt,
)


def _describe_answer():
    return {
        "what_happens": [
            "a figure stands at the wall base at 0.0 s",
            "the figure climbs the wall face at 0.4 s",
            "the figure reaches the top at 1.1 s",
        ],
        "scene": "a tall vertical wall outdoors, frame 0",
        "things": "one person and a tall wall",
        "on_screen_text": "",
    }


def _wonder_answer():
    return {
        "claim": "the clip shows a person running up a tall wall",
        "question": "could a person really run straight up a wall",
        "world": "Earth",
        "checks": [
            {"kind": "gravity",
             "what": "vertical acceleration on the face",
             "why": "free vertical motion must match the world's g",
             "how": "segment the climber and fit a parabola",
             "compare_with": "the world's gravity"},
            {"kind": "range",
             "what": "wall height against body height",
             "why": "answers whether the wall is taller than reachable",
             "how": "measure the wall and the climber against a known size",
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


def _sheet_view(run_dir, turn, **kwargs):
    """Fake ``view_frames`` that writes the sheet files it names."""
    rel = f"artifacts/t{turn}_view_frames_0.jpg"
    (Path(str(run_dir)) / rel).write_bytes(b"\xff\xd8fake-sheet")
    index_rel = f"artifacts/t{turn}_view_frames_1.json"
    (Path(str(run_dir)) / index_rel).write_text("[]", encoding="utf-8")
    return {"ok": True, "summary": "sheet", "files": [rel, index_rel],
            "metrics": {}}


def _use_sheets(monkeypatch, run_dir):
    import src.tools.view_frames as view_frames_mod
    monkeypatch.setattr(view_frames_mod, "view_frames", _sheet_view)
    (Path(str(run_dir)) / "input" / "clip.mp4").write_bytes(
        b"fake-clip-bytes")


def _initial_blob(spark):
    initial = spark.requests[2]["messages"][1]
    assert initial["role"] == "user"
    return json.dumps(initial)


def test_loop_wonder_checks_carry_kind_and_task_maps_fields(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """Wonder's checks carry ``kind``, and the initial task holds each
    check's kind plus the evidence field it maps to (wall run 7)."""
    run_dir = make_run()
    _use_sheets(monkeypatch, run_dir)
    wonder = _wonder_answer()
    spark = script_spark([
        stub_responses["completed"](json.dumps(_describe_answer())),
        stub_responses["completed"](json.dumps(wonder)),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1},
                           "evidence_path": None,
                           "dry_run": False}, "call-s")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    stored = json.loads((run_dir / "artifacts" / "wonder.json").read_text(
        encoding="utf-8"))
    assert [check["kind"] for check in stored["checks"]] == [
        "gravity", "range", "clock"]
    blob = _initial_blob(spark)
    assert f"first_look.question: {wonder['question']}" in blob
    for check in wonder["checks"]:
        assert check["what"] in blob
        assert check["kind"] in blob
    assert "(kind gravity) becomes evidence `segments`" in blob
    assert "(kind range) becomes evidence `range_checks`" in blob
    assert "(kind clock) becomes evidence `clock`" in blob
    assert "every `gravity` check becomes a segment" in blob
    assert "every `range` check becomes one `range_checks` item" in blob
    assert "a `clock` check" in blob
    assert "becomes `clock`" in blob
    assert "an evidence that has range checks and no" in blob
    assert "segment is valid" in blob
    assert "When you have measured the plan's" in blob
    assert "track and a scale" not in blob
    assert "track and a scale" not in initial_task(None)


def test_loop_wonder_kind_is_required():
    """A check without a known ``kind`` is invalid (retried, then the
    plan is skipped like any malformed reply)."""
    assert "kind" in CHECK_REQUIRED
    assert tuple(CHECK_KINDS) == ("gravity", "range", "clock")
    good = _wonder_answer()
    assert validate_wonder(good)
    for bad_kind in ("parabola", "", None):
        bad = json.loads(json.dumps(good))
        bad["checks"][0]["kind"] = bad_kind
        assert not validate_wonder(bad)
    missing = json.loads(json.dumps(good))
    del missing["checks"][1]["kind"]
    assert not validate_wonder(missing)
    prompt = wonder_prompt(_describe_answer())
    assert '"gravity"' in prompt and '"range"' in prompt \
        and '"clock"' in prompt
    assert "backpack" not in prompt


def test_loop_prefix_shows_both_examples_and_own_clip_line():
    """The prefix carries both shape-only examples verbatim and the
    line sending the agent back to its own clip (wall run 7)."""
    prefix = build_prefix()
    assert "shape only" in prefix
    assert "backpack height" in prefix
    assert "https://example.com/pack" in prefix
    assert "steel ruler" in prefix
    assert "https://example.com/ruler" in prefix
    assert OWN_CLIP_LINE in prefix
    assert "comes from your own clip" in prefix
    assert build_prefix() == prefix


def test_loop_finishing_notice_lists_last_dry_run_errors(
        script_spark, stub_responses, drive_loop, make_run, fake_clock,
        monkeypatch, rejecting_validator):
    """The finishing notice names the last dry run's errors in plain
    words; with no dry run it says to write the evidence file now."""
    import src.tools.run_python as run_python_mod

    def _fake_python(run_dir, turn, **kwargs):
        (Path(str(run_dir)) / "workspace" / "evidence.json").write_text(
            json.dumps({"a": 1}), encoding="utf-8")
        return {"ok": True, "summary": "ran", "files": [],
                "metrics": {}}

    monkeypatch.setattr(run_python_mod, "run_python", _fake_python)
    run_dir = make_run()
    validator = rejecting_validator(run_dir, [[
        {"code": "E1", "field": "evidence.segments",
         "detail": "the segment track is too short to fit"},
        {"code": "E2", "field": "evidence.clock",
         "detail": "no clock reading was submitted"}]])

    def _submit_dry(request):
        # A dry run needs a real measurement (a segment with frames):
        # the loop refuses a placeholder without calling the
        # validator (part 06 addendum 2026-10-31, hand run 7).
        measured = {"segments": [{"frames": {"start": 1, "apex": 5,
                                             "end": 9}}]}
        return stub_responses["completed"](
            "dry", [stub_responses["call"](
                "submit", {"evidence": measured, "evidence_path": None,
                           "dry_run": True}, "call-dry")])

    def _jump(request):
        fake_clock.advance(
            config.HARD_CAP_WALL_S * config.WARN_RATIO + 1)
        return stub_responses["completed"]("still working")

    script = [_submit_dry, _jump]
    for index in range(FINISHING_TURNS):
        script.append(stub_responses["completed"](
            f"working {index}", [stub_responses["call"](
                "run_python", {"code": "print(1)", "timeout_s": None,
                               "memory_mb": None},
                f"call-py-{index}")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     validator=validator)
    assert out["status"] == "submitted"
    finishing = [json.dumps(request["messages"])
                 for request in spark.requests
                 if "finishing phase" in json.dumps(request["messages"])]
    assert finishing
    assert "the segment track is too short" in finishing[0]
    assert "no clock reading was submitted" in finishing[0]


def _finishing_script(stub_responses, fake_clock, count):
    def _first(request):
        fake_clock.advance(
            config.HARD_CAP_WALL_S * config.WARN_RATIO + 1)
        return stub_responses["completed"]("warming up")

    script = [_first]
    for index in range(count):
        script.append(stub_responses["completed"](
            f"working {index}", [stub_responses["call"](
                "run_python", {"code": "print(1)", "timeout_s": None,
                               "memory_mb": None},
                f"call-py-{index}")]))
    return script


def test_loop_finishing_phase_submits_evidence_after_four_turns(
        script_spark, stub_responses, drive_loop, make_run, fake_clock,
        monkeypatch, rejecting_validator):
    """A stub that keeps calling ``run_python`` in the finishing phase
    is stopped after four turns; the loop submits
    ``workspace/evidence.json`` itself and the result names the
    validator's first errors (wall run 7)."""
    from src.contract import validate_result
    import src.tools.run_python as run_python_mod

    def _fake_python(run_dir, turn, **kwargs):
        (Path(str(run_dir)) / "workspace" / "evidence.json").write_text(
            json.dumps({"a": 1}), encoding="utf-8")
        return {"ok": True, "summary": "ran", "files": [],
                "metrics": {}}

    monkeypatch.setattr(run_python_mod, "run_python", _fake_python)
    run_dir = make_run()
    validator = rejecting_validator(run_dir, [[
        {"code": "E1", "field": "evidence.segments",
         "detail": "first problem needs a new segment"},
        {"code": "E2", "field": "evidence.clock",
         "detail": "second problem needs a clock reading"}]])
    spark = script_spark(
        _finishing_script(stub_responses, fake_clock, FINISHING_TURNS))
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     validator=validator)
    assert out["status"] == "undetermined"
    assert "not finished" in out["reason"]
    assert out["turns"] == 1 + 1 + FINISHING_TURNS
    assert [call["dry_run"] for call in validator.calls] == [False]
    result = json.loads((run_dir / "result.json").read_text(
        encoding="utf-8"))
    assert validate_result(result) == []
    assert result["verdict"]["kind"] == "undetermined"
    assert "not finished" in result["sentence"]
    assert "first problem needs a new segment" in result["sentence"]
    assert "second problem needs a clock reading" in result["sentence"]
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    pythons = [tool_call for line in lines
               for tool_call in json.loads(line).get("tool_calls", [])
               if tool_call.get("name") == "run_python"
               and tool_call.get("rendered")]
    assert len(pythons) == FINISHING_TURNS


def test_loop_finishing_phase_without_evidence_ends_budget(
        script_spark, stub_responses, drive_loop, make_run, fake_clock,
        monkeypatch):
    """A run with no evidence file at all still ends
    ``undetermined: budget`` (wall run 7)."""
    from src.contract import validate_result
    import src.tools.run_python as run_python_mod

    def _fake_python(run_dir, turn, **kwargs):
        return {"ok": True, "summary": "ran", "files": [],
                "metrics": {}}

    monkeypatch.setattr(run_python_mod, "run_python", _fake_python)
    run_dir = make_run()
    spark = script_spark(
        _finishing_script(stub_responses, fake_clock, FINISHING_TURNS))
    out = drive_loop(run_dir, spark, clock=fake_clock, validator=None)
    assert out["status"] == "undetermined"
    assert "budget" in out["reason"]
    assert out["turns"] == 1 + 1 + FINISHING_TURNS
    result = json.loads((run_dir / "result.json").read_text(
        encoding="utf-8"))
    assert validate_result(result) == []
    assert result["verdict"]["kind"] == "undetermined"

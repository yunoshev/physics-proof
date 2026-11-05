# generated from brief/06 · part 06 owns this file
"""Describe-then-Wonder before turn 1, and the one-third exploration
closing driven by wall time (part 06 addendum 2026-10-29).

Caps always come from :mod:`src.config`; the suite pins no literal cap.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import config
from src.loop.prefix import INITIAL_TASK, initial_task


def _describe_answer():
    return {
        "what_happens": [
            "a figure stands at the left at 0.0 s",
            "the figure jumps at 0.3 s",
            "the figure lands at 0.6 s",
        ],
        "scene": "a flat field filmed from the side, frame 0",
        "things": "one person in light clothing",
        "on_screen_text": "",
    }


def _wonder_answer(question="does the fall match gravity"):
    return {
        "claim": "the clip shows a jump that looks slow",
        "question": question,
        "world": "Earth",
        "checks": [
            {"kind": "gravity",
             "what": "fall acceleration",
             "why": "answers whether the fall matches gravity",
             "how": "track the torso across frames against a known height",
             "compare_with": "the world's gravity"},
        ],
        "realistic_if": "the fit matches within sigma",
        "not_realistic_if": "the fit misses by several sigma",
    }


def _sheet_view(run_dir, turn, **kwargs):
    """Fake ``view_frames`` that writes the sheet files it names."""
    rel = f"artifacts/t{turn}_view_frames_0.jpg"
    (Path(str(run_dir)) / rel).write_bytes(b"\xff\xd8fake-sheet")
    index_rel = f"artifacts/t{turn}_view_frames_1.json"
    (Path(str(run_dir)) / index_rel).write_text(
        "[]", encoding="utf-8")
    return {"ok": True, "summary": "sheet", "files": [rel, index_rel],
            "metrics": {}}


def _use_sheets(monkeypatch, run_dir):
    """Fake the sheet builder (writing the files it names) and plant a
    dummy clip so the clip facts resolve; the agent never reads it."""
    import src.tools.view_frames as view_frames_mod
    monkeypatch.setattr(view_frames_mod, "view_frames", _sheet_view)
    (Path(str(run_dir)) / "input" / "clip.mp4").write_bytes(
        b"fake-clip-bytes")


def _prephase_requests(spark):
    """The pre-loop plan requests before the first turn.

    Detected by their plan prompt (contact sheets of the whole clip),
    not by the absence of a system message: the first turn's initial
    task ("Analyse the clip") starts the measuring loop.
    """
    pre = []
    for request in spark.requests:
        blob = "\n".join(_texts_of(request))
        if "Analyse the clip" in blob:
            break
        pre.append(request)
    return pre


def _texts_of(request):
    return [b.get("text", "")
            for m in request["messages"]
            for b in m.get("content", [])
            if isinstance(b, dict) and b.get("type") == "text"]


def test_loop_preplan_runs_before_turn_1_and_writes_artifacts(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """Both plan calls happen before turn 1 and write their artifacts;
    the initial task then carries the question and each check's what."""
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
    pre = _prephase_requests(spark)
    assert len(pre) == 2
    for request in pre:
        assert request["model"] == config.SPARK_MODEL
        assert (request["max_output_tokens"]
                == config.MAX_OUTPUT_TOKENS)
        images = [b for m in request["messages"]
                  for b in m.get("content", [])
                  if isinstance(b, dict) and b.get("type") == "image"]
        assert images
    assert (run_dir / "artifacts" / "describe.json").is_file()
    assert json.loads(
        (run_dir / "artifacts" / "describe.json").read_text(
            encoding="utf-8")) == _describe_answer()
    assert (run_dir / "artifacts" / "wonder.json").is_file()
    assert json.loads((run_dir / "artifacts" / "wonder.json").read_text(
        encoding="utf-8")) == wonder
    initial = spark.requests[2]["messages"][1]
    assert initial["role"] == "user"
    blob = json.dumps(initial)
    assert "This is your plan. Measure these checks" in blob
    assert f"first_look.question: {wonder['question']}" in blob
    for check in wonder["checks"]:
        assert check["what"] in blob
    # Blindness: frames and clip facts only, never the file name.
    describe_blob = "\n".join(_texts_of(pre[0]))
    assert "duration_s" in describe_blob
    for request in pre:
        blob = "\n".join(_texts_of(request))
        assert "clip." not in blob
        assert ".mp4" not in blob and ".mpg" not in blob


def test_loop_preplan_malformed_retried_once_then_skipped(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """A malformed reply is retried once, then skipped with the loop
    still starting and the reason recorded under logs/."""
    run_dir = make_run()
    _use_sheets(monkeypatch, run_dir)
    spark = script_spark([
        stub_responses["completed"]("not json at all"),
        stub_responses["completed"]('{"what_happens": [broken'),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1},
                           "evidence_path": None,
                           "dry_run": False}, "call-s")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert out["turns"] == 1
    pre = _prephase_requests(spark)
    assert len(pre) == 2
    assert not (run_dir / "artifacts" / "describe.json").exists()
    assert not (run_dir / "artifacts" / "wonder.json").exists()
    skipped = json.loads((run_dir / "logs" / "preplan.json").read_text(
        encoding="utf-8"))
    assert skipped["status"] == "skipped"
    assert skipped["phase"] == "describe"
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    zeros = [json.loads(line) for line in lines
             if json.loads(line).get("turn") == 0]
    assert len(zeros) == 2
    assert all(entry.get("phase") == "describe" for entry in zeros)


def test_loop_preplan_appears_on_ledger(
        script_spark, stub_responses, drive_loop, make_run, make_ledger,
        monkeypatch, accepting_validator):
    """Both plan calls are on the ledger (dollars), never on turns."""
    run_dir = make_run()
    _use_sheets(monkeypatch, run_dir)
    ledger = make_ledger("r", run_dir)
    spark = script_spark([
        stub_responses["completed"](json.dumps(_describe_answer())),
        stub_responses["completed"](json.dumps(_wonder_answer())),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1},
                           "evidence_path": None,
                           "dry_run": False}, "call-s")]),
    ])
    out = drive_loop(run_dir, spark, ledger=ledger,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    zeros = [entry for entry in ledger.entries
             if entry.get("turn") == 0]
    assert len(zeros) == 2
    assert int(ledger.turns) == 1


def _segment_call(stub_responses, call_id):
    return stub_responses["call"](
        "segment", {"phrase": "the wall", "frame_start": 0,
                    "frame_end": 7, "confirm_small_range": True},
        call_id)


def _submit_call(stub_responses, call_id):
    return stub_responses["call"](
        "submit", {"evidence": {"a": 1}, "evidence_path": None,
                   "dry_run": False}, call_id)


def test_loop_preplan_closes_exploration_at_wall_third(
        script_spark, stub_responses, drive_loop, make_run, fake_clock,
        accepting_validator):
    """A stub that never submits finds segment closed once one third of
    the wall budget has passed, and open just before (Moon run 15)."""
    third = config.HARD_CAP_WALL_S / 3

    def _drive_at(level, name):
        run_dir = make_run(name)

        def _advance(request):
            fake_clock.advance(level)
            return stub_responses["completed"]("warming up")

        spark = script_spark([
            _advance,
            stub_responses["completed"](
                "explore", [_segment_call(stub_responses, "call-seg")]),
            stub_responses["completed"](
                "done", [_submit_call(stub_responses, "call-submit")]),
        ])
        out = drive_loop(run_dir, spark, clock=fake_clock,
                         validator=accepting_validator(run_dir))
        assert out["status"] == "submitted"
        lines = (run_dir / "logs" / "loop.jsonl").read_text(
            encoding="utf-8").splitlines()
        rendered = [tc.get("rendered", "")
                    for entry in (json.loads(line) for line in lines)
                    for tc in entry.get("tool_calls", [])
                    if tc.get("rendered")
                    and tc.get("name") == "segment"]
        assert len(rendered) == 1
        return rendered[0]

    fake_clock.now = 0.0
    before = _drive_at(third - 60, "before-third")
    assert "closed until your first dry run" not in before
    assert "sam_unavailable" in before
    fake_clock.now = 0.0
    after = _drive_at(third + 60, "after-third")
    assert after.startswith("closed until your first dry run")


def test_loop_initial_task_names_one_third_budget():
    """The initial task tells the agent to dry-run by one third."""
    assert "by one third of the budget" in INITIAL_TASK
    assert "by one third of the budget" in initial_task(None)
    assert "by one third of the budget" in initial_task(
        _wonder_answer())


def test_loop_preplan_donates_agent_turn_to_turn_1(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """An agent-turn-shaped reply to a pre-loop call is reused as turn
    1 instead of consuming the queue behind it (older harnesses serve
    agent turns first)."""
    run_dir = make_run()
    _use_sheets(monkeypatch, run_dir)
    spark = script_spark([
        stub_responses["completed"](
            "starting", [_segment_call(stub_responses, "call-seg")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, "call-submit")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert out["turns"] == 2
    pre = _prephase_requests(spark)
    assert len(pre) == 1
    skipped = json.loads((run_dir / "logs" / "preplan.json").read_text(
        encoding="utf-8"))
    assert skipped["status"] == "skipped"
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines]
    first = [e for e in entries if e.get("turn") == 1][0]
    names = [tc.get("name") for tc in first.get("tool_calls", [])]
    assert "segment" in names
    assert not (run_dir / "artifacts" / "wonder.json").exists()

# generated from brief/06 · part 06 owns this file
"""``check_line`` dispatch: the blind line-span check (part 06 addendum
2026-10-31, hand run 5).

The loop offers ``check_line`` (part 07 §19): it dispatches the call
like ``check_mask``, with the blind Spark client, the classifier and
the ledger. It is not an exploration tool, so it stays open in the
finishing phase and after the one-third budget closing.
"""

from __future__ import annotations

import json

import pytest

from src import config
from src.loop.prefix import INITIAL_TASK, initial_task
from src.loop.run import EXPLORATION_CLOSED_LINE, FINISHING_CLOSED_LINE

CLAIM = "the white bar: its left edge to its right edge"

SENTENCES = (
    "Never dry-run a placeholder; dry-run what you have measured, "
    "even if it is only one check.",
    "From your first measured check on, keep workspace/evidence.json "
    "current after every measurement; the loop submits that file when "
    "time runs out.",
    "Before a range check goes into a dry run, check its lines with "
    "check_line(frame, lines) on the frame you measured; re-measure "
    "any line the second look does not confirm.",
)


def _submit_call(stub_responses, call_id="call-submit"):
    return stub_responses["call"](
        "submit", {"evidence": {"a": 1}, "evidence_path": None,
                   "dry_run": False},
        call_id)


def _check_line_call(stub_responses, call_id="call-1"):
    return stub_responses["call"](
        "check_line",
        {"frame": 0,
         "lines": [{"x1": 10, "y1": 60, "x2": 150, "y2": 60,
                    "claim": CLAIM}]},
        call_id)


def _write_clip(run_dir, frames=8):
    """A decodable clip matching the loop fixture's timing (8 @ 10 fps)."""
    import cv2
    import numpy as np

    clip = run_dir / "input" / "clip.mp4"
    writer = cv2.VideoWriter(str(clip),
                             cv2.VideoWriter_fourcc(*"mp4v"),
                             10.0, (160, 120))
    assert writer.isOpened(), "no mp4 writer for the fixture clip"
    try:
        for i in range(int(frames)):
            grid = np.zeros((120, 160, 3), dtype=np.uint8)
            x = (i * 3) % 120
            grid[40:80, x:x + 40] = 255
            writer.write(grid)
    finally:
        writer.release()
    return clip


def _usage():
    return {"input_tokens": 10, "cached_tokens": 0, "output_tokens": 5,
            "reasoning_tokens": 0}


def _rendered_of(run_dir, name):
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    return [tc.get("rendered", "")
            for entry in (json.loads(line) for line in lines)
            for tc in entry.get("tool_calls", [])
            if tc.get("rendered") and tc.get("name") == name]


def test_loop_initial_task_names_no_placeholder_lines():
    """The initial task carries the three hand-run-5 sentences, with
    and without a plan."""
    wonder = {
        "question": "Could a hand really be that long?",
        "checks": [{"what": "hand length", "kind": "range",
                    "why": "answers it", "how": "measure it",
                    "compare_with": "body norms"}],
    }
    for task in (INITIAL_TASK, initial_task(None),
                 initial_task(wonder)):
        for sentence in SENTENCES:
            assert sentence in task


def test_loop_check_line_reaches_tool_with_blind_client_and_ledger(
        script_spark, stub_responses, drive_loop, make_run, make_ledger,
        monkeypatch, accepting_validator):
    """A stub agent's ``check_line`` call reaches the tool with the
    blind client, the classifier and the ledger — and the run goes on."""
    import src.loop.run as run_mod

    monkeypatch.setattr(run_mod, "run_preplan",
                        lambda *args, **kwargs: (None, None, None))
    run_dir = make_run()
    _write_clip(run_dir)
    ledger = make_ledger("r", run_dir)
    blind_inputs: list = []
    classifier_seen: list = []

    def _blind(request):
        blind_inputs.append(dict(request))
        if "image" in request:
            return {"descriptions": ["a white bar from its left edge "
                                     "to its right edge"],
                    "usage": _usage()}
        return {"results": [{"agrees": True,
                             "why": "the description matches the claim"}],
                "usage": _usage()}

    def _classifier(claim):
        classifier_seen.append(claim)
        return "no"

    spark = script_spark([
        stub_responses["completed"](
            "checking", [_check_line_call(stub_responses)]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-2")]),
    ])
    out = drive_loop(run_dir, spark, ledger=ledger,
                     validator=accepting_validator(run_dir),
                     blind_spark_client=_blind, classifier=_classifier)
    assert out["status"] == "submitted"
    assert len(blind_inputs) == 2
    # The loop pins only what it owns — the call reaches the tool
    # with the blind client, and the image and the claims never
    # travel together — never the exact key set part 07 builds (part
    # 06 addendum 2026-10-31, part 07 §20: the tool may add keys
    # such as ``kind``, which this stub accepts and ignores).
    assert {"image", "question"} <= set(blind_inputs[0])
    assert "claims" not in blind_inputs[0]
    assert "descriptions" not in blind_inputs[0]
    assert {"descriptions", "claims", "question"} <= set(blind_inputs[1])
    assert "image" not in blind_inputs[1]
    assert blind_inputs[1]["claims"] == [CLAIM]
    assert classifier_seen == [CLAIM]
    assert int(ledger.mask_checks) == 2
    rendered = _rendered_of(run_dir, "check_line")
    assert len(rendered) == 1
    assert "line check on frame 0" in rendered[0]
    assert "white bar from its left edge" in rendered[0]


def test_loop_check_line_stays_open_in_finishing_phase(
        script_spark, stub_responses, drive_loop, make_run, make_ledger,
        monkeypatch, fake_clock, accepting_validator):
    """At 80% of wall time ``segment`` is finishing-closed while
    ``check_line`` still runs (it checks, it does not explore)."""
    import src.loop.run as run_mod

    monkeypatch.setattr(run_mod, "run_preplan",
                        lambda *args, **kwargs: (None, None, None))
    run_dir = make_run()
    _write_clip(run_dir)

    def _blind(request):
        if "image" in request:
            return {"descriptions": ["a white bar from its left edge "
                                     "to its right edge"],
                    "usage": _usage()}
        return {"results": [{"agrees": True, "why": "matches"}],
                "usage": _usage()}

    def _first(request):
        fake_clock.advance(
            config.HARD_CAP_WALL_S * config.WARN_RATIO + 1)
        return stub_responses["completed"]("warming up")

    spark = script_spark([
        _first,
        stub_responses["completed"](
            "finish", [stub_responses["call"](
                "segment", {"phrase": "the wall", "frame_start": 0,
                            "frame_end": 7, "confirm_small_range": True},
                "call-seg"),
                _check_line_call(stub_responses, call_id="call-line")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-submit")]),
    ])
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     ledger=make_ledger("r", run_dir),
                     validator=accepting_validator(run_dir),
                     blind_spark_client=_blind,
                     classifier=lambda claim: "no")
    assert out["status"] == "submitted"
    segments = _rendered_of(run_dir, "segment")
    assert len(segments) == 1
    assert segments[0].startswith(FINISHING_CLOSED_LINE)
    checked = _rendered_of(run_dir, "check_line")
    assert len(checked) == 1
    assert "line check on frame 0" in checked[0]
    assert "closed" not in checked[0]


def test_loop_check_line_stays_open_after_exploration_close(
        script_spark, stub_responses, drive_loop, make_run, make_ledger,
        monkeypatch, fake_clock, accepting_validator):
    """Past one third of wall time with no submit, ``segment`` is
    exploration-closed while ``check_line`` still runs."""
    import src.loop.run as run_mod

    monkeypatch.setattr(run_mod, "run_preplan",
                        lambda *args, **kwargs: (None, None, None))
    run_dir = make_run()
    _write_clip(run_dir)

    def _blind(request):
        if "image" in request:
            return {"descriptions": ["a white bar from its left edge "
                                     "to its right edge"],
                    "usage": _usage()}
        return {"results": [{"agrees": True, "why": "matches"}],
                "usage": _usage()}

    def _first(request):
        fake_clock.advance(config.HARD_CAP_WALL_S / 3.0 + 1)
        return stub_responses["completed"]("warming up")

    spark = script_spark([
        _first,
        stub_responses["completed"](
            "explore", [stub_responses["call"](
                "segment", {"phrase": "the wall", "frame_start": 0,
                            "frame_end": 7, "confirm_small_range": True},
                "call-seg"),
                _check_line_call(stub_responses, call_id="call-line")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-submit")]),
    ])
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     ledger=make_ledger("r", run_dir),
                     validator=accepting_validator(run_dir),
                     blind_spark_client=_blind,
                     classifier=lambda claim: "no")
    assert out["status"] == "submitted"
    segments = _rendered_of(run_dir, "segment")
    assert len(segments) == 1
    assert segments[0].startswith(EXPLORATION_CLOSED_LINE)
    checked = _rendered_of(run_dir, "check_line")
    assert len(checked) == 1
    assert "line check on frame 0" in checked[0]
    assert "closed" not in checked[0]

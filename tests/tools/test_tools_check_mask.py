# generated from brief/07 · part 07 owns this file
"""``check_mask``: context-free coverage, never identity."""

from __future__ import annotations

import json

from src.tools import check_mask, view_frames


def _overlay(make_run):
    run = make_run(frames=40)
    shot = view_frames.view_frames(str(run), 0, frame_start=0,
                                   frame_end=7)
    assert shot["ok"], shot
    return run, shot["files"][0]


def test_blind_call_gets_no_run_context(make_run, blind_ok, ledger):
    run, overlay = _overlay(make_run)
    result = check_mask.check_mask(str(run), 1,
                                   overlay_artifact=overlay,
                                   spark_client=blind_ok,
                                   ledger=ledger)
    assert result["ok"], result
    seen = blind_ok.seen
    assert set(seen) == {"image", "extents", "question"}
    assert seen["question"] == check_mask.NEUTRAL_QUESTION
    assert isinstance(seen["image"], bytes) and seen["image"]
    assert seen["extents"]["width_px"] > 0
    # The question never asks what the object is, and the request
    # carries no phrase, hypothesis, history or clip name.
    lowered = seen["question"].lower()
    assert "what the mask covers" in lowered
    assert "do not" in lowered
    assert "phrase" not in lowered


def test_coverage_record_saved_and_counted(make_run, blind_ok, ledger):
    run, overlay = _overlay(make_run)
    result = check_mask.check_mask(str(run), 1,
                                   overlay_artifact=overlay,
                                   spark_client=blind_ok,
                                   ledger=ledger)
    assert result["ok"], result
    record_rel = result["metrics"]["record_artifact"]
    assert record_rel in result["files"]
    record = json.loads((run / record_rel).read_text(
        encoding="utf-8"))
    assert record["coverage_answer"].startswith("covers the left half")
    assert record["alternatives"] == ["covers the whole bright region"]
    registry = json.loads((run / "workspace" / "mask_checks.json"
                           ).read_text(encoding="utf-8"))
    assert {"artifact": record_rel, "overlay": overlay,
            "turn": 1} in registry
    assert ledger.mask_checks == 1


def test_undecodable_overlay_still_reaches_blind(make_run, blind_ok,
                                                 ledger):
    run = make_run(frames=10)
    overlay = "artifacts/overlay.png"
    (run / overlay).write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    result = check_mask.check_mask(str(run), 0,
                                   overlay_artifact=overlay,
                                   spark_client=blind_ok, ledger=ledger)
    assert result["ok"], result
    assert blind_ok.seen["extents"] == {}


def test_blind_question_asks_about_parts(make_run, blind_ok):
    # Part 07 §14: besides what the tinted region covers, the blind
    # question must ask for separable/stacked parts inside it and any
    # part of the same object left outside — the pack-vs-pack-plus-top
    # ambiguity must surface here.
    assert "stacked" in check_mask.NEUTRAL_QUESTION
    assert "separable" in check_mask.NEUTRAL_QUESTION
    run, overlay = _overlay(make_run)
    result = check_mask.check_mask(str(run), 2,
                                   overlay_artifact=overlay,
                                   spark_client=blind_ok)
    assert result["ok"], result
    question = blind_ok.seen["question"]
    assert "stacked" in question
    assert "separable" in question
    assert "outside" in question
    record = json.loads(
        (run / result["metrics"]["record_artifact"]).read_text(
            encoding="utf-8"))
    assert record["question"] == check_mask.NEUTRAL_QUESTION


def test_blind_question_names_no_kind(make_run, blind_ok, ledger):
    # Part 07 §16: the one-word kind question (§15) is withdrawn. The
    # blind question carries no person/animal/object wording, and the
    # check artifact carries no kind_answer.
    assert "person" not in check_mask.NEUTRAL_QUESTION
    assert "person" not in check_mask.NEUTRAL_QUESTION.lower()
    run, overlay = _overlay(make_run)
    result = check_mask.check_mask(str(run), 3,
                                   overlay_artifact=overlay,
                                   spark_client=blind_ok, ledger=ledger)
    assert result["ok"], result
    assert "person" not in blind_ok.seen["question"]
    record = json.loads(
        (run / result["metrics"]["record_artifact"]).read_text(
            encoding="utf-8"))
    assert "kind_answer" not in record
    assert record["question"] == check_mask.NEUTRAL_QUESTION


def test_agent_supplied_extents_pass_through(make_run, blind_ok):
    run, overlay = _overlay(make_run)
    given = {"width_px": 160, "height_px": 120}
    result = check_mask.check_mask(str(run), 0,
                                   overlay_artifact=overlay,
                                   extents=given, spark_client=blind_ok)
    assert result["ok"], result
    assert blind_ok.seen["extents"] == given
    from src.tools import check_mask as mod

    assert mod.parse_extents('{"a": 1}') == {"a": 1}
    assert mod.parse_extents(None) == {}
    for bad in (42, "[1, 2",):
        try:
            mod.parse_extents(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"parse_extents({bad!r}) must fail")


def test_paths_rejected_and_missing_backend(make_run, blind_ok):
    run = make_run(frames=40)
    absolute = check_mask.check_mask(
        str(run), 0, overlay_artifact="/tmp/x.png",
        spark_client=blind_ok)
    assert not absolute["ok"]
    assert absolute["error"]["code"] == "path_rejected"
    escaped = check_mask.check_mask(
        str(run), 0, overlay_artifact="artifacts/../logs/x.png",
        spark_client=blind_ok)
    assert not escaped["ok"]
    outside = check_mask.check_mask(
        str(run), 0, overlay_artifact="workspace/x.png",
        spark_client=blind_ok)
    assert not outside["ok"]
    assert outside["error"]["code"] == "path_rejected"
    missing = check_mask.check_mask(
        str(run), 0, overlay_artifact="artifacts/t0_ghost.png",
        spark_client=blind_ok)
    assert not missing["ok"]
    assert missing["error"]["code"] == "missing_overlay"
    run2, overlay2 = _overlay(make_run)
    nobackend = check_mask.check_mask(
        str(run2), 0, overlay_artifact=overlay2, spark_client=None)
    assert not nobackend["ok"]
    assert nobackend["error"]["code"] == "blind_unavailable"


def test_blind_failure_is_a_tool_error(make_run, ledger):
    run, overlay = _overlay(make_run)

    def _boom(request):
        raise RuntimeError("model down")

    result = check_mask.check_mask(str(run), 0,
                                   overlay_artifact=overlay,
                                   spark_client=_boom, ledger=ledger)
    assert not result["ok"]
    assert result["error"]["code"] == "blind_failed"
    assert ledger.mask_checks == 0

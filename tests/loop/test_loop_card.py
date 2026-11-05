# generated from brief/06 · part 06 owns this file
"""The clip card: masks before the plan (part 06 addendum 2026-11-04,
street-jump run 83).

Describe names the moving things; the card segments each phrase over
the whole clip, runs ``motion_overview`` on each result, and measures
contacts and the camera from masks — all with stub Spark and stub
SAM, no model calls. Wonder's request and the initial task then quote
the card. Caps always come from :mod:`src.config`; no literal cap or
effort appears here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import config
from src.loop.card import (
    CARD_ARTIFACT_PREFIX,
    CONTACT_PX,
    MAX_MOVING_THINGS,
    describe_moving_things,
)

N_FRAMES = 16
FPS = 10.0


def _make_clip_run(tmp_path, name="card-run"):
    """Fresh run dir with a real readable clip and matching timing."""
    import cv2
    import numpy as np

    run_dir = tmp_path / name
    for sub in ("input", "workspace", "artifacts", "logs"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(run_dir / "input" / "clip.mp4"),
        cv2.VideoWriter_fourcc(*"mp4v"), FPS, (64, 48))
    for index in range(N_FRAMES):
        img = np.full((48, 64, 3), 200 - index, np.uint8)
        cv2.rectangle(img, (5 + index, 5), (20 + index, 20),
                      (0, 0, 255), -1)
        writer.write(img)
    writer.release()
    (run_dir / "input" / "timing.json").write_text(json.dumps({
        "frame_count": N_FRAMES,
        "timestamps": [index / FPS for index in range(N_FRAMES)],
        "measured_fps": FPS, "confirmed_duplicates": [], "cuts": [],
    }) + "\n", encoding="utf-8")
    return run_dir


def _describe_answer(*phrases):
    return {
        "what_happens": [
            "a figure stands at the left at 0.0 s",
            "the figure jumps at 0.3 s",
            "the figure lands at 0.6 s",
        ],
        "scene": "a flat field filmed from the side, frame 0",
        "things": "one person in light clothing and a car",
        "moving_things": list(phrases),
        "on_screen_text": "",
    }


def _wonder_answer(question="could a person really clear the car"):
    return {
        "claim": "the clip shows a leap over a car that looks staged",
        "question": question,
        "world": "Earth",
        "checks": [
            {"kind": "gravity",
             "what": "leap acceleration",
             "why": "a free flight must fall at the world's g",
             "how": "segment the jumper over frames 60..110",
             "compare_with": "the world's gravity"},
            {"kind": "range",
             "what": "car height",
             "why": "checks the scale the leap is judged against",
             "how": "measure the car against a known height",
             "compare_with": "the car's published height"},
        ],
        "realistic_if": "the fit matches within sigma",
        "not_realistic_if": "the fit misses by several sigma",
    }


def _mask_box(height, width, rows, cols):
    import numpy as np

    mask = np.zeros((height, width), dtype=bool)
    mask[rows[0]:rows[1], cols[0]:cols[1]] = True
    return mask


def _stub_sam(calls, layouts, fail_on=()):
    """SAM stub: one object id per phrase, masks from ``layouts``.

    ``layouts`` maps phrase to ``(object_id, per_frame_region)`` where
    the region is either a fixed ``(rows, cols)`` box or a dict of
    ``frame -> (rows, cols)``. ``fail_on`` phrases raise instead.
    """
    import numpy as np

    def _sam(phrase, indices, grids):
        calls.append({"phrase": phrase, "indices": list(indices)})
        if phrase in fail_on:
            raise RuntimeError(f"no masks for {phrase}")
        height, width = np.asarray(grids[0]).shape[:2]
        oid, spec = layouts[phrase]
        seq = []
        for frame in indices:
            if isinstance(spec, dict):
                box = spec.get(frame)
            else:
                box = spec
            if box is None:
                seq.append(np.zeros((height, width), dtype=bool))
            else:
                seq.append(_mask_box(height, width, *box))
        return {oid: seq}

    return _sam


def _initial_task_of(spark):
    """The initial-task text: the user message quoting the plan."""
    for request in spark.requests:
        for message in request["messages"]:
            if message.get("role") != "user":
                continue
            blob = "\n".join(
                block.get("text", "") for block in message.get("content", [])
                if isinstance(block, dict)
                and block.get("type") == "text")
            if "Analyse the clip" in blob:
                return blob
    raise AssertionError("no initial task found in requests")


def test_loop_card_segments_phrases_and_lists_objects(
        tmp_path, script_spark, stub_responses, drive_loop,
        accepting_validator):
    """Two moving things: one whole-clip segment per phrase, one
    overview per result, both objects in ``artifacts/card.json``."""
    run_dir = _make_clip_run(tmp_path)
    sam_calls: list = []
    sam = _stub_sam(sam_calls, {
        "the jumper": ("0", ((2, 8), (2, 8))),
        "the car": ("1", ((2, 8), (40, 46))),
    })
    spark = script_spark([
        stub_responses["completed"](
            json.dumps(_describe_answer("the jumper", "the car"))),
        stub_responses["completed"](json.dumps(_wonder_answer())),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1},
                           "evidence_path": None,
                           "dry_run": False}, "call-s")]),
    ])
    out = drive_loop(run_dir, spark, sam_client=sam,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert len(sam_calls) == 2
    assert [call["phrase"] for call in sam_calls] == [
        "the jumper", "the car"]
    for call in sam_calls:
        assert call["indices"] == list(range(N_FRAMES))
    card = json.loads((run_dir / "artifacts" / "card.json").read_text(
        encoding="utf-8"))
    assert card["status"] == "ok"
    assert len(card["objects"]) == 2
    for entry, phrase in zip(card["objects"],
                             ("the jumper", "the car")):
        assert entry["phrase"] == phrase
        assert entry["masks_artifact"].startswith(
            f"artifacts/{CARD_ARTIFACT_PREFIX}")
        assert (run_dir / entry["masks_artifact"]).is_file()
        assert entry["object_id"]
        assert entry["chart_artifact"] is None or (
            run_dir / entry["chart_artifact"]).is_file()
    assert (run_dir / "logs" / "card.json").is_file()
    spent = int(config.MAX_SAM_FRAMES)
    assert spent > 0


def test_loop_card_no_contact_between_far_masks(
        tmp_path, script_spark, stub_responses, drive_loop,
        accepting_validator):
    """Two masks never within 3 px: the card says no contact, and the
    initial task quotes the objects with that line."""
    run_dir = _make_clip_run(tmp_path, "no-contact")
    sam = _stub_sam([], {
        "the jumper": ("0", ((2, 8), (2, 8))),
        "the car": ("1", ((2, 8), (40, 46))),
    })
    spark = script_spark([
        stub_responses["completed"](
            json.dumps(_describe_answer("the jumper", "the car"))),
        stub_responses["completed"](json.dumps(_wonder_answer())),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1},
                           "evidence_path": None,
                           "dry_run": False}, "call-s")]),
    ])
    out = drive_loop(run_dir, spark, sam_client=sam,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    card = json.loads((run_dir / "artifacts" / "card.json").read_text(
        encoding="utf-8"))
    assert card["contacts"] == []
    task = _initial_task_of(spark)
    assert "the jumper" in task and "the car" in task
    assert CARD_ARTIFACT_PREFIX in task
    assert "no contact between any two objects" in task


def test_loop_card_overlap_lists_contact_range(
        tmp_path, script_spark, stub_responses, drive_loop,
        accepting_validator):
    """Two masks overlapping in frames 10–14: the card lists that
    range with a zero gap, quoted by the task."""
    run_dir = _make_clip_run(tmp_path, "overlap")
    car_spec = {frame: (((2, 8), (2, 8)) if 10 <= frame <= 14
                        else ((2, 8), (40, 46)))
                for frame in range(N_FRAMES)}
    sam = _stub_sam([], {
        "the jumper": ("0", ((2, 8), (2, 8))),
        "the car": ("1", car_spec),
    })
    spark = script_spark([
        stub_responses["completed"](
            json.dumps(_describe_answer("the jumper", "the car"))),
        stub_responses["completed"](json.dumps(_wonder_answer())),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1},
                           "evidence_path": None,
                           "dry_run": False}, "call-s")]),
    ])
    out = drive_loop(run_dir, spark, sam_client=sam,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    card = json.loads((run_dir / "artifacts" / "card.json").read_text(
        encoding="utf-8"))
    assert len(card["contacts"]) == 1
    contact = card["contacts"][0]
    assert contact["ranges"] == [[10, 14]]
    assert contact["min_gap_px"] == pytest.approx(0.0)
    assert contact["a"]["phrase"] == "the jumper"
    assert contact["b"]["phrase"] == "the car"
    task = _initial_task_of(spark)
    assert "10..14" in task
    assert "these masks exist; reuse them" in task


def test_loop_card_wonder_sees_objects_and_contacts(
        tmp_path, script_spark, stub_responses, drive_loop,
        accepting_validator):
    """Wonder's request carries the card's objects and contacts, and
    the initial task quotes each object with its artifact and id."""
    run_dir = _make_clip_run(tmp_path, "wonder-card")
    car_spec = {frame: (((2, 8), (2, 8)) if 10 <= frame <= 14
                        else ((2, 8), (40, 46)))
                for frame in range(N_FRAMES)}
    sam = _stub_sam([], {
        "the jumper": ("0", ((2, 8), (2, 8))),
        "the car": ("1", car_spec),
    })
    spark = script_spark([
        stub_responses["completed"](
            json.dumps(_describe_answer("the jumper", "the car"))),
        stub_responses["completed"](json.dumps(_wonder_answer())),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1},
                           "evidence_path": None,
                           "dry_run": False}, "call-s")]),
    ])
    out = drive_loop(run_dir, spark, sam_client=sam,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    wonder_request = spark.requests[1]
    wonder_blob = json.dumps(wonder_request)
    assert "the jumper" in wonder_blob
    assert "the car" in wonder_blob
    assert "10" in wonder_blob and "14" in wonder_blob
    chart_images = [
        block.get("artifact", "") for message in wonder_request["messages"]
        for block in message.get("content", [])
        if isinstance(block, dict) and block.get("type") == "image"]
    assert any(str(name).startswith(
        f"artifacts/{CARD_ARTIFACT_PREFIX}") for name in chart_images)
    task = _initial_task_of(spark)
    card = json.loads((run_dir / "artifacts" / "card.json").read_text(
        encoding="utf-8"))
    for entry in card["objects"]:
        assert entry["masks_artifact"] in task
        assert f"object id {entry['object_id']}" in task


def test_loop_card_failed_phrase_listed_and_run_starts(
        tmp_path, script_spark, stub_responses, drive_loop,
        accepting_validator):
    """A phrase SAM fails on is listed with its reason, and the loop
    still starts (with the surviving object quoted)."""
    run_dir = _make_clip_run(tmp_path, "fail-one")
    sam_calls: list = []
    sam = _stub_sam(sam_calls, {
        "the jumper": ("0", ((2, 8), (2, 8))),
    }, fail_on=("the car",))
    spark = script_spark([
        stub_responses["completed"](
            json.dumps(_describe_answer("the jumper", "the car"))),
        stub_responses["completed"](json.dumps(_wonder_answer())),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1},
                           "evidence_path": None,
                           "dry_run": False}, "call-s")]),
    ])
    out = drive_loop(run_dir, spark, sam_client=sam,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert [call["phrase"] for call in sam_calls] == [
        "the jumper", "the car"]
    card = json.loads((run_dir / "artifacts" / "card.json").read_text(
        encoding="utf-8"))
    assert [entry["phrase"] for entry in card["objects"]] == ["the jumper"]
    assert len(card["failed"]) == 1
    assert card["failed"][0]["phrase"] == "the car"
    assert card["failed"][0]["reason"]
    assert "the jumper" in _initial_task_of(spark)


def test_loop_card_stops_before_half_sam_budget(
        tmp_path, script_spark, stub_responses, drive_loop, make_ledger,
        accepting_validator):
    """A phrase that would take the card past half of the run's SAM
    frame budget is left out with that reason, and the loop still
    starts (without a card when nothing was built)."""
    from src.loop.card import CARD_LOG_FILENAME

    run_dir = _make_clip_run(tmp_path, "half-cap")
    ledger = make_ledger("r", run_dir)
    ledger.sam_frames_billed = int(config.MAX_SAM_FRAMES) // 2
    sam_calls: list = []
    sam = _stub_sam(sam_calls, {
        "the jumper": ("0", ((2, 8), (2, 8))),
    })
    spark = script_spark([
        stub_responses["completed"](
            json.dumps(_describe_answer("the jumper"))),
        stub_responses["completed"](json.dumps(_wonder_answer())),
        stub_responses["completed"](
            "done", [stub_responses["call"](
                "submit", {"evidence": {"a": 1},
                           "evidence_path": None,
                           "dry_run": False}, "call-s")]),
    ])
    out = drive_loop(run_dir, spark, ledger=ledger, sam_client=sam,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert sam_calls == []
    assert not (run_dir / "artifacts" / "card.json").exists()
    logged = json.loads((run_dir / CARD_LOG_FILENAME).read_text(
        encoding="utf-8"))
    assert logged["status"] == "failed"
    assert len(logged["left_out"]) == 1
    assert logged["left_out"][0]["phrase"] == "the jumper"
    assert "half" in logged["left_out"][0]["reason"]
    assert "no contact" not in _initial_task_of(spark)


def test_loop_card_describe_moving_things_capped():
    """Phrase extraction keeps Describe order and caps at four."""
    assert describe_moving_things({}) == []
    assert describe_moving_things({"moving_things": "a car"}) == []
    assert describe_moving_things(
        {"moving_things": ["  ", "the car"]}) == ["the car"]
    many = [f"thing {index}" for index in range(6)]
    assert describe_moving_things({"moving_things": many}) == many[
        :int(MAX_MOVING_THINGS)]
    assert int(CONTACT_PX) == 3

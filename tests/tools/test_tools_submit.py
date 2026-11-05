# generated from brief/07 · part 07 owns this file
"""``submit``: the only path to result.json; readable rejections."""

from __future__ import annotations

import json

from src.tools import submit


def _evidence():
    return {"first_look": {"q": 1}}


def _accept(result_path=None):
    def _validator(evidence, context, dry_run=False):
        assert isinstance(evidence, dict)
        assert "run_dir" in context and "timing" in context
        return {"accepted": True, "errors": [],
                "result_path": result_path, "result": {"ok": True}}

    return _validator


def _reject(errors):
    def _validator(evidence, context, dry_run=False):
        return {"accepted": False, "errors": list(errors)}

    return _validator


def test_accepted_submit_writes_submission_and_names_result(make_run):
    run = make_run(frames=10)
    out = submit.submit(str(run), 0, _evidence(),
                        validator=_accept(str(run / "result.json")))
    assert out["ok"]
    assert out["metrics"]["accepted"] is True
    assert out["metrics"]["dry_run"] is False
    assert out["metrics"]["result_path"] == str(run / "result.json")
    assert "workspace/submission.json" in out["files"]
    saved = json.loads((run / "workspace" / "submission.json"
                        ).read_text(encoding="utf-8"))
    assert saved == _evidence()


def test_evidence_string_parsed(make_run):
    run = make_run(frames=10)
    out = submit.submit(str(run), 0, json.dumps(_evidence()),
                        validator=_accept())
    assert out["ok"]


def test_bad_evidence_rejected(make_run):
    run = make_run(frames=10)
    out = submit.submit(str(run), 0, "not json{{{",
                        validator=_accept())
    assert not out["ok"]
    assert out["error"]["code"] == "bad_arguments"
    out2 = submit.submit(str(run), 0, [1, 2], validator=_accept())
    assert out2["error"]["code"] == "bad_arguments"


def test_rejection_summary_names_every_code_and_field(make_run):
    run = make_run(frames=10)
    errors = [{"code": "V9", "field": "error_budget",
               "detail": "sigma mismatch"},
              {"code": "V1", "field": "clock",
               "detail": "missing clock"},
              {"code": "V9", "field": "error_budget.components",
               "detail": "unknown component"}]
    out = submit.submit(str(run), 4, _evidence(),
                        validator=_reject(errors))
    assert not out["ok"]
    assert out["error"]["code"] == "submit_rejected"
    for error in errors:
        assert error["code"] in out["summary"]
        assert error["field"] in out["summary"]
    assert out["summary"].index("V1 clock") < out["summary"].index(
        "V9 error_budget"), "V1 errors come first"
    errors_rel = "artifacts/t4_submit_errors.json"
    assert errors_rel in out["files"]
    assert out["metrics"]["errors_artifact"] == errors_rel
    saved = json.loads((run / errors_rel).read_text(encoding="utf-8"))
    assert saved == errors
    assert (run / "workspace" / "submission.json").is_file()


def test_rejection_overflow_marker(make_run):
    run = make_run(frames=10)
    errors = [{"code": "V3", "field": f"f{i}", "detail": "d"}
              for i in range(45)]
    out = submit.submit(str(run), 0, _evidence(),
                        validator=_reject(errors))
    assert "+5 more of V3" in out["summary"]
    assert out["metrics"]["error_count"] == 45


def test_dry_run_validates_writes_nothing(make_run):
    run = make_run(frames=10)
    out = submit.submit(str(run), 0, _evidence(),
                        validator=_accept(), dry_run=True)
    assert out["ok"]
    assert out["metrics"]["dry_run"] is True
    assert not (run / "workspace" / "submission.json").exists(), \
        "a dry run writes no submission"
    assert out["files"] == ["artifacts/t0_submit_errors.json"]
    assert json.loads((run / out["files"][0]).read_text(
        encoding="utf-8")) == []


def test_dry_run_rejection_still_saves_errors(make_run):
    run = make_run(frames=10)
    errors = [{"code": "V1", "field": "scale", "detail": "no scale"}]
    out = submit.submit(str(run), 6, _evidence(),
                        validator=_reject(errors), dry_run=True)
    assert not out["ok"]
    errors_rel = "artifacts/t6_submit_errors.json"
    assert errors_rel in out["files"]
    assert json.loads((run / errors_rel).read_text(
        encoding="utf-8")) == errors
    assert "V1 scale" in out["summary"]


def test_evidence_path_dry_run_passes_and_copies_file(make_run):
    run = make_run(frames=10)
    draft = _evidence()
    (run / "workspace" / "evidence.json").write_text(
        json.dumps(draft, indent=2), encoding="utf-8")
    seen = {}

    def _validator(evidence, context, dry_run=False):
        seen["evidence"] = evidence
        return {"accepted": True, "errors": [],
                "result_path": None, "result": {"ok": True}}

    out = submit.submit(str(run), 3,
                        evidence_path="workspace/evidence.json",
                        validator=_validator, dry_run=True)
    assert out["ok"], out
    assert out["metrics"]["dry_run"] is True
    assert seen["evidence"] == draft, \
        "the validator receives the parsed file object"
    copy_rel = "artifacts/t3_evidence.json"
    assert copy_rel in out["files"]
    assert out["metrics"]["evidence_artifact"] == copy_rel
    assert json.loads((run / copy_rel).read_text(
        encoding="utf-8")) == draft
    assert not (run / "workspace" / "submission.json").exists(), \
        "a dry run writes no submission"
    assert "artifacts/t3_submit_errors.json" in out["files"]


def test_evidence_path_real_submit_writes_both(make_run):
    run = make_run(frames=10)
    draft = _evidence()
    (run / "workspace" / "evidence.json").write_text(
        json.dumps(draft), encoding="utf-8")
    out = submit.submit(str(run), 2,
                        evidence_path="workspace/evidence.json",
                        validator=_accept(str(run / "result.json")))
    assert out["ok"], out
    assert "workspace/submission.json" in out["files"]
    assert "artifacts/t2_evidence.json" in out["files"]
    assert json.loads((run / "workspace" / "submission.json"
                       ).read_text(encoding="utf-8")) == draft


def test_evidence_and_path_together_rejected(make_run):
    run = make_run(frames=10)
    (run / "workspace" / "evidence.json").write_text(
        json.dumps(_evidence()), encoding="utf-8")
    out = submit.submit(str(run), 0, _evidence(),
                        evidence_path="workspace/evidence.json",
                        validator=_accept(), dry_run=True)
    assert not out["ok"]
    assert out["error"]["code"] == "bad_arguments"
    assert "exactly one" in out["summary"]


def test_neither_evidence_nor_path_rejected(make_run):
    run = make_run(frames=10)
    out = submit.submit(str(run), 0, validator=_accept(), dry_run=True)
    assert not out["ok"]
    assert out["error"]["code"] == "bad_arguments"


def test_evidence_path_outside_workspace_rejected(make_run):
    run = make_run(frames=10)
    (run / "artifacts" / "evidence.json").write_text(
        json.dumps(_evidence()), encoding="utf-8")
    for bad in ("artifacts/evidence.json", "input/timing.json",
                "../evidence.json", "/tmp/evidence.json",
                "workspace/../artifacts/evidence.json"):
        out = submit.submit(str(run), 0, evidence_path=bad,
                            validator=_accept(), dry_run=True)
        assert not out["ok"], bad
        assert out["error"]["code"] == "bad_arguments", bad


def test_evidence_path_unreadable_or_bad_json_rejected(make_run):
    run = make_run(frames=10)
    missing = submit.submit(str(run), 0,
                            evidence_path="workspace/missing.json",
                            validator=_accept(), dry_run=True)
    assert not missing["ok"]
    assert missing["error"]["code"] == "bad_arguments"
    (run / "workspace" / "broken.json").write_text("{nope")
    broken = submit.submit(str(run), 0,
                           evidence_path="workspace/broken.json",
                           validator=_accept(), dry_run=True)
    assert not broken["ok"]
    assert broken["error"]["code"] == "bad_arguments"


def test_dry_run_budget_capped(make_run):
    run = make_run(frames=10)
    for _ in range(5):
        out = submit.submit(str(run), 0, _evidence(),
                            validator=_accept(), dry_run=True)
        assert out["ok"]
    capped = submit.submit(str(run), 0, _evidence(),
                           validator=_accept(), dry_run=True)
    assert not capped["ok"]
    assert capped["error"]["code"] == "dry_run_capped"


def test_collect_run_context_shape(make_run):
    run = make_run(frames=10)
    (run / "artifacts" / "x.jpg").write_bytes(b"1")
    (run / "workspace" / "mask_checks.json").write_text(
        json.dumps([{"artifact": "artifacts/t0_check_mask_0.json",
                     "overlay": "artifacts/t0_view_frames_0.jpg",
                     "turn": 0}]), encoding="utf-8")
    context = submit.collect_run_context(str(run), run_id="r1")
    assert context["run_id"] == "r1"
    assert context["timing"]["frame_count"] == 10
    assert "artifacts/x.jpg" in context["artifacts"]
    assert context["mask_checks"] == ["artifacts/t0_check_mask_0.json"]
    assert "workspace/produced_files.json" not in context  # absent: no key


# --- §18: a dry run reaches the validator as a dry run -----------------------
#
# The default validator (no fake) must forward ``dry_run`` to part 11, so a
# one-reference dry run reports SECOND_REFERENCE_REQUIRED instead of being
# judged as a real submit, and an accepted dry run never writes result.json.

FPS_300 = 30.0
N_FRAMES_300 = 300


def _valid_tracks(start=30, end=60, level_y=200.0, g=1.62, scale=0.01,
                  fps=FPS_300):
    airtime = (end - start) / fps
    vy = g * airtime / 2.0
    rows = []
    for frame in range(start, end + 1):
        moment = (frame - start) / fps
        y_m = vy * moment - 0.5 * g * moment * moment
        rows.append({"frame": frame, "x_px": 100.0,
                     "y_px": level_y - y_m / scale})
    curve = [{"t_s": r["frame"] / fps, "x_px": r["x_px"],
              "y_px": r["y_px"]} for r in rows]
    return rows, curve


def _write_mask_npz(path, entries, shape=(240, 352)):
    import numpy as np

    arrays = {}
    manifest = []
    key_no = 0
    for object_id, frames in entries.items():
        for frame, boxes in frames.items():
            canvas = np.zeros(shape, dtype=np.uint8)
            for r0, c0, r1, c1 in boxes:
                canvas[r0:r1, c0:c1] = 1
            key = f"mask_{key_no}"
            key_no += 1
            arrays[key] = canvas
            manifest.append({"key": key, "object_id": str(object_id),
                             "object_id_type": "str",
                             "frame_index": int(frame),
                             "shape": list(shape)})
    arrays["__manifest__"] = np.array(manifest, dtype=object)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(str(path), **arrays)


def _make_default_valid_run(tmp_path, n_refs=2):
    """A run dir plus schema-valid evidence passing every real check.

    Mirrors part 11's own baseline (Moon free-flight track, two scale
    references, still camera) so the default validator — not a fake —
    judges it. With ``n_refs=1`` the evidence keeps the first
    reference only, with the scale's second-reference fields cleared.
    """
    import numpy as _np  # noqa: F401 -- ensures the runtime dep exists

    assert n_refs in (1, 2)
    run_dir = tmp_path / f"run_default_{n_refs}"
    (run_dir / "input").mkdir(parents=True)
    (run_dir / "workspace").mkdir(parents=True)
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "logs").mkdir(parents=True)
    timing = {"claimed_fps": FPS_300, "measured_fps": FPS_300,
              "frame_count": N_FRAMES_300,
              "duration_s": N_FRAMES_300 / FPS_300,
              "timestamps": [i / FPS_300 for i in range(N_FRAMES_300)],
              "confirmed_duplicates": [], "duplicate_runs": [], "cuts": []}
    (run_dir / "input" / "timing.json").write_text(
        json.dumps(timing), encoding="utf-8")
    produced = []

    def _record(rel):
        produced.append(rel)

    def _write_bytes(rel, data):
        path = run_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        _record(rel)

    _write_mask_npz(run_dir / "artifacts" / "ref_a.npz",
                    {"0": {10: [(20, 20, 86, 40)]}})
    _record("artifacts/ref_a.npz")
    _write_mask_npz(run_dir / "artifacts" / "ref_b.npz",
                    {"0": {10: [(20, 100, 86, 271)]}})
    _record("artifacts/ref_b.npz")
    check_a = {"overlay_artifact": "artifacts/view_0.jpg",
               "coverage_answer": "covers the whole reference block",
               "alternatives": [], "confidence": None, "turn": 1}
    check_b = {"overlay_artifact": "artifacts/view_0.jpg",
               "coverage_answer": "covers the whole figure",
               "alternatives": [], "confidence": None, "turn": 1}
    (run_dir / "artifacts" / "check_a.json").write_text(
        json.dumps(check_a), encoding="utf-8")
    _record("artifacts/check_a.json")
    (run_dir / "artifacts" / "check_b.json").write_text(
        json.dumps(check_b), encoding="utf-8")
    _record("artifacts/check_b.json")
    rows, curve = _valid_tracks()
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        json.dumps(rows), encoding="utf-8")
    _record("workspace/track_hop_a.json")
    ref_rows = [{"frame": f, "x_px": 150.0, "y_px": 150.0}
                for f in range(30, 61)]
    (run_dir / "workspace" / "ref_static.json").write_text(
        json.dumps(ref_rows), encoding="utf-8")
    _record("workspace/ref_static.json")
    _write_bytes("artifacts/view_0.jpg", b"fake-image")
    _write_bytes("artifacts/excl_mars.jpg", b"fake-image")
    references = [
        {"name": "reference block",
         "extent_description": "height of the block",
         "extent_type": "face_on",
         "extent_px": {"x1": 20.0, "y1": 20.0, "x2": 20.0, "y2": 86.0,
                       "length_px": 66.0, "frame": 10},
         "size_m": 0.66, "size_tolerance_m": 0.03,
         "size_derivation": {
             "mode": "single", "note": "quoted block height",
             "state_match": {
                 "shown_and_covered": "block body shown and covered",
                 "shown_not_covered": "lid shown but not covered"}},
         "sources": [{"url": "https://example.com/block",
                      "domain": "example.com",
                      "quote": "the block is 66 cm tall",
                      "quote_highlight": "66 cm", "value_m": 0.66,
                      "source_type": "catalogue"}],
         "mask": {"artifact": "artifacts/ref_a.npz", "object_id": "0",
                  "frame": 10,
                  "outline": [[20.0, 20.0], [40.0, 20.0],
                              [40.0, 86.0], [20.0, 86.0]]},
         "mask_check": {
             "artifact": "artifacts/check_a.json",
             "coverage_answer": "covers the whole reference block",
             "confidence": None, "alternative_readings": []}},
        {"name": "standing figure",
         "extent_description": "standing height",
         "extent_type": "rotation_invariant",
         "extent_px": {"x1": 100.0, "y1": 20.0, "x2": 100.0, "y2": 191.0,
                       "length_px": 171.0, "frame": 10},
         "size_m": 1.71, "size_tolerance_m": 0.20,
         "size_derivation": {
             "mode": "single", "note": "quoted standing height",
             "state_match": {
                 "shown_and_covered": "figure shown and covered",
                 "shown_not_covered": "boots shown but not covered"}},
         "sources": [{"url": "https://example.com/height",
                      "domain": "example.com",
                      "quote": "average height 171 cm",
                      "quote_highlight": "171 cm", "value_m": 1.71,
                      "source_type": "reference"}],
         "mask": {"artifact": "artifacts/ref_b.npz", "object_id": "0",
                  "frame": 10,
                  "outline": [[100.0, 20.0], [271.0, 20.0],
                              [271.0, 191.0], [100.0, 191.0]]},
         "mask_check": {
             "artifact": "artifacts/check_b.json",
             "coverage_answer": "covers the whole figure",
             "confidence": None, "alternative_readings": []}},
    ]
    references = references[:n_refs]
    evidence = {
        "first_look": {
            "question": "Does the physics add up to the Moon?",
            "summary": "A suited figure hops across grey ground.",
            "scene_card": {
                "scene": "Grey ground with a suited figure.",
                "place_date": None, "confidence": "medium",
                "objects": ["suited figure", "backpack"]},
            "by_eye": None,
            "views": [{"frame_start": 0, "frame_end": 299,
                       "artifact": "artifacts/view_0.jpg"}],
            "motions": [{"frame_start": 30, "frame_end": 60,
                         "description": "foreground hop",
                         "segment_id": "hop_a", "skip_reason": None}]},
        "references": references,
        "scale": {
            "frame": 10, "m_per_px": 0.01, "sigma_m_per_px": 0.0006,
            "reference_index": 0,
            "extent_px": {"x1": 20.0, "y1": 20.0, "x2": 20.0, "y2": 86.0,
                          "length_px": 66.0, "frame": 10},
            "second_reference_index": (1 if n_refs == 2 else None),
            "second_reference_absent_reason": (
                None if n_refs == 2 else
                "only one thing of known size at the depth of the motion"),
            "check_scale": {"m_per_px": 0.01, "sigma": 0.0012}},
        "segments": [{
            "id": "hop_a", "label": "Jump one", "kind": "free_flight",
            "mask": {"artifact": "artifacts/ref_b.npz",
                     "object_id": "0"},
            "frames": {"start": 30, "apex": 45, "end": 60},
            "key_moments": [
                {"type": "takeoff", "frame": 30,
                 "caption": "leaving the ground"},
                {"type": "apex", "frame": 45,
                 "caption": "hanging at the top"},
                {"type": "landing", "frame": 60,
                 "caption": "touching down softly"}],
            "track_artifact": "workspace/track_hop_a.json",
            "tracked_point": "top of the helmet",
            "fit_curve_px": curve, "repetitions": []}],
        "clock": None,
        "clock_absent_reason": "no visible independent rhythm",
        "worlds": {
            "candidates": [{"world": "Moon"}, {"world": "Earth"}],
            "excluded": [{"world": "Mars",
                          "evidence_text": "grey ground, no red soil",
                          "evidence_frames": [0],
                          "evidence_artifact":
                              "artifacts/excl_mars.jpg"}]},
        "error_budget": {
            "components": [
                {"name": "reference_size",
                 "sigma_contribution": 0.05,
                 "basis": "quoted size spread"},
                {"name": "pixel_scale", "sigma_contribution": 0.03,
                 "basis": "endpoint placement"},
                {"name": "fit", "sigma_contribution": 0.04,
                 "basis": "parabola residuals"},
                {"name": "point_vs_com", "sigma_contribution": 0.05,
                 "basis": "point versus centre"}],
            "sigma_relative": 0.2},
        "camera": {"still": {
            "reference_phrase": "distant rock",
            "reference_track_artifact": "workspace/ref_static.json"}},
        "provenance": {"artifacts": [
            {"name": "view", "path": "artifacts/view_0.jpg"},
            {"name": "segment masks", "path": "artifacts/ref_b.npz"},
            {"name": "mask check", "path": "artifacts/check_b.json"},
            {"name": "track", "path": "workspace/track_hop_a.json"},
            {"name": "reference track",
             "path": "workspace/ref_static.json"}]},
        "page_texts": {},
    }
    # --- part 07 §23: every measured line carries an agreeing
    # ``check_line`` record (part 11 §50 ``REFERENCE_LINE_NOT_CONFIRMED``).
    # One file per measured line — each reference's ``extent_px`` plus
    # the scale's ``extent_px`` — in the shape ``check_line`` writes
    # (§§20/22): ``frame`` plus a single line with the extent's exact
    # endpoints, a claim naming the dimension, ``description``/``view``/
    # ``dimension: "height"``, ``agrees: true`` and ``why``. The same
    # record is appended to ``artifacts/line_checks.jsonl`` so both
    # part-11 loaders (the journal and the ``t*_check_line_*.json``
    # glob) see it. Extra agreeing records never hurt a validator
    # without §50: its line rule only judges lines that have a record.
    _write_agreeing_line_checks(run_dir, evidence, produced)
    (run_dir / "workspace" / "produced_files.json").write_text(
        json.dumps(sorted(set(produced)), indent=2) + "\n",
        encoding="utf-8")
    return run_dir, evidence


def _write_agreeing_line_checks(run_dir, evidence, produced):
    """Write one agreeing ``check_line`` record per measured line.

    Covers each reference's ``extent_px`` and the scale's
    ``extent_px`` (the ``check_scale`` line when it carries its own
    extent endpoints, read defensively). Each record matches
    ``src.tools.check_line`` exactly: ``frame``, ``lines`` with one
    entry, ``overlay_artifact``, ``turn`` and both blind questions.
    """
    from src.tools.check_line import (
        BLIND_LOOK_QUESTION,
        MATCH_QUESTION,
    )

    targets = []
    for pos, ref in enumerate(evidence.get("references", [])):
        if not isinstance(ref, dict):
            continue
        extent = ref.get("extent_px")
        if not isinstance(extent, dict):
            continue
        name = ref.get("name")
        label = name.strip() if isinstance(name, str) and name.strip() \
            else f"references[{pos}]"
        targets.append((label, extent))
    scale = evidence.get("scale")
    if isinstance(scale, dict):
        extent = scale.get("extent_px")
        if isinstance(extent, dict):
            targets.append(("the scale", extent))
        check = scale.get("check_scale")
        if isinstance(check, dict) and all(
                key in check for key in ("x1", "y1", "x2", "y2",
                                         "frame")):
            targets.append(("the check scale", check))
    journal_rel = "artifacts/line_checks.jsonl"
    for index, (label, extent) in enumerate(targets):
        turn = index + 1
        frame = int(extent["frame"])
        line = {"x1": float(extent["x1"]), "y1": float(extent["y1"]),
                "x2": float(extent["x2"]), "y2": float(extent["y2"]),
                "claim": f"height of the {label}",
                "description": (
                    f"the line runs from the top of the {label} "
                    f"to the bottom of the {label} along its height"),
                "view": "front", "dimension": "height",
                "agrees": True,
                "why": ("the description runs along the object's "
                        "height, matching the claim")}
        record = {"frame": frame, "lines": [line],
                  "overlay_artifact": "artifacts/view_0.jpg",
                  "turn": turn,
                  "blind_question": BLIND_LOOK_QUESTION,
                  "match_question": MATCH_QUESTION}
        record_rel = f"artifacts/t{turn}_check_line_0.json"
        (run_dir / record_rel).write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8")
        produced.append(record_rel)
        with (run_dir / journal_rel).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    if targets:
        produced.append(journal_rel)


def test_default_validator_dry_run_single_reference_push(tmp_path):
    run_dir, evidence = _make_default_valid_run(tmp_path, n_refs=1)
    out = submit.submit(str(run_dir), 0, evidence, dry_run=True)
    assert not out["ok"], out
    codes = [e["code"] for e in out["metrics"]["errors"]]
    assert "SECOND_REFERENCE_REQUIRED" in codes
    assert "SECOND_REFERENCE_REQUIRED" in out["summary"]
    assert "references" in out["summary"]
    assert not (run_dir / "result.json").exists(), \
        "a dry run never writes result.json"


def test_default_validator_real_submit_single_reference_accepted(tmp_path):
    run_dir, evidence = _make_default_valid_run(tmp_path, n_refs=1)
    out = submit.submit(str(run_dir), 1, evidence, dry_run=False)
    assert out["ok"], out["metrics"]
    assert out["metrics"]["accepted"] is True
    assert (run_dir / "result.json").is_file(), \
        "a real submit writes result.json"


def test_default_validator_dry_run_clean_writes_nothing(tmp_path):
    run_dir, evidence = _make_default_valid_run(tmp_path, n_refs=2)
    out = submit.submit(str(run_dir), 2, evidence, dry_run=True)
    assert out["ok"], out
    assert out["metrics"]["accepted"] is True
    assert out["metrics"]["errors"] == []
    assert not (run_dir / "result.json").exists(), \
        "an accepted dry run still writes no result.json"
    assert not (run_dir / "workspace" / "submission.json").exists(), \
        "a dry run writes no submission"


# --- part 07 §23: accepted test evidence carries line checks --------
#
# Part 11 §50 refuses a reference whose line has no agreeing
# ``check_line`` record (``REFERENCE_LINE_NOT_CONFIRMED``). The
# helper above must therefore write one agreeing record per measured
# line, and the two acceptance tests above must keep passing both
# with a validator that enforces §50 and with one that does not
# (the current default validator).


def _stub_reference_line_validator(evidence, run_context, dry_run=False):
    """A §50-shaped validator: every reference/scale line confirmed.

    Mirrors brief 11 §50: each reference's ``extent_px`` and the
    scale's ``extent_px`` need a ``check_line`` record of this run on
    the same frame with both endpoints within 2 px, ``agrees`` true
    and ``dimension`` other than ``"unclear"``. Returns
    ``REFERENCE_LINE_NOT_CONFIRMED`` per missing line, else accepts.
    """
    import math
    from pathlib import Path

    def _coords(extent):
        try:
            return ((float(extent["x1"]), float(extent["y1"])),
                    (float(extent["x2"]), float(extent["y2"]))), \
                int(extent["frame"])
        except (KeyError, TypeError, ValueError):
            return None, None

    entries = []
    try:
        text = (Path(str(run_context.get("run_dir", ".")))
                / "artifacts" / "line_checks.jsonl").read_text(
                    encoding="utf-8")
    except OSError:
        text = ""
    for raw in text.splitlines():
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        for item in record.get("lines", []) or []:
            if isinstance(item, dict):
                entries.append((record.get("frame"), item))

    def _close(first, second, tol=2.0):
        try:
            gap = math.hypot(float(first[0]) - float(second[0]),
                             float(first[1]) - float(second[1]))
        except (TypeError, ValueError):
            return False
        return gap <= tol + 1e-9

    def _matches(item, coords):
        try:
            ends = ((float(item["x1"]), float(item["y1"])),
                    (float(item["x2"]), float(item["y2"])))
        except (KeyError, TypeError, ValueError):
            return False
        # ``coords`` is the evidence line, ``ends`` the record; either
        # direction matches.
        first, second = coords
        return ((_close(first, ends[0]) and _close(second, ends[1]))
                or (_close(first, ends[1]) and _close(second, ends[0])))

    wanted = []
    for pos, ref in enumerate(evidence.get("references", [])):
        if isinstance(ref, dict):
            wanted.append((f"references[{pos}].extent_px",
                           ref.get("extent_px")))
    scale = evidence.get("scale")
    if isinstance(scale, dict):
        wanted.append(("scale.extent_px", scale.get("extent_px")))
    errors = []
    for field, extent in wanted:
        coords, frame = _coords(extent) if isinstance(
            extent, dict) else (None, None)
        if coords is None:
            continue
        hits = []
        for rec_frame, item in entries:
            try:
                if int(rec_frame) != frame:
                    continue
            except (TypeError, ValueError):
                continue
            if _matches(item, coords):
                hits.append(item)
        good = [item for item in hits
                if item.get("agrees") is True
                and isinstance(item.get("dimension"), str)
                and item.get("dimension", "").strip()
                and item.get("dimension").strip() != "unclear"]
        if not good:
            errors.append({
                "code": "REFERENCE_LINE_NOT_CONFIRMED",
                "field": field,
                "detail": (
                    f"{field} on frame {frame} has no agreeing "
                    f"check_line record: run check_line on this line "
                    f"with a claim that names its dimension, for "
                    f"example 'height of the thing' (R-S17)")})
    if errors:
        return {"accepted": False, "errors": errors}
    return {"accepted": True, "errors": [],
            "result": {"ok": True}, "result_path": None}


def test_default_valid_run_writes_agreeing_line_checks(tmp_path):
    run_dir, evidence = _make_default_valid_run(tmp_path, n_refs=2)
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    assert journal.is_file(), \
        "the helper writes artifacts/line_checks.jsonl"
    rows = [line for line in journal.read_text(encoding="utf-8"
                                               ).splitlines()
            if line.strip()]
    assert rows, "the journal holds at least one record"
    import glob as _glob

    files = sorted(_glob.glob(str(run_dir / "artifacts"
                                  / "t*_check_line_*.json")))
    assert files, "one check_line file per measured line"
    # Every measured line — each reference plus the scale — has an
    # agreeing record with the §20/§22 shape.
    wanted = [ref["extent_px"] for ref in evidence["references"]]
    wanted.append(evidence["scale"]["extent_px"])
    for extent in wanted:
        frame = int(extent["frame"])
        hit = False
        for raw in rows:
            record = json.loads(raw)
            assert isinstance(record.get("frame"), int)
            assert isinstance(record.get("lines"), list)
            if int(record["frame"]) != frame:
                continue
            for item in record["lines"]:
                if (float(item["x1"]) == float(extent["x1"])
                        and float(item["y1"]) == float(extent["y1"])
                        and float(item["x2"]) == float(extent["x2"])
                        and float(item["y2"]) == float(extent["y2"])
                        and item.get("agrees") is True
                        and item.get("dimension") == "height"
                        and isinstance(item.get("view"), str)
                        and item["view"].strip()
                        and "height" in item["claim"]):
                    hit = True
        assert hit, f"no agreeing line check for {extent!r}"
    out = submit.submit(str(run_dir), 7, evidence,
                        validator=_stub_reference_line_validator,
                        dry_run=True)
    assert out["ok"], out


def test_default_valid_run_passes_line_enforcing_validator(tmp_path):
    for n_refs in (1, 2):
        run_dir, evidence = _make_default_valid_run(
            tmp_path / f"enforcing_{n_refs}", n_refs=n_refs)
        out = submit.submit(str(run_dir), 0, evidence,
                            validator=_stub_reference_line_validator,
                            dry_run=True)
        assert out["ok"], \
            f"n_refs={n_refs} passes a §50 validator: {out}"

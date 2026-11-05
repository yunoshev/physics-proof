# generated from brief/11 · part 11 owns this file
"""A measured line is not hidden, a flight follows one parabola, a
refused value is named (brief §45)."""

import copy
import json
import math

LINE_FRAME = 210
LINE_ENDS = (105.0, 60.0, 117.0, 189.0)
LINE_PX = int(math.hypot(LINE_ENDS[2] - LINE_ENDS[0],
                         LINE_ENDS[3] - LINE_ENDS[1]))
LINE_CLAIM = "height of the suited figure from helmet to boot"

REF_ENDS = (102.0, 60.0, 92.0, 128.0)


def _write_line_check(run_dir, ctx, produced, agrees=True, turn=54):
    record = {
        "frame": LINE_FRAME,
        "lines": [{"x1": LINE_ENDS[0], "y1": LINE_ENDS[1],
                   "x2": LINE_ENDS[2], "y2": LINE_ENDS[3],
                   "claim": LINE_CLAIM,
                   "description": "a vertical line over the figure",
                   "agrees": agrees,
                   "why": "it spans the figure" if agrees else "it misses"}],
        "overlay_artifact": f"artifacts/t{turn}_check_line_0.png",
        "turn": turn}
    rel = f"artifacts/t{turn}_check_line_0.json"
    (run_dir / rel).write_text(json.dumps(record), encoding="utf-8")
    produced.append(rel)
    ctx["artifacts"] = sorted(set(ctx["artifacts"]) | {rel})
    ctx["produced_files"] = sorted(set(ctx["produced_files"]) | {rel})
    return rel


def _one_reference_evidence(evidence):
    evidence = copy.deepcopy(evidence)
    ref = copy.deepcopy(evidence["references"][0])
    length = math.hypot(REF_ENDS[2] - REF_ENDS[0],
                        REF_ENDS[3] - REF_ENDS[1])
    ref["extent_px"] = {"x1": REF_ENDS[0], "y1": REF_ENDS[1],
                        "x2": REF_ENDS[2], "y2": REF_ENDS[3],
                        "length_px": length, "frame": LINE_FRAME}
    evidence["references"] = [ref]
    evidence["scale"]["frame"] = LINE_FRAME
    evidence["scale"]["extent_px"] = dict(ref["extent_px"])
    evidence["scale"]["reference_index"] = 0
    evidence["scale"]["second_reference_index"] = None
    evidence["scale"]["second_reference_absent_reason"] = (
        "only one thing of known size at the depth of the motion")
    return evidence


def test_hidden_confirmed_line_refused(baseline, tmp_path):
    """One reference plus an unreported confirmed line is refused."""
    from src.validate import validate

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    evidence = _one_reference_evidence(evidence)
    _write_line_check(run_dir, ctx, produced, agrees=True)
    report = validate(evidence, ctx, dry_run=True)
    assert report["accepted"] is False
    dropped = [e for e in report["errors"]
               if e.get("code") == "REFERENCE_DROPPED"]
    assert dropped, report["errors"]
    detail = dropped[0]["detail"]
    assert "210" in detail, detail
    assert f"{LINE_PX} px" in detail, detail
    assert LINE_CLAIM in detail, detail


def test_hidden_line_disagreeing_record_passes(baseline, tmp_path):
    """A line the second look rejected is not a measured reference."""
    from src.validate import validate

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    evidence = _one_reference_evidence(evidence)
    _write_line_check(run_dir, ctx, produced, agrees=False)
    report = validate(evidence, ctx, dry_run=True)
    assert not [e for e in report["errors"]
                if e.get("code") == "REFERENCE_DROPPED"], report["errors"]


def test_hidden_line_reported_by_second_reference(baseline, tmp_path):
    """The confirmed line added as the second reference is reported."""
    from src.validate import validate

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    evidence = _one_reference_evidence(evidence)
    _write_line_check(run_dir, ctx, produced, agrees=True)
    second = copy.deepcopy(evidence["references"][0])
    second["name"] = "suited figure height"
    second["extent_px"] = {"x1": LINE_ENDS[0], "y1": LINE_ENDS[1],
                           "x2": LINE_ENDS[2], "y2": LINE_ENDS[3],
                           "length_px": LINE_PX, "frame": LINE_FRAME}
    evidence["references"].append(second)
    evidence["scale"]["second_reference_index"] = 1
    evidence["scale"]["second_reference_absent_reason"] = None
    report = validate(evidence, ctx, dry_run=True)
    assert not [e for e in report["errors"]
                if e.get("code") == "REFERENCE_DROPPED"], report["errors"]


def test_hidden_line_reported_by_matching_extent(baseline, tmp_path):
    """A confirmed line the evidence sits on needs no second reference."""
    from src.validate import validate

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    evidence = _one_reference_evidence(evidence)
    evidence["references"][0]["extent_px"] = {
        "x1": LINE_ENDS[0], "y1": LINE_ENDS[1],
        "x2": LINE_ENDS[2], "y2": LINE_ENDS[3],
        "length_px": LINE_PX, "frame": LINE_FRAME}
    evidence["scale"]["extent_px"] = dict(
        evidence["references"][0]["extent_px"])
    _write_line_check(run_dir, ctx, produced, agrees=True)
    report = validate(evidence, ctx, dry_run=True)
    assert not [e for e in report["errors"]
                if e.get("code") == "REFERENCE_DROPPED"], report["errors"]


# --- a candidate flight follows one parabola -------------------------------

FLIGHTS = [("hop_a", 47, 85), ("hop_b", 120, 150), ("hop_c", 200, 230)]


def _flight_masks(wobble_first=True):
    """Whole-clip masks with three humps; the first wobbles in height.

    Bottoms ride smooth parabolas (one recomputed run each); the
    first hump alternates box height 60/100 so its centroid track
    fits no parabola, the others keep a steady height.
    """
    import numpy as np

    shape = (240, 352)
    per_frame = {}
    for frame in range(300):
        per_frame[frame] = [(100, 150, 160, 210)]

    def _hump(frames, mid, half, rise, wobble):
        for frame in frames:
            unit = (frame - mid) / half
            bottom = int(round(160 - rise * (1 - unit * unit)))
            if wobble and frame % 2:
                height = 100
            else:
                height = 60
            per_frame[frame] = [(bottom - height, 150, bottom, 210)]

    _hump(range(47, 86), 66, 19, 40, wobble_first)
    _hump(range(120, 151), 135, 15, 60, False)
    _hump(range(200, 231), 215, 15, 60, False)
    masks = {}
    for frame, boxes in per_frame.items():
        canvas = np.zeros(shape, dtype=bool)
        for r0, c0, r1, c1 in boxes:
            canvas[r0:r1, c0:c1] = True
        masks[frame] = canvas
    return masks


def _parabola_rows(start, end, level_y=200.0, x_px=100.0,
                   g=1.62, scale=0.01, fps=30.0):
    airtime = (end - start) / fps
    vy = g * airtime / 2.0
    rows = []
    for frame in range(start, end + 1):
        moment = (frame - start) / fps
        y_m = vy * moment - 0.5 * g * moment * moment
        rows.append({"frame": frame, "x_px": x_px,
                     "y_px": level_y - y_m / scale})
    return rows


def _three_flight_evidence(evidence, run_dir, produced):
    from src.helpers.masks_io import save_masks

    evidence = copy.deepcopy(evidence)
    save_masks(str(run_dir / "artifacts" / "masks_all.npz"),
               {"0": _flight_masks()})
    rel_track = {}
    segments = []
    motions = []
    candidates = []
    for pos, (seg_id, start, end) in enumerate(FLIGHTS):
        rows = _parabola_rows(start, end)
        rel = f"workspace/track_{seg_id}.json"
        (run_dir / rel).write_text(json.dumps(rows), encoding="utf-8")
        produced.append(rel)
        rel_track[seg_id] = rows
        mid = (start + end) // 2
        segments.append({
            "id": seg_id, "label": f"Jump {pos + 1}",
            "kind": "free_flight",
            "mask": {"artifact": "artifacts/ref_b.npz",
                     "object_id": "0"},
            "frames": {"start": start, "apex": mid, "end": end},
            "key_moments": [
                {"type": "takeoff", "frame": start,
                 "caption": "leaving the ground"},
                {"type": "apex", "frame": mid,
                 "caption": "hanging at the top"},
                {"type": "landing", "frame": end,
                 "caption": "touching down softly"}],
            "track_artifact": rel,
            "tracked_point": "top of the helmet",
            "fit_curve_px": [
                {"t_s": r["frame"] / 30.0, "x_px": r["x_px"],
                 "y_px": r["y_px"]} for r in rows],
            "repetitions": []})
        motions.append(
            {"frame_start": start, "frame_end": end,
             "description": f"hop {pos + 1}", "segment_id": seg_id,
             "skip_reason": None})
        candidates.append(
            {"id": f"cand_{pos + 1}", "frame_start": start,
             "frame_end": end, "airtime_s": (end - start) / 30.0,
             "peak_rise_px": 60.0, "decision": "measured",
             "segment_id": seg_id, "reason": None})
    evidence["segments"] = segments
    evidence["first_look"]["motions"] = motions
    evidence["first_look"]["overview"]["candidates"] = candidates
    evidence["first_look"]["overview"]["first_check"] = {
        "segment_id": "hop_a", "why": "longest clear flight"}
    return evidence


def test_measured_non_parabolic_flight_refused(baseline, tmp_path):
    """A measured candidate below R² 0.8 names itself and its R²."""
    from src.validate import validate
    from src.validate.validate import _overview_runs_with_r2

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    evidence = _three_flight_evidence(evidence, run_dir, produced)
    ctx["artifacts"] = sorted(set(ctx["artifacts"]) | set(produced))
    ctx["produced_files"] = sorted(set(ctx["produced_files"])
                                   | set(produced))
    _span, runs = _overview_runs_with_r2(
        "artifacts/masks_all.npz", "0", ctx)
    assert runs is not None and len(runs) == 3, runs
    assert runs[0][2] < 0.8, runs
    assert runs[1][2] >= 0.8 and runs[2][2] >= 0.8, runs
    report = validate(evidence, ctx, dry_run=True)
    assert report["accepted"] is False
    bad = [e for e in report["errors"]
           if e.get("code") == "FLIGHT_NOT_PARABOLIC"]
    assert len(bad) == 1, report["errors"]
    assert "F1" in bad[0]["detail"], bad[0]["detail"]
    assert "r²" in bad[0]["detail"], bad[0]["detail"]
    assert f"{runs[0][2]:.2f}" in bad[0]["detail"], bad[0]["detail"]


def test_non_parabolic_flight_decided_otherwise(baseline, tmp_path):
    """The wobbling candidate decided not_a_flight is no error."""
    from src.validate import validate

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    evidence = _three_flight_evidence(evidence, run_dir, produced)
    evidence["segments"] = [s for s in evidence["segments"]
                            if s["id"] != "hop_a"]
    evidence["first_look"]["motions"][0] = {
        "frame_start": 47, "frame_end": 85, "description": "first hop",
        "segment_id": None,
        "skip_reason": "mixed phases, not one stretch of flight"}
    evidence["first_look"]["overview"]["candidates"][0] = {
        "id": "cand_1", "frame_start": 47, "frame_end": 85,
        "airtime_s": 38 / 30.0, "peak_rise_px": 40.0,
        "decision": "not_a_flight", "segment_id": None,
        "reason": "mixed phases, not one stretch of flight"}
    evidence["first_look"]["overview"]["first_check"] = {
        "segment_id": "hop_b", "why": "cleanest flight"}
    ctx["artifacts"] = sorted(set(ctx["artifacts"]) | set(produced))
    ctx["produced_files"] = sorted(set(ctx["produced_files"])
                                   | set(produced))
    report = validate(evidence, ctx, dry_run=True)
    assert not [e for e in report["errors"]
                if e.get("code") == "FLIGHT_NOT_PARABOLIC"], (
        report["errors"])
    # Only dry-run pushes remain (the references sit far from the
    # later first check); nothing blocks acceptance.
    assert all(e.get("push") for e in report["errors"]), report["errors"]


# --- a value that matches no branch is named --------------------------------


def test_unknown_decision_names_allowed_values(baseline, tmp_path):
    """A decision no branch accepts lists the allowed decisions."""
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    evidence["first_look"]["overview"]["candidates"][0] = {
        "id": "cand_1", "frame_start": 30, "frame_end": 60,
        "airtime_s": 1.0, "peak_rise_px": 60.0,
        "decision": "not a free flight", "segment_id": None,
        "reason": "walking step"}
    report = validate(evidence, ctx, dry_run=True)
    assert report["accepted"] is False
    named = [e for e in report["errors"]
             if "candidates[0]" in e.get("field", "")]
    assert named, report["errors"]
    assert any("allowed: measured, not_a_flight, not_measurable"
               in e["detail"] for e in named), named
    assert all("segment_id" not in e["detail"] for e in named), named


def test_named_branch_reports_its_own_problems(baseline, tmp_path):
    """A named decision shows that branch's errors, not another's."""
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    evidence["first_look"]["overview"]["candidates"][0] = {
        "id": "cand_1", "frame_start": 30, "frame_end": 60,
        "airtime_s": 1.0, "peak_rise_px": 60.0,
        "decision": "not_a_flight", "segment_id": "hop_a",
        "reason": "walking step"}
    report = validate(evidence, ctx, dry_run=True)
    assert report["accepted"] is False
    named = [e for e in report["errors"]
             if "candidates[0]" in e.get("field", "")]
    assert named, report["errors"]
    assert any("segment_id" in e["detail"] and "null" in e["detail"]
               for e in named), named

# generated from brief/11 · part 11 owns this file
"""Every listed motion is measured or explained (brief §14)."""

import copy


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def test_motion_naming_missing_segment(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    # Names a segment the evidence does not contain, and leaves the
    # real segment unlisted: schema-valid, but unmeasured.
    bad["first_look"]["motions"] = [
        {"frame_start": 0, "frame_end": 10, "description": "hop",
         "segment_id": "hop_missing", "skip_reason": None}]
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "MOTION_NOT_MEASURED"
               for e in report["errors"]), report["errors"]


def test_motion_entry_listed_twice(baseline, tmp_path):
    import json as _json

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    (run_dir / "workspace" / "track_hop_b.json").write_text(
        _json.dumps(rows), encoding="utf-8")
    produced.append("workspace/track_hop_b.json")
    bad = copy.deepcopy(evidence)
    second = copy.deepcopy(bad["segments"][0])
    second["id"] = "hop_b"
    bad["segments"].append(second)
    bad["first_look"]["overview"]["candidates"].append(
        {"id": "cand_2", "frame_start": 30, "frame_end": 60,
         "airtime_s": 1.0, "peak_rise_px": 60.0,
         "decision": "measured", "segment_id": "hop_b",
         "reason": None})
    bad["first_look"]["motions"] = [
        {"frame_start": 30, "frame_end": 60,
         "description": "foreground hop", "segment_id": "hop_a",
         "skip_reason": None},
        {"frame_start": 30, "frame_end": 60,
         "description": "foreground hop again",
         "segment_id": "hop_a", "skip_reason": None}]
    ctx = dict(ctx, produced_files=list(produced))
    report = _validate(bad, ctx)
    assert report["accepted"] is False
    assert any(e["code"] == "MOTION_NOT_MEASURED"
               for e in report["errors"]), report["errors"]


def test_two_segments_spread_stays_world(baseline, tmp_path):
    import json as _json

    from src.contract import validate_result

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    # A second hop at g = 1.70 (5% σ each): the spread is priced by
    # code, and the Moon still fits natively.
    rows_b = copy.deepcopy(rows)
    for row in rows_b:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * (1.70 / 1.62)
    (run_dir / "workspace" / "track_hop_b.json").write_text(
        _json.dumps(rows_b), encoding="utf-8")
    produced.append("workspace/track_hop_b.json")
    good = copy.deepcopy(evidence)
    second = copy.deepcopy(good["segments"][0])
    second["id"] = "hop_b"
    second["label"] = "Jump two"
    second["track_artifact"] = "workspace/track_hop_b.json"
    second["fit_curve_px"] = [
        {"t_s": r["frame"] / 30.0, "x_px": r["x_px"],
         "y_px": r["y_px"]} for r in rows_b]
    good["segments"].append(second)
    good["first_look"]["overview"]["candidates"].append(
        {"id": "cand_2", "frame_start": 30, "frame_end": 60,
         "airtime_s": 1.0, "peak_rise_px": 60.0,
         "decision": "measured", "segment_id": "hop_b",
         "reason": None})
    good["first_look"]["motions"] = [
        {"frame_start": 30, "frame_end": 60,
         "description": "first hop", "segment_id": "hop_a",
         "skip_reason": None},
        {"frame_start": 90, "frame_end": 120,
         "description": "second hop", "segment_id": "hop_b",
         "skip_reason": None}]
    for comp in good["error_budget"]["components"]:
        if comp["name"] in ("fit", "point_vs_com"):
            comp["sigma_contribution"] = 0.08
    ctx = dict(ctx, produced_files=list(produced))
    full = _validate(good, ctx)
    assert full["accepted"] is True, full["errors"]
    assert validate_result(full["result"]) == []
    assert full["result"]["verdict"]["world"] == "Moon"
    comps = {c["name"]: c["sigma_contribution"]
             for c in full["result"]["error_budget"]["components"]}
    assert "repetition_spread" in comps
    assert comps["repetition_spread"] > 0

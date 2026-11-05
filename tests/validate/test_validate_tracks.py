# generated from brief/11 · part 11 owns this file
"""Tracks, cuts, duplicates and the fit-curve check (V2/V6/V7)."""

import copy
import json


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def test_single_parabola_passes_trend(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True, report["errors"]


def test_clean_parabola_passes(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    evidence = copy.deepcopy(evidence)
    # A reference on the moving thing, or the dry run lists the
    # SELF_REFERENCE_REQUIRED push (brief §53, R-S16).
    evidence["references"][1]["mask"] = {
        "artifact": "artifacts/masks_all.npz", "object_id": "0",
        "frame": 10,
        "outline": [[100.0, 20.0], [271.0, 20.0],
                    [271.0, 191.0], [100.0, 191.0]]}
    report = _validate(evidence, dict(ctx), dry_run=True)
    assert report["errors"] == [], report["errors"]


def _retime(run_dir, ctx, start, end):
    timing = dict(ctx["timing"])
    timing["timestamps"] = [i / 30.0 for i in range(300)]
    return dict(ctx, timing=timing)


def test_cut_crossing_rejected(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    timing_path = run_dir / "input" / "timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    timing["cuts"] = [{"frame_start": 40, "frame_end": 45}]
    timing_path.write_text(json.dumps(timing), encoding="utf-8")
    ctx = dict(ctx, timing=timing)
    report = _validate(copy.deepcopy(evidence), ctx)
    assert report["accepted"] is False
    assert any(e["code"] == "FIT_INCLUDES_CONTACT_OR_DUP"
               and e["field"] == "segments[0].track_artifact"
               for e in report["errors"])


def test_duplicate_frames_rejected(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    timing_path = run_dir / "input" / "timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    timing["confirmed_duplicates"] = [44, 45, 46]
    timing_path.write_text(json.dumps(timing), encoding="utf-8")
    ctx = dict(ctx, timing=timing)
    report = _validate(copy.deepcopy(evidence), ctx)
    assert report["accepted"] is False
    assert any(e["code"] == "FIT_INCLUDES_CONTACT_OR_DUP"
               for e in report["errors"])


def test_invented_curve_sample_rejected_with_ts(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    curve = bad["segments"][0]["fit_curve_px"]
    victim = curve[10]
    victim["y_px"] = victim["y_px"] + 6.0
    victim_ts = victim["t_s"]
    report = _validate(bad, ctx)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "NUMBER_WITHOUT_PROVENANCE"
               and e["field"] == "segments[0].fit_curve_px"]
    assert matches, report["errors"]
    assert any(str(victim_ts)[:6] in e["detail"]
               for e in matches), matches


def test_short_curve_rejected(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["segments"][0]["fit_curve_px"] = \
        bad["segments"][0]["fit_curve_px"][:3]
    report = _validate(bad, ctx)
    assert report["accepted"] is False
    assert any(e["code"] == "NUMBER_WITHOUT_PROVENANCE"
               and "4" in e["detail"] for e in report["errors"])


def test_three_phase_track_rejected(baseline, tmp_path):
    import numpy as np

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    # Level, then a turn, then a parabola: not one stretch of
    # constant acceleration (wall run 2 shape).
    rows = []
    y = 200.0
    for frame in range(55, 181):
        if frame < 100:
            y = 200.0
        elif frame < 130:
            y = 200.0 - 0.5 * (frame - 100)
        else:
            k = frame - 130
            y = 185.0 - 0.8 * k + 0.02 * k * k
        rows.append({"frame": frame, "x_px": 100.0, "y_px": y})
    track = run_dir / "workspace" / "track_hop_a.json"
    track.write_text(json.dumps(rows), encoding="utf-8")
    bad = copy.deepcopy(evidence)
    bad["segments"][0]["frames"] = {"start": 55, "apex": 120,
                                    "end": 180}
    bad["segments"][0]["key_moments"] = [
        {"type": "takeoff", "frame": 55, "caption": "starting out"},
        {"type": "apex", "frame": 120, "caption": "halfway along"},
        {"type": "landing", "frame": 180, "caption": "coming to rest"}]
    bad["segments"][0]["fit_curve_px"] = [
        {"t_s": r["frame"] / 30.0, "x_px": r["x_px"],
         "y_px": r["y_px"]} for r in rows]
    bad["first_look"]["motions"] = [
        {"frame_start": 55, "frame_end": 180,
         "description": "wall run", "segment_id": "hop_a",
         "skip_reason": None}]
    report = _validate(bad, ctx)
    assert report["accepted"] is False
    assert any(e["code"] == "RESIDUAL_TREND" for e in
               report["errors"]), report["errors"]
    assert "fit one phase" in " ".join(
        e["detail"] for e in report["errors"])
    del np

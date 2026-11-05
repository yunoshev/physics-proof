# generated from brief/11 · part 11 owns this file
"""Camera detail names the fix; a flight inside a longer candidate is
judged on its own frames (brief §55)."""

import copy
import json
import random


def _sloped_masks(noisy_mid=False):
    """Level run-up/run-out with a parabola (or noisy level) in the middle.

    Bottoms slope 160→140 over frames 0–29, ride a parabola 140→80→140
    over frames 30–60 (or a level noisy band at 140 when ``noisy_mid``),
    then slope back 140→160 over frames 61–90; every other frame rests
    at ground (bottom 160). The recomputed overview merges frames 4–86
    into one run with R² below 0.8, while the middle on its own is a
    clean parabola (or noise).
    """
    shape = (240, 352)
    per_frame = {}
    for frame in range(300):
        per_frame[frame] = [(100, 150, 160, 210)]
    for frame in range(0, 30):
        bottom = int(round(160 - 20 * (frame / 29.0)))
        per_frame[frame] = [(bottom - 60, 150, bottom, 210)]
    rng = random.Random(7)
    for frame in range(30, 61):
        if noisy_mid:
            bottom = 140
            height = 60 + rng.uniform(-20, 20)
            per_frame[frame] = [(int(bottom - height), 150, bottom, 210)]
        else:
            unit = (frame - 45) / 15.0
            bottom = int(round(140 - 60 * (1 - unit * unit)))
            per_frame[frame] = [(bottom - 60, 150, bottom, 210)]
    for frame in range(61, 91):
        bottom = int(round(140 + 20 * ((frame - 61) / 29.0)))
        per_frame[frame] = [(bottom - 60, 150, bottom, 210)]
    masks = {}
    import numpy as np  # noqa: PLC0415

    for frame, boxes in per_frame.items():
        canvas = np.zeros(shape, dtype=bool)
        for r0, c0, r1, c1 in boxes:
            canvas[r0:r1, c0:c1] = True
        masks[frame] = canvas
    return masks


def _retarget_candidate(evidence, run_dir, produced, noisy_mid=False):
    """Point the overview candidate at the recomputed merged run."""
    from src.helpers.masks_io import save_masks
    from src.validate.validate import _overview_runs_with_r2

    save_masks(str(run_dir / "artifacts" / "masks_all.npz"),
               {"0": _sloped_masks(noisy_mid=noisy_mid)})
    # Rebuild a minimal context for the recompute (masks only).
    import json as _json

    timing = _json.loads(
        (run_dir / "input" / "timing.json").read_text(encoding="utf-8"))
    artifacts = sorted(
        str(p.relative_to(run_dir)) for p in
        (run_dir / "artifacts").rglob("*") if p.is_file())
    ctx = {"run_dir": str(run_dir), "run_id": run_dir.name,
           "timing": timing, "artifacts": artifacts,
           "produced_files": list(produced), "mask_checks": []}
    _span, runs = _overview_runs_with_r2(
        "artifacts/masks_all.npz", "0", ctx)
    assert runs is not None and len(runs) == 1, runs
    start, end, r2 = runs[0]
    assert r2 < 0.8, runs
    evidence = copy.deepcopy(evidence)
    evidence["first_look"]["overview"]["candidates"] = [
        {"id": "cand_1", "frame_start": start, "frame_end": end,
         "airtime_s": (end - start) / 30.0, "peak_rise_px": 60.0,
         "decision": "measured", "segment_id": "hop_a",
         "reason": None}]
    return evidence, start, end, float(r2)


def test_camera_detail_names_relative_track(baseline, tmp_path):
    """A moving still-reference names the relative-track fix."""
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    rows = [{"frame": f, "x_px": 150.0 + (f - 30) * (24.0 / 30.0),
             "y_px": 150.0} for f in range(30, 61)]
    (run_dir / "workspace" / "ref_static.json").write_text(
        json.dumps(rows), encoding="utf-8")
    report = validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is False
    bad = [e for e in report["errors"]
           if e.get("code") == "CAMERA_UNACCOUNTED"]
    assert bad, report["errors"]
    detail = bad[0]["detail"]
    assert "relative_track_artifact" in detail, detail
    assert "helpers.tracks.relative_track" in detail, detail


def test_segment_inside_longer_candidate_passes(baseline, tmp_path):
    """A parabolic jump inside a merged run is no FLIGHT_NOT_PARABOLIC."""
    from src.validate import validate

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    evidence, _s, _e, _r = _retarget_candidate(
        evidence, run_dir, produced, noisy_mid=False)
    report = validate(evidence, ctx, dry_run=True)
    assert not [e for e in report["errors"]
                if e.get("code") == "FLIGHT_NOT_PARABOLIC"], (
        report["errors"])


def test_segment_covering_whole_run_fails_as_before(baseline, tmp_path):
    """A segment spanning the merged run is judged as before."""
    from src.validate import validate
    from tests.validate.conftest import fit_curve_for, parabola_track

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    evidence, start, end, _r = _retarget_candidate(
        evidence, run_dir, produced, noisy_mid=False)
    evidence = copy.deepcopy(evidence)
    rows = parabola_track(start, end)
    rel = "workspace/track_hop_a.json"
    (run_dir / rel).write_text(json.dumps(rows), encoding="utf-8")
    if rel not in produced:
        produced.append(rel)
    for seg in evidence["segments"]:
        if seg.get("id") == "hop_a":
            mid = (start + end) // 2
            seg["frames"] = {"start": start, "apex": mid, "end": end}
            seg["key_moments"] = [
                {"type": "takeoff", "frame": start,
                 "caption": "leaving the ground"},
                {"type": "apex", "frame": mid,
                 "caption": "hanging at the top"},
                {"type": "landing", "frame": end,
                 "caption": "touching down softly"}]
            seg["fit_curve_px"] = fit_curve_for(rows)
    evidence["first_look"]["motions"] = [
        {"frame_start": start, "frame_end": end,
         "description": "foreground hop", "segment_id": "hop_a",
         "skip_reason": None}]
    report = validate(evidence, ctx, dry_run=True)
    bad = [e for e in report["errors"]
           if e.get("code") == "FLIGHT_NOT_PARABOLIC"]
    assert bad, report["errors"]


def test_noisy_middle_names_segment_frames(baseline, tmp_path):
    """A noisy middle inside the merged run names frames 30–60."""
    from src.validate import validate

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    evidence, _s, _e, _r = _retarget_candidate(
        evidence, run_dir, produced, noisy_mid=True)
    report = validate(evidence, ctx, dry_run=True)
    bad = [e for e in report["errors"]
           if e.get("code") == "FLIGHT_NOT_PARABOLIC"]
    assert bad, report["errors"]
    assert "30-60" in bad[0]["detail"], bad[0]["detail"]

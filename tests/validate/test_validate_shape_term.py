# generated from brief/11 · part 11 owns this file
"""The point-versus-centre allowance is at least what the masks show (§57)."""

import copy
import re


def _parabola_top(frame, fps=30.0, scale=0.01, level=150.0):
    g = 1.62
    airtime = 1.0
    vy = g * airtime / 2.0
    moment = (frame - 30) / fps
    y_m = vy * moment - 0.5 * g * moment * moment
    return level - y_m / scale


def _write_constant_masks(run_dir, produced):
    """Uniform rectangle of constant size riding the hop (stable shape)."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    masks = {}
    for frame in range(30, 61):
        canvas = np.zeros((240, 352), dtype=bool)
        centre = int(round(_parabola_top(frame)))
        top = max(0, centre - 40)
        bottom = min(240, top + 80)
        canvas[top:bottom, 150:210] = True
        masks[frame] = canvas
    path = run_dir / "artifacts" / "seg_shape_const.npz"
    save_masks(str(path), {"0": masks})
    rel = "artifacts/seg_shape_const.npz"
    produced.append(rel)
    return rel


def _write_tucking_masks(run_dir, produced):
    """Legs tucking: wide upper block, narrow lower block shrinking.

    Total height 100 px at the ends, 50 px at the apex; the narrow
    lower part drives the centroid and the median row apart, so the
    two parabola fits give different g.
    """
    import numpy as np

    from src.helpers.masks_io import save_masks

    masks = {}
    for frame in range(30, 61):
        unit = (frame - 45) / 15.0
        height = int(round(100 - 50 * (1 - unit * unit)))
        canvas = np.zeros((240, 352), dtype=bool)
        centre = int(round(_parabola_top(frame)))
        top = max(0, centre - height // 2)
        bottom = min(240, top + height)
        upper = min(bottom, top + 30)
        canvas[top:upper, 150:210] = True
        if bottom > upper:
            canvas[upper:bottom, 170:190] = True
        masks[frame] = canvas
    path = run_dir / "artifacts" / "seg_shape_tuck.npz"
    save_masks(str(path), {"0": masks})
    rel = "artifacts/seg_shape_tuck.npz"
    produced.append(rel)
    return rel


def _set_point_vs_com(evidence, value):
    for comp in evidence["error_budget"]["components"]:
        if comp.get("name") == "point_vs_com":
            comp["sigma_contribution"] = float(value)


def _validate(evidence, ctx):
    from src.validate import validate

    return validate(evidence, ctx)


def _refresh_ctx(run_dir, produced):
    import json

    timing = json.loads(
        (run_dir / "input" / "timing.json").read_text(encoding="utf-8"))
    artifacts = sorted(
        str(p.relative_to(run_dir)) for p in
        (run_dir / "artifacts").rglob("*") if p.is_file())
    return {"run_dir": str(run_dir), "run_id": run_dir.name,
            "timing": timing, "artifacts": artifacts,
            "produced_files": list(produced), "mask_checks": []}


def test_constant_shape_passes(baseline, tmp_path):
    evidence, run_dir, _ctx, produced = baseline(tmp_path)
    rel = _write_constant_masks(run_dir, produced)
    good = copy.deepcopy(evidence)
    good["segments"][0]["mask"] = {"artifact": rel, "object_id": "0"}
    _set_point_vs_com(good, 0.08)
    ctx = _refresh_ctx(run_dir, produced)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]


def test_tucking_shape_pushes_budget(baseline, tmp_path):
    evidence, run_dir, _ctx, produced = baseline(tmp_path)
    rel = _write_tucking_masks(run_dir, produced)
    bad = copy.deepcopy(evidence)
    bad["segments"][0]["mask"] = {"artifact": rel, "object_id": "0"}
    _set_point_vs_com(bad, 0.08)
    ctx = _refresh_ctx(run_dir, produced)
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    shape = [e for e in report["errors"]
             if e["code"] == "ERROR_BUDGET_INCOMPLETE"
             and "shape term" in e["detail"]]
    assert shape, report["errors"]
    detail = shape[0]["detail"]
    assert "hop_a" in detail
    assert detail.count("g =") >= 2
    match = re.search(r"shape term ([\d.]+)", detail)
    assert match, detail
    term = float(match.group(1))
    assert term > 0.05 * 1.62, (term, detail)


def test_tucking_shape_equal_passes(baseline, tmp_path):
    evidence, run_dir, _ctx, produced = baseline(tmp_path)
    rel = _write_tucking_masks(run_dir, produced)
    bad = copy.deepcopy(evidence)
    bad["segments"][0]["mask"] = {"artifact": rel, "object_id": "0"}
    _set_point_vs_com(bad, 0.08)
    ctx = _refresh_ctx(run_dir, produced)
    first = _validate(bad, dict(ctx))
    shape = [e for e in first["errors"]
             if e["code"] == "ERROR_BUDGET_INCOMPLETE"
             and "shape term" in e["detail"]]
    assert shape, first["errors"]
    term = float(re.search(r"shape term ([\d.]+)",
                           shape[0]["detail"]).group(1))
    good = copy.deepcopy(bad)
    _set_point_vs_com(good, term)
    good["error_budget"]["sigma_relative"] = 1.0
    again = _validate(good, dict(ctx))
    left = [e for e in again["errors"]
            if e["code"] == "ERROR_BUDGET_INCOMPLETE"
            and "shape term" in e["detail"]]
    assert left == [], again["errors"]


def test_missing_segment_mask_is_missing_field(baseline, tmp_path):
    evidence, run_dir, _ctx, produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["segments"][0]["mask"] = {"artifact": "artifacts/gone.npz",
                                  "object_id": "0"}
    ctx = _refresh_ctx(run_dir, produced)
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "MISSING_FIELD"
               and e["field"] == "segments[0].mask"
               for e in report["errors"]), report["errors"]


def test_existing_fixtures_keep_results(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True, report["errors"]

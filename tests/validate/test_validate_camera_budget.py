# generated from brief/11 · part 11 owns this file
"""Camera accounting (V8) and the error budget (V9, §18)."""

import copy
import json
import math


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def test_relative_track_accepted(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["camera"] = {"relative_track_artifact":
                      "workspace/ref_static.json"}
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]


def test_moving_reference_rejected(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    rows = [{"frame": f, "x_px": 150.0 + (f - 30) * 0.5, "y_px": 150.0}
            for f in range(30, 61)]
    (run_dir / "workspace" / "ref_static.json").write_text(
        json.dumps(rows), encoding="utf-8")
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "CAMERA_UNACCOUNTED"
               for e in report["errors"]), report["errors"]


def test_missing_camera_track_is_missing_field(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["camera"]["still"]["reference_track_artifact"] = \
        "workspace/gone.json"
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "MISSING_FIELD"
               and e["field"] ==
               "camera.still.reference_track_artifact"
               for e in report["errors"]), report["errors"]


def test_missing_budget_component(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    for comp in bad["error_budget"]["components"]:
        if comp["name"] == "fit":
            comp["name"] = "projection"
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "ERROR_BUDGET_INCOMPLETE"
               and "fit" in e["detail"] for e in report["errors"])


def test_submitted_sigma_too_small(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["error_budget"]["sigma_relative"] = 0.001
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "ERROR_BUDGET_INCOMPLETE"
               for e in report["errors"])


def test_sigma_below_single_component(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    # Quadrature total is ~0.0866; 0.04 sits below the 0.05 pieces.
    bad["error_budget"]["sigma_relative"] = 0.04 / 1.62
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "ERROR_BUDGET_INCOMPLETE"
               for e in report["errors"])


def _quad(evidence):
    return math.sqrt(sum(
        c["sigma_contribution"] ** 2
        for c in evidence["error_budget"]["components"]))


def test_sigma_rounding_within_two_percent_passes(baseline, tmp_path):
    from src.contract import validate_result

    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    total = _quad(good)
    good["error_budget"]["sigma_relative"] = \
        (total * 0.996) / 1.62
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert validate_result(report["result"]) == []
    # The result carries the recomputed total, not the rounded one.
    assert report["result"]["error_budget"]["sigma_total"] == \
        report["result"]["error_budget"]["sigma_total"]
    assert abs(report["result"]["error_budget"]["sigma_total"]
               - total) < 1e-9


def test_sigma_beyond_two_percent_fails(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    total = _quad(bad)
    bad["error_budget"]["sigma_relative"] = (total * 0.95) / 1.62
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "ERROR_BUDGET_INCOMPLETE"
               for e in report["errors"])


def test_identical_repetitions_rejected(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["segments"][0]["repetitions"] = [
        {"frames": {"start": 32, "end": 45}, "g_app": 1.61,
         "sigma_g": 0.09},
        {"frames": {"start": 45, "end": 58}, "g_app": 1.61,
         "sigma_g": 0.09},
    ]
    # Price the repetitions so only the identical-residual rule fires.
    bad["error_budget"]["components"].append(
        {"name": "repetition_spread", "sigma_contribution": 0.02,
         "basis": "split-window spread"})
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "ERROR_BUDGET_INCOMPLETE"
               and "identical" in e["detail"] for e in
               report["errors"]), report["errors"]

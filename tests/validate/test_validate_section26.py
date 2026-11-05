# generated from brief/11 · part 11 owns this file
"""§26: every accepted shape assembles; a dropped reference counts."""

import copy
import json


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def test_wall9_clock_shape_fails_dry_run(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["clock"] = {
        "signal_description": "step rate from the gait signal",
        "measured_rate_hz": 4.8,
        "measured_rate_sigma_hz": 0.1,
        "interpretation": "step",
        "band_hz": [4.0, 6.0],
        "natural_range_hz": {"min": 4.6, "max": 5.0, "typical": 4.8},
        "natural_range_source": {
            "url": "https://example.com/gait",
            "quote": "preferred frequency is 4.6 to 5.0 Hz"},
    }
    bad["clock_absent_reason"] = None
    report = _validate(bad, dict(ctx), dry_run=True)
    assert report["accepted"] is False
    fields = [e["field"] for e in report["errors"]
              if isinstance(e, dict)]
    assert "clock.natural_range_hz" in fields, report["errors"]
    match = [e for e in report["errors"]
             if isinstance(e, dict)
             and e.get("field") == "clock.natural_range_hz"]
    assert match, report["errors"]
    assert ("clock.natural_range_hz must be [lo, hi] in Hz"
            in match[0].get("detail", "")), match[0]


def test_empty_segments_with_clock_assembles(baseline, tmp_path):
    from src.validate.validate import assemble_result, run_checks

    evidence, _run, ctx, _produced = baseline(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["segments"] = []
    # No motion measured, so no survey is carried either.
    evidence["first_look"].pop("overview", None)
    evidence["clock"] = {
        "signal_description": "width of the lowest thirty percent",
        "measured_rate_hz": 1.8,
        "measured_rate_sigma_hz": 0.05,
        "interpretation": "step",
        "band_hz": [0.5, 4.0],
        "natural_range_hz": [1.0, 2.0],
        "natural_range_source": {
            "url": "https://example.com/gait",
            "quote": "preferred frequency is 1 to 2 Hz"},
    }
    evidence["clock_absent_reason"] = None
    # Needs a measurement to be valid; the point here is assembly
    # never raises on schema-valid input, clock included.
    errors, computed = run_checks(evidence, dict(ctx), dry_run=True)
    assert not any(
        isinstance(e, dict)
        and e.get("field") == "clock.natural_range_hz"
        for e in errors), errors
    result = assemble_result(evidence, dict(ctx), computed)
    assert result["clock"] is not None
    assert result["clock"]["natural_range_hz"] == [1.0, 2.0]


def _two_ref_evidence(evidence):
    """Earlier evidence with two disagreeing references."""
    early = copy.deepcopy(evidence)
    assert len(early["references"]) >= 2
    first = early["references"][0]
    first["name"] = "crate height"
    first["size_m"] = 0.66
    first["size_tolerance_m"] = 0.02
    first["extent_px"] = {"x1": 20.0, "y1": 20.0, "x2": 20.0,
                          "y2": 88.0, "length_px": 68.0, "frame": 10}
    second = early["references"][1]
    second["name"] = "standing figure"
    second["size_m"] = 1.7
    second["size_tolerance_m"] = 0.02
    second["extent_px"] = {"x1": 100.0, "y1": 20.0, "x2": 100.0,
                           "y2": 164.0, "length_px": 144.0, "frame": 10}
    return early


def _write_earlier(run_dir, produced, evidence):
    import pathlib

    rel = "artifacts/t29_evidence.json"
    target = pathlib.Path(str(run_dir)) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence), encoding="utf-8")
    if rel not in produced:
        produced.append(rel)
    return rel


def test_dropped_reference_disagrees(baseline, tmp_path):
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    early = _two_ref_evidence(evidence)
    _write_earlier(run_dir, produced, early)
    ctx = dict(ctx, artifacts=sorted(
        {*ctx.get("artifacts", []), "artifacts/t29_evidence.json"}),
        produced_files=list(produced))
    final = copy.deepcopy(evidence)
    final["references"] = [copy.deepcopy(early["references"][0])]
    final["scale"]["second_reference_index"] = None
    final["scale"]["second_reference_absent_reason"] = (
        "only one thing of known size at the depth of the motion")
    report = _validate(final, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    reason = report["result"]["verdict"]["reason"] or ""
    assert "references disagree" in reason, reason
    assert "0.009706" in reason or "0.0097" in reason, reason
    assert "0.0118" in reason, reason
    # The dry run says so as a push before the real submit.
    dry = _validate(copy.deepcopy(final), dict(ctx), dry_run=True)
    assert dry["accepted"] is False, dry["errors"]
    pushes = [e for e in dry["errors"]
              if isinstance(e, dict) and e.get("push") is True]
    assert any("references disagree" in e.get("detail", "")
               for e in pushes), dry["errors"]


def test_dropped_reference_excused_by_absent_reason(baseline, tmp_path):
    import pathlib

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    early = _two_ref_evidence(evidence)
    # The blind check of the dropped reference records that its mask
    # covers something else.
    check_rel = "artifacts/check_dropped.json"
    (pathlib.Path(str(run_dir)) / check_rel).write_text(json.dumps(
        {"overlay_artifact": "artifacts/view_0.jpg",
         "coverage_answer": "covers the wall, something else entirely",
         "alternatives": [], "confidence": None, "turn": 1}),
        encoding="utf-8")
    produced.append(check_rel)
    early["references"][1]["mask_check"] = {
        "artifact": check_rel,
        "coverage_answer": "covers the wall, something else entirely",
        "confidence": None, "alternative_readings": []}
    _write_earlier(run_dir, produced, early)
    ctx = dict(ctx, artifacts=sorted(
        {*ctx.get("artifacts", []),
         "artifacts/t29_evidence.json", check_rel}),
        produced_files=list(produced))
    final = copy.deepcopy(evidence)
    final["references"] = [copy.deepcopy(early["references"][0])]
    final["scale"]["second_reference_index"] = None
    final["scale"]["second_reference_absent_reason"] = (
        "the standing figure covers something else on its check, "
        "so only the crate counts")
    report = _validate(final, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    reason = report["result"]["verdict"]["reason"] or ""
    assert "references disagree" not in reason, reason
    assert "one reference" in reason, reason

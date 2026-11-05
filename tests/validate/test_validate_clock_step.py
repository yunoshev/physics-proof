# generated from brief/11 · part 11 owns this file
"""The clock is a calculation step (brief §32)."""

import copy


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _clock(rate, sigma=0.3, lo=4.0, hi=5.0, interpretation="step",
           band=(3.0, 6.0)):
    return {
        "signal_description": "steady steps on the approach run",
        "measured_rate_hz": rate,
        "measured_rate_sigma_hz": sigma,
        "interpretation": interpretation,
        "band_hz": [band[0], band[1]],
        "natural_range_hz": [lo, hi],
        "natural_range_source": {
            "url": "https://example.com/gait",
            "quote": "step rate is 4 to 5 Hz"},
    }


def test_clock_step_between_scale_and_uncertainty(baseline, tmp_path):
    # Wall run 15's shape: a normal step rate on the approach run.
    # The result carries a clock step after the scale/fit steps and
    # before uncertainty, titled by its interpretation.
    from src.contract import validate_result

    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["clock"] = _clock(4.0)
    good["clock_absent_reason"] = None
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    result = report["result"]
    assert validate_result(result) == []
    assert result["clock"]["reads_normal"] is True
    steps = result["calculation_steps"]
    ids = [s["id"] for s in steps]
    assert ids == [
        "time_from_frames", "mask_check", "mask_check", "scale",
        "segment", "fit", "measured_g", "clock", "uncertainty",
        "verdict",
    ]
    clock_step = steps[ids.index("clock")]
    assert clock_step["title"] == "Clock: step rate"
    text = " ".join(
        block.get("fallback", block.get("text", ""))
        for block in clock_step["short"])
    assert "4.00" in text
    assert "0.30" in text
    assert "example.com" in text
    assert "plays at real speed" in text


def test_clock_step_without_segments(baseline, tmp_path):
    # Wall run 15's shape (brief §35): no segments, one range check
    # and a clock reading normal. The result still carries its clock
    # step, between the scale/range steps and uncertainty.
    import json as _json

    from src.contract import validate_result

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = copy.deepcopy(evidence)
    good["segments"] = []
    # Range-only evidence measures no motion, so it carries no survey.
    good["first_look"].pop("overview", None)
    good["first_look"]["motions"] = [
        {"frame_start": 0, "frame_end": 299,
         "description": "hand held still for the still frame",
         "segment_id": None,
         "skip_reason": "no flight: still frame, no motion to measure"}]
    good["clock"] = _clock(4.0)
    good["clock_absent_reason"] = None
    good["worlds"] = {"candidates": [{"world": "Earth"}],
                      "excluded": []}
    good["error_budget"] = {"components": [], "sigma_relative": 0.0}
    good["range_checks"] = [
        {
            "id": "stripe_ratio",
            "label": "stripe ratio",
            "answers": "It settles whether the two stripes match.",
            "unit": "ratio",
            "frame": 10,
            "extents": [
                {"name": "block stripe", "x1": 25.0, "y1": 25.0,
                 "x2": 25.0, "y2": 80.0, "length_px": 55.0,
                 "frame": 10},
                {"name": "figure stripe", "x1": 150.0, "y1": 25.0,
                 "x2": 150.0, "y2": 80.0, "length_px": 55.0,
                 "frame": 10}],
            "value": 1.0,
            "sigma": 0.04,
            "formula": "block stripe_px / figure stripe_px",
            "uses_scale": False,
            "measurement_artifact": "artifacts/measure_ratio.txt",
            "range": {
                "min": 0.9, "max": 1.1, "typical": 1.0,
                "what": "stripe ratios in the survey",
                "bounds_kind": "min-max", "percentiles": None,
                "sources": [
                    {"url": "https://example.com/ratios",
                     "domain": "example.com",
                     "quote": "stripe ratios run from 90 percent "
                              "to 110 percent",
                     "quote_highlight": "90 percent",
                     "value": 0.9, "bound": "min",
                     "source_type": "survey report"},
                    {"url": "https://example.com/ratios",
                     "domain": "example.com",
                     "quote": "stripe ratios run from 90 percent "
                              "to 110 percent",
                     "quote_highlight": "110 percent",
                     "value": 1.1, "bound": "max",
                     "source_type": "survey report"}],
            },
        },
    ]
    (run_dir / "artifacts" / "measure_ratio.txt").write_text(
        "block stripe: x1 = 25.0 y1 = 25.0 x2 = 25.0 y2 = 80.0 "
        "length_px = 55.0\n"
        "figure stripe: x1 = 150.0 y1 = 25.0 x2 = 150.0 y2 = 80.0 "
        "length_px = 55.0\n"
        "value = 1.0\nsigma = 0.04\n", encoding="utf-8")
    (run_dir / "artifacts" / "t1_web_search_0.json").write_text(
        _json.dumps({
            "query": "stripe ratio survey",
            "facts": [
                {"url": "https://example.com/ratios",
                 "quote": "stripe ratios run from 90 percent to "
                          "110 percent",
                 "text": "stripe ratios run from 90 percent to "
                         "110 percent"}]}),
        encoding="utf-8")
    # Append: the baseline journal already confirms the reference
    # lines (§50); overwriting it would drop those records.
    with (run_dir / "artifacts" / "line_checks.jsonl").open(
            "a", encoding="utf-8") as _journal:
        _journal.write(
            _json.dumps({
                "frame": 10,
                "lines": [
                    {"x1": 25.0, "y1": 25.0, "x2": 25.0, "y2": 80.0,
                     "claim": "block stripe",
                     "description": "the line runs along block stripe",
                     "agrees": True,
                     "why": "the description matches"},
                    {"x1": 150.0, "y1": 25.0, "x2": 150.0,
                     "y2": 80.0,
                     "claim": "figure stripe",
                     "description": "the line runs along figure stripe",
                     "agrees": True,
                     "why": "the description matches"}],
                "overlay_artifact": "artifacts/view_0.jpg",
                "turn": 1}) + "\n")
    for rel in ("artifacts/measure_ratio.txt",
                "artifacts/t1_web_search_0.json",
                "artifacts/line_checks.jsonl"):
        ctx["artifacts"].append(rel)
        ctx["artifacts"].sort()
        ctx["produced_files"].append(rel)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert validate_result(report["result"]) == []
    assert report["result"]["clock"]["reads_normal"] is True
    steps = report["result"]["calculation_steps"]
    ids = [s["id"] for s in steps]
    assert ids == [
        "time_from_frames", "mask_check", "mask_check", "scale",
        "clock", "scale", "uncertainty", "verdict",
    ]
    clock_step = steps[ids.index("clock")]
    assert clock_step["title"] == "Clock: step rate"
    text = " ".join(
        block.get("fallback", block.get("text", ""))
        for block in clock_step["short"])
    assert "4.00" in text
    assert "0.30" in text
    assert "example.com" in text
    assert "plays at real speed" in text


def test_clock_step_reads_retime(baseline, tmp_path):
    # A slow clock: the step names the retime the clock implies.
    import json as _json

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    for row in rows:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * (0.79 / 1.62)
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        _json.dumps(rows), encoding="utf-8")
    good = copy.deepcopy(evidence)
    curve = good["segments"][0]["fit_curve_px"]
    for sample, row in zip(curve, rows):
        sample["y_px"] = row["y_px"]
    good["clock"] = _clock(0.6, sigma=0.02, lo=1.4, hi=2.0,
                           interpretation="stride", band=(0.5, 4.0))
    good["clock_absent_reason"] = None
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    steps = report["result"]["calculation_steps"]
    clock_step = [s for s in steps if s["id"] == "clock"][0]
    assert clock_step["title"] == "Clock: stride rate"
    text = " ".join(
        block.get("fallback", block.get("text", ""))
        for block in clock_step["short"])
    assert "slowed down" in text
    assert "0.60" in text
    assert "example.com" in text

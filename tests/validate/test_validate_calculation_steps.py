# generated from brief/11 · part 11 owns this file
"""The result carries the whole calculation, step by step (§29)."""

import copy


def test_full_steps_two_references_one_segment(baseline, tmp_path):
    # The spec's clip-a bullet, two references over one measured
    # segment: every step the evidence supports, in order, with the
    # result's own numbers in the formulas.
    from src.contract import validate_result
    from src.validate import validate
    from src.validate.io import format_g

    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True, report["errors"]
    result = report["result"]
    assert validate_result(result) == []
    steps = result["calculation_steps"]
    assert [s["id"] for s in steps] == [
        "time_from_frames", "mask_check", "mask_check", "scale",
        "segment", "fit", "measured_g", "clock", "uncertainty",
        "verdict",
    ]
    for step in steps:
        assert step["title"]
        assert step["short"], step["id"]
    # The scale, the fit acceleration and g in the formulas equal
    # the result's values at the printed precision.
    scale = steps[3]
    assert scale["title"] == "Pixel scale"
    chip = scale["short"][1]["chip"]
    assert chip["text"] == \
        f"{result['scale']['m_per_px']:.6f} m/px"
    assert f"{result['scale']['m_per_px']:.6f}" in \
        scale["short"][1]["fallback"]
    fit = steps[5]
    assert fit["title"] == "Fit Jump one"
    seg_fit = result["segments"][0]["fit"]
    assert f"{seg_fit['a_px_s2']:.1f}" in fit["short"][1]["fallback"]
    assert f"g = {seg_fit['g_app']:.3f} m/s2" in \
        fit["short"][1]["chip"]["text"]
    measured = steps[6]
    numbers = format_g(result["verdict"]["g_measured"],
                       result["verdict"]["sigma_g"]).replace("±", "+/-")
    assert numbers in measured["short"][1]["fallback"]
    verdict_step = steps[-1]
    assert verdict_step["title"] == "Verdict"
    assert verdict_step["short"][0]["chip"]["text"] == \
        result["verdict"]["world"]
    # Motions that were not measured are not calculation steps.
    motions = result["first_look"]["motions"]
    assert motions
    titles = [s["title"] for s in steps]
    for motion in motions:
        assert motion["description"] not in titles

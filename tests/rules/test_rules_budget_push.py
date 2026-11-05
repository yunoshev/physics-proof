import math

from src.rules import (
    PUSH_CODES,
    REQUIRED_COMPONENTS,
    check_re1_sigma,
    check_re2_independent_repetitions,
    check_re3_no_cross_run,
    push_clock_required,
    push_motions_scan,
    push_second_reference,
)


def _comps(**kw):
    base = {"reference_size": 0.05, "pixel_scale": 0.03, "fit": 0.04,
            "point_vs_com": 0.02}
    base.update(kw)
    return base


def test_re1_required_components_pinned():
    assert tuple(REQUIRED_COMPONENTS) == ("reference_size", "pixel_scale",
                                          "fit", "point_vs_com")


def test_re1_sigma_recompute_and_components():
    comps = _comps()
    total = math.sqrt(sum(v ** 2 for v in comps.values()))
    assert check_re1_sigma(components=comps, sigma_total=total) is None


def test_re1_sigma_smaller_than_any_component_rejected():
    comps = _comps()
    err = check_re1_sigma(components=comps, sigma_total=0.01)
    assert err is not None and err[0] == "ERROR_BUDGET_TOO_SMALL"


def test_re1_reading_spread_is_an_explicit_term():
    comps = _comps()
    total = math.sqrt(sum(v ** 2 for v in comps.values()) + 0.05 ** 2)
    assert check_re1_sigma(components=comps, reading_spread=0.05,
                            sigma_total=total) is None
    err = check_re1_sigma(components=comps, reading_spread=0.05,
                           sigma_total=0.05)
    assert err is not None


def test_re2_identical_residuals_rejected():
    assert check_re2_independent_repetitions(
        residuals_list=[[1.0, 2.0], [1.5, 2.5]]) is None
    err = check_re2_independent_repetitions(
        residuals_list=[[1.0, 2.0], [1.0, 2.0]])
    assert err is not None and "IDENTICAL" in err[0]


def test_re3_cross_run_reference_rejected():
    assert check_re3_no_cross_run(text_fields=["measured g on this clip"]) is None
    err = check_re3_no_cross_run(text_fields=["compared with run 7, ratio 1.48"])
    assert err is not None and err[0] == "CROSS_RUN_REFERENCE"


def test_push_codes_hold_exactly_three():
    assert tuple(PUSH_CODES) == ("SECOND_REFERENCE_REQUIRED",
                                 "CLOCK_REQUIRED", "MOTIONS_SCAN_MISSING")


def test_push_second_reference():
    assert push_second_reference(n_references=2) is None
    err = push_second_reference(n_references=1)
    assert err is not None and err[0] == "SECOND_REFERENCE_REQUIRED"


def test_push_clock():
    assert push_clock_required(g_fits_any_world=True,
                               has_clock=False) is None
    assert push_clock_required(g_fits_any_world=False,
                               has_clock=True) is None
    err = push_clock_required(g_fits_any_world=False, has_clock=False)
    assert err is not None and err[0] == "CLOCK_REQUIRED"


def test_push_motions_scan():
    assert push_motions_scan(viewed_every_0_25s=True) is None
    err = push_motions_scan(viewed_every_0_25s=False)
    assert err is not None and err[0] == "MOTIONS_SCAN_MISSING"


def test_push_helpers_fire_individually():
    assert push_second_reference(n_references=1)[0] == "SECOND_REFERENCE_REQUIRED"
    assert push_clock_required(
        g_fits_any_world=False, has_clock=False)[0] == "CLOCK_REQUIRED"
    assert push_motions_scan(
        viewed_every_0_25s=False)[0] == "MOTIONS_SCAN_MISSING"

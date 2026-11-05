from src.rules import (
    check_rr1_range_bounds,
    check_rr2_quoted_sources,
    check_rr3_ratio_no_scale,
    check_rr4_sigma_floor,
    check_rr5_answers_question,
)


def test_rr1_bounds_require_min_max_and_basis():
    assert check_rr1_range_bounds(
        quantity="hand length", of_what="the hand", kind_of_thing="adult hand",
        lo=0.16, hi=0.22, basis="5th–95th percentile") is None
    err = check_rr1_range_bounds(
        quantity="hand length", of_what="the hand", kind_of_thing="adult hand",
        lo=0.19, hi=None, basis="5th–95th percentile")
    assert err is not None and err[0] == "RANGE_SOURCE_MISSING"


def test_rr2_sources_quote_both_bounds():
    assert check_rr2_quoted_sources(
        lo=0.16, hi=0.22, lo_quote="range 0.16–0.22 m",
        hi_quote="range 0.16–0.22 m") is None
    err = check_rr2_quoted_sources(lo=0.16, hi=0.22, lo_quote="no numbers",
                                    hi_quote="0.22 m max")
    assert err is not None and err[0] == "RANGE_SOURCE_MISSING"


def test_rr3_ratio_needs_no_scale():
    assert check_rr3_ratio_no_scale(is_ratio=True, uses_scale=False) is None
    err = check_rr3_ratio_no_scale(is_ratio=True, uses_scale=True)
    assert err is not None and err[0] == "RANGE_USES_SCALE_NEEDLESSLY"


def test_rr4_code_measured_with_sigma_floors():
    # floor is sqrt(2) px * 0.01 m/px ≈ 0.0141: 0.02 passes, 0.0001 fails.
    assert check_rr4_sigma_floor(sigma=0.02, length_px=100.0,
                                 m_per_px=0.01) is None
    err = check_rr4_sigma_floor(sigma=0.0001, length_px=100.0,
                                m_per_px=0.01)
    assert err is not None and err[0] == "RANGE_SIGMA_TOO_SMALL"


def test_rr5_each_check_answers_question():
    assert check_rr5_answers_question(
        check_id="wall", question="Can a person run up a wall this tall?",
        motion_checks=True) is None
    err = check_rr5_answers_question(check_id="wall", question="",
                                     motion_checks=True)
    assert err is not None


def test_rr_suite_accepts_complete_check():
    assert check_rr1_range_bounds(
        quantity="palm/hand ratio", of_what="the hand",
        kind_of_thing="adult hand", lo=0.53, hi=0.68,
        basis="5th–95th percentile") is None
    assert check_rr2_quoted_sources(
        lo=0.53, hi=0.68, lo_quote="53% minimum observed",
        hi_quote="68% maximum observed") is None
    assert check_rr3_ratio_no_scale(is_ratio=True, uses_scale=False) is None
    assert check_rr4_sigma_floor(sigma=0.02, length_px=50.0,
                                 m_per_px=0.001) is None

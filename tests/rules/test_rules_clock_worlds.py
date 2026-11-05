from src.rules import (
    check_rc2_in_band,
    check_rc3_ambiguity,
    check_rc4_natural_range,
    check_rq1_question,
    check_rw1_candidate_worlds,
    implied_true_rate,
)


def test_rc2_only_in_band_rates():
    assert check_rc2_in_band(rate_hz=2.0, band_hz=(1.0, 4.0)) is None
    assert check_rc2_in_band(rate_hz=None, band_hz=(1.0, 4.0),
                             no_clock=True) is None
    err = check_rc2_in_band(rate_hz=9.0, band_hz=(1.0, 4.0))
    assert err is not None and err[0] == "CLOCK_OUT_OF_BAND"
    edge = check_rc2_in_band(rate_hz=None, band_hz=(1.0, 4.0))
    assert edge is not None and edge[0] == "CLOCK_BAND_EDGE"


def test_rc3_ambiguity_forces_undetermined_when_verdict_changing():
    err = check_rc3_ambiguity(ambiguous=True, verdict_changes=True,
                              picked_single=True)
    assert err is not None and err[0] == "CLOCK_AMBIGUOUS"
    assert check_rc3_ambiguity(ambiguous=True, verdict_changes=False,
                               picked_single=True) is None


def test_rc4_implied_true_rate_arithmetic():
    assert implied_true_rate(measured_hz=0.8, slowdown_k=2.0) == 1.6
    # measured = true / s, so true = k * measured
    assert abs(implied_true_rate(measured_hz=1.288, slowdown_k=1.5)
               - 1.932) < 1e-9


def test_rc4_requires_natural_range_plus_source():
    assert check_rc4_natural_range(natural_range=(1.0, 2.0),
                                   source="sprinter cadence survey") is None
    err = check_rc4_natural_range(natural_range=None, source=None)
    assert err is not None and err[0] == "CLOCK_RANGE_MISSING"


def test_rq1_viewer_question_required():
    assert check_rq1_question(
        question="Is this hop realistic on the Moon?",
        summary="A figure hops; g on the flight answers it.") is None
    err = check_rq1_question(question=None)
    assert err is not None and err[0] == "QUESTION_MISSING"
    phys = check_rq1_question(
        question="Does the ascent match Earth gravity?",
        summary="A run up a wall.")
    assert phys is not None and phys[0] == "QUESTION_PHYSICS_WORDING"


def test_rw1_fits_only_candidates():
    err = check_rw1_candidate_worlds(candidates=["Earth"], excluded=[],
                                     verdict_world="Moon")
    assert err is not None and err[0] == "WORLD_NOT_FROM_SCENE"
    assert check_rw1_candidate_worlds(candidates=["Earth"], excluded=[],
                                      verdict_world="Earth") is None


def test_rw1_single_candidate_empty_excluded_passes():
    assert check_rw1_candidate_worlds(candidates=["Moon"], excluded=[],
                                      verdict_world="Moon") is None

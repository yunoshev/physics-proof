from src.rules import (
    CANDIDATE_DECISIONS,
    check_rm6_overview,
    check_rm7_first_check,
    check_rs11_next_to_motion,
    check_rs12_short_segment,
)


def _overview(*cands):
    return {"candidates": list(cands)}


def test_rm6_missing_overview_rejected():
    err = check_rm6_overview(overview=None, motions=[], segments=[])
    assert err is not None and err[0] == "MOTION_OVERVIEW_MISSING"


def test_rm6_overview_all_candidates_decided():
    ov = _overview({"decision": "measured", "segment_id": "s1"},
                   {"decision": "not_a_flight", "reason": "walking step"})
    motions = [{"segment_id": "s1"}]
    assert check_rm6_overview(overview=ov, motions=motions,
                              segments=["s1"]) is None


def test_rm6_measured_without_segment_rejected():
    ov = _overview({"decision": "measured", "segment_id": "sX"})
    err = check_rm6_overview(overview=ov, motions=[{"segment_id": "sX"}],
                             segments=["s1"])
    assert err is not None and err[0] == "MOTION_NOT_MEASURED"


def test_rm6_measured_candidate_missing_from_motions_rejected():
    ov = _overview({"decision": "measured", "segment_id": "s1"})
    err = check_rm6_overview(overview=ov, motions=[], segments=["s1"])
    assert err is not None and err[0] == "MOTION_NOT_MEASURED"


def test_rm6_dismissed_without_reason_rejected():
    ov = _overview({"decision": "not_measurable"})
    err = check_rm6_overview(overview=ov, motions=[], segments=[])
    assert err is not None


def test_rm6_decision_words_restricted_to_listed_three():
    assert tuple(CANDIDATE_DECISIONS) == ("measured", "not_a_flight",
                                          "not_measurable")
    for bad in ("not_measured", "not_free_flight", "not_free", "skipped"):
        ov = _overview({"decision": bad, "reason": "x"})
        err = check_rm6_overview(overview=ov, motions=[], segments=[])
        assert err is not None and err[0] == "CANDIDATE_DECISION_WORD", bad


def test_rm7_first_check_named_with_reason():
    ov = {"candidates": [], "first_check": {"segment_id": "s1",
                                            "reason": "most frames"}}
    assert check_rm7_first_check(overview=ov, segments=["s1"]) is None


def test_rm7_first_check_missing_rejected():
    err = check_rm7_first_check(overview={}, segments=["s1"])
    assert err is not None and err[0] == "FIRST_CHECK_MISSING"


def test_rm7_first_check_must_be_a_measured_segment():
    ov = {"candidates": [], "first_check": {"segment_id": "sX",
                                            "reason": "clean"}}
    err = check_rm7_first_check(overview=ov, segments=["s1"])
    assert err is not None and err[0] == "FIRST_CHECK_MISSING"


def test_rs11_reference_next_to_motion_passes():
    # 1 s before takeoff at 24 fps: inside the 2 s window.
    assert check_rs11_next_to_motion(frame=217, takeoff_frame=241, fps=24.0,
                                     mask_present_in_window=True) is None


def test_rs11_far_or_late_reference_needs_a_note():
    err = check_rs11_next_to_motion(frame=0, takeoff_frame=241, fps=24.0,
                                    mask_present_in_window=True)
    assert err is not None and err[0] == "REFERENCE_FAR_FROM_MOTION"


def test_rs12_still_reference_needs_a_short_segment():
    assert check_rs12_short_segment(moves=False, span_frames=50) is None
    assert check_rs12_short_segment(moves=True, span_frames=192) is None
    err = check_rs12_short_segment(moves=False, span_frames=192)
    assert err is not None and err[0] == "STILL_SEGMENT_TOO_LONG"

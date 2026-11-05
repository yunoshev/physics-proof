from src.rules import (
    check_rs1_mask_check,
    check_rs2_multi_reading,
    check_rs2_spread_pricing,
    check_rs3_same_mask,
    check_rs4_extent_type,
    check_rs6_pairwise_agreement,
    check_rs6_scale_mean,
    check_rs6a_single_reference,
    check_rs6b_one_thing_one_reference,
    check_rs7_state_match,
    check_rs8_gap_calls_for_third,
    check_rs9_still_sharp_frame,
    check_rs11_next_to_motion,
    check_rs13_size_as_quoted,
    check_rs14_shape_stable,
    check_rs15_gap_points_at_part_whole,
    check_rs16_moving_thing_reference,
    check_rs17_line_checked,
)


def test_rs1_requires_mask_check():
    assert check_rs1_mask_check(mask_check_artifact="artifacts/t1.json") is None
    err = check_rs1_mask_check(mask_check_artifact=None)
    assert err is not None and err[0] == "MASK_CHECK_MISSING"


def test_rs2_silent_single_choice_rejected():
    err = check_rs2_multi_reading(readings=["pack", "pack+top"],
                                  measurements_per_reading=["pack"],
                                  justification=None)
    assert err is not None and err[0] == "REFERENCE_READING_UNPRICED"


def test_rs2_per_reading_g_or_overlay_justification_passes():
    assert check_rs2_multi_reading(
        readings=["pack", "pack+top"],
        measurements_per_reading=["pack", "pack+top"]) is None
    assert check_rs2_multi_reading(
        readings=["pack", "pack+top"], measurements_per_reading=["pack"],
        justification="chose pack against overlay artifact t3 frame 200") is None


def test_rs2_equal_size_alternatives_need_no_spread():
    assert check_rs2_spread_pricing(size=0.66, alt_size=0.66,
                                    reading_spread=0.0) is None


def test_rs2_full_pricing_half_size_difference():
    required = abs(0.91 - 0.66) / (2 * 0.66)
    assert check_rs2_spread_pricing(size=0.66, alt_size=0.91,
                                    reading_spread=required) is None
    err = check_rs2_spread_pricing(size=0.66, alt_size=0.91,
                                   reading_spread=0.12)
    assert err is not None and err[0] == "READING_SPREAD_TOO_SMALL"


def test_rs2_ruled_out_by_other_reference_excuses_spread():
    assert check_rs2_spread_pricing(
        size=0.66, alt_size=0.91, reading_spread=0.0,
        ruled_out_by_other_reference=True) is None


def test_rs3_same_mask_twice_hard_reject():
    err = check_rs3_same_mask(iou=0.95)
    assert err is not None and err[0] == "SECOND_REFERENCE_SAME_OBJECT"


def test_rs3_nested_mask_is_a_different_thing():
    assert check_rs3_same_mask(iou=0.2) is None


def test_rs4_projected_requires_allowance():
    assert check_rs4_extent_type(extent_type="face_on",
                                 has_projection_allowance=False) is None
    assert check_rs4_extent_type(extent_type="projected",
                                 has_projection_allowance=True) is None
    err = check_rs4_extent_type(extent_type="projected",
                                has_projection_allowance=False)
    assert err is not None


def test_rs6_pairwise_agreement_within_2sigma():
    assert check_rs6_pairwise_agreement(scales=[0.0116, 0.0114],
                                        sigmas=[0.0004, 0.0004]) is None
    err = check_rs6_pairwise_agreement(scales=[0.00985, 0.0119],
                                       sigmas=[0.0004, 0.0005])
    assert err is not None and err[0] == "REFERENCES_DISAGREE"


def test_rs6_scale_is_inverse_variance_weighted_mean():
    mean, _sigma = check_rs6_scale_mean(scales=[0.0136, 0.0138, 0.0137],
                                        sigmas=[0.0004, 0.0004, 0.0004])
    assert abs(mean - 0.0137) < 1e-9


def test_rs6a_one_reference_gives_no_verdict():
    err = check_rs6a_single_reference(n_references=1,
                                      absent_reason="only one thing of known size")
    assert err is not None and err[0] == "ONE_REFERENCE_UNDETERMINED"
    assert check_rs6a_single_reference(n_references=2,
                                       absent_reason=None) is None


def test_rs6b_same_thing_twice_rejected():
    ref_a = {"object_name": "backpack", "size_m": 0.66,
             "size_source": "NASM PLSS page"}
    ref_b = {"object_name": "backpack", "size_m": 0.66,
             "size_source": "NASM PLSS page"}
    err = check_rs6b_one_thing_one_reference(ref_a=ref_a, ref_b=ref_b)
    assert err is not None and err[0] == "SECOND_REFERENCE_SAME_THING"


def test_rs6b_same_size_same_source_rejected():
    ref_a = {"object_name": "pack frame 96", "size_m": 0.66,
             "size_source": "NASM PLSS page"}
    ref_b = {"object_name": "pack frame 128", "size_m": 0.66,
             "size_source": "NASM PLSS page"}
    err = check_rs6b_one_thing_one_reference(ref_a=ref_a, ref_b=ref_b)
    assert err is not None and err[0] == "SECOND_REFERENCE_SAME_THING"


def test_rs6b_different_things_pass():
    ref_a = {"object_name": "backpack", "size_m": 0.66,
             "size_source": "NASM PLSS page"}
    ref_b = {"object_name": "suited figure height", "size_m": 1.70,
             "size_source": "astronaut facts"}
    assert check_rs6b_one_thing_one_reference(ref_a=ref_a,
                                              ref_b=ref_b) is None


def test_rs7_state_match_required():
    assert check_rs7_state_match(
        state_match={"covered": "helmet and boots",
                     "not_covered": "gloves"}) is None
    err = check_rs7_state_match(state_match=None)
    assert err is not None and err[0] == "STATE_MATCH_MISSING"


def test_rs8_five_percent_gap_calls_for_third():
    err = check_rs8_gap_calls_for_third(scales=[0.0102, 0.0113])
    assert err is not None and err[0] == "THIRD_REFERENCE_REQUIRED"
    assert check_rs8_gap_calls_for_third(scales=[0.0116, 0.0117]) is None
    assert check_rs8_gap_calls_for_third(
        scales=[0.0102, 0.0113, 0.0108],
        rel_sigmas=[0.04, 0.04, 0.03]) is None


def test_rs9_riding_reference_measured_before_motion():
    assert check_rs9_still_sharp_frame(frame=200, motion_start_frame=241,
                                       rides_on_mover=True) is None
    err = check_rs9_still_sharp_frame(frame=250, motion_start_frame=241,
                                      rides_on_mover=True)
    assert err is not None and err[0] == "REFERENCE_MEASURED_IN_MOTION"


def test_rs11_tightened_present_in_window_is_error():
    err = check_rs11_next_to_motion(frame=0, takeoff_frame=241, fps=24.0,
                                    mask_present_in_window=True, note=None)
    assert err is not None and err[0] == "REFERENCE_FAR_FROM_MOTION"


def test_rs11_tightened_absent_with_note_is_push_only():
    res = check_rs11_next_to_motion(frame=0, takeoff_frame=241, fps=24.0,
                                    mask_present_in_window=False,
                                    note="not in window frames")
    assert res is not None and res[0] == "REFERENCE_FAR_FROM_MOTION_PUSH"


def test_rs13_single_sum_mean_within_one_percent():
    assert check_rs13_size_as_quoted(mode="single", value=0.66,
                                     single=0.66) is None
    assert check_rs13_size_as_quoted(mode="sum", value=0.914,
                                     parts=[0.66, 0.254]) is None
    assert check_rs13_size_as_quoted(mode="mean", value=1.70,
                                     parts=[1.69, 1.71]) is None


def test_rs13_adjusted_size_rejected():
    err = check_rs13_size_as_quoted(mode="single", value=1.60, single=1.70)
    assert err is not None and err[0] == "SIZE_ADJUSTED"
    err2 = check_rs13_size_as_quoted(mode="single", value=1.70, single=1.70,
                                     adjusted=True)
    assert err2 is not None and err2[0] == "SIZE_ADJUSTED"


def test_rs14_stable_and_skipped_pass():
    assert check_rs14_shape_stable(length_px=130.0,
                                   median_rest_px=129.0) is None


def test_rs14_unstable_shape_rejected():
    # R-S14 (2026-11-03): the length along the measured line — here the
    # width at push-off, not the height — must sit within 5% of rest.
    err = check_rs14_shape_stable(length_px=153.0, median_rest_px=126.0)
    assert err is not None and err[0] == "REFERENCE_SHAPE_UNSTABLE"
    err_w = check_rs14_shape_stable(length_px=80.0, median_rest_px=100.0)
    assert err_w is not None and err_w[0] == "REFERENCE_SHAPE_UNSTABLE"


def test_rs15_gap_detail_points_at_part_whole():
    assert check_rs15_gap_points_at_part_whole(
        detail="mask covers the whole unit plus a mounted top part") is None
    err = check_rs15_gap_points_at_part_whole(detail="will search more")
    assert err is not None


def test_rs16_moving_thing_with_quoted_size_must_be_a_reference():
    assert check_rs16_moving_thing_reference(
        mover_has_quoted_size=True, mover_id="figure",
        reference_ids=["figure", "pack"]) is None
    err = check_rs16_moving_thing_reference(
        mover_has_quoted_size=True, mover_id="figure",
        reference_ids=["pack"])
    assert err is not None and err[0] == "MOVER_NOT_A_REFERENCE"


def test_rs16_no_quoted_size_no_requirement():
    assert check_rs16_moving_thing_reference(
        mover_has_quoted_size=False, mover_id=None,
        reference_ids=["pack"]) is None


def test_rs16_extent_description_match_passes_without_flag():
    # The extent along the source's named dimension needs no extra flag.
    assert check_rs16_moving_thing_reference(
        mover_has_quoted_size=True, mover_id="ball",
        reference_ids=["ball"]) is None


def test_rs17_agreeing_check_passes():
    assert check_rs17_line_checked(has_agreeing_check=True) is None


def test_rs17_unchecked_line_rejected():
    err = check_rs17_line_checked(has_agreeing_check=False)
    assert err is not None and err[0] == "LINE_NOT_CONFIRMED"


def test_rs17_unclear_dimension_rejected():
    err = check_rs17_line_checked(has_agreeing_check=True,
                                  dimension_unclear=True)
    assert err is not None and err[0] == "LINE_NOT_CONFIRMED"

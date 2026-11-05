import math

from src.rules import (
    check_rm1_no_contact_in_fit,
    check_rm2_residual_trend,
    check_rm3_camera_accounted,
    check_rm4_motions_covered,
    check_rm5_single_phase,
)


def test_rm1_fit_excludes_contact():
    assert check_rm1_no_contact_in_fit(fitted_frames=[1, 2, 3],
                                       contact_frames=[5, 6]) is None
    err = check_rm1_no_contact_in_fit(fitted_frames=[1, 2, 3],
                                      contact_frames=[3, 4])
    assert err is not None and err[0] == "FIT_INCLUDES_CONTACT_OR_DUP"


def test_rm2_clean_fit_passes_mixed_window_fails():
    assert check_rm2_residual_trend(residual_trend_z=1.2) is None
    err = check_rm2_residual_trend(residual_trend_z=8.5)
    assert err is not None and err[0] == "RESIDUAL_TREND"


def test_rm3_still_needs_measurement_or_relative_track():
    assert check_rm3_camera_accounted(
        camera_still=True, still_displacement_px=1.0,
        has_relative_track=False) is None
    assert check_rm3_camera_accounted(
        camera_still=False, still_displacement_px=9.0,
        has_relative_track=True) is None
    err = check_rm3_camera_accounted(
        camera_still=True, still_displacement_px=9.0,
        has_relative_track=False)
    assert err is not None and err[0] == "CAMERA_UNACCOUNTED"


def test_rm4_every_motion_measured_or_explained():
    motions = [{"segment_id": "seg_a"}, {"skip_reason": "too short: 3 frames"}]
    assert check_rm4_motions_covered(motions=motions,
                                     segments=["seg_a"]) is None
    bad = [{"segment_id": None}]
    err = check_rm4_motions_covered(motions=bad, segments=["seg_a"])
    assert err is not None and err[0] == "MOTION_NOT_MEASURED"


def test_rm5_one_phase_per_window():
    assert check_rm5_single_phase(residual_trend_z=0.5) is None
    err = check_rm5_single_phase(residual_trend_z=5.0)
    assert err is not None and err[0] == "RESIDUAL_TREND"

"""R-M motion checks."""

from __future__ import annotations

#: R-M2/R-M5 gate from part 09: residual_trend_z above 3 is not one phase.
RESIDUAL_TREND_Z_MAX = 3.0


def check_rm1_no_contact_in_fit(*, fitted_frames, contact_frames):
    """R-M1: fit only unsupported motion (no contact frames in the fit)."""
    overlap = sorted(set(fitted_frames) & set(contact_frames))
    if overlap:
        return ("FIT_INCLUDES_CONTACT_OR_DUP", "segments[].frames",
                f"fitted frames intersect contact frames {overlap}")
    return None


def check_rm2_residual_trend(*, residual_trend_z: float):
    """R-M2: a systematic residual trend means the point deforms."""
    if residual_trend_z <= RESIDUAL_TREND_Z_MAX:
        return None
    return ("RESIDUAL_TREND", "segments[].fit",
            f"residual_trend_z {residual_trend_z} > {RESIDUAL_TREND_Z_MAX}: "
            "the window is not one stretch of constant acceleration; "
            "re-track a rigid point")


def check_rm3_camera_accounted(*, camera_still: bool | None,
                               still_displacement_px: float | None = None,
                               still_threshold_px: float = 2.0,
                               has_relative_track: bool = False):
    """R-M3: moving camera ⇒ scene-relative trajectories."""
    if has_relative_track:
        return None
    if camera_still and still_displacement_px is not None \
            and still_displacement_px <= still_threshold_px:
        return None
    return ("CAMERA_UNACCOUNTED", "camera",
            "need a camera-still attestation backed by a reference-track "
            "measurement, or a scene-relative trajectory")


def check_rm4_motions_covered(*, motions, segments):
    """R-M4: every listed motion is measured or has a skip reason."""
    seg_ids = {s for s in segments}
    for i, motion in enumerate(motions):
        if motion.get("segment_id") in seg_ids:
            continue
        if motion.get("skip_reason"):
            continue
        return ("MOTION_NOT_MEASURED", f"first_look.motions[{i}]",
                "every motion is measured as its own segment or carries "
                "a reason it cannot be measured")
    return None


def check_rm5_single_phase(*, residual_trend_z: float):
    """R-M5: one phase per window (takeoff/landing/plant/surface change)."""
    return check_rm2_residual_trend(residual_trend_z=residual_trend_z)

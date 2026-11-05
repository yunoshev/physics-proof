"""R-S scale checks."""

from __future__ import annotations

import math

#: R-S3 (amended): IoU above this means the same mask passed twice.
SAME_MASK_IOU = 0.8

#: R-S8 / part 11 §15, §39: gap and tightness thresholds.
GAP_FRAC = 0.05

#: R-S14: rest-shape tolerance.
SHAPE_TOL_FRAC = 0.05

#: R-S13: quoted-size recompute tolerance.
SIZE_TOL_FRAC = 0.01


def check_rs1_mask_check(*, mask_check_artifact):
    """R-S1: every size-bearing reference has a blind mask check."""
    if mask_check_artifact:
        return None
    return ("MASK_CHECK_MISSING", "references[].mask_check",
            "a reference without a check_mask artifact is rejected")


def check_rs2_multi_reading(*, readings, measurements_per_reading,
                            justification: str | None = None):
    """R-S2: multiple coverage readings need per-reading g or a reasoned pick."""
    if len(readings) <= 1:
        return None
    if set(measurements_per_reading or ()) >= set(readings):
        return None
    if justification and "overlay" in justification and (
            "artifact" in justification or "frame" in justification):
        return None
    return ("REFERENCE_READING_UNPRICED", "references[].readings",
            "silent single choice among readings is rejected; carry a g per "
            "reading or justify one choice against the overlay")


def check_rs2_spread_pricing(*, size, alt_size, reading_spread,
                             ruled_out_by_other_reference: bool = False):
    """R-S2 (amended): an alternative size is priced in full.

    Required spread is half the size difference as a relative term:
    ``|alt - size| / (2 * size)``. An alternative equal to the headline
    needs no spread; one ruled out by another reference is excused.
    """
    if alt_size == size:
        return None
    if ruled_out_by_other_reference:
        return None
    required = abs(alt_size - size) / (2.0 * size)
    if reading_spread is not None and reading_spread + 1e-12 >= required:
        return None
    return ("READING_SPREAD_TOO_SMALL", "error_budget.reading_spread",
            f"alternative {alt_size} vs headline {size} needs spread "
            f">= {required:.4f} (half the size difference); "
            f"given {reading_spread}")


def check_rs3_same_mask(*, iou: float):
    """R-S3 (amended): IoU above 0.8 is the same mask twice (hard reject).

    A nested mask (backpack inside its wearer) has low IoU and passes.
    """
    if iou > SAME_MASK_IOU:
        return ("SECOND_REFERENCE_SAME_OBJECT", "references[1].mask",
                f"masks overlap with IoU {iou:.3f} > {SAME_MASK_IOU}: "
                "the same mask passed twice, not a second reference")
    return None


def check_rs4_extent_type(*, extent_type: str, has_projection_allowance: bool):
    """R-S4: a projected extent needs a projection allowance in the budget."""
    if extent_type in ("face_on", "rotation_invariant"):
        return None
    if extent_type == "projected" and has_projection_allowance:
        return None
    return ("EXTENT_PROJECTION_MISSING", "references[].extent_type",
            "projected extent without a projection allowance is rejected")


def check_rs6_pairwise_agreement(*, scales, sigmas):
    """R-S6: every pair of references agrees within 2σ combined."""
    n = len(scales)
    for i in range(n):
        for j in range(i + 1, n):
            combined = math.sqrt(sigmas[i] ** 2 + sigmas[j] ** 2)
            if abs(scales[i] - scales[j]) > 2.0 * combined:
                return ("REFERENCES_DISAGREE", f"references[{i},{j}]",
                        f"scales {scales[i]} and {scales[j]} differ by more "
                        f"than 2σ (σ {sigmas[i]}, {sigmas[j]})")
    return None


def check_rs6_scale_mean(*, scales, sigmas):
    """R-S6: the scale is the inverse-variance weighted mean of references."""
    weights = [1.0 / (s ** 2) for s in sigmas]
    total = sum(weights)
    mean = sum(v * w for v, w in zip(scales, weights)) / total
    sigma = math.sqrt(1.0 / total)
    spread_floor = max(scales) - min(scales)
    if len(scales) > 1:
        sigma = max(sigma, spread_floor / 2.0)
    return (mean, sigma)


def check_rs6a_single_reference(*, n_references: int, absent_reason: str | None):
    """R-S6a: one reference gives no verdict (undetermined), never a reject."""
    if n_references >= 2:
        return None
    if absent_reason:
        return ("ONE_REFERENCE_UNDETERMINED", "scale",
                "scale rests on one reference: verdict is undetermined")
    return ("SECOND_REFERENCE_ABSENT_UNEXPLAINED", "scale",
            "one reference with no second_reference_absent_reason")


def _norm_thing(value) -> str:
    return " ".join(str(value or "").lower().split())


def check_rs6b_one_thing_one_reference(*, ref_a: dict, ref_b: dict):
    """R-S6b: one thing is one reference.

    Two references must be different things with their own quoted sizes.
    Measuring the same thing again (same object name, or the same quoted
    size from the same source) is a line check, not a second reference.
    """
    name_a, name_b = _norm_thing(ref_a.get("object_name")), _norm_thing(ref_b.get("object_name"))
    if name_a and name_a == name_b:
        return ("SECOND_REFERENCE_SAME_THING", "references[1]",
                f"both references are '{ref_a.get('object_name')}': one "
                "thing is one reference; a second line on it is a line "
                "check, not a second reference")
    size_a, size_b = ref_a.get("size_m"), ref_b.get("size_m")
    src_a, src_b = _norm_thing(ref_a.get("size_source")), _norm_thing(ref_b.get("size_source"))
    if size_a is not None and size_a == size_b and src_a and src_a == src_b:
        return ("SECOND_REFERENCE_SAME_THING", "references[1]",
                "same quoted size from the same source on both references: "
                "one thing is one reference")
    return None


def check_rs7_state_match(*, state_match: dict | None):
    """R-S7: a size describes the thing as it is seen (state_match)."""
    if state_match and state_match.get("covered") and state_match.get("not_covered") is not None:
        return None
    return ("STATE_MATCH_MISSING", "references[].size_derivation.state_match",
            "state_match must say what the mask shows that the source covers "
            "and what it shows that the source does not")


def check_rs8_gap_calls_for_third(*, scales, rel_sigmas=None):
    """R-S8: a >5% gap between references calls for a third reference."""
    if len(scales) < 2:
        return None
    mean = sum(scales) / len(scales)
    gap = (max(scales) - min(scales)) / mean if mean else 0.0
    if gap <= GAP_FRAC:
        return None
    if len(scales) >= 3:
        # A third settles the gap only when tight enough (rel σ ≤ 5%)
        # to tell the two sides apart (part 11 §39).
        for k, s in enumerate(scales):
            rel = (rel_sigmas[k] if rel_sigmas else 0.0) or 0.0
            if rel <= GAP_FRAC:
                return None
        return ("THIRD_REFERENCE_REQUIRED", "scale",
                f"references differ by {gap * 100:.1f}% (> 5%) and no third "
                "reference is tight enough (rel σ ≤ 5%) to settle the gap")
    return ("THIRD_REFERENCE_REQUIRED", "scale",
            f"references differ by {gap * 100:.1f}% (> 5%, even within 2σ): "
            "measure a third reference of a different thing")


def check_rs9_still_sharp_frame(*, frame: int, motion_start_frame: int,
                                rides_on_mover: bool):
    """R-S9: a reference riding on the mover is read before the motion."""
    if rides_on_mover and frame >= motion_start_frame:
        return ("REFERENCE_MEASURED_IN_MOTION", "references[].frame",
                f"reference on frame {frame} rides the mover; use a still "
                f"frame before motion start ({motion_start_frame})")
    return None


def check_rs11_next_to_motion(*, frame: int, takeoff_frame: int, fps: float,
                              mask_present_in_window: bool,
                              note: str | None = None):
    """R-S11 (+tightening): measured ≤2 s before the first-check takeoff.

    When the reference's own mask is present on frames within 2 s before
    the first-check takeoff, it is measured there. A note excuses a far
    frame only when the reference is absent from that window.
    """
    dt_s = (takeoff_frame - frame) / fps if fps else float("inf")
    in_window = 0 <= dt_s <= 2.0
    if in_window:
        return None
    if mask_present_in_window:
        return ("REFERENCE_FAR_FROM_MOTION", "references[].frame",
                f"frame {frame} is {dt_s:.2f} s before takeoff "
                f"({takeoff_frame}); when the mask is present within 2 s "
                "before the first-check takeoff it is measured there")
    if note:
        return ("REFERENCE_FAR_FROM_MOTION_PUSH", "references[].frame",
                "far/late frame with a note: push only, accepted as "
                "undetermined on a real submit")
    return ("REFERENCE_FAR_FROM_MOTION", "references[].frame",
            f"frame {frame} needs a note when no window frame shows it")


def check_rs13_size_as_quoted(*, mode: str, value: float,
                              parts: list | None = None,
                              single: float | None = None,
                              adjusted: bool = False):
    """R-S13: a size is used as quoted (single, sum, or mean), never tuned."""
    if adjusted:
        return ("SIZE_ADJUSTED", "references[].size_m",
                "never adjust a quoted size by an estimate: no 'reduced for "
                "a crouch', no 'about 10 cm less'")
    if mode == "single":
        expected = single
    elif mode == "sum":
        expected = sum(parts or [])
    elif mode == "mean":
        expected = (sum(parts or []) / len(parts)) if parts else None
    else:
        return ("SIZE_MODE_UNKNOWN", "references[].size_m",
                "mode must be single, sum, or mean")
    if expected is None or expected == 0:
        return ("SIZE_MODE_UNKNOWN", "references[].size_m",
                "quoted parts missing for mode")
    if abs(value - expected) / abs(expected) <= SIZE_TOL_FRAC:
        return None
    return ("SIZE_ADJUSTED", "references[].size_m",
            f"value {value} differs from the quoted {mode} {expected} by "
            "more than 1%: used as quoted, never tuned")


def check_rs14_shape_stable(*, length_px: float, median_rest_px: float):
    """R-S14: the length along the measured line is within 5% of rest.

    The length is read along the reference's own line, not only as
    height: a body changes its height and its width at push-off, landing
    and in a stride.
    """
    if median_rest_px == 0:
        return ("REFERENCE_SHAPE_UNSTABLE", "references[].extent_px",
                "rest median is zero")
    frac = abs(length_px - median_rest_px) / abs(median_rest_px)
    if frac <= SHAPE_TOL_FRAC:
        return None
    return ("REFERENCE_SHAPE_UNSTABLE", "references[].extent_px",
            f"length {length_px} differs {frac * 100:.1f}% (> 5%) from the "
            "rest median along the same line; measure where the thing "
            "keeps its shape")


def check_rs15_gap_points_at_part_whole(*, detail: str):
    """R-S15: a gap detail first blames part/whole before a third search."""
    low = detail.lower()
    if ("part" in low and "whole" in low) or "mounted" in low or "covered" in low:
        return None
    return ("GAP_DETAIL_MISSING_PART_WHOLE", "scale",
            "when references disagree, first check each for a part/whole "
            "mismatch before searching for a third")


def check_rs16_moving_thing_reference(*, mover_has_quoted_size: bool,
                                      mover_id: str | None,
                                      reference_ids):
    """R-S16: the moving thing's own size comes first (when quotable)."""
    if not mover_has_quoted_size:
        return None
    if mover_id in (reference_ids or []):
        return None
    return ("MOVER_NOT_A_REFERENCE", "references",
            "the moving thing has a quoted size: it is one of the "
            "references, on a rest frame before the motion (R-S14)")


def check_rs17_line_checked(*, has_agreeing_check: bool,
                            dimension_unclear: bool = False):
    """R-S17: every reference line is checked blind (check_line agrees)."""
    if dimension_unclear:
        return ("LINE_NOT_CONFIRMED", "references[].line",
                "the blind look says the dimension is unclear: the line "
                "cannot set the scale")
    if has_agreeing_check:
        return None
    return ("LINE_NOT_CONFIRMED", "references[].line",
            "a reference line with no agreeing check_line cannot set "
            "the scale")

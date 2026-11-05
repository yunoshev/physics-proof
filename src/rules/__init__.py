"""Measuring-rule checks (part 08): pure, testable functions.

Each function returns ``None`` on pass or an ``(code, field, detail)``
triple on failure. Codes mirror part 11's validator vocabulary where the
rule is submit-enforced; push codes mirror part 11 §16 (dry run only).
No I/O, no models, no imports outside the standard library.
"""

from .time import check_t1_time_base, check_t2_fit_frames
from .scale import (
    check_rs1_mask_check,
    check_rs2_multi_reading,
    check_rs2_spread_pricing,
    check_rs3_same_mask,
    check_rs4_extent_type,
    check_rs6_pairwise_agreement,
    check_rs6b_one_thing_one_reference,
    check_rs6_scale_mean,
    check_rs6a_single_reference,
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
from .motion import (
    check_rm1_no_contact_in_fit,
    check_rm2_residual_trend,
    check_rm3_camera_accounted,
    check_rm4_motions_covered,
    check_rm5_single_phase,
)
from .clock import (
    check_rc2_in_band,
    check_rc3_ambiguity,
    check_rc4_natural_range,
    implied_true_rate,
)
from .worlds import check_rq1_question, check_rw1_candidate_worlds
from .dryrun import MOTIONS_SCAN_SPACING_S
from .budget import (
    PUSH_CODES,
    REQUIRED_COMPONENTS,
    check_re1_sigma,
    check_re2_independent_repetitions,
    check_re3_no_cross_run,
    push_clock_required,
    push_motions_scan,
    push_second_reference,
)
from .ranges import (
    check_rr1_range_bounds,
    check_rr2_quoted_sources,
    check_rr3_ratio_no_scale,
    check_rr4_sigma_floor,
    check_rr5_answers_question,
)
from .trajectories import (
    CANDIDATE_DECISIONS,
    check_rm6_overview,
    check_rm7_first_check,
    check_rs12_short_segment,
)

__all__ = [
    "CANDIDATE_DECISIONS",
    "MOTIONS_SCAN_SPACING_S",
    "PUSH_CODES",
    "REQUIRED_COMPONENTS",
    "check_t1_time_base",
    "check_t2_fit_frames",
    "check_rs1_mask_check",
    "check_rs2_multi_reading",
    "check_rs2_spread_pricing",
    "check_rs3_same_mask",
    "check_rs4_extent_type",
    "check_rs6_pairwise_agreement",
    "check_rs6_scale_mean",
    "check_rs6a_single_reference",
    "check_rs6b_one_thing_one_reference",
    "check_rs7_state_match",
    "check_rs8_gap_calls_for_third",
    "check_rs9_still_sharp_frame",
    "check_rs11_next_to_motion",
    "check_rs12_short_segment",
    "check_rs13_size_as_quoted",
    "check_rs14_shape_stable",
    "check_rs15_gap_points_at_part_whole",
    "check_rs16_moving_thing_reference",
    "check_rs17_line_checked",
    "check_rm1_no_contact_in_fit",
    "check_rm2_residual_trend",
    "check_rm3_camera_accounted",
    "check_rm4_motions_covered",
    "check_rm5_single_phase",
    "check_rm6_overview",
    "check_rm7_first_check",
    "check_rc2_in_band",
    "check_rc3_ambiguity",
    "check_rc4_natural_range",
    "implied_true_rate",
    "check_rq1_question",
    "check_rw1_candidate_worlds",
    "check_re1_sigma",
    "check_re2_independent_repetitions",
    "check_re3_no_cross_run",
    "push_clock_required",
    "push_motions_scan",
    "push_second_reference",
    "check_rr1_range_bounds",
    "check_rr2_quoted_sources",
    "check_rr3_ratio_no_scale",
    "check_rr4_sigma_floor",
    "check_rr5_answers_question",
]

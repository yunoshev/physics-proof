# generated from brief/11 · part 11 owns this file
"""Shared constants for submit-time result validation (part 11).

Pinned interface (brief §10): other parts import exactly these names.
``src.contract``'s schema test compares its ``error_budget.components``
description with :data:`REQUIRED_COMPONENTS`.
"""

from __future__ import annotations

__all__ = [
    "PUSH_CODES",
    "REQUIRED_COMPONENTS",
    "SAME_OBJECT_IOU",
    "WORLD_G",
]

#: Two masks show the same object when their intersection over union
#: on the measuring frame is above this limit (brief §54: the shape
#: check's masks, ``RANGE_CHECK_ON_REFERENCE`` and
#: ``SELF_REFERENCE_REQUIRED`` all read this one constant).
SAME_OBJECT_IOU = 0.75

#: Always-required error-budget component names (brief §2 V9, §15).
REQUIRED_COMPONENTS = (
    "reference_size",
    "pixel_scale",
    "fit",
    "point_vs_com",
)

#: Dry-run-only push codes (brief §16.2, §43, §53). A real submit is
#: judged as now: a single reference or a missing clock gives an
#: accepted undetermined result, a missing or partial motion
#: survey gives an accepted undetermined verdict, and a missing
#: self reference is never a refusal. Part 06 reads this tuple.
PUSH_CODES = (
    "SECOND_REFERENCE_REQUIRED",
    "CLOCK_REQUIRED",
    "MOTIONS_SCAN_MISSING",
    "MOTION_OVERVIEW_MISSING",
    "MOTION_OVERVIEW_PARTIAL",
    "FLIGHT_NOT_CONSIDERED",
    "REFERENCE_FAR_FROM_MOTION",
    "SELF_REFERENCE_REQUIRED",
)

#: Nominal surface gravity per world, m/s² (brief §§3, 9).
WORLD_G = {
    "Moon": 1.62,
    "Earth": 9.81,
    "Mars": 3.71,
}

#: Every error code this module can emit (brief §§2, 6–9, 12–16, 20,
#: 23–25, 28, 31–33, 36–39, 44–50, 52–56).
#: Part 07's submit description names the scale codes; its test reads
#: this file's source to confirm the codes are real validator codes.
ERROR_CODES = (
    "REFERENCE_SAME_THING",
    "MISSING_FIELD",
    "NUMBER_WITHOUT_PROVENANCE",
    "MASK_CHECK_MISSING",
    "SECOND_REFERENCE_SAME_OBJECT",
    "SECOND_REFERENCE_ABSENT_UNEXPLAINED",
    "REFERENCE_READING_UNPRICED",
    "READING_SPREAD_TOO_SMALL",
    "FIT_INCLUDES_CONTACT_OR_DUP",
    "RESIDUAL_TREND",
    "CAMERA_UNACCOUNTED",
    "ERROR_BUDGET_INCOMPLETE",
    "WORLD_NOT_FROM_SCENE",
    "CLOCK_LOGIC",
    "UNMEASURED_NUMBER_IN_TEXT",
    "REFERENCES_DISAGREE",
    "ALTERNATIVE_NOT_ADDRESSED",
    "THIRD_REFERENCE_REQUIRED",
    "STATE_MATCH_MISSING",
    "SIZE_NOT_AS_QUOTED",
    "SIZE_DIMENSION_UNLABELLED",
    "REFERENCE_SHAPE_UNSTABLE",
    "REFERENCE_SHAPE_UNCHECKED",
    "MOTION_NOT_MEASURED",
    "SECOND_REFERENCE_REQUIRED",
    "CLOCK_REQUIRED",
    "MOTIONS_SCAN_MISSING",
    "RANGE_NUMBER_WITHOUT_PROVENANCE",
    "RANGE_FORMULA_MISMATCH",
    "RANGE_SOURCE_MISSING",
    "RANGE_SIGMA_TOO_SMALL",
    "MEASUREMENT_MISSING",
    "EXAMPLE_VALUE_COPIED",
    "RANGE_EXTENT_OFF_FRAME",
    "RANGE_EXTENT_NOT_ON_MASK",
    "RANGE_LINE_NOT_CONFIRMED",
    "RANGE_CHECK_ON_REFERENCE",
    "LINE_NOT_CONFIRMED",
    "REFERENCE_LINE_NOT_CONFIRMED",
    "REFERENCE_DROPPED",
    "FLIGHT_NOT_PARABOLIC",
    "MOTION_OVERVIEW_MISSING",
    "MOTION_OVERVIEW_PARTIAL",
    "FLIGHT_NOT_CONSIDERED",
    "REFERENCE_FAR_FROM_MOTION",
    "MOTION_SKIP_REASON",
)

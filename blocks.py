"""Thin shim so sandboxed agent code can use plain ``import blocks``.

Re-exports everything from physics_proof.blocks.
"""

from physics_proof.blocks import (
    MaskSet,
    decide,
    fit_parabola,
    ghost,
    largest_component,
    load_masks,
    mask_stats,
    read_frames,
    relative_track,
    save_masks,
    scale_from_reference,
    spans_of,
    spans_of_track,
    step_rate,
    to_metres,
    track_quality,
    video_info,
)

__all__ = [
    "MaskSet",
    "save_masks",
    "load_masks",
    "video_info",
    "read_frames",
    "mask_stats",
    "largest_component",
    "spans_of",
    "spans_of_track",
    "track_quality",
    "fit_parabola",
    "scale_from_reference",
    "to_metres",
    "decide",
    "relative_track",
    "step_rate",
    "ghost",
]

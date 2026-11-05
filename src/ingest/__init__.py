"""Ingest and anonymisation (part 05).

Owns the agent's entry into the world: the anonymised copy at
``input/clip.<ext>``, the measured timing report at
``input/timing.json``, and the operator-only trace at
``logs/probe.json``. Also owns the generated-clip verifier
(:mod:`src.ingest.verify`) so analysis and generation share one
definition of "duplicate" (part 05 §4).
"""
from __future__ import annotations

from .hygiene import (
    HYGIENE_DECODE_SIZE,
    INTERPOLATION_CV_THRESHOLD,
    INTERPOLATION_MIN_FRAMES,
    NEAR_DUPLICATE_HASH_BITS,
    SCENE_CHANGE_THRESHOLD,
    decode_small_frames,
    dhash_bits,
    frame_md5s,
    hamming,
    timeline_hygiene,
)
from .ingest import (
    IngestError,
    anonymous_name,
    ingest,
    write_probe_json,
    write_timing_json,
)
from .measure import (
    VFR_DELTA_SPREAD_THRESHOLD,
    decode_timestamps,
    measure_timing,
    timing_from_timestamps,
)
from .probe import parse_fps, probe
from .verify import FPS_MATCH_REL_TOL, verify_generated_clip

__all__ = [
    "FPS_MATCH_REL_TOL",
    "HYGIENE_DECODE_SIZE",
    "INTERPOLATION_CV_THRESHOLD",
    "INTERPOLATION_MIN_FRAMES",
    "NEAR_DUPLICATE_HASH_BITS",
    "SCENE_CHANGE_THRESHOLD",
    "VFR_DELTA_SPREAD_THRESHOLD",
    "IngestError",
    "anonymous_name",
    "decode_small_frames",
    "decode_timestamps",
    "dhash_bits",
    "frame_md5s",
    "hamming",
    "ingest",
    "measure_timing",
    "parse_fps",
    "probe",
    "timeline_hygiene",
    "timing_from_timestamps",
    "verify_generated_clip",
    "write_probe_json",
    "write_timing_json",
]

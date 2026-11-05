"""Measured timing (part 05 §2).

The container's claimed fps is never trusted and never passed to the
agent as fact. ``measure_timing()`` decodes per-frame presentation
timestamps with ffprobe and derives everything from them; the pure
``timing_from_timestamps()`` core is unit-testable without a file.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from .probe import IngestError

__all__ = [
    "VFR_DELTA_SPREAD_THRESHOLD",
    "decode_timestamps",
    "timing_from_timestamps",
    "measure_timing",
]

#: A timestamp sequence counts as variable-frame-rate when the
#: inter-frame spread ``(p95 - p05) / median`` exceeds this fraction.
VFR_DELTA_SPREAD_THRESHOLD = 0.05


def decode_timestamps(video_path: str | Path) -> list[float]:
    """Decode per-frame presentation timestamps (seconds) with ffprobe.

    Raises:
        IngestError: the stream cannot be decoded or yields no stamps.
    """
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise IngestError("unreadable video: required tool 'ffprobe' not found")
    try:
        raw = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "frame=pkt_pts_time,best_effort_timestamp_time",
             "-of", "json", str(video_path)],
            capture_output=True, text=True, timeout=300, check=True,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            OSError) as exc:
        raise IngestError(
            f"unreadable video: timestamp decode failed: {exc}") from exc
    try:
        frames = (json.loads(raw) or {}).get("frames") or []
    except ValueError as exc:
        raise IngestError(
            f"unreadable video: timestamp output unparsable: {exc}") from exc
    stamps: list[float] = []
    for frame in frames:
        text = frame.get("pkt_pts_time",
                         frame.get("best_effort_timestamp_time"))
        try:
            stamps.append(float(text))
        except (TypeError, ValueError):
            raise IngestError(
                "unreadable video: incomplete frame timestamps") from None
    if not stamps:
        raise IngestError("unreadable video: no decodable video frames")
    return stamps


def timing_from_timestamps(timestamps, claimed_fps) -> dict:
    """Build the timing facts from decoded stamps plus the stored claim.

    Args:
        timestamps: Per-frame presentation times in seconds (strictly
            the decoded values; the claim never enters the arithmetic).
        claimed_fps: Container claim, recorded for the discrepancy log
            only (may be None).

    The measured fps is ``1 / median(delta)``; the delta distribution
    (min/p05/median/p95/max) is always reported, and ``vfr`` says
    whether the deltas are irregular (part 05 §2: then downstream code
    must use per-frame stamps, never the single fps number).
    """
    stamps = [float(t) for t in timestamps]
    count = len(stamps)
    if count == 0:
        raise IngestError("unreadable video: no decodable video frames")
    if count == 1:
        return {
            "claimed_fps": claimed_fps,
            "measured_fps": None,
            "delta_s": None,
            "vfr": False,
            "vfr_note": None,
            "frame_count": 1,
            "duration_s": 0.0,
            "timestamps": list(stamps),
        }
    deltas = np.diff(np.asarray(stamps, dtype=float))
    if np.any(~np.isfinite(deltas)) or np.any(deltas <= 0):
        raise IngestError(
            "unreadable video: non-monotonic frame timestamps")
    dist = {
        "min": float(np.min(deltas)),
        "p05": float(np.percentile(deltas, 5)),
        "median": float(np.median(deltas)),
        "p95": float(np.percentile(deltas, 95)),
        "max": float(np.max(deltas)),
    }
    median = dist["median"]
    measured = float(1.0 / median) if median > 0 else None
    spread = (dist["p95"] - dist["p05"]) / median if median > 0 else 0.0
    vfr = bool(spread > VFR_DELTA_SPREAD_THRESHOLD)
    duration = float(stamps[-1] - stamps[0] + median)
    return {
        "claimed_fps": claimed_fps,
        "measured_fps": measured,
        "delta_s": dist,
        "vfr": vfr,
        "vfr_note": ("irregular timestamps: use per-frame timestamps, "
                     "not measured_fps" if vfr else None),
        "frame_count": count,
        "duration_s": duration,
        "timestamps": list(stamps),
    }


def measure_timing(video_path: str | Path,
                   probe_info: dict | None = None) -> dict:
    """Measure one file's timing from decoded frame timestamps.

    Args:
        video_path: The (anonymised copy) to measure.
        probe_info: Optional :func:`probe` result, reused for the claim
            so the container is not probed twice.

    Returns the :func:`timing_from_timestamps` dict.
    """
    from .probe import probe as _probe  # noqa: PLC0415 (lazy: no cycle)

    info = probe_info if probe_info is not None else _probe(video_path)
    stamps = decode_timestamps(video_path)
    return timing_from_timestamps(stamps, info.get("claimed_fps"))

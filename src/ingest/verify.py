"""Generated-clip verification (part 05 §4).

Our own clip tooling is not trusted: every clip this project generates
(clips A and B, part 03) passes the same duplicate check after
generation. The known failure — forcing a constant frame rate during
encoding silently duplicating frames — is avoided by piping raw frames
at the source rate, and the acceptance harness asserts A has zero
confirmed duplicates while B has zero confirmed duplicates and the
same measured fps as A. A generated clip that fails is regenerated,
never analysed. (Generation itself is owned by the part-03
clip-preparation script; the verifier lives here so analysis and
generation share one definition of "duplicate".)
"""
from __future__ import annotations

from pathlib import Path

__all__ = ["FPS_MATCH_REL_TOL", "verify_generated_clip"]

#: Two clips count as "the same measured fps" when their relative
#: difference is within this fraction.
FPS_MATCH_REL_TOL = 0.02


def verify_generated_clip(clip_path: str | Path,
                          expected_fps: float | None = None) -> dict:
    """Verify a generated clip against the shared duplicate definition.

    Args:
        clip_path: Clip to verify (e.g. freshly generated clip A or B).
        expected_fps: When given (clip B vs clip A), the measured fps
            the clip must match within :data:`FPS_MATCH_REL_TOL`.

    Returns a JSON-serialisable dict with ``ok`` (True only with zero
    confirmed duplicates, and a matching fps when one is expected),
    the measured facts, and a fixed-template ``reason`` (None when ok).
    """
    from .hygiene import timeline_hygiene  # noqa: PLC0415 (lazy: no cycle)
    from .measure import measure_timing  # noqa: PLC0415 (lazy: no cycle)

    timing = measure_timing(clip_path)
    hygiene = timeline_hygiene(clip_path, timing)
    measured = timing.get("measured_fps")
    confirmed = hygiene["confirmed_duplicates"]
    reason: str | None = None
    fps_match: bool | None = None
    if confirmed:
        reason = "confirmed_duplicates_present"
    elif expected_fps is not None:
        try:
            want = float(expected_fps)
        except (TypeError, ValueError):
            want = 0.0
        if not want > 0 or measured is None:
            fps_match = False
            reason = "unmeasurable_fps"
        else:
            fps_match = bool(abs(float(measured) - want) / want
                             <= FPS_MATCH_REL_TOL)
            if not fps_match:
                reason = "fps_mismatch"
    return {
        "path": str(clip_path),
        "ok": reason is None,
        "reason": reason,
        "measured_fps": measured,
        "frame_count": timing.get("frame_count"),
        "duration_s": timing.get("duration_s"),
        "confirmed_duplicates": confirmed,
        "confirmed_runs": hygiene["confirmed_runs"],
        "suspect_duplicates": hygiene["suspect_duplicates"],
        "cuts": hygiene["cuts"],
        "expected_fps": expected_fps,
        "fps_match": fps_match,
    }

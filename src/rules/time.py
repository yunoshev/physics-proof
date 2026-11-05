"""R-T time-base checks."""

from __future__ import annotations


def check_t1_time_base(*, uses_measured_timestamps: bool,
                       bare_fps: float | None = None):
    """R-T1: times come from measured timestamps, never a bare fps claim."""
    if uses_measured_timestamps:
        return None
    return ("TIME_BASE_BARE_FPS", "timing",
            "use measured frame timestamps (timing.json), never a bare fps "
            f"argument (got fps={bare_fps})")


def check_t2_fit_frames(*, fitted_frames, confirmed_duplicates,
                        cuts, corrections=None):
    """R-T2: no confirmed duplicates / cuts in a fit without a logged fix.

    ``cuts`` is an iterable of ``(start, end)`` spans (inclusive) that a
    fit window must not cross. ``corrections`` maps an excused frame (or
    ``(start, end)`` cut span) to a log string, e.g. duplicates collapsed
    to one timestamp.
    """
    corrections = corrections or {}
    fitted = set(fitted_frames)
    bad_dups = [f for f in fitted
                if f in set(confirmed_duplicates) and f not in corrections]
    if bad_dups:
        return ("FIT_INCLUDES_CONTACT_OR_DUP", "segments[].frames",
                f"fitted frames include confirmed duplicates {sorted(bad_dups)} "
                "without a logged correction")
    for (start, end) in cuts:
        if (start, end) in corrections:
            continue
        crossed = sorted(f for f in fitted if start <= f <= end)
        if crossed:
            return ("FIT_INCLUDES_CONTACT_OR_DUP", "segments[].frames",
                    f"fit window crosses a cut [{start}, {end}] "
                    f"(frames {crossed}); never fit across a cut")
    return None

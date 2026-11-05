"""R-C clock checks and R-C4 arithmetic."""

from __future__ import annotations


def check_rc2_in_band(*, rate_hz: float | None, band_hz, no_clock: bool = False):
    """R-C2: the helper never returns a frequency outside the band."""
    if no_clock:
        return None
    if rate_hz is None:
        return ("CLOCK_BAND_EDGE", "clock.rate_hz",
                "peak at the band edge is 'no reliable clock', not a number")
    lo, hi = band_hz
    if lo <= rate_hz <= hi:
        return None
    return ("CLOCK_OUT_OF_BAND", "clock.rate_hz",
            f"rate {rate_hz} Hz outside the stated band [{lo}, {hi}] Hz")


def check_rc3_ambiguity(*, ambiguous: bool, verdict_changes: bool,
                        picked_single: bool):
    """R-C3: step/stride ambiguity that changes the verdict ⇒ undetermined."""
    if ambiguous and verdict_changes and picked_single:
        return ("CLOCK_AMBIGUOUS", "clock",
                "helper flagged step-vs-stride ambiguity and the pick "
                "changes the verdict: the honest output is undetermined")
    return None


def check_rc4_natural_range(*, natural_range, source: str | None):
    """R-C4: a clock needs a stated natural range with its source."""
    if not natural_range or not source:
        return ("CLOCK_RANGE_MISSING", "clock.natural_range",
                "clock evidence without a stated natural range + source "
                "is rejected")
    lo, hi = natural_range
    if lo is None or hi is None or lo >= hi:
        return ("CLOCK_RANGE_MISSING", "clock.natural_range",
                "natural range must be [lo, hi] with lo < hi")
    return None


def implied_true_rate(*, measured_hz: float, slowdown_k: float) -> float:
    """R-C4: true rate = k × measured rate (measured = true ÷ s)."""
    return slowdown_k * measured_hz

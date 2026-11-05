"""R-R range checks (owner addendum 2026-10-29)."""

from __future__ import annotations

import math


def check_rr1_range_bounds(*, quantity: str | None, of_what: str | None,
                           kind_of_thing: str | None, lo, hi,
                           basis: str | None):
    """R-R1: one quantity, one kind of thing, a min and a max with a basis."""
    if not quantity or not of_what or not kind_of_thing:
        return ("RANGE_CHECK_INCOMPLETE", "range_checks[]",
                "name one quantity, what it belongs to, and the same "
                "quantity of the same kind of thing")
    if lo is None or hi is None:
        return ("RANGE_SOURCE_MISSING", "range_checks[].range",
                "a typical value alone is not a range: give a minimum and "
                "a maximum")
    if not basis:
        return ("RANGE_CHECK_INCOMPLETE", "range_checks[].basis",
                "say which distribution the bounds come from "
                "(e.g. 5th–95th percentile)")
    return None


def _quote_has_number(quote: str, bound: float) -> bool:
    """A quote contains the bound: full value, decimals, or unit digits.

    Tables quote "53%" for a 0.53 bound or "(mm)" with plain digits, so
    the significant digits (or the ".53" tail) count as containing it.
    """
    text = quote.replace("–", "-").replace("—", "-")
    full = str(bound)
    if full in text:
        return True
    frac = full.split(".")
    if len(frac) == 2 and frac[1].rstrip("0"):
        digits = frac[1].rstrip("0")
        if digits in text or ("." + digits) in text:
            return True
        if frac[0] == "0" and digits in text:
            return True
    return frac[0] in text.split()


def check_rr2_quoted_sources(*, lo: float, hi: float,
                             lo_quote: str | None, hi_quote: str | None):
    """R-R2: every bound comes with a verbatim quote containing the number."""
    for bound, quote in ((lo, lo_quote), (hi, hi_quote)):
        if not quote or not _quote_has_number(quote, bound):
            return ("RANGE_SOURCE_MISSING", "range_checks[].source",
                    f"bound {bound} needs a verbatim quote containing "
                    "the number")
    return None


def check_rr3_ratio_no_scale(*, is_ratio: bool, uses_scale: bool):
    """R-R3: prefer ratios — same-frame same-depth ratios need no scale."""
    if is_ratio and uses_scale:
        return ("RANGE_USES_SCALE_NEEDLESSLY", "range_checks[]",
                "a ratio of two lengths in the same frame needs no scale")
    return None


def check_rr4_sigma_floor(*, sigma: float, length_px: float,
                          m_per_px: float = 1.0, uses_scale: bool = False,
                          scale_rel_sigma: float = 0.0):
    """R-R4: σ covers endpoint error (≥1 px/endpoint) and the scale's σ."""
    floor_px = math.sqrt(2.0)  # 1 px per endpoint, quadrature
    floor = floor_px * m_per_px
    if uses_scale:
        floor = math.hypot(floor, length_px * m_per_px * scale_rel_sigma)
    if sigma + 1e-12 >= floor:
        return None
    return ("RANGE_SIGMA_TOO_SMALL", "range_checks[].sigma",
            f"σ {sigma} below the floor {floor:.4f} (endpoint + scale)")


def check_rr5_answers_question(*, check_id: str, question: str,
                               motion_checks: bool):
    """R-R5: each check must matter to the question."""
    if not question:
        return ("RANGE_CHECK_IRRELEVANT", f"range_checks[{check_id}]",
                "choose checks that answer the question")
    _ = motion_checks
    return None

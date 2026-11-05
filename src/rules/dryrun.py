"""Dry-run pushes (part 08 addendum, part 11 §16).

Three easy exits the dry run rejects while there is still time to do
better. A real submit still accepts them as undetermined. These codes
appear only in a dry run, and they make the dry run not clean.
Compatibility module: the push helpers live in :mod:`src.rules.budget`
and are re-exported here under the historical names.
"""

from __future__ import annotations

from .budget import (
    PUSH_CODES,
    push_clock_required,
    push_motions_scan,
    push_second_reference,
)

__all__ = [
    "MOTIONS_SCAN_SPACING_S",
    "PUSH_CODES",
    "push_clock",
    "push_motions_scan",
    "push_second_reference",
]

#: R-M4: the whole clip must be viewed at most at this spacing.
MOTIONS_SCAN_SPACING_S = 0.25


def push_clock(*, g_fits_any_world: bool, has_clock: bool):
    """Alias for :func:`src.rules.budget.push_clock_required`."""
    return push_clock_required(g_fits_any_world=g_fits_any_world,
                               has_clock=has_clock)

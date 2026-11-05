"""R-E honest error budget + dry-run pushes."""

from __future__ import annotations

import math

#: Always-required budget components (R-E1).
REQUIRED_COMPONENTS = (
    "reference_size",
    "pixel_scale",
    "fit",
    "point_vs_com",
)

#: Dry-run-only pushes (part 11 §16): easy exits blocked while time remains.
PUSH_CODES = (
    "SECOND_REFERENCE_REQUIRED",
    "CLOCK_REQUIRED",
    "MOTIONS_SCAN_MISSING",
)


def check_re1_sigma(*, components: dict, reading_spread: float = 0.0,
                    sigma_total: float):
    """R-E1: σ is the quadrature sum (+ reading spread); never below a part."""
    missing = [c for c in REQUIRED_COMPONENTS if c not in components]
    if missing:
        return ("ERROR_BUDGET_INCOMPLETE", "error_budget",
                f"missing components: {missing}")
    values = [components[c] for c in REQUIRED_COMPONENTS]
    recomputed = math.sqrt(sum(v ** 2 for v in values) + reading_spread ** 2)
    if sigma_total + 1e-12 < max(values + ([reading_spread] if reading_spread else [])):
        return ("ERROR_BUDGET_TOO_SMALL", "error_budget.sigma",
                f"σ {sigma_total} is smaller than a single component")
    if sigma_total + 1e-12 < recomputed:
        return ("ERROR_BUDGET_TOO_SMALL", "error_budget.sigma",
                f"σ {sigma_total} is smaller than the quadrature total "
                f"{recomputed:.4f}")
    return None


def check_re2_independent_repetitions(*, residuals_list) -> object | None:
    """R-E2: repetitions are fitted independently (no copy-paste)."""
    seen = []
    for i, residuals in enumerate(residuals_list):
        key = tuple(residuals)
        if key in seen:
            return ("REPETITION_RESIDUALS_IDENTICAL", f"segments[{i}]",
                    "identical residuals: repetitions must be fitted "
                    "independently, never copy-pasted")
        seen.append(key)
    return None


def check_re3_no_cross_run(*, text_fields):
    """R-E3: nothing in a submission references another run's measurements."""
    blob = " ".join(text_fields).lower()
    for marker in ("other run", "run-id", "clip b", "compared with run"):
        if marker in blob:
            return ("CROSS_RUN_REFERENCE", "submission",
                    "cross-clip ratio is a cross-check for the harness, "
                    "never part of a submission")
    return None


def push_second_reference(*, n_references: int):
    """Dry-run push: one reference must try for a second (R-S6)."""
    if n_references >= 2:
        return None
    return ("SECOND_REFERENCE_REQUIRED", "references",
            "measure a second thing of independently known size at the "
            "depth of the motion: the moving thing itself, something it "
            "wears or carries, or a fixed thing beside it (R-S6)")


def push_clock_required(*, g_fits_any_world: bool, has_clock: bool):
    """Dry-run push: g fits no world and there is no clock (R-C1)."""
    if g_fits_any_world or has_clock:
        return None
    return ("CLOCK_REQUIRED", "clock",
            "any repeating motion is a clock candidate (steps, swings, "
            "wing beats, turning wheels): measure its rate (R-C1)")


def push_motions_scan(*, viewed_every_0_25s: bool):
    """Dry-run push: the whole clip was not viewed at ≤0.25 s spacing."""
    if viewed_every_0_25s:
        return None
    return ("MOTIONS_SCAN_MISSING", "first_look.motions",
            "view the whole clip at a spacing of at most 0.25 s (R-M4)")

# generated from brief/09 · part 09 owns this file
"""Range-check building blocks (part 09 §7).

Part 11 checks every range check the hard way (``RANGE_EXTENT_NOT_ON_MASK``,
``RANGE_FORMULA_MISMATCH``, ``RANGE_SIGMA_TOO_SMALL``,
``RANGE_NUMBER_WITHOUT_PROVENANCE``); this module makes the right numbers
the easy ones. Pure functions over numpy arrays and plain values — no model
calls, no network — with no I/O except printing (so the ``run_python`` call
that prints a check is the check's ``measurement_artifact``).

Time is never involved here; image coordinates grow downward in pixels,
and a length is a pixel distance until :func:`range_value` applies the
scale.
"""

from __future__ import annotations

import json
import math

__all__ = [
    "mask_extent",
    "range_value",
    "print_check",
]


def _as_mask(mask):
    """A 2-D bool array, or ``ValueError`` (``"bad_mask"``)."""
    import numpy as np

    arr = np.asarray(mask)
    if arr.ndim != 2:
        raise ValueError(
            f"bad_mask: need a 2-D mask, got {arr.ndim}-D")
    return arr.astype(bool)


def _as_direction(direction):
    """A normalised ``(dx, dy)`` image-coordinate vector.

    Raises ``ValueError`` (``"bad_direction"``) on anything that is not
    two finite numbers with a nonzero length.
    """
    try:
        dx, dy = (float(v) for v in direction)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_direction: direction must be (dx, dy) numbers, "
            f"got {direction!r}: {exc}") from exc
    if not (math.isfinite(dx) and math.isfinite(dy)):
        raise ValueError(
            f"bad_direction: direction must be finite, got "
            f"{direction!r}")
    norm = math.hypot(dx, dy)
    if norm <= 0.0:
        raise ValueError(
            f"bad_direction: direction must be nonzero, got "
            f"{direction!r}")
    return dx / norm, dy / norm


def _principal_direction(xs, ys):
    """The mask's principal axis: first right-singular vector of the
    centred ``(x, y)`` pixel cloud (an unsigned direction)."""
    import numpy as np

    cloud = np.stack([np.asarray(xs, dtype=float) - float(np.mean(xs)),
                      np.asarray(ys, dtype=float) - float(np.mean(ys))],
                     axis=1)
    if not bool((cloud ** 2).sum() > 0.0):
        return 1.0, 0.0
    _, _, vt = np.linalg.svd(cloud, full_matrices=False)
    dx, dy = float(vt[0, 0]), float(vt[0, 1])
    norm = math.hypot(dx, dy)
    if norm <= 0.0:
        return 1.0, 0.0
    return dx / norm, dy / norm


def mask_extent(mask, direction=None):
    """The two mask pixels farthest apart along ``direction``.

    Returns ``{"x1", "y1", "x2", "y2", "length_px"}``: integer pixel
    coordinates of both endpoints and their Euclidean distance. Both
    endpoints are mask pixels by construction — the pair of True
    pixels maximising the projected distance along ``direction`` — so
    a check built from them passes part 11's
    ``RANGE_EXTENT_NOT_ON_MASK`` on geometry alone.

    ``direction`` is a unit vector ``(dx, dy)`` in image coordinates
    (``y`` grows downward), such as ``(0, 1)`` for a vertical extent.
    With ``None`` the mask's principal axis (first principal
    component of the pixel cloud) is used.

    Raises ``ValueError`` (``"empty_mask"``) on an empty mask and
    ``ValueError`` (``"bad_direction"`` / ``"bad_mask"``) on an
    unusable direction or input.
    """
    import numpy as np

    hit = _as_mask(mask)
    ys, xs = np.nonzero(hit)
    if len(xs) == 0:
        raise ValueError("empty_mask: mask_extent needs a nonempty mask")
    if direction is None:
        dx, dy = _principal_direction(xs, ys)
    else:
        dx, dy = _as_direction(direction)
    projection = (xs.astype(float) * dx + ys.astype(float) * dy)
    first = int(np.argmin(projection))
    last = int(np.argmax(projection))
    x1, y1 = int(xs[first]), int(ys[first])
    x2, y2 = int(xs[last]), int(ys[last])
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "length_px": float(math.hypot(x2 - x1, y2 - y1))}


def _as_extent(extent, pos):
    """A ``(name, length_px)`` pair, or ``ValueError`` naming the field."""
    if not isinstance(extent, dict):
        raise ValueError(
            f"bad_extent: extents[{pos}] must be a mapping, got "
            f"{extent!r}")
    name = extent.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(
            f"bad_extent: extents[{pos}].name is missing: each extent "
            f"needs a short name (the formula quotes it)")
    try:
        length = float(extent.get("length_px"))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_extent: extents[{pos}].length_px is missing or not a "
            f"number: {exc}") from exc
    if not math.isfinite(length) or length <= 0:
        raise ValueError(
            f"bad_extent: extents[{pos}].length_px must be a positive "
            f"number, got {extent.get('length_px')!r}")
    return name.strip(), length


def range_value(kind, extents, m_per_px=None, m_per_px_sigma=None):
    """A range-check value recomputed exactly as part 11 §20 does.

    Returns ``{"value", "sigma", "formula", "uses_scale"}``:

    - ``kind="ratio"`` takes two extents: ``value`` is
      ``extents[0].length_px / extents[1].length_px`` and ``formula``
      is ``"<name0>_px / <name1>_px"`` (for example ``"palm_px /
      hand_px"``);
    - ``kind="length"`` takes one extent and the scale: ``value`` is
      ``length_px × m_per_px`` and ``formula`` is ``"length_px ×
      m_per_px"``.

    ``sigma`` propagates 1 px per endpoint (``√2`` px per extent, in
    quadrature over the extents), plus the scale's relative ``σ`` for
    a length — the same floor part 11's ``RANGE_SIGMA_TOO_SMALL``
    demands, so a value built here clears it by construction.

    Raises ``ValueError`` (``"bad_kind"``) on another kind,
    ``ValueError`` (``"bad_extent"``) on a missing or unusable
    extent, and ``ValueError`` (``"bad_scale"``) on a missing or
    unusable scale for a length.
    """
    if kind == "ratio":
        items = list(extents or [])
        if len(items) != 2:
            raise ValueError(
                f"bad_extent: kind 'ratio' needs two extents, got "
                f"{len(items)}")
        (name0, first), (name1, second) = (_as_extent(items[0], 0),
                                           _as_extent(items[1], 1))
        value = first / second
        rel_sq = ((math.sqrt(2.0) / first) ** 2
                  + (math.sqrt(2.0) / second) ** 2)
        return {"value": float(value),
                "sigma": float(abs(value) * math.sqrt(rel_sq)),
                "formula": f"{name0}_px / {name1}_px",
                "uses_scale": False}
    if kind == "length":
        items = list(extents or [])
        if len(items) != 1:
            raise ValueError(
                f"bad_extent: kind 'length' needs one extent, got "
                f"{len(items)}")
        _name, length = _as_extent(items[0], 0)
        try:
            scale = float(m_per_px)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"bad_scale: kind 'length' needs m_per_px, got "
                f"{m_per_px!r}: {exc}") from exc
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError(
                f"bad_scale: m_per_px must be a positive number, got "
                f"{m_per_px!r}")
        spread = 0.0 if m_per_px_sigma is None else m_per_px_sigma
        try:
            spread = float(spread)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"bad_scale: m_per_px_sigma must be a number, got "
                f"{m_per_px_sigma!r}: {exc}") from exc
        if not math.isfinite(spread) or spread < 0:
            raise ValueError(
                f"bad_scale: m_per_px_sigma must be non-negative, got "
                f"{m_per_px_sigma!r}")
        value = length * scale
        rel_sq = ((math.sqrt(2.0) / length) ** 2
                  + (spread / scale) ** 2)
        return {"value": float(value),
                "sigma": float(abs(value) * math.sqrt(rel_sq)),
                "formula": "length_px × m_per_px",
                "uses_scale": True}
    raise ValueError(
        f"bad_kind: kind must be 'ratio' or 'length', got {kind!r}")


def print_check(item):
    """Print a range check as one JSON line, and return that line.

    Every number the evidence cites — the value, its σ and every
    extent endpoint — is in the printed line, so the ``run_python``
    call that prints it is the check's ``measurement_artifact`` and
    part 11's ``RANGE_NUMBER_WITHOUT_PROVENANCE`` is satisfied by
    construction. Keys are sorted for stable output.
    """
    if not isinstance(item, dict):
        raise ValueError(
            f"bad_check: print_check needs a mapping, got "
            f"{type(item).__name__}")
    line = json.dumps(item, sort_keys=True)
    print(line, flush=True)
    return line

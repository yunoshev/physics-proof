# owned by part 09 · tests for src/helpers/ranges.py
"""Synthetic known-answer tests for the range-check builders."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from src.helpers.ranges import mask_extent, print_check, range_value


def _rectangle(rows=10, cols=30, top=10, left=20):
    """A filled ``rows`` × ``cols`` rectangle on a padded canvas."""
    mask = np.zeros((top + rows + 10, left + cols + 10), dtype=bool)
    mask[top:top + rows, left:left + cols] = True
    return mask, top, left


def test_mask_extent_rectangle_corners_along_axis():
    """A vertical extent spans the rectangle's top and bottom rows."""
    mask, top, left = _rectangle(rows=20, cols=30)
    extent = mask_extent(mask, (0, 1))
    assert extent["y1"] == top
    assert extent["y2"] == top + 20 - 1
    assert extent["length_px"] == pytest.approx(20 - 1)
    assert mask[extent["y1"], extent["x1"]]
    assert mask[extent["y2"], extent["x2"]]


def test_mask_extent_horizontal_axis():
    """A horizontal extent spans the rectangle's left/right columns."""
    mask, top, left = _rectangle(rows=20, cols=30)
    extent = mask_extent(mask, (1, 0))
    assert extent["x1"] == left
    assert extent["x2"] == left + 30 - 1
    assert extent["length_px"] == pytest.approx(30 - 1)


def test_mask_extent_disc_diameter_within_one_px():
    """A disc's extent is its diameter, within 1 px, on mask pixels."""
    radius = 40
    size = 2 * radius + 11
    centre = size // 2
    grid = np.arange(size)
    disc = ((grid[:, None] - centre) ** 2
            + (grid[None, :] - centre) ** 2 <= radius ** 2)
    extent = mask_extent(disc, (1, 0))
    assert extent["length_px"] == pytest.approx(2 * radius, abs=1.0)
    assert disc[extent["y1"], extent["x1"]]
    assert disc[extent["y2"], extent["x2"]]


def test_mask_extent_principal_axis_without_direction():
    """With no direction the long axis of a bar is measured."""
    mask = np.zeros((30, 120), dtype=bool)
    mask[10:20, 10:100] = True
    extent = mask_extent(mask)
    assert extent["length_px"] == pytest.approx(90 - 1, abs=1.5)
    assert mask[extent["y1"], extent["x1"]]
    assert mask[extent["y2"], extent["x2"]]


def test_mask_extent_empty_mask_raises():
    """An empty mask raises, never a zero-length extent."""
    with pytest.raises(ValueError, match="empty_mask"):
        mask_extent(np.zeros((8, 8), dtype=bool), (0, 1))
    with pytest.raises(ValueError, match="bad_direction"):
        mask_extent(np.ones((4, 4), dtype=bool), (0, 0))


def _check_for(extents, value, sigma, uses_scale):
    """A minimal part-11 range check around the built numbers."""
    return {"value": value, "sigma": sigma, "extents": extents,
            "uses_scale": uses_scale}


def test_range_value_ratio_matches_part11_recompute():
    """``ratio`` recomputes as part 11 does, and clears its σ floor."""
    from src.validate.ranges import (_recomputed_value,
                                    _required_sigma)

    first = {"name": "palm", "length_px": 200.0}
    second = {"name": "hand", "length_px": 100.0}
    built = range_value("ratio", [first, second])
    assert built["value"] == pytest.approx(2.0)
    assert built["formula"] == "palm_px / hand_px"
    assert built["uses_scale"] is False
    check = _check_for([first, second], built["value"],
                       built["sigma"], built["uses_scale"])
    recomputed = _recomputed_value(check, None)
    options = (recomputed if isinstance(recomputed, tuple)
               else (recomputed,))
    assert any(abs(guess - built["value"]) / abs(built["value"])
               <= 0.02 for guess in options)
    required = _required_sigma(check, None, None)
    assert required is not None
    assert built["sigma"] + 1e-12 >= required


def test_range_value_length_matches_part11_recompute():
    """``length`` scales one extent, with the scale's σ propagated."""
    from src.validate.ranges import (_recomputed_value,
                                    _required_sigma)

    extent = {"name": "hand", "length_px": 150.0}
    built = range_value("length", [extent], m_per_px=0.01,
                        m_per_px_sigma=0.0005)
    assert built["value"] == pytest.approx(1.5)
    assert built["formula"] == "length_px × m_per_px"
    assert built["uses_scale"] is True
    check = _check_for([extent], built["value"], built["sigma"],
                       built["uses_scale"])
    assert _recomputed_value(check, 0.01) == pytest.approx(1.5)
    required = _required_sigma(check, 0.01, 0.0005)
    assert required is not None
    assert built["sigma"] + 1e-12 >= required
    # A hand recompute carries the same floor: endpoint error plus
    # the scale's relative error.
    expect = abs(built["value"]) * math.sqrt(
        (math.sqrt(2.0) / 150.0) ** 2 + (0.0005 / 0.01) ** 2)
    assert built["sigma"] == pytest.approx(expect)


def test_range_value_rejects_bad_inputs():
    """Wrong kinds, counts and scales raise coded errors."""
    good = {"name": "hand", "length_px": 150.0}
    with pytest.raises(ValueError, match="bad_kind"):
        range_value("area", [good])
    with pytest.raises(ValueError, match="bad_extent"):
        range_value("ratio", [good])
    with pytest.raises(ValueError, match="bad_extent"):
        range_value("length", [{**good, "length_px": 0.0}],
                    m_per_px=0.01)
    with pytest.raises(ValueError, match="bad_scale"):
        range_value("length", [good])


def test_print_check_emits_every_number_on_one_line(capsys):
    """The printed line carries the value, σ and every endpoint."""
    item = {"value": 1.5, "sigma": 0.08, "formula": "length_px × m_per_px",
            "uses_scale": True,
            "extents": [{"name": "hand", "x1": 10, "y1": 20,
                         "x2": 10, "y2": 170, "length_px": 150.0,
                         "frame": 3}]}
    line = print_check(item)
    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert json.loads(out.strip()) == json.loads(line) == item
    for number in ("1.5", "0.08", "150.0"):
        assert number in out

# owned by part 09 · tests for src/helpers/clock.py
"""Synthetic known-answer tests for the gait signal and step clock."""

from __future__ import annotations

import numpy as np
import pytest

from src.helpers.clock import clock_evidence, gait_signal, step_rate

FPS = 30.0


def _walker(widths, height=100, pad=20):
    """One centred rectangle per frame, with the given widths."""
    masks = {}
    rows = int(height + 2 * pad)
    widest = int(max(widths)) + 2 * pad
    for frame, width in enumerate(widths):
        mask = np.zeros((rows, widest), dtype=bool)
        half = int(round(width)) // 2
        cx = widest // 2
        mask[pad:pad + height, cx - half:cx + half] = True
        masks[frame] = mask
    return masks


def _planted_gait(rate_hz=2.0, seconds=6.0, trend=14.0, seed=3):
    """Width oscillation at the planted rate over a perspective trend."""
    n = int(seconds * FPS)
    t = np.arange(n) / FPS
    rng = np.random.default_rng(seed)
    widths = (30.0 + 12.0 * np.sin(2.0 * np.pi * rate_hz * t)
              + trend * t / seconds
              + rng.normal(0.0, 0.3, n))
    return t, widths


def test_gait_signal_measures_lowest_width_over_height():
    """The signal is the lowest-30% width divided by mask height."""
    masks = _walker([30, 40, 30])
    rows = gait_signal(masks)
    assert [r["frame"] for r in rows] == [0, 1, 2]
    assert rows[1]["gait"] > rows[0]["gait"] > 0
    assert rows[0]["gait"] == pytest.approx(rows[2]["gait"])
    assert rows[0]["gait"] == pytest.approx(30.0 / 100.0, abs=0.05)


def test_gait_signal_empty_mask_raises():
    """An empty frame raises empty_mask, never a zero width."""
    with pytest.raises(ValueError, match="empty_mask"):
        gait_signal({0: np.zeros((10, 10), dtype=bool)})


def test_step_rate_returns_planted_rate_in_band():
    """A detrended in-band gait returns the planted rate and the pair."""
    t, widths = _planted_gait()
    signal = [r["gait"] for r in gait_signal(_walker(widths))]
    result, flag = step_rate(signal, t, (1.0, 4.0))
    assert flag is None
    assert result["peak_hz"] == pytest.approx(2.0, abs=0.3)
    assert result["as_step_hz"] == pytest.approx(result["peak_hz"])
    assert result["as_stride_hz"] == pytest.approx(
        result["peak_hz"] / 2.0)
    assert result["alt_step_hz"] == pytest.approx(
        result["peak_hz"] * 2.0)
    evidence = result["harmonic_evidence"]
    assert set(evidence) == {"power_at_peak", "power_at_double",
                             "power_at_half", "ratio_double",
                             "ratio_half"}
    assert all(v >= 0 for v in evidence.values())


def test_band_edge_returns_no_reliable_clock():
    """A peak on the lowest in-band bin is not clamped into a number."""
    n = 120
    t = np.arange(n) / FPS
    freqs = np.fft.rfftfreq(n, d=1.0 / FPS)
    inside = [f for f in freqs if 1.0 < f < 4.0]
    edge = min(inside)
    signal = list(np.sin(2.0 * np.pi * edge * t))
    result, flag = step_rate(signal, t, (1.0, 4.0))
    assert result is None
    assert flag == "no_reliable_clock"


def test_step_rate_rejects_bad_inputs():
    """Short, non-increasing, badly banded and unresolvable inputs."""
    t = np.arange(120) / FPS
    signal = list(np.sin(2.0 * np.pi * 2.0 * t))
    with pytest.raises(ValueError, match="short_signal"):
        step_rate([1.0] * 7, list(range(7)))
    with pytest.raises(ValueError, match="bad_timebase"):
        step_rate(signal, [0.0] * 120)
    with pytest.raises(ValueError, match="bad_band"):
        step_rate(signal, t, (4.0, 1.0))
    # One sample per second cannot place a bin strictly inside 1–4 Hz.
    with pytest.raises(ValueError, match="peak_at_band_edge"):
        step_rate(list(np.sin(np.arange(8, dtype=float))),
                  [float(i) for i in range(8)], (1.0, 4.0))


def _planted_rate():
    """A step_rate result from the synthetic gait at 2 Hz."""
    t, widths = _planted_gait()
    signal = [r["gait"] for r in gait_signal(_walker(widths))]
    result, flag = step_rate(signal, t, (1.0, 4.0))
    assert flag is None
    return result


def _source():
    return {"url": "https://example.test/survey",
            "quote": "adults step at 1 to 2 Hz"}


def test_clock_evidence_builds_contract_clock():
    """The built object is exactly part 12's evidence clock shape."""
    from src.contract import load_evidence_schema

    result = _planted_rate()
    clock = clock_evidence(result, "width of the lowest thirty percent "
                           "of the mask over height, sampled per frame",
                           "step", [1.0, 2.0], _source(), [1.0, 4.0],
                           180, "step_rate")
    schema = load_evidence_schema()["properties"]["clock"]
    branch = next(option for option in schema["anyOf"]
                  if option.get("type") == "object")
    assert set(clock) == set(branch["required"])
    assert clock["interpretation"] == "step"
    assert clock["measured_rate_hz"] == pytest.approx(
        result["as_step_hz"])
    assert clock["measured_rate_sigma_hz"] > 0
    assert clock["band_hz"] == [1.0, 4.0]
    assert clock["natural_range_hz"] == [1.0, 2.0]
    assert clock["natural_range_source"] == _source()


def test_clock_evidence_converts_min_max_range():
    """A {min, max} natural range becomes [lo, hi] (wall runs 9/10)."""
    result = _planted_rate()
    clock = clock_evidence(result, "lowest-30%-percent width signal",
                           "stride", {"min": 1.0, "max": 2.0},
                           _source(), {"min": 1.0, "max": 4.0},
                           180, "step_rate")
    assert clock["natural_range_hz"] == [1.0, 2.0]
    assert clock["band_hz"] == [1.0, 4.0]
    assert clock["measured_rate_hz"] == pytest.approx(
        result["as_stride_hz"])
    assert set(clock) == {"signal_description", "measured_rate_hz",
                          "measured_rate_sigma_hz", "interpretation",
                          "band_hz", "natural_range_hz",
                          "natural_range_source"}


def test_clock_evidence_names_missing_fields():
    """Each missing argument raises naming that field."""
    result = _planted_rate()
    good = dict(signal_description="lowest-30% width signal",
                interpretation="step", natural_range_hz=[1.0, 2.0],
                natural_range_source=_source(), band_hz=[1.0, 4.0],
                window_frames=180, method="step_rate")
    with pytest.raises(ValueError, match="signal_description"):
        clock_evidence(result, None, **{k: v for k, v in good.items()
                                        if k != "signal_description"})
    with pytest.raises(ValueError, match="interpretation"):
        clock_evidence(result, **{**good, "interpretation": "leap"})
    with pytest.raises(ValueError, match="natural_range_hz"):
        clock_evidence(result, **{**good, "natural_range_hz": None})
    with pytest.raises(ValueError, match="natural_range_source"):
        clock_evidence(result, **{**good,
                                  "natural_range_source": {"url": "",
                                                           "quote": ""}})
    with pytest.raises(ValueError, match="band_hz"):
        clock_evidence(result, **{**good, "band_hz": None})
    with pytest.raises(ValueError, match="window_frames"):
        clock_evidence(result, **{**good, "window_frames": 0})
    with pytest.raises(ValueError, match="method"):
        clock_evidence(result, **{**good, "method": "  "})
    with pytest.raises(ValueError, match="no_reliable_clock"):
        clock_evidence(None, **good)
    with pytest.raises(ValueError, match="interpretation"):
        clock_evidence(result, **{**good, "interpretation": None})


def test_clock_evidence_never_promotes_an_edge_peak():
    """The (result, flag) pair with an edge flag raises, not a clock."""
    n = 120
    t = np.arange(n) / FPS
    freqs = np.fft.rfftfreq(n, d=1.0 / FPS)
    edge = min(f for f in freqs if 1.0 < f < 4.0)
    pair = step_rate(list(np.sin(2.0 * np.pi * edge * t)), t,
                     (1.0, 4.0))
    assert pair[1] == "no_reliable_clock"
    with pytest.raises(ValueError, match="no_reliable_clock"):
        clock_evidence(pair, "lowest-30% width signal", "step",
                       [1.0, 2.0], _source(), [1.0, 4.0], n,
                       "step_rate")

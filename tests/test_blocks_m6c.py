"""M6c probes: gait_signal + step_rate edge handling (all offline)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from physics_proof.blocks import gait_signal, step_rate


def walker_masks(
    n: int = 96, fps: float = 24.0, f: float = 3.5, shrink: bool = True
) -> np.ndarray:
    """Two-leg stick figure walking at f steps/s, shrinking 2x + panning.

    Feet scissor in anti-phase at the stride rate f/2, so the leg spread
    peaks once per step at f. With shrink, scale s(t) goes 1 -> 0.5
    (receding) and the figure drifts (panning camera); without shrink the
    figure keeps a fixed size and place. Returns bool [N, H, W] masks.
    """
    H, W = 120, 160
    masks = np.zeros((n, H, W), dtype=bool)
    yy, xx = np.mgrid[0:H, 0:W]
    for i in range(n):
        t = i / fps
        s = 1.0 - 0.5 * i / (n - 1) if shrink else 1.0
        cx = 70.0 + (25.0 * i / (n - 1) if shrink else 0.0)
        feet_y = 82.0 + (15.0 * i / (n - 1) if shrink else 0.0)
        leg = 38.0 * s
        hip_y = feet_y - leg
        d = 13.0 * s * math.sin(math.pi * f * t)
        r = max(1.0, 2.5 * s)
        frame = np.zeros((H, W), dtype=bool)
        for fx in (cx - d, cx + d):
            for u in np.linspace(0, 1, 24):
                px = cx + (fx - cx) * u
                py = hip_y + (feet_y - hip_y) * u
                frame |= (yy - py) ** 2 + (xx - px) ** 2 <= r * r
        torso_w, torso_h = 5.0 * s, 30.0 * s
        frame |= (np.abs(xx - cx) <= torso_w) & (np.abs(yy - (hip_y - torso_h / 2)) <= torso_h / 2)
        head_r = max(1.5, 6.0 * s)
        head_y = hip_y - torso_h - head_r + 1.0 * s
        frame |= (yy - head_y) ** 2 + (xx - cx) ** 2 <= head_r * head_r
        masks[i] = frame
    return masks


# Probe 1: receding + panning walker at 3.5 steps/s recovers 3.5.
def test_gait_receding_pan_step_rate() -> None:
    fps, f, n = 24.0, 3.5, 96
    masks = walker_masks(n, fps, f)
    assert masks.shape == (n, 120, 160)
    g = gait_signal(masks)
    assert g.shape == (n,)
    assert np.all(np.isfinite(g))
    assert float(g.max() - g.min()) > 0.05
    out = step_rate(g, fps)
    assert out["edge"] is False
    assert abs(out["hz"] - f) <= out["hz_err"]
    assert out["period_frames"] == pytest.approx(fps / out["hz"])
    assert out["peak_ratio"] > 10.0


def test_gait_receding_pan_short_window() -> None:
    # Same check on 62 frames, the maintainer's run-up length.
    fps, f, n = 24.0, 3.5, 62
    g = gait_signal(walker_masks(n, fps, f))
    assert np.all(np.isfinite(g))
    out = step_rate(g, fps)
    assert out["edge"] is False
    assert abs(out["hz"] - f) <= out["hz_err"]


def test_gait_scale_invariant() -> None:
    fps, f, n = 24.0, 3.5, 96
    moving = gait_signal(walker_masks(n, fps, f, shrink=True))
    still = gait_signal(walker_masks(n, fps, f, shrink=False))
    assert np.corrcoef(moving, still)[0, 1] > 0.9


# Probe 2: a pure trend reports edge, with finite in-band values.
@pytest.mark.parametrize("trend", ["ramp", "perspective", "constant"])
def test_step_rate_pure_trend_edge(trend: str) -> None:
    n = 62
    if trend == "ramp":
        series = np.linspace(0.0, 10.0, n)
    elif trend == "perspective":
        series = 1.0 / (1.0 + np.arange(n) / 40.0)
    else:
        series = np.full(n, 5.0)
    out = step_rate(series, 24.0)
    assert out["edge"] is True
    assert 1.0 <= out["hz"] <= 8.0
    assert math.isfinite(out["hz"]) and out["hz"] > 0
    assert math.isfinite(out["period_frames"]) and out["period_frames"] > 0
    assert math.isfinite(out["peak_ratio"]) or out["peak_ratio"] == float("inf")


def test_step_rate_hz_never_leaves_band() -> None:
    rng = np.random.default_rng(7)
    fps, n = 24.0, 72
    t = np.arange(n) / fps
    for series in [
        np.linspace(0.0, 5.0, n) + 0.5 * np.sin(2 * np.pi * 3.5 * t),
        3.0 * np.exp(-t / 2.0),
        rng.standard_normal(n).cumsum(),
    ]:
        for detrend in ("median", "quadratic"):
            out = step_rate(series, fps, detrend=detrend)  # type: ignore[arg-type]
            assert 1.0 <= out["hz"] <= 8.0, (series[:3], detrend, out)
            assert math.isfinite(out["period_frames"]) and out["period_frames"] > 0


# Probe 3: old quadratic behaviour still available; M6b sine still passes.
def test_step_rate_quadratic_detrend_kept() -> None:
    rng = np.random.default_rng(11)
    fps, f0, n = 24.0, 3.2, 60
    t = np.arange(n) / fps
    series = np.sin(2 * np.pi * f0 * t) + 0.3 * rng.standard_normal(n)
    for detrend in ("median", "quadratic"):
        out = step_rate(series, fps, detrend=detrend)  # type: ignore[arg-type]
        assert abs(out["hz"] - f0) <= out["hz_err"]
        assert out["hz_err"] < 0.3
    with pytest.raises(ValueError, match="detrend"):
        step_rate(series, fps, detrend="mean")  # type: ignore[arg-type]


def test_gait_signal_errors() -> None:
    masks = walker_masks()
    with pytest.raises(TypeError, match="single-object"):
        gait_signal({1: masks})
    with pytest.raises(ValueError, match="band"):
        gait_signal(masks, band=0.0)
    with pytest.raises(ValueError, match="band"):
        gait_signal(masks, band=1.5)
    empty = np.zeros((4, 8, 8), dtype=bool)
    assert np.all(np.isnan(gait_signal(empty)))
    mixed = np.zeros((3, 10, 10), dtype=bool)
    mixed[1, 2:8, 3:7] = True
    got = gait_signal(mixed)
    assert np.isnan(got[0]) and np.isnan(got[2]) and np.isfinite(got[1])
    assert got[1] == pytest.approx(4.0 / 6.0)

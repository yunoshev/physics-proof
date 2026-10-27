"""M6b probes: blocks for moving cameras and time scale (all offline)."""

from __future__ import annotations

import numpy as np
import pytest

from physics_proof.blocks import (
    decide,
    fit_parabola,
    ghost,
    mask_stats,
    relative_track,
    step_rate,
    to_metres,
)


def camera_scene(n: int = 48, fps: float = 24.0, a_true: float = 2.0):
    """Panning (+200 px) and zooming (1.3x) camera over a wall and a parabola.

    Wall world rect x in [0, 200], y in [0, 600]; the point flies
    y(t) = 120 + 30 t + a_true * 200 * t^2 / 2 in world units, so its true
    acceleration is a_true wall widths/s^2. Returns (reference masks
    [N, H, W] bool, analytic target rows in px, disc target masks [N, H, W]).
    """
    wall_w = 200.0
    a_world = a_true * wall_w
    ref = np.zeros((n, 1700, 320), dtype=bool)
    discs = np.zeros((n, 1700, 320), dtype=bool)
    rows: list[float] = []
    yy, xx = np.mgrid[0:1700, 0:320]
    for i in range(n):
        s = 1.0 + 0.3 * i / (n - 1)
        oy = -200.0 * i / (n - 1)
        wy = 120.0 + 30.0 * (i / fps) + 0.5 * a_world * (i / fps) ** 2
        x0, x1 = int(round(0.0)), int(round(wall_w * s))
        y0p, y1p = int(round((0.0 - oy) * s)), int(round((600.0 - oy) * s))
        ref[i, y0p:y1p, x0:x1] = True
        cx, cy, r = 100.0 * s, (wy - oy) * s, 5.0 * s
        discs[i] = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r
        rows.append(float(cy))
    return ref, rows, discs


# Probe 1: pan/zoom cancel out; acceleration recovered within 2 %.
def test_relative_track_pan_zoom_numeric() -> None:
    fps, a_true = 24.0, 2.0
    ref, rows, _ = camera_scene(a_true=a_true)
    out = relative_track(rows, ref)
    assert out["frames"] == list(range(48))
    assert out["value"].shape == (48,) and out["size_px"].shape == (48,)
    assert np.all(np.isfinite(out["value"]))
    assert out["zoom"]["ratio"] == pytest.approx(1.3, rel=0.05)
    fit = fit_parabola(out["frames"], out["value"], fps)
    assert fit["g_px"] == pytest.approx(a_true, rel=0.02)


def test_relative_track_mask_stats_target() -> None:
    fps, a_true = 24.0, 2.0
    ref, _, discs = camera_scene(a_true=a_true)
    stats = mask_stats(discs)
    out = relative_track(stats, ref, point="centroid")
    assert np.all(np.isfinite(out["value"]))
    fit = fit_parabola(out["frames"], out["value"], fps)
    assert fit["g_px"] == pytest.approx(a_true, rel=0.02)
    bottom = relative_track(stats, ref, anchor="bottom", size="height", point="bottom")
    assert bottom["value"].shape == (48,)
    assert np.all(np.isfinite(bottom["value"]))


def test_relative_track_missing_and_errors() -> None:
    ref, rows, _ = camera_scene()
    rows[5] = None  # type: ignore[list-item]
    out = relative_track(rows, ref)
    assert np.isnan(out["value"][5])
    assert np.isnan(out["size_px"][5])
    assert np.all(np.isfinite(np.delete(out["value"], 5)))
    with pytest.raises(ValueError, match="anchor"):
        relative_track(rows, ref, anchor="middle")
    with pytest.raises(ValueError, match="size"):
        relative_track(rows, ref, size="area")
    with pytest.raises(ValueError, match="point"):
        relative_track(mask_stats(np.zeros((48, 8, 8), dtype=bool)), ref, point="left")
    with pytest.raises(TypeError, match="single-object"):
        relative_track(rows, {1: ref})
    with pytest.raises(ValueError, match="target values"):
        relative_track(rows[:-1], ref)


# Probe 2: 3.2 Hz bob with noise; pure noise has a lower peak_ratio.
def test_step_rate_sine() -> None:
    rng = np.random.default_rng(11)
    fps, f0, n = 24.0, 3.2, 60
    t = np.arange(n) / fps
    series = np.sin(2 * np.pi * f0 * t) + 0.3 * rng.standard_normal(n)
    out = step_rate(series, fps)
    assert out["n"] == n
    assert abs(out["hz"] - f0) <= out["hz_err"]
    assert out["hz_err"] < 0.3
    assert out["period_frames"] == pytest.approx(fps / out["hz"])
    noise = step_rate(0.3 * rng.standard_normal(n), fps)
    assert noise["peak_ratio"] < out["peak_ratio"]


def test_step_rate_needs_two_periods() -> None:
    with pytest.raises(ValueError, match="2 periods"):
        step_rate([1.0] * 10, 24.0)
    with pytest.raises(ValueError, match="min_hz"):
        step_rate(np.zeros(60), 24.0, min_hz=8.0, max_hz=1.0)
    with pytest.raises(TypeError, match="sequence"):
        step_rate({1: 2}, 24.0)
    with pytest.raises(ValueError, match="finite"):
        step_rate([1.0, float("nan")] * 30, 24.0)


# Probe 3: ghost matches y0 + v0 t + a t^2 / 2.
def test_ghost_formula() -> None:
    frames = [10, 12, 14, 16, 18]
    got = ghost(3.0, 1.0, 0.5, frames, 2.0)
    assert got == pytest.approx([3.0, 4.25, 6.0, 8.25, 11.0])
    assert ghost(1.0, 2.0, 0.0, [0, 1, 2, 3], 1.0) == pytest.approx([1.0, 3.0, 5.0, 7.0])
    with pytest.raises(ValueError, match="one frame"):
        ghost(0.0, 0.0, 0.0, [], 24.0)
    with pytest.raises(ValueError, match="fps"):
        ghost(0.0, 0.0, 0.0, [0], 0.0)


# Probe 4: the wall-run table; g <= 0 says no playback speed explains it.
HYP = {"unsupported on Earth": 9.81}


@pytest.mark.parametrize(
    ("g", "g_err", "state", "k"),
    [
        (0.0, 0.5, "none_fits", None),
        (-1.0, 0.5, "none_fits", None),
        (9.5, 0.5, "fits:unsupported on Earth", None),
    ],
)
def test_decide_wall_run(g, g_err, state, k) -> None:
    out = decide(g, g_err, HYP)
    assert out["state"] == state
    assert set(out["sigmas"]) == set(HYP)
    if state == "none_fits":
        assert out["k"] is None
        assert "no playback speed" in out["text"]
        assert len(out["text"].split(". ")) == 1
    else:
        assert out["world"] == "unsupported on Earth"
        assert out["k"] == pytest.approx((9.81 / g) ** 0.5)


def test_decide_old_slowdown_text_kept() -> None:
    # Below every default world but positive: still a slow-clip explanation.
    out = decide(0.72, 0.05)
    assert out["state"] == "none_fits"
    assert "would have to be running " in out["text"]


# Probe 5: to_metres with g_px == 0.
def test_to_metres_zero() -> None:
    assert to_metres(0.0, 0.2, 10.0, 0.5) == (0.0, 0.02)

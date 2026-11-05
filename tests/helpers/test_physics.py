# owned by part 09 · tests for src/helpers/physics.py
"""Synthetic known-answer tests for the physics helpers."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.helpers import tracks
from src.helpers.physics import (fit_parabola, ghost,
                                 scale_from_reference, track_to_metres,
                                 worlds_fit)

FPS = 30.0
G_TRUE = 1.62
M_PER_PX = 0.01


def _parabola_track(g=G_TRUE, noise_px=0.0, seed=0, n=21):
    """Rectangle in exact parabolic motion, tracked to metres."""
    rng = np.random.default_rng(seed)
    v0 = 1.0
    take_cx, take_cy = 50.0, 200.0
    masks = {}
    for k in range(n):
        t = k / FPS
        y_m = v0 * t - 0.5 * g * t * t
        cy = take_cy - y_m / M_PER_PX
        if noise_px:
            cy += float(rng.normal(0.0, noise_px))
        mask = np.zeros((240, 120), dtype=bool)
        r0, r1 = int(round(cy)) - 20, int(round(cy)) + 20
        mask[max(r0, 0):r1, 40:60] = True
        masks[k] = mask
    rows = tracks.track_point(masks, "centroid")
    metres = track_to_metres(rows, M_PER_PX,
                             {"x_px": take_cx, "y_px": take_cy})
    times = [r["t"] / FPS for r in rows]
    heights = [r["y_m"] for r in metres["rows"]]
    return times, heights, metres


def test_track_recovers_planted_g_exact():
    """Track → metres → fit recovers the planted g (pixel rounding)."""
    times, heights, metres = _parabola_track()
    assert metres["m_per_px"] == pytest.approx(M_PER_PX)
    fit = fit_parabola(times, heights)
    # Masks live on the pixel grid, so the centroid carries up to
    # half-pixel rounding; the planted g is recovered within 0.02.
    assert fit["g_app"] == pytest.approx(G_TRUE, abs=0.02)
    assert fit["n"] == 21


def test_exact_parabola_has_null_trend():
    """A rounding-error-only fit reports a null trend, not dust."""
    t = np.arange(21) / FPS
    y = 1.0 + 0.5 * t - 0.5 * G_TRUE * t * t
    fit = fit_parabola(t, y)
    assert fit["g_app"] == pytest.approx(G_TRUE, abs=1e-9)
    assert fit["residual_trend"] == 0.0
    assert fit["residual_trend_z"] == 0.0


def test_track_recovers_planted_g_within_sigma():
    """With pixel noise the planted g lands inside the quoted sigma."""
    times, heights, _ = _parabola_track(noise_px=0.5, seed=11)
    fit = fit_parabola(times, heights)
    assert fit["g_app_sigma"] > 0
    assert abs(fit["g_app"] - G_TRUE) <= 3.0 * fit["g_app_sigma"]


def test_scale_propagates_sigma():
    """Standard propagation, and sigma covers a planted 1-sigma error."""
    m_per_px, sigma = scale_from_reference(100.0, 2.0, 1.0, 0.04)
    assert m_per_px == pytest.approx(0.01)
    assert sigma == pytest.approx(
        0.01 * math.sqrt(0.02 ** 2 + 0.04 ** 2))
    # Planted truth: extent overstated by exactly one extent-sigma.
    m_rec, sigma_rec = scale_from_reference(102.0, 2.0, 1.0, 0.04)
    assert abs(m_rec - 0.01) <= sigma_rec
    with pytest.raises(ValueError, match="bad_scale"):
        scale_from_reference(0.0, 2.0, 1.0, 0.04)


def test_track_to_metres_flips_y_once():
    """Image-down becomes metres-up, exactly once, about the origin."""
    rows = [{"frame": 0, "t": 0.0, "x_px": 60.0, "y_px": 190.0},
            {"frame": 1, "t": 0.1, "x_px": 40.0, "y_px": 210.0}]
    out = track_to_metres(rows, 0.01, {"x_px": 50.0, "y_px": 200.0})
    assert [(r["x_m"], r["y_m"]) for r in out["rows"]] == [
        (pytest.approx(0.1), pytest.approx(0.1)),
        (pytest.approx(-0.1), pytest.approx(-0.1))]
    assert out["m_per_px"] == pytest.approx(0.01)
    assert out["sigma_m_per_px"] == pytest.approx(0.0)
    paired = track_to_metres(rows, (0.01, 0.0004),
                             {"x_px": 50.0, "y_px": 200.0})
    assert paired["sigma_m_per_px"] == pytest.approx(0.0004)
    with pytest.raises(ValueError, match="bad_track"):
        track_to_metres([], 0.01, {"x_px": 0.0, "y_px": 0.0})


def test_worlds_fit_native_and_retime_arithmetic():
    """|Δ| ≤ 2σ fits natively; otherwise s = √(g_world / g_app)."""
    out = worlds_fit(1.62, 0.1, [{"name": "Moon", "g": 1.62},
                                 {"name": "Earth", "g": 9.81}])
    by_name = {row["name"]: row for row in out}
    assert by_name["Moon"]["fits_native"] is True
    assert by_name["Moon"]["delta_sigma"] == pytest.approx(0.0)
    assert by_name["Moon"]["retime_factor"] == pytest.approx(1.0)
    assert by_name["Earth"]["fits_native"] is False
    assert by_name["Earth"]["delta_sigma"] == pytest.approx(81.9)
    assert by_name["Earth"]["retime_factor"] == pytest.approx(
        math.sqrt(9.81 / 1.62))
    with pytest.raises(ValueError, match="bad_sigma"):
        worlds_fit(1.62, 0.0, [{"name": "Moon", "g": 1.62}])
    with pytest.raises(ValueError, match="bad_world"):
        worlds_fit(1.62, 0.1, [])


def test_ghost_lands_at_analytic_point():
    """The ghost returns to takeoff height at t = 2·vy/g."""
    state = {"x0": 0.0, "y0": 1.0, "vx": 0.5, "vy": 2.0}
    grid = [i * 0.01 for i in range(101)]
    result = ghost(state, 9.81, M_PER_PX, grid)
    t_land = 2.0 * 2.0 / 9.81
    assert result["landing"]["t"] == pytest.approx(t_land)
    assert result["landing"]["x_m"] == pytest.approx(0.5 * t_land)
    assert result["landing"]["y_m"] == pytest.approx(1.0)
    assert result["path"][0]["t"] == pytest.approx(0.0)
    assert result["path"][-1]["t"] == pytest.approx(t_land)
    for point in result["path"]:
        assert point["y_m"] >= 1.0 - 1e-9
    with pytest.raises(ValueError, match="no_takeoff"):
        ghost({"x0": 0.0, "y0": 0.0, "vx": 0.5, "vy": 0.0},
              9.81, M_PER_PX, grid)


def test_fit_rejects_short_and_degenerate_tracks():
    """Fewer than 4 points, or a flat time base, raise coded errors."""
    with pytest.raises(ValueError, match="short_track"):
        fit_parabola([0.0, 1.0, 2.0], [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="degenerate_track"):
        fit_parabola([1.0, 1.0, 1.0, 1.0, 1.0],
                     [1.0, 2.0, 3.0, 4.0, 5.0])


def test_noisy_parabola_stays_below_z_gate():
    """Noise at 1% of the rise: z < 3 in at least 95 of 100 seeds."""
    passes = 0
    for seed in range(100):
        rng = np.random.default_rng(seed)
        t = np.arange(100) / FPS
        y = 1.0 + 0.5 * t - 0.81 * t * t
        rise = float(y.max() - y.min())
        fit = fit_parabola(t, y + rng.normal(0.0, 0.01 * rise, 100))
        if fit["residual_trend_z"] < 3:
            passes += 1
    assert passes >= 95


def test_mixed_window_trips_both_gates():
    """Level motion joined to a parabola: z > 3 and |trend| > 0.3."""
    for seed in (7, 21, 99):
        rng = np.random.default_rng(seed)
        t = np.arange(60) / FPS
        y = np.zeros(60)
        y[30:] = -0.81 * (t[30:] - t[30]) ** 2
        rise = float(y.max() - y.min())
        assert rise > 0
        fit = fit_parabola(t, y + rng.normal(0.0, 0.01 * rise, 60))
        assert fit["residual_trend_z"] > 3
        assert abs(fit["residual_trend"]) > 0.3


def test_trend_is_not_pearson_with_t():
    """The cubic trend fires where Pearson(residuals, t) stays ~zero."""
    t = np.arange(60) / FPS
    y = np.zeros(60)
    y[30:] = -0.81 * (t[30:] - t[30]) ** 2
    fit = fit_parabola(t, y)
    pearson = float(np.corrcoef(fit["residuals"], t)[0, 1])
    assert abs(pearson) < 1e-6
    assert abs(fit["residual_trend"]) > 0.3
    assert fit["residual_trend_z"] > 3


def test_ghost_lands_below_takeoff():
    """Moon run 22: a landing below takeoff stretches the flight."""
    state = {"x0": 0.0, "y0": 0.0, "vx": 0.5, "vy": 0.61}
    grid = [i * 0.01 for i in range(200)]
    result = ghost(state, 1.62, M_PER_PX, grid, land_y_m=-0.19)
    expected = (0.61 + math.sqrt(0.61 ** 2 + 2.0 * 1.62 * 0.19)) / 1.62
    assert expected == pytest.approx(0.99, abs=0.01)
    assert result["landing"]["t"] == pytest.approx(expected)
    assert result["path"][-1]["y_m"] == pytest.approx(-0.19)
    assert result["landing"]["y_m"] == pytest.approx(-0.19)


def test_ghost_default_landing_is_unchanged():
    """land_y_m=0 matches the old 2·vy/g call exactly."""
    state = {"x0": 0.0, "y0": 1.0, "vx": 0.5, "vy": 2.0}
    grid = [i * 0.01 for i in range(101)]
    before = ghost(state, 9.81, M_PER_PX, grid)
    after = ghost(state, 9.81, M_PER_PX, grid, land_y_m=0.0)
    assert after["landing"]["t"] == pytest.approx(before["landing"]["t"])
    assert after["landing"]["t"] == pytest.approx(2.0 * 2.0 / 9.81)
    assert after["landing"]["y_m"] == pytest.approx(1.0)
    assert len(after["path"]) == len(before["path"])
    for new, old in zip(after["path"], before["path"]):
        assert new == pytest.approx(old)


def test_ghost_landing_above_peak_falls_back():
    """A landing level above the peak falls back to 2·vy/g."""
    state = {"x0": 0.0, "y0": 1.0, "vx": 0.5, "vy": 2.0}
    grid = [i * 0.01 for i in range(101)]
    peak = 2.0 * 2.0 / (2.0 * 9.81)
    result = ghost(state, 9.81, M_PER_PX, grid,
                   land_y_m=peak + 1.0)
    t_return = 2.0 * 2.0 / 9.81
    assert result["landing"]["t"] == pytest.approx(t_return)
    assert result["landing"]["y_m"] == pytest.approx(1.0)

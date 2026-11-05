# generated from brief/09 · part 09 owns this file
"""Verified gravity, scale and ghost arithmetic (part 09).

Pure functions over numpy arrays. Image coordinates grow downward in
pixels; physics works in metres with ``y`` up. The conversion happens
in exactly one place (:func:`track_to_metres`), so sign errors have
one home. Time is always seconds from measured timestamps — no helper
accepts a container fps.
"""

from __future__ import annotations

import math

__all__ = [
    "fit_parabola",
    "ghost",
    "scale_from_reference",
    "track_to_metres",
    "worlds_fit",
]


def _as_vector(values, name):
    """A finite float vector, or ``ValueError`` (``"bad_track"``)."""
    import numpy as np

    try:
        arr = np.asarray([float(v) for v in values], dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_track: {name} must be finite numbers: {exc}") from exc
    if arr.ndim != 1 or len(arr) == 0:
        raise ValueError(f"bad_track: {name} must be a non-empty series")
    if not bool(np.all(np.isfinite(arr))):
        raise ValueError(f"bad_track: {name} holds a non-finite value")
    return arr


def fit_parabola(t, y_m):
    """Least-squares ``y = y0 + v0·t + ½·a·t²``.

    Returns ``{"y0", "v0", "a", "g_app", "g_app_sigma", "rmse",
    "residuals", "residual_trend", "residual_trend_z", "n"}``: the
    fitted intercept, initial velocity and acceleration ``a`` (hence
    ``g_app = |a|``), its sigma from the residual sum of squares with
    honest degrees of freedom (``n - 3``), the root-mean-square
    residual, the residual series, the sample count, and two residual
    trend statistics (see below).

    A large residual trend is the signature of a non-rigid tracked
    point (R-M2) and is returned, never hidden. It is *not* the slope
    of residuals vs. time: least-squares residuals are orthogonal to
    every design column, and ``t`` is one of them, so that slope is
    zero by construction and can never fire. Instead:

    - ``residual_trend`` is the correlation between the residuals and
      the centred cubic term ``(t - t̄)³`` made orthogonal to the
      design columns ``(1, t, t²)`` — the partial correlation of a
      cubic term. Near zero for one stretch of constant acceleration;
      large in magnitude when the window mixes phases (support, a
      change of surface, a turn) or the tracked point deforms.
    - ``residual_trend_z`` is the ``|t|`` statistic of the cubic
      coefficient ``j`` in the extended fit ``y = y0 + v0·t + ½·a·t²
      + j·t³``, computed on the same points as the fit. A
      ``residual_trend_z`` above 3 means the window is not one stretch
      of constant acceleration: it mixes phases or the tracked point
      deforms. (With only 4 points the cubic addition consumes all
      freedom, so ``residual_trend_z`` is reported as 0.0.)

    When the fit is exact to floating-point dust (rmse below 1e-9 of
    the data span) both statistics are 0.0: the correlation of rounding
    error is arbitrary, not a measurement.

    Raises ``ValueError`` (``"short_track"``) on fewer than 4 points
    and (``"degenerate_track"``) when the time base is degenerate.
    """
    import numpy as np

    t_arr = _as_vector(t, "t")
    y_arr = _as_vector(y_m, "y_m")
    if len(t_arr) != len(y_arr):
        raise ValueError("bad_track: t and y_m need the same length")
    n = len(t_arr)
    if n < 4:
        raise ValueError(
            f"short_track: need at least 4 points, got {n}")
    design = np.column_stack([np.ones(n), t_arr, 0.5 * t_arr * t_arr])
    try:
        beta, _, rank, _ = np.linalg.lstsq(design, y_arr, rcond=None)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            f"degenerate_track: cannot fit a parabola: {exc}") from exc
    if rank < 3:
        raise ValueError("degenerate_track: the time base is degenerate")
    try:
        gram_inv = np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            f"degenerate_track: the time base is degenerate: "
            f"{exc}") from exc
    y0, v0, accel = (float(beta[0]), float(beta[1]), float(beta[2]))
    predicted = design @ beta
    residuals = y_arr - predicted
    rss = float(residuals @ residuals)
    dof = n - 3
    sigma2 = rss / dof
    sigma_a = math.sqrt(sigma2 * float(gram_inv[2, 2])) if sigma2 > 0 \
        else 0.0
    rmse = math.sqrt(rss / n) if rss > 0 else 0.0

    # Floating-point dust is not a measurement: when the fit is exact
    # to rounding error, the correlation of the residuals with anything
    # is arbitrary, so both trend statistics are reported as 0.0 (the
    # validator's sub-nanometre guard expresses the same idea in
    # metres; this keeps the raw statistic honest in any unit).
    span = float(y_arr.max() - y_arr.min())
    span = max(span, float(np.abs(y_arr).max()), 1e-300)
    dust = rmse <= 1e-9 * span

    # -- residual trend: partial correlation of a cubic term --------
    if dust:
        return {"y0": y0, "v0": v0, "a": accel, "g_app": abs(accel),
                "g_app_sigma": float(sigma_a), "rmse": float(rmse),
                "residuals": [float(r) for r in residuals],
                "residual_trend": 0.0, "residual_trend_z": 0.0, "n": n}
    centred = t_arr - float(t_arr.mean())
    cubic = centred ** 3
    gamma, _, _, _ = np.linalg.lstsq(design, cubic, rcond=None)
    cubic_orth = cubic - design @ gamma
    denom = float(np.linalg.norm(residuals)
                  * np.linalg.norm(cubic_orth))
    if denom > 0:
        residual_trend = float((residuals @ cubic_orth) / denom)
    else:
        residual_trend = 0.0

    # -- residual_trend_z: |t| of the cubic coefficient ------------
    if n < 5:
        residual_trend_z = 0.0
    else:
        extended = np.column_stack(
            [np.ones(n), t_arr, 0.5 * t_arr * t_arr, t_arr ** 3])
        beta_ext, _, rank_ext, _ = np.linalg.lstsq(
            extended, y_arr, rcond=None)
        cubic_coef = float(beta_ext[3])
        if rank_ext < 4:
            residual_trend_z = 0.0
        else:
            resid_ext = y_arr - extended @ beta_ext
            rss_ext = float(resid_ext @ resid_ext)
            dof_ext = n - 4
            try:
                gram_ext_inv = np.linalg.inv(extended.T @ extended)
            except np.linalg.LinAlgError:
                gram_ext_inv = None
            if gram_ext_inv is None:
                residual_trend_z = 0.0
            else:
                sigma2_ext = rss_ext / dof_ext
                var_j = sigma2_ext * float(gram_ext_inv[3, 3])
                if var_j > 0:
                    residual_trend_z = abs(cubic_coef) / math.sqrt(var_j)
                elif cubic_coef != 0.0:
                    residual_trend_z = float("inf")
                else:
                    residual_trend_z = 0.0
    return {"y0": y0, "v0": v0, "a": accel, "g_app": abs(accel),
            "g_app_sigma": float(sigma_a), "rmse": float(rmse),
            "residuals": [float(r) for r in residuals],
            "residual_trend": float(residual_trend),
            "residual_trend_z": float(residual_trend_z), "n": n}


def scale_from_reference(extent_px, extent_px_sigma, size_m,
                         size_m_sigma):
    """Metres per pixel from a reference of known size.

    ``m_per_px = size_m / extent_px`` with standard propagation
    ``σ = m·√((σ_px/extent_px)² + (σ_m/size_m)²)``. Returns
    ``(m_per_px, sigma)`` as floats — always a pair where an error is
    meaningful. Raises ``ValueError`` (``"bad_scale"``) on
    non-positive or non-finite inputs.
    """
    try:
        extent = float(extent_px)
        sigma_px = float(extent_px_sigma)
        size = float(size_m)
        sigma_m = float(size_m_sigma)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_scale: scale inputs must be numbers: {exc}") from exc
    if not all(math.isfinite(v)
               for v in (extent, sigma_px, size, sigma_m)):
        raise ValueError("bad_scale: scale inputs must be finite")
    if extent <= 0 or size <= 0 or sigma_px < 0 or sigma_m < 0:
        raise ValueError("bad_scale: extent and size must be positive, "
                         "sigmas non-negative")
    m_per_px = size / extent
    sigma = m_per_px * math.sqrt((sigma_px / extent) ** 2
                                 + (sigma_m / size) ** 2)
    return float(m_per_px), float(sigma)


def _split_pair(value, name):
    """A ``(value, sigma)`` pair from a bare number or a pair."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"bad_scale: {name} pair must be numbers: "
                f"{exc}") from exc
    try:
        return float(value), 0.0
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_scale: {name} must be a number or a "
            f"(value, sigma) pair: {exc}") from exc


def track_to_metres(track, m_per_px, origin):
    """Pixel track → metres, flipping ``y``.

    The one home of the sign flip: image ``y`` grows downward, physics
    works in metres with ``y`` up, so ``y_m = (origin_y - y_px) ·
    m_per_px`` and ``x_m = (x_px - origin_x) · m_per_px``. ``origin``
    is ``{"x_px", "y_px"}`` (a tuple/list ``(x, y)`` also works),
    usually the takeoff pixel. ``m_per_px`` is a bare number or a
    ``(value, sigma)`` pair.

    Returns ``{"rows", "m_per_px", "sigma_m_per_px", "origin_px"}``:
    rows are ``{"frame", "t", "x_m", "y_m"}``. Errors are carried as
    the single scale-relative term ``sigma_m_per_px``; per-point
    pixel noise is the fit's job, not this function's.
    """
    scale, sigma = _split_pair(m_per_px, "m_per_px")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("bad_scale: m_per_px must be positive")
    if not math.isfinite(sigma) or sigma < 0:
        raise ValueError("bad_scale: sigma_m_per_px must be "
                         "non-negative")
    if isinstance(origin, dict):
        try:
            ox = float(origin["x_px"])
            oy = float(origin["y_px"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"bad_origin: origin needs x_px and y_px: "
                f"{exc}") from exc
    else:
        try:
            ox, oy = float(origin[0]), float(origin[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError(
                f"bad_origin: origin must be {{\"x_px\", \"y_px\"}} "
                f"or (x, y): {exc}") from exc
    if not math.isfinite(ox) or not math.isfinite(oy):
        raise ValueError("bad_origin: origin must be finite")
    rows = []
    for row in track or []:
        try:
            rows.append({"frame": int(row["frame"]),
                         "t": float(row.get("t", row["frame"])),
                         "x_m": (float(row["x_px"]) - ox) * scale,
                         "y_m": (oy - float(row["y_px"])) * scale})
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"bad_track: rows need frame, x_px, y_px: "
                f"{exc}") from exc
    if not rows:
        raise ValueError("bad_track: the track holds no rows")
    return {"rows": rows, "m_per_px": scale,
            "sigma_m_per_px": sigma,
            "origin_px": {"x_px": ox, "y_px": oy}}


def worlds_fit(g_app, sigma, candidate_worlds):
    """Native-speed fit arithmetic over the candidate worlds.

    For each candidate ``{"name", "g"}`` (``"g_m_s2"`` is accepted as
    an alias): ``delta_sigma = |g - g_app| / sigma`` and
    ``fits_native = delta_sigma <= 2`` (part 02 §4); ``retime_factor =
    √(g_world / g_app)`` — the slow-down that would map the measured
    gravity onto that world — is reported per candidate as pure
    arithmetic (``None`` when ``g_app`` is not positive, never a
    guessed number). This function contains no scene judgement: which
    candidates are even considered (R-W1) lives in validation.

    Returns a list of ``{"name", "g", "delta_sigma", "fits_native",
    "retime_factor"}``. Raises ``ValueError`` (``"bad_gravity"``,
    ``"bad_sigma"``, ``"bad_world"``) on unusable inputs.
    """
    try:
        measured = float(g_app)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_gravity: g_app must be a number: {exc}") from exc
    try:
        spread = float(sigma)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_sigma: sigma must be a number: {exc}") from exc
    if not math.isfinite(measured) or measured < 0:
        raise ValueError("bad_gravity: g_app must be finite and "
                         "non-negative")
    if not math.isfinite(spread) or spread <= 0:
        raise ValueError("bad_sigma: sigma must be finite and positive")
    if not isinstance(candidate_worlds, (list, tuple)) or (
            not candidate_worlds):
        raise ValueError("bad_world: candidate_worlds must be a "
                         "non-empty list of {name, g}")
    out = []
    for candidate in candidate_worlds:
        if not isinstance(candidate, dict):
            raise ValueError(
                f"bad_world: candidate {candidate!r} must be "
                "{name, g}")
        name = candidate.get("name")
        gravity = candidate.get("g", candidate.get("g_m_s2"))
        try:
            world_g = float(gravity)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"bad_world: candidate {name!r} needs a numeric "
                f"gravity: {exc}") from exc
        if not math.isfinite(world_g) or world_g <= 0:
            raise ValueError(
                f"bad_world: candidate {name!r} gravity must be "
                "finite and positive")
        delta = abs(world_g - measured) / spread
        if measured > 0:
            retime = math.sqrt(world_g / measured)
        else:
            retime = None
        out.append({"name": str(name), "g": world_g,
                    "delta_sigma": float(delta),
                    "fits_native": bool(delta <= 2.0),
                    "retime_factor": (float(retime)
                                      if retime is not None else None)})
    return out


def ghost(takeoff_state, g_ghost, m_per_px, t_grid, land_y_m=0.0):
    """Propagate a takeoff state under ``g_ghost``.

    ``takeoff_state`` is ``{"x0", "y0", "vx", "vy"}`` in metres with
    ``y`` up; ``g_ghost`` the (positive) gravity to integrate under;
    ``t_grid`` the grid of times (seconds, takeoff-relative) at which
    to sample the path; ``land_y_m`` the landing height in metres
    relative to the takeoff point with ``y`` up (a landing below
    takeoff gives a negative ``land_y_m``). Returns ``{"path",
    "landing"}``: path entries are ``{"t", "x_m", "y_m", "x_px",
    "y_px"}`` (pixel equivalents are relative to the metre origin via
    ``m_per_px``), and landing is where the path, after its peak,
    reaches the height ``land_y_m``, at ``t_land = (vy + sqrt(vy² -
    2·g·land_y_m)) / g``. With ``land_y_m = 0`` this is today's
    ``2·vy/g``, so every existing call keeps its result. The path is
    sampled on the grid up to ``t_land``, and the exact landing point
    is always appended, even between grid samples. When the path peaks
    below ``land_y_m`` (``vy² < 2·g·land_y_m``), the landing falls back
    to the return to takeoff height. (Part 11 decides *which* gravity
    the ghost uses; this just integrates.)

    Raises ``ValueError`` (``"no_takeoff"``) when ``vy <= 0`` — the
    path never returns to takeoff height — and (``"bad_gravity"``,
    ``"bad_scale"``, ``"short_grid"``, ``"bad_landing"``) on unusable
    inputs.
    """
    try:
        x0 = float(takeoff_state["x0"])
        y0 = float(takeoff_state["y0"])
        vx = float(takeoff_state["vx"])
        vy = float(takeoff_state["vy"])
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError(
            f"bad_takeoff: takeoff_state needs x0, y0, vx, vy: "
            f"{exc}") from exc
    if not all(math.isfinite(v) for v in (x0, y0, vx, vy)):
        raise ValueError("bad_takeoff: takeoff_state must be finite")
    try:
        gravity = float(g_ghost)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_gravity: g_ghost must be a number: {exc}") from exc
    if not math.isfinite(gravity) or gravity <= 0:
        raise ValueError("bad_gravity: g_ghost must be finite and "
                         "positive")
    scale, _ = _split_pair(m_per_px, "m_per_px")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("bad_scale: m_per_px must be positive")
    try:
        grid = [float(v) for v in t_grid]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"short_grid: t_grid must hold times in seconds: "
            f"{exc}") from exc
    if not grid or not all(math.isfinite(v) for v in grid):
        raise ValueError("short_grid: t_grid must hold finite times")
    if vy <= 0:
        raise ValueError("no_takeoff: vy must be positive for the "
                         "path to return to takeoff height")
    try:
        land = float(land_y_m)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_landing: land_y_m must be a number: {exc}") from exc
    if not math.isfinite(land):
        raise ValueError("bad_landing: land_y_m must be finite")

    def _at(moment):
        x_m = x0 + vx * moment
        y_m = y0 + vy * moment - 0.5 * gravity * moment * moment
        return {"t": float(moment), "x_m": float(x_m),
                "y_m": float(y_m), "x_px": float(x_m / scale),
                "y_px": float(y_m / scale)}

    t_return = 2.0 * vy / gravity
    discriminant = vy * vy - 2.0 * gravity * land
    if discriminant < 0.0:
        t_land = t_return
    else:
        t_land = (vy + math.sqrt(discriminant)) / gravity
    path = [_at(moment) for moment in sorted(grid)
            if 0.0 <= moment <= t_land]
    landing = _at(t_land)
    if not path or path[-1]["t"] < t_land:
        path.append(dict(landing))
    return {"path": path,
            "landing": {"t": float(landing["t"]),
                        "x_m": float(landing["x_m"]),
                        "y_m": float(landing["y_m"]),
                        "x_px": float(landing["x_px"]),
                        "y_px": float(landing["y_px"])}}

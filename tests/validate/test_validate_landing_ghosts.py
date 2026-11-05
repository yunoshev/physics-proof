# generated from brief/11 · part 11 owns this file
"""Ghosts and world outcomes land at the clip's landing level (§31)."""

import copy
import json
import math


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _off_level_rows(start=30, end=60, level_y=200.0, x_px=100.0,
                    g=1.59, land_below=0.19, fps=30.0, scale=0.01):
    """Free-flight rows landing ``land_below`` metres below takeoff."""
    airtime = (end - start) / fps
    vy = (0.5 * g * airtime * airtime - land_below) / airtime
    rows = []
    for frame in range(start, end + 1):
        moment = (frame - start) / fps
        y_m = vy * moment - 0.5 * g * moment * moment
        rows.append({"frame": frame, "x_px": x_px,
                     "y_px": level_y - y_m / scale})
    return rows, vy, airtime


def _takeoff_vy(rows, fps=30.0, scale=0.01, level_y=200.0):
    """The validator's takeoff velocity, refit the same way."""
    from src.helpers.physics import fit_parabola

    times = [row["frame"] / fps for row in rows]
    heights = [(level_y - row["y_px"]) * scale for row in rows]
    fit = fit_parabola(times, heights)
    t_start = rows[0]["frame"] / fps
    return fit["v0"] + fit["a"] * t_start, abs(fit["a"])


def _off_level_evidence(evidence, run_dir):
    """Baseline evidence whose hop lands 0.19 m below takeoff."""
    rows, _vy, _airtime = _off_level_rows()
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        json.dumps(rows), encoding="utf-8")
    good = copy.deepcopy(evidence)
    good["segments"][0]["frames"]["apex"] = 41
    good["segments"][0]["fit_curve_px"] = [
        {"t_s": row["frame"] / 30.0, "x_px": row["x_px"],
         "y_px": row["y_px"]} for row in rows]
    return good, rows


def test_moon_ghost_lands_at_landing_level(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good, rows = _off_level_evidence(evidence, run_dir)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["verdict"]["world"] == "Moon"
    segment = report["result"]["segments"][0]
    ghosts = {g["role"]: g for g in segment["ghosts"]}
    assert set(ghosts) == {"earth_counterfactual", "fitting_world"}
    airtime = (60 - 30) / 30.0
    t_start = segment["times_s"]["start"]
    moon = ghosts["fitting_world"]
    assert moon["world"] == "Moon"
    # The Moon ghost lands within 0.05 s of the measured airtime.
    assert abs(moon["landing"]["t_s"] - t_start - airtime) < 0.05
    # Its last point is at the landing level, 0.19 m below takeoff.
    assert moon["points"][-1]["y_px"] == moon["landing"]["y_px"]
    assert abs((200.0 - moon["landing"]["y_px"]) * 0.01
               - (-0.19)) < 1e-6


def test_earth_ghost_lands_below_takeoff(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good, rows = _off_level_evidence(evidence, run_dir)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    segment = report["result"]["segments"][0]
    ghosts = {g["role"]: g for g in segment["ghosts"]}
    earth = ghosts["earth_counterfactual"]
    vy, _g = _takeoff_vy(rows)
    expected = (vy + math.sqrt(vy * vy + 2.0 * 9.81 * 0.19)) / 9.81
    t_start = segment["times_s"]["start"]
    assert abs(earth["landing"]["t_s"] - t_start - expected) < 1e-6
    assert earth["points"][-1]["y_px"] == earth["landing"]["y_px"]


def test_world_outcomes_use_landing_level(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good, rows = _off_level_evidence(evidence, run_dir)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    segment = report["result"]["segments"][0]
    vy, _g = _takeoff_vy(rows)
    outcomes = {o["world"]: o for o in segment["world_outcomes"]}
    for world, gravity in (("Moon", 1.62), ("Earth", 9.81)):
        expected = (vy + math.sqrt(
            vy * vy + 2.0 * gravity * 0.19)) / gravity
        assert abs(outcomes[world]["landing_time_s"]
                   - expected) < 1e-6, world


def test_level_landing_matches_return_to_takeoff(baseline, tmp_path):
    # A segment that lands at its takeoff height gives the same
    # ghosts and outcomes as before: t_land = 2·vy/g.
    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True, report["errors"]
    segment = report["result"]["segments"][0]
    rows = json.loads(
        (_run / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    vy, g_app = _takeoff_vy(rows)
    outcomes = {o["world"]: o for o in segment["world_outcomes"]}
    assert abs(outcomes["Moon"]["landing_time_s"]
               - 2.0 * vy / 1.62) < 1e-6
    assert abs(outcomes["Earth"]["landing_time_s"]
               - 2.0 * vy / 9.81) < 1e-6
    for ghost in segment["ghosts"]:
        assert abs((200.0 - ghost["landing"]["y_px"]) * 0.01) < 1e-6

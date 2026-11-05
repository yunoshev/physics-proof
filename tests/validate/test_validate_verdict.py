# generated from brief/11 · part 11 owns this file
"""Verdict computation, ghosts and the sentence (brief §3)."""

import copy


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def test_world_verdict_and_sentence(baseline, tmp_path):
    from src.contract import validate_result

    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert validate_result(report["result"]) == []
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "world"
    assert verdict["world"] == "Moon"
    sentence = report["result"]["sentence"]
    assert "Moon" in sentence
    assert "1.62" in sentence


def test_sentence_never_raw_repr(baseline, tmp_path):
    import re

    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    sentence = report["result"]["sentence"]
    assert "e+" not in sentence and "e-" not in sentence
    for number in re.findall(r"\d+\.\d+", sentence):
        assert len(number.split(".")[1]) <= 4, number


def test_ghosts_moon_roles(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    ghosts = report["result"]["segments"][0]["ghosts"]
    roles = {(g["role"], g["world"]) for g in ghosts}
    assert ("earth_counterfactual", "Earth") in roles
    assert ("fitting_world", "Moon") in roles
    assert len(ghosts) == 2
    for ghost in ghosts:
        assert len(ghost["points"]) >= 5
        assert ghost["landing"]["t_s"] > 0


def test_ghosts_empty_on_earth(baseline, tmp_path):
    import json as _json

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    for row in rows:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * (9.81 / 1.62)
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        _json.dumps(rows), encoding="utf-8")
    good = copy.deepcopy(evidence)
    curve = good["segments"][0]["fit_curve_px"]
    for sample, row in zip(curve, rows):
        sample["y_px"] = row["y_px"]
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["verdict"]["world"] == "Earth"
    assert report["result"]["segments"][0]["ghosts"] == []


def test_wall_segments_get_no_ghosts(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["segments"][0]["kind"] = "free_flight"
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True
    wall = copy.deepcopy(evidence)
    wall["segments"][0]["kind"] = "wall"
    wall["segments"][0]["key_moments"] = [
        {"type": "wall_start", "frame": 30, "caption": "starting up"},
        {"type": "wall_end", "frame": 60, "caption": "topping out"}]
    report = _validate(wall, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["segments"][0]["ghosts"] == []


def test_impossible_keeps_counterfactuals(baseline, tmp_path):
    import json as _json

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    for row in rows:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * (5.0 / 1.62)
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        _json.dumps(rows), encoding="utf-8")
    good = copy.deepcopy(evidence)
    curve = good["segments"][0]["fit_curve_px"]
    for sample, row in zip(curve, rows):
        sample["y_px"] = row["y_px"]
    good["clock"] = {
        "signal_description": "steady steps",
        "measured_rate_hz": 1.9,
        "measured_rate_sigma_hz": 0.01,
        "interpretation": "step",
        "band_hz": [0.5, 4.0],
        "natural_range_hz": [1.8, 2.0],
        "natural_range_source": {
            "url": "https://example.com/gait",
            "quote": "step rate is 1.8 to 2.0 Hz"},
    }
    good["clock_absent_reason"] = None
    good["error_budget"]["sigma_relative"] = 0.05
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "impossible", verdict
    ghosts = report["result"]["segments"][0]["ghosts"]
    roles = {g["role"] for g in ghosts}
    assert "earth_counterfactual" in roles
    assert "fitting_world" in roles


def test_synthesis_paths_valid(tmp_path):
    from src.contract import validate_result
    from src.validate import synthesize_undetermined, write_result

    run_dir = tmp_path / "run"
    result = synthesize_undetermined(str(run_dir), "run-x", "budget",
                                     detail="turns >= 90")
    assert validate_result(result) == []
    assert result["verdict"]["kind"] == "undetermined"
    path = write_result(str(run_dir), result)
    assert path.endswith("result.json")


def test_only_writer_of_result(baseline, tmp_path):
    import pathlib

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True
    assert report["result_path"] == str(run_dir / "result.json")
    assert (run_dir / "result.json").exists()
    writers = [p for p in pathlib.Path("src").rglob("*.py")
               if "write_result" in p.read_text(encoding="utf-8")
               and "validate" not in str(p)
               and "loop" not in str(p) and "tools" not in str(p)]
    assert writers == [], writers

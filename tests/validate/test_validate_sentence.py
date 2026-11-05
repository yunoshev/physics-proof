# generated from brief/11 · part 11 owns this file
"""Display sentences answer realistic or not (brief §19)."""

import copy
import json as _json


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _rescale(run_dir, evidence, ratio):
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    for row in rows:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * ratio
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        _json.dumps(rows), encoding="utf-8")
    good = copy.deepcopy(evidence)
    curve = good["segments"][0]["fit_curve_px"]
    for sample, row in zip(curve, rows):
        sample["y_px"] = row["y_px"]
    return good


def _clock(rate, sigma=0.05, lo=1.0, hi=2.0, interpretation="step"):
    return {
        "signal_description": "width of the lowest thirty percent",
        "measured_rate_hz": rate,
        "measured_rate_sigma_hz": sigma,
        "interpretation": interpretation,
        "band_hz": [0.5, 4.0],
        "natural_range_hz": [lo, hi],
        "natural_range_source": {
            "url": "https://example.com/gait",
            "quote": "preferred frequency is 1 to 2 Hz"},
    }


def test_world_sentence_realistic_on_moon(baseline, tmp_path):
    from src.contract import validate_result

    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert validate_result(report["result"]) == []
    sentence = report["result"]["sentence"]
    assert sentence.startswith("Realistic on the Moon: measured g = "), \
        sentence
    assert "σ from the Moon's 1.62." in sentence, sentence


def test_retimed_sentence_not_realistic_at_this_speed(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _rescale(run_dir, evidence, 0.79 / 1.62)
    good["clock"] = _clock(0.6, sigma=0.02, lo=1.4, hi=2.0,
                           interpretation="stride")
    good["clock_absent_reason"] = None
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["verdict"]["kind"] == "retimed"
    sentence = report["result"]["sentence"]
    assert sentence.startswith(
        "Not realistic at this speed: slowed down ×"), sentence
    assert "; at real speed it fits the Moon (clock agrees)." in \
        sentence, sentence
    assert "Measured g = " in sentence and "m/s²." in sentence, \
        sentence


def test_impossible_sentence_names_candidate_world(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _rescale(run_dir, evidence, 5.0 / 1.62)
    good["worlds"] = {"candidates": [{"world": "Earth"}],
                      "excluded": []}
    good["clock"] = _clock(1.9, sigma=0.01, lo=1.8, hi=2.0)
    good["clock_absent_reason"] = None
    good["error_budget"]["sigma_relative"] = 0.05
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["verdict"]["kind"] == "impossible"
    sentence = report["result"]["sentence"]
    assert sentence.startswith("Not realistic on Earth: "), sentence
    assert "Measured g = " in sentence and "m/s²." in sentence, \
        sentence


def test_undetermined_sentence_with_measured_g(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _rescale(run_dir, evidence, 1.177 / 1.62)
    good["clock_absent_reason"] = "no visible independent rhythm"
    good["error_budget"]["sigma_relative"] = 0.0736
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["verdict"]["kind"] == "undetermined"
    sentence = report["result"]["sentence"]
    assert sentence.startswith("Undetermined: "), sentence
    assert "Measured g = " in sentence and "m/s²." in sentence, \
        sentence


def test_single_candidate_empty_excluded_accepted(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["worlds"] = {"candidates": [{"world": "Moon"}],
                      "excluded": []}
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["verdict"]["kind"] == "world"
    assert report["result"]["sentence"].startswith(
        "Realistic on the Moon: "), report["result"]["sentence"]

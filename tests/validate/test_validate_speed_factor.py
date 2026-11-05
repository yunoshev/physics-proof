# generated from brief/11 · part 11 owns this file
"""A speed factor is always above 1 (brief §42).

The stored stretch ``s`` is presented ÷ real; the printed factor is
``k`` (``s`` when slowed, ``1/s`` when sped up), in the sentence, in
every step text and in every reason the validator writes.
``verdict.factor`` stores ``k`` with ``direction``; the candidates'
``retime_factor`` stays ``s``.
"""

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


def _clock(rate, sigma=0.05, lo=1.0, hi=2.0, interpretation="stride"):
    return {
        "signal_description": "width of the lowest thirty percent",
        "measured_rate_hz": rate,
        "measured_rate_sigma_hz": sigma,
        "interpretation": interpretation,
        "band_hz": [0.5, 4.0],
        "natural_range_hz": [lo, hi],
        "natural_range_source": {
            "url": "https://example.com/gait",
            "quote": "stride rate is 1.4 to 2.0 Hz"},
    }


def _sped_up(run_dir, evidence):
    # Moon gravity seen through a sped-up clip: s = 0.4665, k = 2.14.
    good = _rescale(run_dir, evidence, (1.62 / 0.4665 ** 2) / 1.62)
    good["clock"] = _clock(1.82, sigma=0.05, lo=1.4, hi=2.0)
    good["clock_absent_reason"] = None
    return good


def _step_texts(steps):
    texts = []

    def _walk(value):
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                _walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                _walk(item)

    _walk(steps)
    return texts


def test_sped_up_sentence_and_factor(baseline, tmp_path):
    # The sped-up Moon run: s = 0.4665 reads "sped up ×2.14" and
    # verdict.factor stores k = 2.14 with direction "sped".
    from src.contract import validate_result

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _sped_up(run_dir, evidence)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    result = report["result"]
    assert validate_result(result) == []
    verdict = result["verdict"]
    assert verdict["kind"] == "retimed", verdict
    assert verdict["world"] == "Moon"
    assert verdict["direction"] == "sped"
    assert abs(verdict["factor"] - 2.14) < 0.01, verdict["factor"]
    sentence = result["sentence"]
    assert sentence.startswith(
        "Not realistic at this speed: sped up ×2.14; "
        "at real speed it fits the Moon"), sentence
    moon = [c for c in result["worlds"]["candidates"]
            if c["world"] == "Moon"][0]
    assert abs(moon["retime_factor"] - 0.4665) < 0.01, moon


def test_slowed_down_sentence_unchanged(baseline, tmp_path):
    # s = 1.50 still reads "slowed down ×1.50".
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _rescale(run_dir, evidence, 0.72 / 1.62)
    good["clock"] = _clock(0.6, sigma=0.02, lo=1.4, hi=2.0)
    good["clock_absent_reason"] = None
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "retimed", verdict
    assert verdict["direction"] == "slowed"
    assert abs(verdict["factor"] - 1.50) < 0.01, verdict["factor"]
    sentence = report["result"]["sentence"]
    assert "slowed down ×1.50" in sentence, sentence
    assert "×0." not in sentence, sentence


def test_no_below_one_factor_in_retimed_texts(baseline, tmp_path):
    # No sentence or step text of a retimed result prints "×0.".
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _sped_up(run_dir, evidence)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    result = report["result"]
    assert result["verdict"]["kind"] == "retimed"
    assert "×0." not in result["sentence"], result["sentence"]
    for text in _step_texts(result["calculation_steps"]):
        assert "×0." not in text, text

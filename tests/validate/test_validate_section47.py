# generated from brief/11 · part 11 owns this file
"""A size comes from a named dimension (brief §47, R-S13).

``SIZE_DIMENSION_UNLABELLED`` refuses a reference whose source value
appears in the quote only inside a run of three or more numbers
joined by "×" or "x" with no dimension word next to that number.
"""

import copy
import json


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _requote(run_dir, url, quote):
    """Point the first reference at a fresh source with a search record."""
    record = json.loads(
        (run_dir / "artifacts" / "t0_web_search_0.json").read_text(
            encoding="utf-8"))
    record["facts"].append({"url": url, "quote": quote, "text": quote})
    (run_dir / "artifacts" / "t0_web_search_0.json").write_text(
        json.dumps(record), encoding="utf-8")
    return {"url": url, "domain": "example.com", "quote": quote,
            "quote_highlight": quote, "value_m": None,
            "source_type": "catalogue"}


def _dim_codes(report):
    return [e for e in report["errors"]
            if e["code"] == "SIZE_DIMENSION_UNLABELLED"]


def test_size_dimension_unlabelled_rejected(baseline, tmp_path):
    """The Moon run's oxygen purge unit: 0.381 m from an unlabelled list."""
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    quote = "3-D: 38.1cm × 17.8cm × 20.3cm, 12.3kg"
    url = "https://example.com/ops-unit"
    source = _requote(run_dir, url, quote)
    source["value_m"] = 0.381
    ref = bad["references"][0]
    ref["name"] = "oxygen purge unit"
    ref["size_m"] = 0.381
    ref["sources"] = [source]
    report = _validate(copy.deepcopy(bad), dict(ctx))
    assert report["accepted"] is False, report["errors"]
    matches = _dim_codes(report)
    assert matches, [e["code"] for e in report["errors"]]
    assert len(matches) == 1
    assert matches[0]["field"] == "references[0].sources[0].quote"
    detail = matches[0]["detail"]
    assert "oxygen purge unit" in detail, detail
    assert "0.381" in detail, detail
    assert "38.1cm × 17.8cm × 20.3cm" in detail, detail
    assert "does not name its dimensions" in detail, detail
    assert "(R-S13)" in detail, detail
    dry = _validate(copy.deepcopy(bad), dict(ctx), dry_run=True)
    assert dry["accepted"] is False
    assert _dim_codes(dry), [e["code"] for e in dry["errors"]]


def test_size_dimension_labelled_passes(baseline, tmp_path):
    """The PLSS line names its height, so 0.66 m is used as quoted."""
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    quote = ("The PLSS was 26 inches (66 cm) high, "
             "18 inches (46 cm) wide")
    url = "https://example.com/plss-manual"
    source = _requote(run_dir, url, quote)
    source["value_m"] = 0.66
    good["references"][0]["sources"] = [source]
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert _dim_codes(report) == []


def test_size_dimension_tall_names_metric_passes(baseline, tmp_path):
    """The "tall" dimension reads 1.7002 m, metric list and all."""
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    quote = ("Overall: 5 ft. 6 15/16 in. tall x 2 ft. 8 5/16 in. wide "
             "x 11 in. deep (170.02 x 82 x 27.9cm)")
    url = "https://example.com/suit-spec"
    source = _requote(run_dir, url, quote)
    source["value_m"] = 1.7002
    ref = good["references"][0]
    ref["name"] = "suited figure height"
    ref["size_m"] = 1.7002
    ref["size_tolerance_m"] = 0.05
    ref["extent_px"] = {"x1": 20.0, "y1": 20.0, "x2": 20.0,
                        "y2": 190.02, "length_px": 170.02,
                        "frame": 10}
    ref["sources"] = [source]
    # The moved extent end needs its own blind check (§50).
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "frame": 10,
            "lines": [{"x1": 20.0, "y1": 20.0, "x2": 20.0,
                       "y2": 190.02,
                       "claim": "height of the suited figure height",
                       "description":
                           "the line runs along the suited figure height",
                       "view": "front", "dimension": "height",
                       "agrees": True,
                       "why": "the description matches the claim"}],
            "overlay_artifact": "artifacts/t1_check_line_0.png",
            "turn": 1}) + "\n")
    good["references"] = [ref]
    good["scale"]["second_reference_index"] = None
    good["scale"]["second_reference_absent_reason"] = \
        "no second independent object visible at the same depth"
    good["scale"]["extent_px"] = dict(ref["extent_px"])
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert _dim_codes(report) == []

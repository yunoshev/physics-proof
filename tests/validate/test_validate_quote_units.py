# generated from brief/11 · part 11 owns this file
"""A table's unit counts; a quote must be in the search (brief §24)."""

import copy
import json

TABLE_QUOTE = ("Hand length (mm) 182.50 \u00b1 6.60 199.50 \u00b1 9.40 "
               "188.10 \u00b1 11.10 213.90\u2013171.10")


def test_table_label_unit_supports_bounds():
    from src.validate.ranges import quote_contains_number

    assert quote_contains_number(TABLE_QUOTE, "", 0.1711) is True
    assert quote_contains_number(TABLE_QUOTE, "", 0.2139) is True
    assert quote_contains_number(TABLE_QUOTE, "", 0.5) is False


def test_two_units_give_no_label_fallback():
    from src.validate.ranges import named_units, quote_contains_number

    # Each bare number matches the bound under one of the two units,
    # so any single-unit fallback would accept it: only the veto
    # rejects.
    quote = "Hand length (mm) 171.10, width (cm) 17.11"
    assert named_units(quote) == {"mm", "cm"}
    assert quote_contains_number(quote, "", 0.1711) is False
    # The suffixed number still converts with its own unit.
    assert quote_contains_number("palm 8.2 cm", "", 0.082) is True


def test_fact_text_unit_fallback():
    from src.validate.ranges import quote_contains_number

    assert quote_contains_number("171.10", "", 0.1711,
                                 fact_text="171.10 mm") is True
    assert quote_contains_number("171.10", "", 171.10,
                                 fact_text="171.10 mm") is False
    # No unit anywhere: a bare number stays unitless, as before.
    assert quote_contains_number("0.45", "", 0.45) is True


def test_quote_shortening_and_dash_variants():
    from src.validate.ranges import quote_in_search

    facts = {"https://example.com/survey": [
        {"quote": "  average   hand length 171 mm ",
         "text": "the survey reports 171 mm"}]}
    assert quote_in_search("hand length 171 mm",
                           "https://example.com/survey", facts) is True
    facts = {"https://example.com/survey": [
        {"quote": "range 213.90\u2013171.10 mm", "text": ""}]}
    assert quote_in_search("range 213.90-171.10 mm",
                           "https://example.com/survey", facts) is True
    assert quote_in_search("171.10 mm",
                           "https://example.com/survey", facts) is True
    assert quote_in_search("",
                           "https://example.com/survey", facts) is False
    assert quote_in_search("range 171.10 mm",
                           "https://example.com/other", facts) is False


def _table_evidence(evidence):
    """Baseline evidence plus a table-quoted hand-length range check."""
    good = copy.deepcopy(evidence)
    good["range_checks"] = [
        {
            "id": "hand_length",
            "label": "hand length",
            "answers": "It settles whether the hand length is adult.",
            "unit": "m",
            "frame": 0,
            "extents": [
                {"name": "hand length", "x1": 50.0, "y1": 40.0,
                 "x2": 50.0, "y2": 240.0, "length_px": 200.0,
                 "frame": 0}],
            "value": 0.19,
            "sigma": 0.012,
            "formula": "length_px x m_per_px",
            "uses_scale": False,
            "measurement_artifact": "artifacts/measure_hand.txt",
            "range": {
                "min": 0.1711, "max": 0.2139, "typical": 0.19,
                "what": "adult hands, anthropometric table, 2012",
                "bounds_kind": "min-max", "percentiles": None,
                "sources": [
                    {"url": "https://example.com/handsurvey",
                     "domain": "example.com",
                     "quote": TABLE_QUOTE,
                     "quote_highlight": "213.90",
                     "value": 0.2139, "bound": "max",
                     "source_type": "survey report"},
                    {"url": "https://example.com/handsurvey",
                     "domain": "example.com",
                     "quote": TABLE_QUOTE,
                     "quote_highlight": "171.10",
                     "value": 0.1711, "bound": "min",
                     "source_type": "survey report"}],
            },
        },
    ]
    return good


def _table_files(run_dir, ctx, search_quote):
    import numpy as np

    from src.helpers.masks_io import save_masks

    (run_dir / "artifacts" / "measure_hand.txt").write_text(
        "hand_px = 200.0\nx1 = 50.0\ny1 = 40.0\nx2 = 50.0\ny2 = 240.0\n"
        "length_px = 200.0\nvalue = 0.19\nsigma = 0.012\n"
        "formula = length_px x m_per_px\n",
        encoding="utf-8")
    search = {"query": "adult hand length table",
              "facts": [{"url": "https://example.com/handsurvey",
                         "quote": search_quote,
                         "text": search_quote}]}
    (run_dir / "artifacts" / "t9_web_search_9.json").write_text(
        json.dumps(search), encoding="utf-8")
    # The typed extent must lie on a mask from this run (brief §25).
    canvas = np.zeros((300, 400), dtype=bool)
    canvas[40:241, 45:55] = True
    save_masks(str(run_dir / "artifacts" / "extent_cover.npz"),
               {"cover": {0: canvas}})
    # The typed extent needs an agreeing check_line record (§28).
    # Append: the baseline journal already confirms the reference
    # lines (§50); overwriting it would drop those records.
    with (run_dir / "artifacts" / "line_checks.jsonl").open(
            "a", encoding="utf-8") as _journal:
        _journal.write(
            json.dumps({
                "frame": 0,
                "lines": [{
                    "x1": 50.0, "y1": 40.0, "x2": 50.0, "y2": 240.0,
                    "claim": "hand length",
                    "description": "the line runs along the hand",
                    "agrees": True, "why": "the description matches"}],
                "overlay_artifact": "artifacts/t1_check_line_0.png",
                "turn": 1}) + "\n")
    ctx["artifacts"] = sorted(
        str(p.relative_to(run_dir)) for p in
        (run_dir / "artifacts").rglob("*") if p.is_file())
    ctx["produced_files"] = sorted(set(ctx["produced_files"]) | {
        "artifacts/measure_hand.txt", "artifacts/t9_web_search_9.json",
        "artifacts/extent_cover.npz", "artifacts/line_checks.jsonl"})


def test_table_quote_accepted_end_to_end(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _table_evidence(evidence)
    _table_files(run_dir, ctx, TABLE_QUOTE)
    report = validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]


def test_two_unit_quote_rejected_end_to_end(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _table_evidence(evidence)
    quote = "Hand length (mm) 171.10, width (cm) 17.11"
    for source in good["range_checks"][0]["range"]["sources"]:
        source["quote"] = quote
    _table_files(run_dir, ctx, quote)
    report = validate(good, dict(ctx), dry_run=True)
    assert report["accepted"] is False
    assert any(e["code"] == "RANGE_SOURCE_MISSING"
               for e in report["errors"]), report["errors"]


def _min_max_quotes(good, min_quote, max_quote):
    sources = good["range_checks"][0]["range"]["sources"]
    for source in sources:
        if source.get("bound") == "min":
            source["quote"] = min_quote
            source["quote_highlight"] = "171 mm"
        else:
            source["quote"] = max_quote
            source["quote_highlight"] = "214 mm"


def test_range_quote_absent_from_search_fails_with_new_detail(
        baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _table_evidence(evidence)
    min_quote = "smallest adult hand length 171 mm"
    max_quote = "largest adult hand length 214 mm"
    _min_max_quotes(good, min_quote, max_quote)
    # The run's records carry a different quote for that URL.
    _table_files(run_dir, ctx, TABLE_QUOTE)
    report = validate(good, dict(ctx), dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "RANGE_SOURCE_MISSING"]
    assert len(matches) == 2, report["errors"]
    for match in matches:
        assert match["detail"] == (
            "this quote is not in what web_search returned for "
            "https://example.com/handsurvey; copy it from the search "
            "result"), match["detail"]
    # The same quotes present in the records pass.
    _table_files(run_dir, ctx, min_quote + " " + max_quote)
    report = validate(good, dict(ctx), dry_run=True)
    assert not any(e["code"] == "RANGE_SOURCE_MISSING"
                   for e in report["errors"]), report["errors"]


def test_reference_quote_absent_fails_with_new_detail(
        baseline, tmp_path):
    from src.validate import validate

    evidence, _run_dir, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["references"][0]["sources"][0]["quote"] = \
        "the block is about yay high"
    report = validate(bad, dict(ctx), dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["field"] == "references[0].sources[0].quote"]
    assert matches, report["errors"]
    assert matches[0]["detail"] == (
        "this quote is not in what web_search returned for "
        "https://example.com/block; copy it from the search "
        "result"), matches[0]["detail"]


def test_reference_quotes_present_pass(baseline, tmp_path):
    from src.validate import validate

    evidence, _run_dir, ctx, _produced = baseline(tmp_path)
    report = validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert not any(e["field"].endswith(".quote")
                   for e in report["errors"]), report["errors"]

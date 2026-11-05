# generated from brief/11 · part 11 owns this file
"""A range check never re-measures a reference (brief §48)."""

import copy
import json

import pytest

REF_LINE = {"x1": 20.0, "y1": 20.0, "x2": 20.0, "y2": 86.0,
            "length_px": 66.0, "frame": 10}


def _write_search(run_dir, ctx):
    search = {"query": "block line length survey",
              "facts": [
                  {"url": "https://example.com/blockline",
                   "quote": "shortest block line 0.10 m",
                   "text": "shortest block line 0.10 m"},
                  {"url": "https://example.com/blockline",
                   "quote": "longest block line 0.30 m",
                   "text": "longest block line 0.30 m"},
              ]}
    (run_dir / "artifacts" / "t9_web_search_9.json").write_text(
        json.dumps(search), encoding="utf-8")
    ctx["artifacts"].append("artifacts/t9_web_search_9.json")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/t9_web_search_9.json")


def _write_measure(run_dir, ctx, x1=20.0, y1=20.0, x2=20.0, y2=86.0,
                   length=66.0, value=0.66, sigma=0.05):
    (run_dir / "artifacts" / "measure_block.txt").write_text(
        f"x1 = {x1}\ny1 = {y1}\nx2 = {x2}\ny2 = {y2}\n"
        f"length_px = {length}\nvalue = {value}\nsigma = {sigma}\n"
        "formula = length_px x m_per_px\n",
        encoding="utf-8")
    ctx["artifacts"].append("artifacts/measure_block.txt")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/measure_block.txt")


def _write_journal(run_dir, ctx, x1=20.0, y1=20.0, x2=20.0, y2=86.0):
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "frame": 10,
            "lines": [{"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                       "claim": "reference block height",
                       "description": ("the line runs along the "
                                       "reference block height"),
                       "agrees": True,
                       "why": "the description matches the claim"}],
            "overlay_artifact": "artifacts/t1_check_line_0.png",
            "turn": 1}) + "\n")
    if "artifacts/line_checks.jsonl" not in ctx["artifacts"]:
        ctx["artifacts"].append("artifacts/line_checks.jsonl")
    ctx["artifacts"].sort()
    if "artifacts/line_checks.jsonl" not in ctx["produced_files"]:
        ctx["produced_files"].append("artifacts/line_checks.jsonl")


def _block_check_evidence(evidence, extent=None):
    good = copy.deepcopy(evidence)
    good["range_checks"] = [{
        "id": "block_height",
        "label": "reference block height",
        "answers": "It settles whether the stacked block is quoted.",
        "unit": "m",
        "frame": 10,
        "extents": [dict({"name": "reference block height"},
                         **(extent if extent is not None else REF_LINE))],
        "value": 0.66,
        "sigma": 0.05,
        "formula": "length_px x m_per_px",
        "uses_scale": True,
        "measurement_artifact": "artifacts/measure_block.txt",
        "range": {
            "min": 0.10, "max": 0.30, "typical": 0.20,
            "what": "quoted block lines, line survey, 2012",
            "bounds_kind": "min-max", "percentiles": None,
            "sources": [
                {"url": "https://example.com/blockline",
                 "domain": "example.com",
                 "quote": "shortest block line 0.10 m",
                 "quote_highlight": "0.10 m",
                 "value": 0.10, "bound": "min",
                 "source_type": "survey report"},
                {"url": "https://example.com/blockline",
                 "domain": "example.com",
                 "quote": "longest block line 0.30 m",
                 "quote_highlight": "0.30 m",
                 "value": 0.30, "bound": "max",
                 "source_type": "survey report"}],
        },
    }]
    return good


def test_range_check_on_reference_line_refused(baseline, tmp_path):
    # Brief §48, Moon run 85786ac8's shape: the range check measures
    # the same line as the reference, so its length equals the quoted
    # size by construction. The submit is refused, and the refused
    # check never decides the verdict (which stays off impossible).
    from src.validate import validate
    from src.validate.validate import assemble_result, run_checks

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = _block_check_evidence(evidence)
    _write_search(run_dir, ctx)
    _write_measure(run_dir, ctx)
    _write_journal(run_dir, ctx)
    dry = validate(good, ctx, dry_run=True)
    assert dry["accepted"] is False
    matches = [e for e in dry["errors"]
               if e["code"] == "RANGE_CHECK_ON_REFERENCE"]
    assert len(matches) == 1, dry["errors"]
    assert matches[0]["field"] == "range_checks[0]", dry["errors"]
    assert "reference block height" in matches[0]["detail"]
    assert "reference block" in matches[0]["detail"]
    assert "frame 10" in matches[0]["detail"]
    assert "Remove the range check" in matches[0]["detail"]
    errors, computed = run_checks(copy.deepcopy(good), dict(ctx),
                                  dry_run=True)
    assert any(e["code"] == "RANGE_CHECK_ON_REFERENCE"
               for e in errors), errors
    result = assemble_result(copy.deepcopy(good), dict(ctx), computed)
    scored = {c["id"]: c for c in result["range_checks"]}
    assert scored["block_height"]["outcome"] == "not_counted"
    assert result["verdict"]["kind"] != "impossible"


@pytest.mark.parametrize("extent", [
    pytest.param(dict(REF_LINE, frame=321), id="other-frame"),
    pytest.param(dict(REF_LINE, x2=25.0), id="endpoint-5px-away"),
])
def test_range_check_moved_off_the_line_passes(baseline, tmp_path,
                                               extent):
    # The same check on another frame, or with one endpoint 5 px
    # away, measures something else: no RANGE_CHECK_ON_REFERENCE.
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = _block_check_evidence(evidence, extent=extent)
    _write_search(run_dir, ctx)
    _write_measure(run_dir, ctx)
    _write_journal(run_dir, ctx)
    dry = validate(good, ctx, dry_run=True)
    assert not any(e["code"] == "RANGE_CHECK_ON_REFERENCE"
                   for e in dry["errors"]), (extent, dry["errors"])


def test_range_check_on_other_lines_passes(baseline, tmp_path):
    # Hand run 1's shape: the references sit on other lines than the
    # range checks, so the rule stays silent.
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    ref = evidence["references"][0]
    ref["name"] = "phone long edge"
    ref["extent_description"] = "long edge of the phone"
    ref["extent_px"] = {"x1": 10.0, "y1": 300.0, "x2": 10.0,
                        "y2": 339.2, "length_px": 329.2, "frame": 10}
    evidence["scale"]["extent_px"] = dict(ref["extent_px"])
    good = _block_check_evidence(evidence)
    _write_search(run_dir, ctx)
    _write_measure(run_dir, ctx)
    _write_journal(run_dir, ctx)
    dry = validate(good, ctx, dry_run=True)
    assert not any(e["code"] == "RANGE_CHECK_ON_REFERENCE"
                   for e in dry["errors"]), dry["errors"]

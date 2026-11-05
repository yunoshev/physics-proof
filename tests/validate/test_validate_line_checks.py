# generated from brief/11 · part 11 owns this file
"""A range check's lines are confirmed by ``check_line`` (brief §28)."""

import copy
import json


def _write_search(run_dir, ctx):
    search = {"query": "extent line survey",
              "facts": [
                  {"url": "https://example.com/linesurvey",
                   "quote": "shortest line 0.190 m",
                   "text": "shortest line 0.190 m"},
                  {"url": "https://example.com/linesurvey",
                   "quote": "longest line 0.210 m",
                   "text": "longest line 0.210 m"},
              ]}
    (run_dir / "artifacts" / "t9_web_search_9.json").write_text(
        json.dumps(search), encoding="utf-8")
    ctx["artifacts"].append("artifacts/t9_web_search_9.json")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/t9_web_search_9.json")


def _write_measure(run_dir, ctx):
    (run_dir / "artifacts" / "measure_line.txt").write_text(
        "x1 = 100.0\ny1 = 100.0\nx2 = 150.0\ny2 = 100.0\n"
        "length_px = 50.0\nvalue = 0.20\nsigma = 0.02\n"
        "formula = length_px\n",
        encoding="utf-8")
    ctx["artifacts"].append("artifacts/measure_line.txt")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/measure_line.txt")


def _write_cover(run_dir, ctx):
    import numpy as np

    from src.helpers.masks_io import save_masks

    canvas = np.zeros((300, 400), dtype=bool)
    canvas[90:111, 90:161] = True
    save_masks(str(run_dir / "artifacts" / "extent_cover.npz"),
               {"cover": {0: canvas}})
    ctx["artifacts"].append("artifacts/extent_cover.npz")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/extent_cover.npz")


def _write_journal(run_dir, ctx, lines):
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        for record in lines:
            handle.write(json.dumps(record) + "\n")
    if "artifacts/line_checks.jsonl" not in ctx["artifacts"]:
        ctx["artifacts"].append("artifacts/line_checks.jsonl")
    ctx["artifacts"].sort()
    if "artifacts/line_checks.jsonl" not in ctx["produced_files"]:
        ctx["produced_files"].append("artifacts/line_checks.jsonl")


def _line_evidence(evidence):
    good = copy.deepcopy(evidence)
    good["range_checks"] = [{
        "id": "line_length",
        "label": "line length",
        "answers": "It settles whether the line length is quoted.",
        "unit": "m",
        "frame": 0,
        "extents": [{"name": "hand line", "x1": 100.0, "y1": 100.0,
                     "x2": 150.0, "y2": 100.0, "length_px": 50.0,
                     "frame": 0}],
        "value": 0.20,
        "sigma": 0.02,
        "formula": "length_px",
        "uses_scale": False,
        "measurement_artifact": "artifacts/measure_line.txt",
        "range": {
            "min": 0.19, "max": 0.21, "typical": 0.20,
            "what": "quoted lines, line survey, 2012",
            "bounds_kind": "min-max", "percentiles": None,
            "sources": [
                {"url": "https://example.com/linesurvey",
                 "domain": "example.com",
                 "quote": "shortest line 0.190 m",
                 "quote_highlight": "0.190 m",
                 "value": 0.19, "bound": "min",
                 "source_type": "survey report"},
                {"url": "https://example.com/linesurvey",
                 "domain": "example.com",
                 "quote": "longest line 0.210 m",
                 "quote_highlight": "0.210 m",
                 "value": 0.21, "bound": "max",
                 "source_type": "survey report"}],
        },
    }]
    return good


def _agreeing_record():
    return {"frame": 0,
            "lines": [{"x1": 100.0, "y1": 100.0, "x2": 150.0,
                       "y2": 100.0, "claim": "hand line",
                       "description": "the line runs along the hand",
                       "agrees": True,
                       "why": "the description matches the claim"}],
            "overlay_artifact": "artifacts/t1_check_line_0.png",
            "turn": 1}


def test_line_check_agreeing_records_pass(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = _line_evidence(evidence)
    _write_search(run_dir, ctx)
    _write_measure(run_dir, ctx)
    _write_cover(run_dir, ctx)
    _write_journal(run_dir, ctx, [_agreeing_record()])
    report = validate(good, ctx, dry_run=True)
    assert not any(e["code"] == "RANGE_LINE_NOT_CONFIRMED"
                   for e in report["errors"]), report["errors"]


def test_line_check_disagreeing_record_names_blind_description(
        baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = _line_evidence(evidence)
    _write_search(run_dir, ctx)
    _write_measure(run_dir, ctx)
    _write_cover(run_dir, ctx)
    record = _agreeing_record()
    record["lines"][0]["agrees"] = False
    record["lines"][0]["description"] = (
        "the line crosses the empty table beside the hand")
    _write_journal(run_dir, ctx, [record])
    report = validate(good, ctx, dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "RANGE_LINE_NOT_CONFIRMED"]
    assert matches, report["errors"]
    assert ("the line crosses the empty table beside the hand"
            in matches[0]["detail"]), matches[0]["detail"]


def test_line_check_missing_record_names_check_line_call(
        baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = _line_evidence(evidence)
    _write_search(run_dir, ctx)
    _write_measure(run_dir, ctx)
    _write_cover(run_dir, ctx)
    report = validate(good, ctx, dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "RANGE_LINE_NOT_CONFIRMED"]
    assert matches, report["errors"]
    detail = matches[0]["detail"]
    assert "check_line(frame=0" in detail, detail
    assert "hand line" in detail, detail
    assert "100.0" in detail and "150.0" in detail, detail

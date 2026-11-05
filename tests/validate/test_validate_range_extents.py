# generated from brief/11 · part 11 owns this file
"""Range extents lie on what they measure (brief §25)."""

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


def _write_measure(run_dir, ctx, extents, value=0.20, sigma=0.02):
    lines = []
    for pos, extent in enumerate(extents):
        for key in ("x1", "y1", "x2", "y2", "length_px"):
            lines.append(f"{key} = {extent[key]}")
    lines.append(f"value = {value}")
    lines.append(f"sigma = {sigma}")
    lines.append("formula = length_px")
    (run_dir / "artifacts" / "measure_line.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    ctx["artifacts"].append("artifacts/measure_line.txt")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/measure_line.txt")


def _write_cover(run_dir, ctx, shape, boxes):
    import numpy as np

    from src.helpers.masks_io import save_masks

    canvas = np.zeros(shape, dtype=bool)
    for r0, c0, r1, c1 in boxes:
        canvas[r0:r1, c0:c1] = True
    save_masks(str(run_dir / "artifacts" / "extent_cover.npz"),
               {"cover": {0: canvas}})
    ctx["artifacts"].append("artifacts/extent_cover.npz")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/extent_cover.npz")


def _line_check(extents):
    return {
        "id": "line_length",
        "label": "line length",
        "answers": "It settles whether the line length is quoted.",
        "unit": "m",
        "frame": 0,
        "extents": extents,
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
    }


def _line_evidence(evidence, extents):
    good = copy.deepcopy(evidence)
    good["range_checks"] = [_line_check(extents)]
    return good


def test_extent_leaving_picture_rejected(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    # Hand run 2's extent on a 576 x 1024 frame: x = 750 leaves it.
    extents = [{"name": "hand length", "x1": 350.0, "y1": 350.0,
                "x2": 750.0, "y2": 350.0, "length_px": 400.0,
                "frame": 0}]
    good = _line_evidence(evidence, extents)
    _write_search(run_dir, ctx)
    _write_measure(run_dir, ctx, extents)
    _write_cover(run_dir, ctx, (1024, 576), [(0, 0, 10, 10)])
    report = validate(good, ctx, dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "RANGE_EXTENT_OFF_FRAME"]
    assert matches, report["errors"]
    assert "750" in matches[0]["detail"]
    assert "576x1024" in matches[0]["detail"]


def test_extent_away_from_every_mask_rejected(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    extents = [{"name": "hand line", "x1": 100.0, "y1": 100.0,
                "x2": 150.0, "y2": 100.0, "length_px": 50.0,
                "frame": 0}]
    good = _line_evidence(evidence, extents)
    _write_search(run_dir, ctx)
    _write_measure(run_dir, ctx, extents)
    _write_cover(run_dir, ctx, (300, 400), [(0, 0, 10, 10)])
    report = validate(good, ctx, dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "RANGE_EXTENT_NOT_ON_MASK"]
    assert matches, report["errors"]
    assert ("segment hand line on frame 0; both ends of the line "
            "must lie on its mask") in matches[0]["detail"]


def test_extent_frame_without_any_mask_names_it(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    # Frame 305 is past every mask in the run (the whole-clip survey
    # masks cover frames 0-299), so no mask covers it.
    extents = [{"name": "hand line", "x1": 100.0, "y1": 100.0,
                "x2": 150.0, "y2": 100.0, "length_px": 50.0,
                "frame": 305}]
    good = _line_evidence(evidence, extents)
    _write_search(run_dir, ctx)
    _write_measure(run_dir, ctx, extents)
    _write_cover(run_dir, ctx, (300, 400), [(0, 0, 10, 10)])
    report = validate(good, ctx, dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "RANGE_EXTENT_NOT_ON_MASK"]
    assert matches, report["errors"]
    assert "no mask from this run covers frame 305" in matches[0][
        "detail"]


def test_extent_ends_on_mask_passes(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    extents = [{"name": "hand line", "x1": 100.0, "y1": 100.0,
                "x2": 150.0, "y2": 100.0, "length_px": 50.0,
                "frame": 0}]
    good = _line_evidence(evidence, extents)
    _write_search(run_dir, ctx)
    _write_measure(run_dir, ctx, extents)
    _write_cover(run_dir, ctx, (300, 400), [(90, 90, 111, 161)])
    report = validate(good, ctx, dry_run=True)
    assert not any(e["code"] in ("RANGE_EXTENT_OFF_FRAME",
                                 "RANGE_EXTENT_NOT_ON_MASK")
                   for e in report["errors"]), report["errors"]

# generated from brief/11 · part 11 owns this file
"""The shape check measures along the reference's own line (brief §52,
R-S14).

The mask size on a frame is the spread of its pixels along the
direction of the reference's ``extent_px`` line (plus 1 px); a
vertical line gives the mask height, as before. A rectangle 50 px
high and 100 px wide, 125 px wide on the measuring frame, is
unstable under a horizontal line (125 against 100) and steady under
a vertical one. A diagonal-line stand-in for the sped-up run's
"suited figure width" (84 along the line against 78 at rest) is
unstable while the vertical backpack line is not.
"""

import copy
import json


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _write_rect_mask(run_dir, produced, rel, frames, width_at,
                     height=50, top=20, left=20, shape=(240, 352)):
    """One-object mask with per-frame widths (part-09 writer)."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    masks = {}
    for frame in frames:
        width = width_at(frame) if callable(width_at) else width_at
        canvas = np.zeros(shape, dtype=bool)
        canvas[top:top + height, left:left + width] = True
        masks[int(frame)] = canvas
    path = run_dir / rel
    save_masks(str(path), {"0": masks})
    produced.append(rel)
    return rel


def _no_flight_survey(run_dir, produced, n_frames=300):
    """A whole-clip survey with no flight (no candidates)."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    ground = {}
    for frame in range(n_frames):
        canvas = np.zeros((240, 352), dtype=bool)
        canvas[100:160, 150:210] = True
        ground[int(frame)] = canvas
    path = run_dir / "artifacts" / "masks_rest.npz"
    save_masks(str(path), {"0": ground})
    produced.append("artifacts/masks_rest.npz")
    return "artifacts/masks_rest.npz"


def _write_line(run_dir, produced, frame, x1, y1, x2, y2, name):
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "frame": frame,
            "lines": [{"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                       "claim": f"height of the {name}",
                       "description": f"the line runs along the {name}",
                       "view": "front", "dimension": "height",
                       "agrees": True,
                       "why": "the description matches the claim"}],
            "overlay_artifact": "artifacts/t1_check_line_0.png",
            "turn": 1}) + "\n")
    if "artifacts/line_checks.jsonl" not in produced:
        produced.append("artifacts/line_checks.jsonl")


def _refresh(run_dir, produced):
    timing = json.loads(
        (run_dir / "input" / "timing.json").read_text(encoding="utf-8"))
    artifacts = sorted(
        str(p.relative_to(run_dir)) for p in
        (run_dir / "artifacts").rglob("*") if p.is_file())
    return {"run_dir": str(run_dir), "run_id": run_dir.name,
            "timing": timing, "artifacts": artifacts,
            "produced_files": list(produced), "mask_checks": []}


def _rect_evidence(baseline, tmp_path, horizontal):
    """Baseline with a 100 px wide rectangle mask, 125 on frame 61."""
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    rel = _write_rect_mask(run_dir, produced,
                           "artifacts/rect_shape_0.npz",
                           list(range(62)),
                           lambda f: 125 if f == 61 else 100)
    ref = good["references"][0]
    ref["mask"] = {"artifact": rel, "object_id": "0", "frame": 61,
                   "outline": [[20.0, 20.0], [145.0, 20.0],
                               [145.0, 70.0], [20.0, 70.0]]}
    if horizontal:
        ref["extent_px"] = {"x1": 20.0, "y1": 45.0, "x2": 86.0,
                            "y2": 45.0, "length_px": 66.0,
                            "frame": 61}
    else:
        ref["extent_px"] = {"x1": 20.0, "y1": 20.0, "x2": 20.0,
                            "y2": 86.0, "length_px": 66.0,
                            "frame": 61}
    _write_line(run_dir, produced, 61, ref["extent_px"]["x1"],
                ref["extent_px"]["y1"], ref["extent_px"]["x2"],
                ref["extent_px"]["y2"], "rectangle")
    survey = _no_flight_survey(run_dir, produced)
    good["first_look"]["overview"]["artifact"] = survey
    return good, _refresh(run_dir, produced)


def test_horizontal_line_measures_width(baseline, tmp_path):
    """125 px wide on the measuring frame against 100 at rest."""
    good, ctx = _rect_evidence(baseline, tmp_path, horizontal=True)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is False, report["errors"]
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_SHAPE_UNSTABLE"
               and e["field"] == "references[0].extent_px"]
    assert matches, report["errors"]
    detail = matches[0]["detail"]
    assert "125" in detail, detail
    assert "100" in detail, detail
    assert "along the measured line" in detail, detail


def test_vertical_line_measures_height(baseline, tmp_path):
    """The same masks are steady under a vertical line (50 = 50)."""
    good, ctx = _rect_evidence(baseline, tmp_path, horizontal=False)
    report = _validate(good, dict(ctx))
    assert not [e for e in report["errors"]
                if e["code"] in ("REFERENCE_SHAPE_UNSTABLE",
                                 "REFERENCE_SHAPE_UNCHECKED")], \
        report["errors"]


def _width_evidence(baseline, tmp_path):
    """The sped-up run's shape: figure width 84 along its line.

    Rest frames span 78 px along the reference's horizontal line;
    the measuring frame spans 84 px. The vertical backpack line is
    steady at 66 px everywhere.
    """
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    fig_rel = _write_rect_mask(
        run_dir, produced, "artifacts/t91_segment_0.npz",
        list(range(21)), lambda f: 84 if f == 10 else 78,
        height=131, top=50, left=67)
    pack_rel = _write_rect_mask(
        run_dir, produced, "artifacts/t92_segment_1.npz",
        list(range(21)), 20, height=66, top=20, left=20)
    pack, figure = good["references"]
    pack["name"] = "backpack height"
    pack["mask"] = {"artifact": pack_rel, "object_id": "0",
                    "frame": 10,
                    "outline": [[20.0, 20.0], [40.0, 20.0],
                                [40.0, 86.0], [20.0, 86.0]]}
    figure["name"] = "suited figure width"
    figure["size_m"] = 0.82
    figure["size_tolerance_m"] = 0.20
    figure["extent_px"] = {"x1": 67.0, "y1": 115.0, "x2": 147.0,
                           "y2": 115.0, "length_px": 80.0,
                           "frame": 10}
    figure["sources"] = [
        {"url": "https://example.com/suitwidth",
         "domain": "example.com",
         "quote": "suited width 82 cm",
         "quote_highlight": "82 cm",
         "value_m": 0.82,
         "source_type": "reference"}]
    figure["mask"] = {"artifact": fig_rel, "object_id": "0",
                      "frame": 10,
                      "outline": [[67.0, 50.0], [151.0, 50.0],
                                  [151.0, 181.0], [67.0, 181.0]]}
    check = {"overlay_artifact": "artifacts/view_0.jpg",
             "coverage_answer": "covers the suited figure",
             "alternatives": [], "confidence": None, "turn": 1}
    (run_dir / "artifacts" / "check_fig.json").write_text(
        json.dumps(check), encoding="utf-8")
    produced.append("artifacts/check_fig.json")
    figure["mask_check"] = {
        "artifact": "artifacts/check_fig.json",
        "coverage_answer": "covers the suited figure",
        "confidence": None, "alternative_readings": []}
    facts = json.loads(
        (run_dir / "artifacts" / "t0_web_search_0.json").read_text(
            encoding="utf-8"))
    facts["facts"].append(
        {"url": "https://example.com/suitwidth",
         "quote": "suited width 82 cm",
         "text": "suited width 82 cm"})
    (run_dir / "artifacts" / "t0_web_search_0.json").write_text(
        json.dumps(facts), encoding="utf-8")
    _write_line(run_dir, produced, 10, 67.0, 115.0, 147.0, 115.0,
                "suited figure width")
    return good, _refresh(run_dir, produced)


def test_figure_width_unstable_backpack_steady(baseline, tmp_path):
    """84 along the line against 78 at rest; the backpack passes."""
    good, ctx = _width_evidence(baseline, tmp_path)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is False, report["errors"]
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_SHAPE_UNSTABLE"]
    assert len(matches) == 1, report["errors"]
    assert matches[0]["field"] == "references[1].extent_px", matches
    detail = matches[0]["detail"]
    assert "84" in detail, detail
    assert "78" in detail, detail
    assert "along the measured line" in detail, detail

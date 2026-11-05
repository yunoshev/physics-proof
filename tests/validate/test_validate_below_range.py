# generated from brief/11 · part 11 owns this file
"""Falling short of a range never decides "not realistic" (brief §38).

A range check whose measured value lies below the range's minimum
has the outcome ``below``. Its step reads "below the typical range",
and on its own it decides no "not realistic" verdict. Above the
maximum keeps its current meaning.
"""

import copy
import json


def _write(path, content, produced, run_dir):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    produced.append(str(path.relative_to(run_dir)))


def _write_cover(run_dir, produced):
    import numpy as np

    from src.helpers.masks_io import save_masks

    canvas = np.zeros((500, 300), dtype=bool)
    canvas[100:410, 140:160] = True
    save_masks(str(run_dir / "artifacts" / "cover.npz"),
               {"cover": {0: canvas}})
    produced.append("artifacts/cover.npz")


def _write_journal(run_dir, ctx, frame, x1, y1, x2, y2, name,
                   dimension="height", view="front"):
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "frame": frame,
            "lines": [{"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                       "claim": name,
                       "description": f"the line runs along {name}",
                       "view": view, "dimension": dimension,
                       "agrees": True,
                       "why": "the description matches the claim"}],
            "overlay_artifact": "artifacts/t1_check_line_0.png",
            "turn": 1}) + "\n")
    for rel in ("artifacts/line_checks.jsonl",):
        if rel not in ctx["artifacts"]:
            ctx["artifacts"].append(rel)
    ctx["artifacts"].sort()
    if "artifacts/line_checks.jsonl" not in ctx["produced_files"]:
        ctx["produced_files"].append("artifacts/line_checks.jsonl")


def _write_search(run_dir, ctx, facts):
    _write(run_dir / "artifacts" / "t1_web_search_0.json",
           json.dumps({"query": "range survey", "facts": facts}),
           ctx["produced_files"], run_dir)
    ctx["artifacts"].append("artifacts/t1_web_search_0.json")
    ctx["artifacts"].sort()


def _refresh_ctx(ctx, produced):
    ctx["artifacts"] = sorted(set(ctx["artifacts"]) | set(produced))
    ctx["produced_files"] = sorted(
        set(ctx["produced_files"]) | set(produced))


def _check_record(run_dir, ctx, produced, name, coverage):
    content = {"overlay_artifact": "artifacts/view_0.jpg",
               "coverage_answer": coverage,
               "alternatives": [], "confidence": None, "turn": 1}
    rel = f"artifacts/check_{name}.json"
    _write(run_dir / rel, json.dumps(content), produced, run_dir)
    return rel


def _mask(run_dir, produced, name, boxes):
    from src.helpers.masks_io import save_masks

    masks = {}
    for object_id, frames in boxes.items():
        per_frame = {}
        for frame, rects in frames.items():
            import numpy as np

            canvas = np.zeros((500, 300), dtype=bool)
            for r0, c0, r1, c1 in rects:
                canvas[r0:r1, c0:c1] = True
            per_frame[int(frame)] = canvas
        masks[object_id] = per_frame
    rel = f"artifacts/{name}.npz"
    save_masks(str(run_dir / rel), masks)
    produced.append(rel)
    return rel


def _range_only(evidence, ref, scale_m, scale_sigma, check):
    """A still-frame evidence: no segments, one reference, checks."""
    good = copy.deepcopy(evidence)
    good["segments"] = []
    # Range-only evidence measures no motion, so it carries no survey.
    good["first_look"].pop("overview", None)
    good["worlds"] = {"candidates": [{"world": "Earth"}],
                      "excluded": []}
    good["clock"] = None
    good["clock_absent_reason"] = "no motion measured"
    good["error_budget"] = {"components": [], "sigma_relative": 0.0}
    good["first_look"]["motions"] = [
        {"frame_start": 0, "frame_end": 0,
         "description": "still frame, no motion",
         "segment_id": None,
         "skip_reason": "still frame: no motion to measure"}]
    good["references"] = [ref]
    scale = copy.deepcopy(good["scale"])
    scale.update({"frame": 0, "m_per_px": scale_m,
                  "sigma_m_per_px": scale_sigma,
                  "reference_index": 0,
                  "extent_px": dict(ref["extent_px"]),
                  "second_reference_index": None,
                  "second_reference_absent_reason":
                      "only one thing of known size in the still",
                  "check_scale": None})
    good["scale"] = scale
    good["range_checks"] = [check]
    return good


def _reference(name, extent, size_m, tol_m, quote, highlight,
               url, check_rel, mask_rel):
    x1, y1, x2, y2, length, frame = extent
    return {
        "name": name,
        "extent_description": f"measured extent of {name}",
        "extent_type": "face_on",
        "extent_px": {"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                      "length_px": length, "frame": frame},
        "size_m": size_m,
        "size_tolerance_m": tol_m,
        "size_derivation": {
            "mode": "single", "note": "quoted size",
            "state_match": {
                "shown_and_covered": "mark shown and covered",
                "shown_not_covered": "edge shown but not covered"}},
        "sources": [{"url": url, "domain": "example.com",
                     "quote": quote, "quote_highlight": highlight,
                     "value_m": size_m, "source_type": "survey"}],
        "mask": {"artifact": mask_rel, "object_id": "0",
                 "frame": frame,
                 "outline": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]},
        "mask_check": {"artifact": check_rel,
                       "coverage_answer": "covers the survey mark",
                       "confidence": None,
                       "alternative_readings": []},
    }


def _check(check_id, label, extents, value, sigma, uses_scale,
           low, high, typical, what, min_quote, min_hi,
           max_quote, max_hi, url):
    names = [e[0] for e in extents]
    items = [{"name": name, "x1": x1, "y1": y1, "x2": x2,
              "y2": y2, "length_px": length, "frame": frame}
             for name, x1, y1, x2, y2, length, frame in extents]
    _ = names
    return {
        "id": check_id, "label": label,
        "answers": "It settles part of the question.",
        "unit": "m", "frame": 0, "extents": items,
        "value": value, "sigma": sigma,
        "formula": "length_px x m_per_px",
        "uses_scale": uses_scale,
        "measurement_artifact": "artifacts/measure.txt",
        "range": {
            "min": low, "max": high, "typical": typical,
            "what": what, "bounds_kind": "min-max",
            "percentiles": None,
            "sources": [
                {"url": url, "domain": "example.com",
                 "quote": min_quote, "quote_highlight": min_hi,
                 "value": low, "bound": "min",
                 "source_type": "survey report"},
                {"url": url, "domain": "example.com",
                 "quote": max_quote, "quote_highlight": max_hi,
                 "value": high, "bound": "max",
                 "source_type": "survey report"}]},
    }


def _below_run(baseline, tmp_path):
    from src.validate import validate  # noqa: F401

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    _write_cover(run_dir, produced)
    mask_rel = _mask(run_dir, produced, "mark",
                     {"0": {0: [(110, 140, 280, 160)]}})
    check_rel = _check_record(run_dir, ctx, produced, "mark",
                              "covers the survey mark")
    ref = _reference("survey mark", (150.0, 120.0, 150.0, 270.0,
                                     150.0, 0),
                     0.15, 0.005, "the survey mark is 15 cm tall",
                     "15 cm", "https://example.com/mark",
                     check_rel, mask_rel)
    # A second reference at the same scale, so the check decides as
    # before (§51 needs two references for a verdict).
    peg_rel = _mask(run_dir, produced, "peg",
                    {"0": {0: [(120, 55, 220, 65)]}})
    peg_check = _check_record(run_dir, ctx, produced, "peg",
                              "covers the survey peg")
    peg = _reference("survey peg", (60.0, 120.0, 60.0, 220.0,
                                    100.0, 0),
                     0.10, 0.005, "the survey peg is 10 cm tall",
                     "10 cm", "https://example.com/peg",
                     peg_check, peg_rel)
    check = _check(
        "jump_height", "jump height at apex",
        [("jump", 150.0, 112.0, 150.0, 400.0, 288.0, 0)],
        0.288, 0.021, True, 0.41, 0.60, 0.50,
        "adult men vertical jump height norms",
        "adult men vertical jump height norms minimum 41 cm",
        "41 cm",
        "adult men vertical jump height norms maximum 60 cm",
        "60 cm", "https://example.com/jump")
    good = _range_only(evidence, ref, 0.001, 0.000036, check)
    good["references"].append(peg)
    good["scale"]["second_reference_index"] = 1
    good["scale"]["second_reference_absent_reason"] = None
    _write(run_dir / "artifacts" / "measure.txt",
           "x1 = 150.0\ny1 = 112.0\nx2 = 150.0\ny2 = 400.0\n"
           "length_px = 288.0\nvalue = 0.288\nsigma = 0.021\n"
           "formula = length_px x m_per_px\n",
           produced, run_dir)
    ctx["artifacts"].append("artifacts/measure.txt")
    ctx["artifacts"].sort()
    _write_journal(run_dir, ctx, 0, 150.0, 112.0, 150.0, 400.0,
                   "jump")
    # The survey-mark reference line needs its own blind check (§50).
    _write_journal(run_dir, ctx, 0, 150.0, 120.0, 150.0, 270.0,
                   "height of the survey mark")
    _write_journal(run_dir, ctx, 0, 60.0, 120.0, 60.0, 220.0,
                   "height of the survey peg")
    _write_search(run_dir, ctx, [
        {"url": "https://example.com/mark",
         "quote": "the survey mark is 15 cm tall",
         "text": "the survey mark is 15 cm tall"},
        {"url": "https://example.com/peg",
         "quote": "the survey peg is 10 cm tall",
         "text": "the survey peg is 10 cm tall"},
        {"url": "https://example.com/jump",
         "quote": ("adult men vertical jump height norms "
                   "minimum 41 cm"),
         "text": ("adult men vertical jump height norms "
                   "minimum 41 cm")},
        {"url": "https://example.com/jump",
         "quote": ("adult men vertical jump height norms "
                   "maximum 60 cm"),
         "text": ("adult men vertical jump height norms "
                  "maximum 60 cm")},
    ])
    _refresh_ctx(ctx, produced)
    return good, run_dir, ctx


def test_below_minimum_decides_no_not_realistic(baseline, tmp_path):
    # Moon run 23's range check: 0.288 m against a 0.41 m minimum
    # yields outcome below, and on its own decides no
    # "not realistic" verdict.
    from src.validate import validate

    good, _run, ctx = _below_run(baseline, tmp_path)
    dry = validate(good, ctx, dry_run=True)
    hard = [e for e in dry["errors"]
            if isinstance(e, dict) and not e.get("push")]
    assert hard == [], dry["errors"]
    report = validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    scored = {c["id"]: c for c in report["result"]["range_checks"]}
    entry = scored["jump_height"]
    assert entry["outcome"] == "below", entry
    assert entry["side"] == "below", entry
    assert abs(entry["delta_sigma"] - 5.8) < 0.1, entry
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "undetermined", verdict
    assert verdict["decided_by"] == "jump_height", verdict
    reason = verdict["reason"] or ""
    assert "below the typical range" in reason, reason
    sentence = report["result"]["sentence"]
    assert sentence.startswith("Undetermined:"), sentence
    assert "below the typical range" in sentence, sentence
    steps = [s for s in report["result"]["calculation_steps"]
             if s.get("title") == "Range check jump height at apex"]
    assert steps, report["result"]["calculation_steps"]
    full = " ".join(b.get("text", "")
                    for b in steps[0].get("full", [])
                    if isinstance(b, dict))
    assert "below the typical range" in full, full


def _above_run(baseline, tmp_path):
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    _write_cover(run_dir, produced)
    mask_rel = _mask(run_dir, produced, "pole",
                     {"0": {0: [(110, 140, 230, 160)]}})
    check_rel = _check_record(run_dir, ctx, produced, "pole",
                              "covers the survey pole")
    ref = _reference("survey pole", (150.0, 120.0, 150.0, 220.0,
                                     100.0, 0),
                     5.0, 0.1, "the survey pole is 5 m tall",
                     "5 m", "https://example.com/pole",
                     check_rel, mask_rel)
    # A second reference at the same scale, so the check decides as
    # before (§51 needs two references for a verdict).
    post_rel = _mask(run_dir, produced, "post",
                     {"0": {0: [(120, 55, 160, 65)]}})
    post_check = _check_record(run_dir, ctx, produced, "post",
                               "covers the gate post")
    post = _reference("gate post", (60.0, 120.0, 60.0, 160.0,
                                    40.0, 0),
                      2.0, 0.05, "the gate post is 2 m tall",
                      "2 m", "https://example.com/post",
                      post_check, post_rel)
    check = _check(
        "wall_height", "wall height",
        [("wall", 150.0, 100.0, 150.0, 302.0, 202.0, 0)],
        10.1, 0.5, True, 2.0, 4.0, 3.0,
        "tall garden walls, survey of walls, 2020",
        "tall garden walls stand at least 2 m", "2 m",
        "tall garden walls stand at most 4.0 m", "4.0 m",
        "https://example.com/walls")
    good = _range_only(evidence, ref, 0.05, 0.0015, check)
    good["references"].append(post)
    good["scale"]["second_reference_index"] = 1
    good["scale"]["second_reference_absent_reason"] = None
    _write(run_dir / "artifacts" / "measure.txt",
           "x1 = 150.0\ny1 = 100.0\nx2 = 150.0\ny2 = 302.0\n"
           "length_px = 202.0\nvalue = 10.1\nsigma = 0.5\n"
           "formula = length_px x m_per_px\n",
           produced, run_dir)
    ctx["artifacts"].append("artifacts/measure.txt")
    ctx["artifacts"].sort()
    _write_journal(run_dir, ctx, 0, 150.0, 100.0, 150.0, 302.0,
                   "wall")
    # The survey-pole reference line needs its own blind check (§50).
    _write_journal(run_dir, ctx, 0, 150.0, 120.0, 150.0, 220.0,
                   "height of the survey pole")
    _write_journal(run_dir, ctx, 0, 60.0, 120.0, 60.0, 160.0,
                   "height of the gate post")
    _write_search(run_dir, ctx, [
        {"url": "https://example.com/pole",
         "quote": "the survey pole is 5 m tall",
         "text": "the survey pole is 5 m tall"},
        {"url": "https://example.com/post",
         "quote": "the gate post is 2 m tall",
         "text": "the gate post is 2 m tall"},
        {"url": "https://example.com/walls",
         "quote": "tall garden walls stand at least 2 m",
         "text": "tall garden walls stand at least 2 m"},
        {"url": "https://example.com/walls",
         "quote": "tall garden walls stand at most 4.0 m",
         "text": "tall garden walls stand at most 4.0 m"},
    ])
    _refresh_ctx(ctx, produced)
    return good, run_dir, ctx


def test_above_maximum_still_decides_not_realistic(baseline,
                                                   tmp_path):
    # Wall run 15's check: 10.1 m against a 4.0 m maximum still
    # decides "not realistic".
    from src.validate import validate

    good, _run, ctx = _above_run(baseline, tmp_path)
    report = validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    scored = {c["id"]: c for c in report["result"]["range_checks"]}
    entry = scored["wall_height"]
    assert entry["outcome"] == "outside", entry
    assert entry["side"] == "above", entry
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "impossible", verdict
    assert verdict["decided_by"] == "wall_height", verdict
    sentence = report["result"]["sentence"]
    assert sentence.startswith("Not realistic on Earth:"), sentence
    assert "above" in sentence and "maximum" in sentence, sentence

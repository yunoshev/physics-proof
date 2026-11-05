# generated from brief/11 · part 11 owns this file
"""A size as quoted, a steady reference shape, next to the motion.

Owner addendum §44 (from the Moon and sped-up Moon runs): R-S13
(SIZE_NOT_AS_QUOTED), R-S14 (REFERENCE_SHAPE_UNSTABLE), the
tightened R-S11 (REFERENCE_FAR_FROM_MOTION as a refusal), and the
part/whole sentence on the gap details (R-S15).
"""

import copy
import json


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _append_line_check(run_dir, frame, x1=20.0, y1=20.0, x2=20.0,
                       y2=86.0, name="reference block"):
    """A blind check record for a moved reference extent (§50)."""
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


def _set_size(ref, size_m):
    ref["size_m"] = size_m
    for source in ref.get("sources", []) or []:
        if isinstance(source, dict):
            source["value_m"] = size_m
    return ref


def _size_codes(report):
    return [e for e in report["errors"]
            if e["code"] == "SIZE_NOT_AS_QUOTED"]


def test_size_not_as_quoted_single(baseline, tmp_path):
    """The Moon run's figure: 1.6 m single against 1.7, 1.7 sources."""
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    figure = bad["references"][1]
    figure["size_m"] = 1.6
    figure["sources"] = [copy.deepcopy(figure["sources"][0]),
                         copy.deepcopy(figure["sources"][0])]
    for source in figure["sources"]:
        source["value_m"] = 1.7
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False, report["errors"]
    matches = _size_codes(report)
    assert matches, report["errors"]
    detail = matches[0]["detail"]
    assert "1.6" in detail, detail
    assert "1.7" in detail, detail
    assert matches[0]["field"] == "references[1].size_m"


def _single_reference(evidence):
    evidence = copy.deepcopy(evidence)
    evidence["references"] = evidence["references"][:1]
    evidence["scale"]["second_reference_index"] = None
    evidence["scale"]["second_reference_absent_reason"] = \
        "no second independent object visible at the same depth"
    return evidence


def _requote_first_reference(run_dir, pairs):
    """Give the first reference fresh sources with a search record."""
    import json as _json

    facts = []
    sources = []
    for url, value, words in pairs:
        quote = f"unit {words} is {value:g} m tall"
        sources.append({"url": url, "domain": "example.com",
                        "quote": quote, "quote_highlight": f"{value:g} m",
                        "value_m": value, "source_type": "catalogue"})
        facts.append({"url": url, "quote": quote, "text": quote})
    path = run_dir / "artifacts" / "t0_web_search_0.json"
    record = _json.loads(path.read_text(encoding="utf-8"))
    record["facts"].extend(facts)
    path.write_text(_json.dumps(record), encoding="utf-8")
    return sources


def test_size_sum_passes(baseline, tmp_path):
    """Run 22's pack: 0.9144 m sum of 0.6604 and 0.254 m passes."""
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _single_reference(evidence)
    ref = good["references"][0]
    ref["size_derivation"]["mode"] = "sum"
    ref["size_m"] = 0.9144
    ref["sources"] = _requote_first_reference(
        run_dir,
        [("https://example.com/plss", 0.6604, "life-support"),
         ("https://example.com/ops", 0.254, "top")])
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert _size_codes(report) == []


def test_size_sum_sped_up_pack_passes(baseline, tmp_path):
    """The sped-up run's pack: 0.914 m sum of 0.66 and 0.254 passes."""
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _single_reference(evidence)
    ref = good["references"][0]
    ref["size_derivation"]["mode"] = "sum"
    ref["size_m"] = 0.914
    ref["sources"] = _requote_first_reference(
        run_dir,
        [("https://example.com/plss", 0.66, "life-support"),
         ("https://example.com/ops", 0.254, "top")])
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert _size_codes(report) == []


def test_size_mean_passes(baseline, tmp_path):
    """A mean of two quoted heights is used as quoted."""
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _single_reference(evidence)
    ref = good["references"][0]
    ref["size_derivation"]["mode"] = "mean"
    ref["size_m"] = 1.71
    ref["sources"] = _requote_first_reference(
        run_dir,
        [("https://example.com/height-a", 1.70, "standing-a"),
         ("https://example.com/height-b", 1.72, "standing-b")])
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert _size_codes(report) == []


def _shape_mask(run_dir, produced, frames, heights, shape=(240, 352)):
    """Reference mask with given per-frame heights (brief §44)."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    masks = {}
    for frame in frames:
        canvas = np.zeros(shape, dtype=bool)
        height = heights(frame) if callable(heights) else heights
        canvas[20:20 + height, 20:40] = True
        masks[int(frame)] = canvas
    path = run_dir / "artifacts" / "ref_shape.npz"
    save_masks(str(path), {"0": masks})
    produced.append("artifacts/ref_shape.npz")
    return "artifacts/ref_shape.npz"


def _rest_survey(run_dir, produced, n_frames=300):
    """A whole-clip survey with no flight (brief §44: no candidates)."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    ground = {frame: [(100, 150, 160, 210)] for frame in range(n_frames)}
    canvas_all = {}
    for frame, boxes in ground.items():
        canvas = np.zeros((240, 352), dtype=bool)
        for r0, c0, r1, c1 in boxes:
            canvas[r0:r1, c0:c1] = True
        canvas_all[int(frame)] = canvas
    path = run_dir / "artifacts" / "masks_rest.npz"
    save_masks(str(path), {"0": canvas_all})
    produced.append("artifacts/masks_rest.npz")
    return "artifacts/masks_rest.npz"


def _shape_evidence(baseline, tmp_path, measure_frame, mask_frames,
                    heights):
    """Baseline evidence with a multi-frame reference mask."""
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    rel = _shape_mask(run_dir, produced, mask_frames, heights)
    ref = good["references"][0]
    ref["mask"] = {"artifact": rel, "object_id": "0", "frame": 10,
                   "outline": [[20.0, 20.0], [40.0, 20.0],
                               [40.0, 120.0], [20.0, 120.0]]}
    ref["extent_px"]["frame"] = measure_frame
    # The moved measuring frame needs its own blind check (§50).
    _append_line_check(run_dir, measure_frame)
    survey = _rest_survey(run_dir, produced)
    good["first_look"]["overview"]["artifact"] = survey
    ctx = dict(ctx, produced_files=list(produced),
               artifacts=sorted(
                   str(p.relative_to(run_dir)) for p in
                   (run_dir / "artifacts").rglob("*") if p.is_file()))
    return good, ctx


def test_shape_unstable_rejected(baseline, tmp_path):
    """125 px on the measuring frame against 100 px at rest."""
    frames = list(range(62))
    good, ctx = _shape_evidence(
        baseline, tmp_path, 61, frames,
        lambda frame: 125 if frame == 61 else 100)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is False, report["errors"]
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_SHAPE_UNSTABLE"]
    assert matches, report["errors"]
    detail = matches[0]["detail"]
    assert "125" in detail, detail
    assert "100" in detail, detail
    assert matches[0]["field"] == "references[0].extent_px"


def test_shape_stable_on_rest_passes(baseline, tmp_path):
    """The same mask measured on a rest frame passes."""
    frames = list(range(62))
    good, ctx = _shape_evidence(
        baseline, tmp_path, 50, frames,
        lambda frame: 125 if frame == 61 else 100)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]


def test_shape_few_frames_skipped_with_scale_note(baseline, tmp_path):
    """Three rest frames: no error, and the scale step says so."""
    good, ctx = _shape_evidence(baseline, tmp_path, 50, [10, 48, 49, 50],
                                100)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert not any(e["code"] == "REFERENCE_SHAPE_UNSTABLE"
                   for e in report["errors"])
    scale_step = next(s for s in report["result"]["calculation_steps"]
                      if s["id"] == "scale")
    assert any("skipped" in c.get("text", "")
               for c in scale_step["caveats"]), \
        scale_step["caveats"]


def _far_evidence(baseline, tmp_path, mask_frames):
    """Baseline hop moved to takeoff frame 101 (brief §44)."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)

    rows = []
    airtime = (131 - 101) / 30.0
    vy = 1.62 * airtime / 2.0
    for frame in range(101, 132):
        moment = (frame - 101) / 30.0
        y_m = vy * moment - 0.5 * 1.62 * moment * moment
        rows.append({"frame": frame, "x_px": 100.0,
                     "y_px": 200.0 - y_m / 0.01})
    target = run_dir / "workspace" / "track_hop_b.json"
    target.write_text(json.dumps(rows), encoding="utf-8")
    produced.append(str(target.relative_to(run_dir)))
    segment = good["segments"][0]
    segment["frames"] = {"start": 101, "apex": 116, "end": 131}
    segment["key_moments"] = [
        {"type": "takeoff", "frame": 101,
         "caption": "leaving the ground"},
        {"type": "apex", "frame": 116, "caption": "hanging high"},
        {"type": "landing", "frame": 131,
         "caption": "touching down softly"}]
    segment["track_artifact"] = "workspace/track_hop_b.json"
    segment["fit_curve_px"] = [
        {"t_s": row["frame"] / 30.0, "x_px": row["x_px"],
         "y_px": row["y_px"]} for row in rows]
    good["first_look"]["motions"] = [
        {"frame_start": 101, "frame_end": 131,
         "description": "foreground hop", "segment_id": "hop_a",
         "skip_reason": None}]
    ground = {frame: [(100, 150, 160, 210)] for frame in range(300)}
    for frame in range(101, 132):
        unit = (frame - 116) / 15.0
        bottom = int(round(160 - 60 * (1 - unit * unit)))
        ground[frame] = [(bottom - 60, 150, bottom, 210)]
    survey = {}
    for frame, boxes in ground.items():
        canvas = np.zeros((240, 352), dtype=bool)
        for r0, c0, r1, c1 in boxes:
            canvas[r0:r1, c0:c1] = True
        survey[int(frame)] = canvas
    save_masks(str(run_dir / "artifacts" / "masks_far.npz"),
               {"0": survey})
    produced.append("artifacts/masks_far.npz")
    overview = good["first_look"]["overview"]
    overview["artifact"] = "artifacts/masks_far.npz"
    overview["candidates"] = [
        {"id": "cand_1", "frame_start": 101, "frame_end": 131,
         "airtime_s": 1.0, "peak_rise_px": 60.0, "decision": "measured",
         "segment_id": "hop_a", "reason": None}]
    ref = good["references"][0]
    boxes = {}
    for frame in mask_frames:
        canvas = np.zeros((240, 352), dtype=bool)
        canvas[20:120, 20:40] = True
        boxes[int(frame)] = canvas
    save_masks(str(run_dir / "artifacts" / "ref_far.npz"),
               {"0": boxes})
    produced.append("artifacts/ref_far.npz")
    ref["mask"] = {"artifact": "artifacts/ref_far.npz", "object_id": "0",
                   "frame": 10,
                   "outline": [[20.0, 20.0], [40.0, 20.0],
                               [40.0, 120.0], [20.0, 120.0]]}
    ref["extent_px"]["frame"] = 0
    # The moved measuring frame needs its own blind check (§50).
    _append_line_check(run_dir, 0)
    ref["size_derivation"]["note"] = (
        "measured on frame 0 with the figure at rest")
    ctx = dict(ctx, produced_files=list(produced),
               artifacts=sorted(
                   str(p.relative_to(run_dir)) for p in
                   (run_dir / "artifacts").rglob("*") if p.is_file()))
    return good, ctx


def test_far_with_present_mask_is_error(baseline, tmp_path):
    """Mask on frames 41–100, measured on frame 0: a refusal."""
    good, ctx = _far_evidence(baseline, tmp_path,
                              [10] + list(range(41, 101)))
    dry = _validate(copy.deepcopy(good), dict(ctx), dry_run=True)
    assert dry["accepted"] is False, dry["errors"]
    matches = [e for e in dry["errors"]
               if e["code"] == "REFERENCE_FAR_FROM_MOTION"
               and e["field"] == "references[0]"]
    assert matches, dry["errors"]
    assert all(m.get("push") is False for m in matches), dry["errors"]
    detail = matches[0]["detail"]
    assert "41–101" in detail, detail
    assert "41–100" in detail, detail
    from src.validate import DRY_RUN_HARD_HEADER, DRY_RUN_PUSH_HEADER

    assert DRY_RUN_HARD_HEADER in dry["reply"]
    assert dry["reply"].index("REFERENCE_FAR_FROM_MOTION") < \
        dry["reply"].index(DRY_RUN_PUSH_HEADER)
    real = _validate(copy.deepcopy(good), dict(ctx))
    assert real["accepted"] is False, real["errors"]
    assert any(e["code"] == "REFERENCE_FAR_FROM_MOTION"
               for e in real["errors"]), real["errors"]


def test_far_without_present_mask_is_push(baseline, tmp_path):
    """Mask only on frames 0–20: a push, accepted in a real submit."""
    good, ctx = _far_evidence(baseline, tmp_path, list(range(21)))
    dry = _validate(copy.deepcopy(good), dict(ctx), dry_run=True)
    matches = [e for e in dry["errors"]
               if e["code"] == "REFERENCE_FAR_FROM_MOTION"
               and e["field"] == "references[0]"]
    assert matches, dry["errors"]
    assert all(m.get("push") is True for m in matches), dry["errors"]
    assert not any(e["code"] == "REFERENCE_FAR_FROM_MOTION"
                   and e.get("push") is False for e in dry["errors"])
    real = _validate(copy.deepcopy(good), dict(ctx))
    assert real["accepted"] is True, real["errors"]


def _disagreeing_pair(evidence):
    """Two references 7.6% apart with quoting sources (brief §39)."""
    evidence = copy.deepcopy(evidence)
    pack, width = evidence["references"]
    pack["name"] = "pack panel"
    _set_size(pack, 0.66)
    pack["size_tolerance_m"] = 0.02
    pack["extent_px"]["length_px"] = 69.87
    width["name"] = "suited width"
    _set_size(width, 0.82)
    width["size_tolerance_m"] = 0.05
    width["extent_px"]["length_px"] = 80.41
    return evidence


def _with_third_reference(evidence, run_dir, produced, name, size_m,
                          size_tolerance_m, length_px):
    """A disjoint third reference mask on the common frame."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    canvas = np.zeros((240, 352), dtype=bool)
    canvas[120:186, 200:300] = True
    path = run_dir / "artifacts" / "ref_gap_c.npz"
    save_masks(str(path), {"0": {10: canvas}})
    produced.append("artifacts/ref_gap_c.npz")
    third = copy.deepcopy(evidence["references"][0])
    third["name"] = name
    _set_size(third, size_m)
    third["size_tolerance_m"] = size_tolerance_m
    third["extent_px"]["length_px"] = length_px
    third["mask"] = {"artifact": "artifacts/ref_gap_c.npz",
                     "object_id": "0", "frame": 10,
                     "outline": [[200.0, 120.0], [300.0, 120.0],
                                 [300.0, 186.0], [200.0, 186.0]]}
    evidence["references"].append(third)
    return evidence


def _gap_ctx(run_dir, produced):
    return {"run_dir": str(run_dir), "run_id": run_dir.name,
            "timing": json.loads(
                (run_dir / "input" / "timing.json").read_text(
                    encoding="utf-8")),
            "artifacts": sorted(
                str(p.relative_to(run_dir)) for p in
                (run_dir / "artifacts").rglob("*") if p.is_file()),
            "produced_files": list(produced), "mask_checks": []}


def test_gap_details_point_at_part_whole(baseline, tmp_path):
    """Gap refusals name the part/whole check first (brief §44)."""
    evidence, run_dir, _ctx, produced = baseline(tmp_path / "one")
    bad = _disagreeing_pair(evidence)
    bad = _with_third_reference(bad, run_dir, produced, "flagpole",
                                2.4384, 0.8, 98.18)
    ctx = _gap_ctx(run_dir, produced)
    report = _validate(bad, ctx)
    assert report["accepted"] is False
    gap = [e for e in report["errors"]
           if e["code"] == "THIRD_REFERENCE_REQUIRED"]
    assert gap, report["errors"]
    assert "part/whole" in gap[0]["detail"], gap[0]["detail"]

    evidence2, run_dir2, ctx2, _produced2 = baseline(tmp_path / "two")
    disagreeing = copy.deepcopy(evidence2)
    for pos, size in enumerate((2.0, 2.07)):
        ref = disagreeing["references"][pos]
        _set_size(ref, size)
        ref["size_tolerance_m"] = 0.002
        ref["extent_px"]["length_px"] = 200.0
    report2 = _validate(disagreeing, dict(ctx2))
    assert report2["accepted"] is False
    pairs = [e for e in report2["errors"]
             if e["code"] == "REFERENCES_DISAGREE"]
    assert pairs, report2["errors"]
    assert "part/whole" in pairs[0]["detail"], pairs[0]["detail"]

# generated from brief/11 · part 11 owns this file
"""The shape check reads every mask of the same object (brief §49).

Run `b825e17e`'s figure reference is measured on a frame whose own
mask covers only flight frames, so the old single-mask check
skipped it. The whole-clip mask of the same figure gives 22 rest
frames with a lower median, and the reference is unstable. With
only its own mask, the clip still has rest frames near the motion,
so the submit is refused as unchecked. In a 4-frame clip the check
is skipped as before.
"""

import copy
import json


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _refresh_ctx(run_dir, produced):
    timing = json.loads(
        (run_dir / "input" / "timing.json").read_text(encoding="utf-8"))
    artifacts = sorted(
        str(p.relative_to(run_dir)) for p in
        (run_dir / "artifacts").rglob("*") if p.is_file())
    return {"run_dir": str(run_dir), "run_id": run_dir.name,
            "timing": timing, "artifacts": artifacts,
            "produced_files": list(produced), "mask_checks": []}


def _box_mask(run_dir, rel, produced, frames, height, cols=(20, 40),
              top=20, shape=(240, 352)):
    """Write a mask artifact with one object of fixed heights."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    per_frame = {}
    for frame in frames:
        canvas = np.zeros(shape, dtype=bool)
        canvas[top:top + height, cols[0]:cols[1]] = True
        per_frame[int(frame)] = canvas
    path = run_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    save_masks(str(path), {"0": per_frame})
    produced.append(str(path.relative_to(run_dir)))
    return str(rel)


def _shape_pair(baseline, tmp_path, with_other=True):
    """Baseline evidence with a single-frame own mask at frame 10.

    The own mask (``artifacts/t41_segment_0.npz``) is 155 px high
    on the measuring frame. The other mask
    (``artifacts/t6_segment_0.npz``) carries the same box on
    frame 10 (IoU 1.0) and 125 px boxes on frames 0-9, 11-20.
    Without the other mask the reference has 1 rest frame while
    the clip has eligible rest frames near the motion.
    """
    evidence, run_dir, _ctx, produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    own_rel = _box_mask(run_dir, "artifacts/t41_segment_0.npz",
                        produced, [10], 155)
    ref = good["references"][0]
    ref["mask"] = {"artifact": own_rel, "object_id": "0", "frame": 10,
                   "outline": [[20.0, 20.0], [40.0, 20.0],
                               [40.0, 175.0], [20.0, 175.0]]}
    ref["extent_px"]["frame"] = 10
    if with_other:
        import numpy as np

        from src.helpers.masks_io import save_masks

        per_frame = {}
        for frame in list(range(0, 10)) + [10] + list(range(11, 21)):
            height = 155 if frame == 10 else 125
            canvas = np.zeros((240, 352), dtype=bool)
            canvas[20:20 + height, 20:40] = True
            per_frame[int(frame)] = canvas
        other = run_dir / "artifacts" / "t6_segment_0.npz"
        save_masks(str(other), {"0": per_frame})
        produced.append(str(other.relative_to(run_dir)))
    ctx = _refresh_ctx(run_dir, produced)
    return good, ctx, run_dir, produced


def test_cross_mask_unstable_names_both_heights(baseline, tmp_path):
    """The whole-clip mask gives 20 rest frames at 125 px: unstable."""
    good, ctx = _shape_pair(baseline, tmp_path, with_other=True)[:2]
    report = _validate(good, dict(ctx))
    assert report["accepted"] is False, report["errors"]
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_SHAPE_UNSTABLE"
               and e["field"] == "references[0].extent_px"]
    assert matches, report["errors"]
    detail = matches[0]["detail"]
    assert "155" in detail, detail
    assert "125" in detail, detail


def test_own_mask_only_gives_unchecked_with_window(baseline, tmp_path):
    """Only the single-frame own mask: unchecked, naming 0-20."""
    good, ctx = _shape_pair(baseline, tmp_path, with_other=False)[:2]
    report = _validate(good, dict(ctx))
    assert report["accepted"] is False, report["errors"]
    assert not any(e["code"] == "REFERENCE_SHAPE_UNSTABLE"
                   and e["field"] == "references[0].extent_px"
                   for e in report["errors"]), report["errors"]
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_SHAPE_UNCHECKED"
               and e["field"] == "references[0].extent_px"]
    assert matches, report["errors"]
    detail = matches[0]["detail"]
    assert "10" in detail, detail
    assert "segment it over frames 0–" in detail, detail
    assert "(its rest frames near the motion)" in detail, detail


def test_four_frame_clip_skips_shape_check(baseline, tmp_path):
    """Four frames of 100 px masks: no shape error, scale says skipped."""
    evidence, run_dir, _ctx, produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    timing = {"claimed_fps": 30.0, "measured_fps": 30.0,
              "frame_count": 4, "duration_s": 4 / 30.0,
              "timestamps": [i / 30.0 for i in range(4)],
              "confirmed_duplicates": [], "cuts": []}
    (run_dir / "input" / "timing.json").write_text(
        json.dumps(timing), encoding="utf-8")
    for pos, cols in ((0, (20, 40)), (1, (100, 120))):
        rel = _box_mask(run_dir, f"artifacts/ref_small_{pos}.npz",
                        produced, [0, 1, 2, 3], 100, cols=cols)
        ref = good["references"][pos]
        ref["mask"] = {"artifact": rel, "object_id": "0", "frame": 2,
                       "outline": [[20.0, 20.0], [40.0, 20.0],
                                   [40.0, 120.0], [20.0, 120.0]]}
        ref["extent_px"]["frame"] = 2
    # The moved measuring frames need their own blind checks (§50).
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        for ref in good["references"]:
            extent = ref["extent_px"]
            handle.write(json.dumps({
                "frame": 2,
                "lines": [{"x1": extent["x1"], "y1": extent["y1"],
                           "x2": extent["x2"], "y2": extent["y2"],
                           "claim": f"height of the {ref['name']}",
                           "description":
                               f"the line runs along the {ref['name']}",
                           "view": "front", "dimension": "height",
                           "agrees": True,
                           "why": "the description matches the claim"}],
                "overlay_artifact": "artifacts/t1_check_line_0.png",
                "turn": 1}) + "\n")
    ctx = _refresh_ctx(run_dir, produced)
    report = _validate(good, dict(ctx))
    shape_errors = [e for e in report["errors"]
                    if e["code"] in ("REFERENCE_SHAPE_UNSTABLE",
                                     "REFERENCE_SHAPE_UNCHECKED")]
    assert shape_errors == [], report["errors"]
    steps = (report.get("result") or {}).get("calculation_steps", [])
    scale_steps = [s for s in steps if s.get("id") == "scale"]
    assert scale_steps, steps
    caveats = scale_steps[0].get("caveats", [])
    assert any("skipped" in str(c.get("text", "")) for c in caveats), \
        caveats

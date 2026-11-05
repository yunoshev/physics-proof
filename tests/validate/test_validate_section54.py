# generated from brief/11 · part 11 owns this file
"""One object means IoU above 0.75 (brief §54).

On Moon run ``20261103T023347Z-e84d1289`` the backpack reference
mask and a mask of the figure wearing it have IoU 0.503, while two
masks of one object from different ``segment`` calls have IoU
0.896–1.0. With the old 0.5 limit the figure's mask counted as a
mask of the backpack, so the backpack counted as the moving thing
and the ``SELF_REFERENCE_REQUIRED`` push was never listed. Every
same-object match — the shape check's masks (§49),
``RANGE_CHECK_ON_REFERENCE`` (§51) and ``SELF_REFERENCE_REQUIRED``
(§53) — now uses IoU above 0.75, read from one named constant.
"""

import copy
import json


FRAME = 10
SHAPE = (240, 352)

#: Backpack-like box: rows 20-120, cols 20-120 (100 x 100).
PACK = (20, 20, 120, 120)
#: Figure-wearing-it-like box: rows 20-160, cols 20-160
#: (140 x 140). IoU with PACK is 10000/19600 ≈ 0.51.
FIGURE_BOX = (20, 20, 160, 160)
#: Same-object-like box: rows 20-122, cols 20-123 (102 x 103),
#: covering PACK. IoU with PACK is 10000/10506 ≈ 0.95.
SAME_BOX = (20, 20, 122, 123)
#: Loose box: rows 20-120, cols 20-187 (100 x 167).
#: IoU with PACK is 10000/16700 ≈ 0.60.
LOOSE_BOX = (20, 20, 120, 187)
#: Tight box: rows 20-120, cols 20-145 (100 x 125).
#: IoU with PACK is 10000/12500 = 0.80.
TIGHT_BOX = (20, 20, 120, 145)


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _refresh(run_dir, produced):
    timing = json.loads(
        (run_dir / "input" / "timing.json").read_text(encoding="utf-8"))
    artifacts = sorted(
        str(p.relative_to(run_dir)) for p in
        (run_dir / "artifacts").rglob("*") if p.is_file())
    return {"run_dir": str(run_dir), "run_id": run_dir.name,
            "timing": timing, "artifacts": artifacts,
            "produced_files": list(produced), "mask_checks": []}


def _write_box(run_dir, rel, produced, frames, box):
    """One object ``"0"`` with the same box on each listed frame."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    r0, c0, r1, c1 = box
    per_frame = {}
    for frame in frames:
        canvas = np.zeros(SHAPE, dtype=bool)
        canvas[r0:r1, c0:c1] = True
        per_frame[int(frame)] = canvas
    path = run_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    save_masks(str(path), {"0": per_frame})
    produced.append(str(path.relative_to(run_dir)))
    return str(rel)


def _pack_ctx(baseline, tmp_path, siblings):
    """Baseline run plus a PACK reference mask and sibling masks.

    ``siblings`` maps artifact rel path to its box; every sibling
    covers frames 0-20. Returns ``(evidence, ctx, run_dir,
    produced)`` with ``references[0]`` repointed at the PACK mask
    (its extent and checks are untouched).
    """
    evidence, run_dir, _ctx, produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    pack_rel = _write_box(run_dir, "artifacts/ref_pack.npz",
                          produced, [FRAME], PACK)
    good["references"][0]["mask"] = {
        "artifact": pack_rel, "object_id": "0", "frame": FRAME,
        "outline": [[20.0, 20.0], [120.0, 20.0],
                    [120.0, 120.0], [20.0, 120.0]]}
    for rel, box in siblings.items():
        _write_box(run_dir, rel, produced,
                   list(range(0, 21)), box)
    return good, _refresh(run_dir, produced), run_dir, produced


def test_same_object_limit_is_three_quarters():
    """One named constant holds the limit and the matches read it."""
    from src.validate import SAME_OBJECT_IOU
    from src.validate.checks import SAME_OBJECT_IOU as FROM_CHECKS

    assert SAME_OBJECT_IOU == 0.75
    assert FROM_CHECKS == 0.75

    from pathlib import Path

    text = (Path(__file__).parent.parent.parent
            / "src" / "validate" / "validate.py").read_text(
                encoding="utf-8")
    for func in ("_same_object_mask_dicts",
                 "_reference_on_moving_thing"):
        start = text.index(f"def {func}(")
        end = text.index("\ndef ", start + 1)
        body = text[start:end]
        assert "SAME_OBJECT_IOU" in body, func
        assert "0.5" not in body, func


def test_iou_zero_point_six_is_two_objects(baseline, tmp_path):
    """A sibling at IoU ≈ 0.60 is not a mask of the object."""
    from src.validate.io import load_mask_frame
    from src.validate.validate import (
        _mask_iou_arrays,
        _same_object_mask_dicts,
    )

    _good, ctx, _run, _produced = _pack_ctx(
        baseline, tmp_path, {"artifacts/t79_segment_0.npz": LOOSE_BOX})
    ref_array = load_mask_frame("artifacts/ref_pack.npz", "0",
                                FRAME, ctx)
    assert ref_array is not None
    import numpy as np

    loose = np.zeros(SHAPE, dtype=bool)
    r0, c0, r1, c1 = LOOSE_BOX
    loose[r0:r1, c0:c1] = True
    iou = _mask_iou_arrays(ref_array, loose)
    assert 0.59 < iou < 0.61, iou
    assert iou <= 0.75
    assert _same_object_mask_dicts(
        "artifacts/ref_pack.npz", "0", FRAME, ref_array, ctx) == []


def test_iou_zero_point_eight_is_one_object(baseline, tmp_path):
    """A sibling at IoU = 0.80 still counts as the same object."""
    from src.validate.io import load_mask_frame
    from src.validate.validate import (
        _mask_iou_arrays,
        _same_object_mask_dicts,
    )

    _good, ctx, _run, _produced = _pack_ctx(
        baseline, tmp_path, {"artifacts/t47_segment_0.npz": TIGHT_BOX})
    ref_array = load_mask_frame("artifacts/ref_pack.npz", "0",
                                FRAME, ctx)
    assert ref_array is not None
    import numpy as np

    tight = np.zeros(SHAPE, dtype=bool)
    r0, c0, r1, c1 = TIGHT_BOX
    tight[r0:r1, c0:c1] = True
    iou = _mask_iou_arrays(ref_array, tight)
    assert iou == 0.8, iou
    assert iou > 0.75
    siblings = _same_object_mask_dicts(
        "artifacts/ref_pack.npz", "0", FRAME, ref_array, ctx)
    assert len(siblings) == 1, siblings
    assert int(siblings[0][FRAME].sum()) == 100 * 125


def test_backpack_masks_t79_excluded_t47_included(baseline, tmp_path):
    """Run e84d1289's geometry: 0.51 is out, 0.95 is in."""
    from src.validate.io import load_mask_frame
    from src.validate.validate import (
        _mask_iou_arrays,
        _reference_on_moving_thing,
        _same_object_mask_dicts,
    )

    _good, ctx, _run, _produced = _pack_ctx(baseline, tmp_path, {
        "artifacts/t79_segment_0.npz": FIGURE_BOX,
        "artifacts/t47_segment_0.npz": SAME_BOX,
    })
    ref_array = load_mask_frame("artifacts/ref_pack.npz", "0",
                                FRAME, ctx)
    assert ref_array is not None
    import numpy as np

    def _box_array(box):
        canvas = np.zeros(SHAPE, dtype=bool)
        r0, c0, r1, c1 = box
        canvas[r0:r1, c0:c1] = True
        return canvas

    iou_worn = _mask_iou_arrays(ref_array, _box_array(FIGURE_BOX))
    assert 0.50 < iou_worn < 0.52, iou_worn
    iou_same = _mask_iou_arrays(ref_array, _box_array(SAME_BOX))
    assert 0.94 < iou_same < 0.96, iou_same
    siblings = _same_object_mask_dicts(
        "artifacts/ref_pack.npz", "0", FRAME, ref_array, ctx)
    assert len(siblings) == 1, siblings
    assert int(siblings[0][FRAME].sum()) == 102 * 103

    # The overview's figure mask: the worn box shifted by 5 px, so it
    # counts as the figure's own sibling (IoU ≈ 0.87) while staying
    # far from the backpack (IoU ≈ 0.44).
    _write_box(_run, "artifacts/overview_fig.npz", _produced,
               [FRAME], (25, 25, 165, 165))
    ctx = _refresh(_run, _produced)
    pack_ref = {"mask": {"artifact": "artifacts/ref_pack.npz",
                         "object_id": "0"},
                "extent_px": {"frame": FRAME}}
    assert _reference_on_moving_thing(
        pack_ref, "artifacts/overview_fig.npz", "0", ctx) is False
    figure_ref = {"mask": {"artifact": "artifacts/overview_fig.npz",
                           "object_id": "0"},
                  "extent_px": {"frame": FRAME}}
    assert _reference_on_moving_thing(
        figure_ref, "artifacts/overview_fig.npz", "0", ctx) is True


def test_loose_sibling_leaves_shape_unchecked(baseline, tmp_path):
    """A 0.60 sibling adds no rest frames: the shape is unchecked."""
    good, ctx, _run, _produced = _pack_ctx(
        baseline, tmp_path, {"artifacts/t9_segment_0.npz": LOOSE_BOX})
    report = _validate(good, dict(ctx))
    assert report["accepted"] is False, report["errors"]
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_SHAPE_UNCHECKED"
               and e["field"] == "references[0].extent_px"]
    assert matches, report["errors"]
    assert "segment it over frames 0–" in matches[0]["detail"], \
        matches[0]["detail"]
    assert not [e for e in report["errors"]
                if e["code"] == "REFERENCE_SHAPE_UNSTABLE"
                and e["field"] == "references[0].extent_px"], \
        report["errors"]


def test_tight_sibling_counts_as_rest_frames(baseline, tmp_path):
    """A 0.80 sibling at rest height keeps the shape check passing."""
    good, ctx, _run, _produced = _pack_ctx(
        baseline, tmp_path, {"artifacts/t9_segment_0.npz": TIGHT_BOX})
    report = _validate(good, dict(ctx))
    shape_errors = [e for e in report["errors"]
                    if e["code"] in ("REFERENCE_SHAPE_UNSTABLE",
                                     "REFERENCE_SHAPE_UNCHECKED")
                    and e["field"] == "references[0].extent_px"]
    assert not shape_errors, report["errors"]

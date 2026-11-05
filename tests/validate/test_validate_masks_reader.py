# generated from brief/11 · part 11 owns this file
"""Masks read the helpers' way (brief §25)."""

import copy


def _ctx(run_dir):
    return {"run_dir": str(run_dir), "run_id": run_dir.name,
            "timing": {}, "artifacts": [], "produced_files": [],
            "mask_checks": []}


def test_helpers_writer_mask_found_on_frame(tmp_path):
    import numpy as np

    from src.helpers.masks_io import save_masks
    from src.validate.io import mask_frames_for_object

    run_dir = tmp_path / "run"
    (run_dir / "artifacts").mkdir(parents=True)
    frames = {}
    for frame in range(200, 261):
        canvas = np.zeros((24, 32), dtype=bool)
        canvas[4:12, 4:12] = True
        frames[frame] = canvas
    save_masks(str(run_dir / "artifacts" / "seg.npz"), {"tracked": frames})
    ctx = _ctx(run_dir)
    found = mask_frames_for_object("artifacts/seg.npz", "tracked", ctx)
    assert found is not None
    assert 210 in found
    assert found == list(range(200, 261))


def test_legacy_manifest_mask_found_on_frame(tmp_path):
    import numpy as np

    from src.validate.io import mask_frames_for_object

    run_dir = tmp_path / "run-legacy"
    (run_dir / "artifacts").mkdir(parents=True)
    arrays = {}
    manifest = []
    for position, frame in enumerate(range(200, 261)):
        canvas = np.zeros((24, 32), dtype=np.uint8)
        canvas[4:12, 4:12] = 1
        key = f"mask_{position}"
        arrays[key] = canvas
        manifest.append({"key": key, "object_id": "tracked",
                         "object_id_type": "str",
                         "frame_index": int(frame),
                         "shape": [24, 32]})
    arrays["__manifest__"] = np.array(manifest, dtype=object)
    np.savez(str(run_dir / "artifacts" / "seg.npz"), **arrays)
    ctx = _ctx(run_dir)
    found = mask_frames_for_object("artifacts/seg.npz", "tracked", ctx)
    assert found is not None
    assert 210 in found
    assert found == list(range(200, 261))


def test_overlapping_references_pass_common_frame(baseline, tmp_path):
    import numpy as np

    from src.helpers.masks_io import save_masks
    from src.validate import validate

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    # Two references masked on overlapping frames, written by the
    # helpers' own writer: the common-frame check must pass.
    left = np.zeros((240, 352), dtype=bool)
    left[20:86, 20:40] = True
    right = np.zeros((240, 352), dtype=bool)
    right[20:86, 100:271] = True
    both_left = {frame: left.copy() for frame in (10, 11)}
    both_right = {frame: right.copy() for frame in (11, 12)}
    save_masks(str(run_dir / "artifacts" / "over_a.npz"),
               {"0": both_left})
    save_masks(str(run_dir / "artifacts" / "over_b.npz"),
               {"1": both_right})
    produced.extend(["artifacts/over_a.npz", "artifacts/over_b.npz"])
    good = copy.deepcopy(evidence)
    good["references"][0]["mask"] = {
        "artifact": "artifacts/over_a.npz", "object_id": "0",
        "frame": 11,
        "outline": [[20.0, 20.0], [40.0, 20.0],
                    [40.0, 86.0], [20.0, 86.0]]}
    good["references"][1]["mask"] = {
        "artifact": "artifacts/over_b.npz", "object_id": "1",
        "frame": 11,
        "outline": [[100.0, 20.0], [271.0, 20.0],
                    [271.0, 86.0], [100.0, 86.0]]}
    ctx = dict(ctx, produced_files=list(produced),
               artifacts=sorted(
                   str(p.relative_to(run_dir)) for p in
                   (run_dir / "artifacts").rglob("*") if p.is_file()))
    report = validate(good, ctx)
    assert report["accepted"] is True, report["errors"]

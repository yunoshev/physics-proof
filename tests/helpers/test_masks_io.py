# owned by part 09 · tests for src/helpers/masks_io.py
"""Synthetic known-answer tests for mask I/O and clip facts."""

from __future__ import annotations

import json

import numpy as np
import pytest

from src.helpers import masks_io


def _box(rows, cols, r0, r1, c0, c1):
    arr = np.zeros((rows, cols), dtype=bool)
    arr[r0:r1, c0:c1] = True
    return arr


def test_masks_roundtrip_lossless(tmp_path):
    """Save/load restores object ids, frames, shapes and pixels exactly."""
    masks = {
        0: {3: _box(10, 12, 1, 5, 2, 9),
            4: _box(10, 12, 0, 10, 0, 12)},
        "obj1": {0: _box(10, 12, 2, 8, 3, 7)},
    }
    path = tmp_path / "sub" / "masks.npz"
    masks_io.save_masks(path, masks)
    assert path.suffix == ".npz"
    back = masks_io.load_masks(path)
    assert set(back) == {0, "obj1"}
    assert sorted(back[0]) == [3, 4]
    assert sorted(back["obj1"]) == [0]
    for oid, frames in masks.items():
        for frame, mask in frames.items():
            got = back[oid][frame]
            assert got.dtype == bool
            assert got.shape == mask.shape
            assert bool((got == mask).all())


def test_masks_roundtrip_empty(tmp_path):
    """An empty mapping round-trips to an empty mapping."""
    path = tmp_path / "empty.npz"
    masks_io.save_masks(path, {})
    assert masks_io.load_masks(path) == {}


def test_masks_rejects_bad_input(tmp_path):
    """Non-mappings and non-2-D arrays raise coded ValueErrors."""
    with pytest.raises(ValueError, match="bad_masks"):
        masks_io.save_masks(tmp_path / "a.npz", ["not", "a", "dict"])
    with pytest.raises(ValueError, match="bad_mask"):
        masks_io.save_masks(tmp_path / "b.npz",
                             {0: {0: np.zeros((4, 4, 3), dtype=bool)}})
    with pytest.raises(ValueError, match="bad_masks"):
        masks_io.save_masks(tmp_path / "c.npz", {0: {True: np.zeros(
            (4, 4), dtype=bool)}})


def test_load_masks_missing_file(tmp_path):
    """A missing file raises OSError (callers map it to MISSING_FIELD)."""
    with pytest.raises(OSError):
        masks_io.load_masks(tmp_path / "absent.npz")


def test_clip_facts_matches_planted_timing(tmp_path):
    """Frame count, fps, timestamps, duplicate runs and cuts match."""
    timing = tmp_path / "timing.json"
    stamps = [i / 29.97 for i in range(90)]
    timing.write_text(json.dumps({
        "frame_count": 90, "measured_fps": 29.97,
        "timestamps": stamps,
        "duplicate_runs": [[10, 11], [50]],
        "confirmed_duplicates": [10, 11, 50],
        "cuts": [70], "cut_indices": [70]}), encoding="utf-8")
    facts = masks_io.clip_facts(timing)
    assert facts["frame_count"] == 90
    assert facts["measured_fps"] == pytest.approx(29.97)
    assert isinstance(facts["timestamps"], np.ndarray)
    assert facts["timestamps"] == pytest.approx(stamps)
    assert facts["duplicate_runs"] == [[10, 11], [50]]
    assert facts["cut_indices"] == [70]


def test_clip_facts_tolerates_key_variants(tmp_path):
    """fps/cuts aliases and a flat confirmed-duplicates list are read."""
    timing = tmp_path / "timing.json"
    timing.write_text(json.dumps({
        "frame_count": 4, "fps": 30.0,
        "timestamps": [0.0, 0.033, 0.067, 0.1],
        "confirmed_duplicates": [1, 2],
        "cuts": [3]}), encoding="utf-8")
    facts = masks_io.clip_facts(timing)
    assert facts["measured_fps"] == pytest.approx(30.0)
    assert facts["duplicate_runs"] == [[1, 2]]
    assert facts["cut_indices"] == [3]


def test_clip_facts_rejects_bad_timing(tmp_path):
    """Mismatched timestamps and non-positive fps raise bad_timing."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"frame_count": 4, "measured_fps": 30.0,
                               "timestamps": [0.0, 0.1]}), encoding="utf-8")
    with pytest.raises(ValueError, match="bad_timing"):
        masks_io.clip_facts(bad)
    bad2 = tmp_path / "bad2.json"
    bad2.write_text(json.dumps({"frame_count": 2, "measured_fps": 0.0,
                                "timestamps": [0.0, 0.1]}), encoding="utf-8")
    with pytest.raises(ValueError, match="bad_timing"):
        masks_io.clip_facts(bad2)
    with pytest.raises(OSError):
        masks_io.clip_facts(tmp_path / "absent.json")


def _solid_clip(path, colors, size=(48, 64)):
    """Write one solid-colour frame per entry of ``colors`` (BGR)."""
    import cv2

    height, width = size
    writer = cv2.VideoWriter(str(path),
                             cv2.VideoWriter_fourcc(*"mp4v"),
                             30.0, (width, height))
    if not writer.isOpened():
        raise RuntimeError("video writer unavailable")
    try:
        for color in colors:
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:, :] = color
            writer.write(frame)
    finally:
        writer.release()


def test_read_frames_returns_requested_order(tmp_path):
    """Frames come back decoded, in the order requested."""
    import cv2  # noqa: F401 (probe availability)

    colors = [(30 * i % 256, 200 - 20 * i % 256, 50 + 10 * i)
              for i in range(10)]
    clip = tmp_path / "clip.mp4"
    try:
        _solid_clip(clip, colors)
    except RuntimeError:
        pytest.skip("video writer unavailable in this environment")
    frames = masks_io.read_frames(clip, [7, 2, 9])
    assert len(frames) == 3
    for frame, want in zip(frames, (colors[7], colors[2], colors[9])):
        assert frame.shape == (48, 64, 3)
        mean = frame.reshape(-1, 3).mean(axis=0)
        assert np.abs(mean - np.asarray(want)).max() < 30.0


def test_read_frames_rejects_bad_video(tmp_path):
    """A missing video or a bad index raises a coded ValueError."""
    with pytest.raises(ValueError, match="no_such_video"):
        masks_io.read_frames(tmp_path / "absent.mp4", [0])
    colors = [(10, 10, 10), (20, 20, 20)]
    clip = tmp_path / "clip.mp4"
    try:
        _solid_clip(clip, colors)
    except RuntimeError:
        pytest.skip("video writer unavailable in this environment")
    with pytest.raises(ValueError, match="unreadable_frame"):
        masks_io.read_frames(clip, [0, 9999])

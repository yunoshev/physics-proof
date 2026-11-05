# owned by part 09 · tests for src/helpers/tracks.py
"""Synthetic known-answer tests for mask statistics and tracks."""

from __future__ import annotations

import numpy as np
import pytest

from src.helpers import tracks


def _rect(rows=50, cols=40, r0=10, r1=30, c0=5, c1=25):
    arr = np.zeros((rows, cols), dtype=bool)
    arr[r0:r1, c0:c1] = True
    return arr


def test_mask_stats_rectangle():
    """Top/bottom/left/right, centroid, height, width, area are exact."""
    stats = tracks.mask_stats(_rect())
    assert (stats["top"], stats["bottom"]) == (10, 29)
    assert (stats["left"], stats["right"]) == (5, 24)
    assert (stats["height"], stats["width"]) == (20, 20)
    assert stats["area"] == 400
    assert stats["centroid"] == {"x": pytest.approx(14.5),
                                 "y": pytest.approx(19.5)}


def test_mask_stats_empty_mask():
    """An empty mask raises empty_mask, never zeros at the origin."""
    with pytest.raises(ValueError, match="empty_mask"):
        tracks.mask_stats(np.zeros((8, 8), dtype=bool))
    with pytest.raises(ValueError, match="bad_mask"):
        tracks.mask_stats(np.zeros((4, 4, 3), dtype=bool))


def test_largest_component_removes_stray_blob():
    """A stray blob must not move the bottom of the body."""
    mask = _rect()
    mask[45:48, 35:38] = True  # small stray blob, lower than the body
    assert tracks.mask_stats(mask)["bottom"] == 47
    cleaned = tracks.largest_component(mask)
    assert cleaned.dtype == bool
    assert cleaned.sum() == 400
    assert tracks.mask_stats(cleaned)["bottom"] == 29
    with pytest.raises(ValueError, match="empty_mask"):
        tracks.largest_component(np.zeros((6, 6), dtype=bool))


def test_track_point_modes_on_rectangle():
    """All four modes land on the known rectangle geometry."""
    masks = {0: _rect(), 1: _rect(), 2: _rect()}
    stamps = {0: 0.0, 1: 0.5, 2: 1.0}
    centroid = tracks.track_point(masks, "centroid", stamps)
    bottom = tracks.track_point(masks, "bottom_centre", stamps)
    top = tracks.track_point(masks, "top_centre", stamps)
    lowest = tracks.track_point(masks, "lowest_point", stamps)
    assert [r["x_px"] for r in centroid] == [pytest.approx(14.5)] * 3
    assert [r["y_px"] for r in centroid] == [pytest.approx(19.5)] * 3
    assert [r["y_px"] for r in bottom] == [pytest.approx(29.0)] * 3
    assert [r["y_px"] for r in top] == [pytest.approx(10.0)] * 3
    assert [r["y_px"] for r in lowest] == [pytest.approx(29.0)] * 3
    assert [r["t"] for r in centroid] == [pytest.approx(v) for v in
                                          (0.0, 0.5, 1.0)]
    assert all(r["mode"] == "centroid" for r in centroid)


def test_track_point_skips_empty_frames():
    """Empty frames are skipped; a fully empty series raises."""
    masks = {0: _rect(), 1: np.zeros((50, 40), dtype=bool), 2: _rect()}
    rows = tracks.track_point(masks, "centroid")
    assert [r["frame"] for r in rows] == [0, 2]
    assert [r["t"] for r in rows] == [pytest.approx(0.0),
                                      pytest.approx(2.0)]
    with pytest.raises(ValueError, match="empty_mask"):
        tracks.track_point({0: np.zeros((4, 4), dtype=bool)}, "centroid")
    with pytest.raises(ValueError, match="bad_mode"):
        tracks.track_point(masks, "head_bob")


def _rows(frames, x=0.0, y=0.0):
    return [{"frame": f, "t": float(f), "x_px": float(x), "y_px": float(y),
             "mode": "centroid"} for f in frames]


def test_track_quality_clean_track_is_ok():
    """A steady track on one blob passes every flag."""
    masks = {f: _rect() for f in range(5)}
    quality = tracks.track_quality(_rows(range(5)), {"body": masks})
    assert quality == {"gaps": [], "jumps": [], "splits": [],
                       "identity_swaps": [], "ok": True}


def test_track_quality_gaps():
    """Frames missing between the first and last are gaps."""
    masks = {f: _rect() for f in (0, 1, 3, 4)}
    quality = tracks.track_quality(_rows((0, 1, 3, 4)), {"body": masks})
    assert quality["gaps"] == [2]
    assert not quality["ok"]


def test_track_quality_jumps():
    """A displacement above one mask-height per frame is a jump."""
    rows = _rows(range(4))
    rows[2]["x_px"] = 45.0  # 45 px sideways on a 20 px tall mask
    rows[3]["x_px"] = 45.0  # ... and stays there, so only frame 2 jumps
    masks = {f: _rect() for f in range(4)}
    quality = tracks.track_quality(rows, {"body": masks})
    assert quality["jumps"] == [2]
    assert quality["gaps"] == []


def test_track_quality_splits():
    """A second component above 25% of the largest is a split."""
    split = np.zeros((50, 40), dtype=bool)
    split[10:30, 5:15] = True
    split[10:30, 20:30] = True  # two equal halves, 10 columns apart
    masks = {0: _rect(), 1: split}
    quality = tracks.track_quality(_rows((0, 1)), {"body": masks})
    assert quality["splits"] == [1]
    quality = tracks.track_quality(_rows((0,)), {"body": {0: _rect()}})
    assert quality["splits"] == []


def _block(r0, r1, c0, c1):
    arr = np.zeros((40, 60), dtype=bool)
    arr[r0:r1, c0:c1] = True
    return arr


def test_track_quality_identity_swaps():
    """Crossing objects flag the swap; static objects do not."""
    left = _block(10, 20, 5, 15)
    right = _block(10, 20, 45, 55)
    crossing = {"a": {0: left, 1: right}, "b": {0: right, 1: left}}
    rows = [{"frame": 0, "t": 0.0, "x_px": 10.0, "y_px": 15.0,
             "mode": "centroid", "object_id": "a"},
            {"frame": 1, "t": 1.0, "x_px": 50.0, "y_px": 15.0,
             "mode": "centroid", "object_id": "a"}]
    quality = tracks.track_quality(rows, crossing)
    assert quality["identity_swaps"] == [1]
    assert not quality["ok"]
    static = {"a": {0: left, 1: left}, "b": {0: right, 1: right}}
    quality = tracks.track_quality(rows, static)
    assert quality["identity_swaps"] == []


def _textured_clip(tmp_path, n_frames=20, height=240, width=320,
                   square=30, shift_from=None, shift_px=3, seed=7):
    """Write a textured clip with a bright square sweeping across it.

    The background is fixed random texture (a tripod shot); the white
    square sits on rows 100..100+square and moves right 8 px a frame.
    With ``shift_from`` set, frames ``shift_from:`` show the same
    background shifted right by ``shift_px`` px (a camera move). Returns
    ``(video_path, masks)`` with ``masks`` in ``load_masks`` shape.
    """
    import cv2

    rng = np.random.default_rng(seed)
    background = rng.integers(0, 256, (height, width, 3),
                              dtype=np.uint8)
    video_path = str(tmp_path / "still.mp4")
    writer = cv2.VideoWriter(
        video_path, cv2.VideoWriter_fourcc(*"mp4v"), 30.0,
        (width, height))
    assert writer.isOpened()
    try:
        masks = {}
        for frame in range(n_frames):
            if shift_from is not None and frame >= shift_from:
                canvas = np.zeros_like(background)
                canvas[:, shift_px:] = background[:, :-shift_px]
            else:
                canvas = background.copy()
            x0 = 10 + 8 * frame
            canvas[100:100 + square, x0:x0 + square] = 255
            writer.write(canvas)
            mask = np.zeros((height, width), dtype=bool)
            mask[100:100 + square, x0:x0 + square] = True
            masks[frame] = mask
    finally:
        writer.release()
    return video_path, {"square": masks}


def _grown_meets(box, bbox, margin=20):
    x, y, w, h = box
    grown = (x - margin, y - margin, x + w + margin, y + h + margin)
    bx0, by0, bx1, by1 = bbox
    return (grown[0] < bx1 and bx0 < grown[2]
            and grown[1] < by1 and by0 < grown[3])


def test_find_still_patches_avoids_the_mover(tmp_path):
    """Boxes grown by 20 px never meet the square on any frame."""
    from src.helpers.tracks import find_still_patches

    video_path, avoid = _textured_clip(tmp_path)
    frames = list(range(20))
    boxes = find_still_patches(video_path, frames, avoid=avoid,
                               size=64, count=3)
    assert 1 <= len(boxes) <= 3
    for box in boxes:
        assert len(box) == 4
        _, _, w, h = box
        assert (w, h) == (64, 64)
        for frame in frames:
            ys, xs = np.nonzero(avoid["square"][frame])
            bbox = (int(xs.min()), int(ys.min()),
                    int(xs.max()) + 1, int(ys.max()) + 1)
            assert not _grown_meets(box, bbox)


def test_still_track_static_camera_stays_put(tmp_path):
    """On a tripod shot the tracked patch moves at most 0.5 px."""
    from src.helpers.tracks import find_still_patches, still_track

    video_path, avoid = _textured_clip(tmp_path)
    frames = list(range(20))
    box = find_still_patches(video_path, frames, avoid=avoid,
                             size=64, count=3)[0]
    rows = still_track(video_path, frames, box, avoid=avoid)
    assert [r["frame"] for r in rows] == frames
    assert all(set(r) == {"frame", "x_px", "y_px"} for r in rows)
    x0, y0 = rows[0]["x_px"], rows[0]["y_px"]
    for row in rows:
        assert abs(row["x_px"] - x0) <= 0.5
        assert abs(row["y_px"] - y0) <= 0.5


def test_still_track_reports_a_camera_shift(tmp_path):
    """A 3 px background shift reads 3 ± 0.5 px from that frame on."""
    from src.helpers.tracks import find_still_patches, still_track

    video_path, avoid = _textured_clip(tmp_path, shift_from=10,
                                       shift_px=3)
    frames = list(range(20))
    box = find_still_patches(video_path, frames, avoid=avoid,
                             size=64, count=3)[0]
    rows = still_track(video_path, frames, box, avoid=avoid)
    x0, y0 = rows[0]["x_px"], rows[0]["y_px"]
    for row in rows[:10]:
        assert abs(row["x_px"] - x0) <= 0.5
        assert abs(row["y_px"] - y0) <= 0.5
    for row in rows[10:]:
        assert abs(row["x_px"] - x0 - 3.0) <= 0.5
        assert abs(row["y_px"] - y0) <= 0.5


def test_still_track_box_on_the_mover_raises(tmp_path):
    """A box on the square's path names the square and a frame."""
    from src.helpers.tracks import still_track

    video_path, avoid = _textured_clip(tmp_path)
    frames = list(range(20))
    # The square sits at x = 10 + 8f on rows 100..130: this box
    # covers its frame-5 position.
    box = (10 + 8 * 5 - 17, 100 - 17, 64, 64)
    with pytest.raises(ValueError) as excinfo:
        still_track(video_path, frames, box, avoid=avoid)
    assert "square" in str(excinfo.value)
    assert any(str(f) in str(excinfo.value) for f in frames)


def test_still_track_rejects_bad_inputs(tmp_path):
    """Bad videos, frames and boxes raise coded ValueErrors."""
    from src.helpers.tracks import find_still_patches, still_track

    video_path, avoid = _textured_clip(tmp_path)
    frames = list(range(20))
    box = find_still_patches(video_path, frames, avoid=avoid,
                             size=64, count=1)[0]
    with pytest.raises(ValueError, match="no_such_video"):
        still_track(str(tmp_path / "missing.mp4"), frames, box)
    with pytest.raises(ValueError, match="bad_frames"):
        still_track(video_path, [], box)
    with pytest.raises(ValueError, match="bad_box"):
        still_track(video_path, frames, (0, 0, -4, 64))
    with pytest.raises(ValueError, match="bad_box"):
        find_still_patches(video_path, frames, size=0)
    with pytest.raises(ValueError, match="no_such_video"):
        find_still_patches(str(tmp_path / "missing.mp4"), frames)



def test_relative_track_subtracts_on_common_frames():
    """A minus B on shared frames; disjoint tracks raise."""
    track_a = _rows((1, 2, 3), x=10.0, y=20.0)
    track_b = [{"frame": 2, "t": 2.0, "x_px": 4.0, "y_px": 25.0},
               {"frame": 3, "t": 3.0, "x_px": 6.0, "y_px": 18.0},
               {"frame": 4, "t": 4.0, "x_px": 0.0, "y_px": 0.0}]
    rel = tracks.relative_track(track_a, track_b)
    assert [(r["frame"], r["x_px"], r["y_px"]) for r in rel] == [
        (2, pytest.approx(6.0), pytest.approx(-5.0)),
        (3, pytest.approx(4.0), pytest.approx(2.0))]
    assert [r["t"] for r in rel] == [pytest.approx(2.0),
                                    pytest.approx(3.0)]
    with pytest.raises(ValueError, match="no_common_frames"):
        tracks.relative_track(_rows((0,)), _rows((9,)))

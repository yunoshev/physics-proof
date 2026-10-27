"""M6 probes: verified physics blocks (all offline)."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pytest

import physics_proof.blocks as blocks
from physics_proof.blocks import (
    MaskSet,
    decide,
    fit_parabola,
    largest_component,
    load_masks,
    mask_stats,
    save_masks,
    scale_from_reference,
    spans_of,
    spans_of_track,
    to_metres,
    track_quality,
)

ROOT = Path(__file__).resolve().parents[1]


def disc(h: int, w: int, cy: float, cx: float, r: float) -> np.ndarray:
    """Filled disc mask, shape [H, W] bool."""
    yy, xx = np.mgrid[0:h, 0:w]
    return ((yy - cy) ** 2 + (xx - cx) ** 2 <= r * r).astype(bool)


def moving_disc_track(n: int = 40, h: int = 64, w: int = 64, r: int = 10) -> np.ndarray:
    """Clean track: one disc gliding right, shape [N, H, W] bool."""
    return np.stack([disc(h, w, 32.0, 12.0 + i, float(r)) for i in range(n)])


# Probe 1: synthetic parabolas, fixed seed.
def test_fit_parabola_calibrated() -> None:
    rng = np.random.default_rng(7)
    fps, g_true, sigma = 30.0, 400.0, 1.5
    trials, hits, errs, estimates = 200, 0, [], []
    for _ in range(trials):
        n = int(rng.integers(30, 46))
        frames = np.arange(n) + int(rng.integers(0, 50))
        v0 = float(rng.uniform(-300.0, 50.0))
        c = float(rng.uniform(0.0, 400.0))
        t = frames / fps
        y = 0.5 * g_true * t * t + v0 * t + c + rng.normal(0.0, sigma, n)
        out = fit_parabola(frames, y, fps)
        assert out["n"] == n
        assert out["window"] == {"first": int(frames[0]), "last": int(frames[-1])}
        assert out["g_px_err"] > 0
        assert out["rms"] == pytest.approx(float(np.sqrt(np.mean(out["residuals"] ** 2))))
        errs.append(out["g_px_err"])
        estimates.append(out["g_px"])
        if abs(out["g_px"] - g_true) <= out["g_px_err"]:
            hits += 1
    assert hits >= 0.66 * trials
    assert float(np.mean(errs)) == pytest.approx(float(np.std(estimates)), rel=0.20)


def test_fit_parabola_needs_five_points() -> None:
    with pytest.raises(ValueError):
        fit_parabola([0, 1, 2, 3], [1.0, 2.0, 3.0, 4.0], 30.0)


# Probe 2: decide hand cases (7 from the task + 6 of our own).
@pytest.mark.parametrize(
    ("g", "g_err", "worlds", "state", "nearest", "k"),
    [
        (1.60, 0.10, None, "fits:Moon", "Moon", None),
        (9.70, 0.40, None, "fits:Earth", "Earth", None),
        (0.72, 0.05, None, "none_fits", "Moon", 1.500),
        (4.36, 0.30, None, "none_fits", "Earth", 1.500),
        (5.00, 3.00, None, "undetermined", None, None),
        (2.02, 0.20, None, "fits:Moon", "Moon", None),
        (2.03, 0.20, None, "none_fits", "Moon", None),
        # Own: exact Mars value with Mars passed fits Mars (sigma = 0/0.1).
        (3.71, 0.10, {"Earth": 9.81, "Moon": 1.62, "Mars": 3.71}, "fits:Mars", "Mars", None),
        # Own: exact Earth value fits Earth (sigma = 0/0.01).
        (9.81, 0.01, None, "fits:Earth", "Earth", None),
        # Own: huge error covers both default worlds -> undetermined.
        # sigma Earth = (0.5-9.81)/5 = -1.862, sigma Moon = (0.5-1.62)/5 = -0.224.
        (0.50, 5.00, None, "undetermined", None, None),
        # Own: far above Earth -> none_fits, nearest Earth, clip runs fast.
        # k = sqrt(9.81/20) = 0.70036 < 1.
        (20.0, 0.50, None, "none_fits", "Earth", 0.70036),
        # Own: between Moon and Earth -> none_fits, nearest Moon.
        # |ln(3/1.62)| = 0.616 < |ln(3/9.81)| = 1.185; k = sqrt(1.62/3) = 0.73485.
        (3.00, 0.10, None, "none_fits", "Moon", 0.73485),
        # Own: tight Mars window excludes its neighbours.
        # sigma Mars = (3.0-3.71)/0.2 = -3.55; sigma Moon = (3.0-1.62)/0.2 = 6.9.
        (3.00, 0.20, {"Earth": 9.81, "Moon": 1.62, "Mars": 3.71}, "none_fits", "Mars", None),
    ],
)
def test_decide_table(g, g_err, worlds, state, nearest, k) -> None:
    out = decide(g, g_err, worlds)
    assert out["state"] == state
    if nearest is not None:
        assert out["nearest"] == nearest
    if k is not None:
        assert out["k"] == pytest.approx(k, abs=0.001)
    assert isinstance(out["text"], str) and len(out["text"].split(". ")) == 1
    if state == "none_fits":
        assert "would have to be running " in out["text"]
        assert "×" in out["text"]
    assert set(out["sigmas"]) == set((worlds or {"Earth": 9.81, "Moon": 1.62}))


def test_decide_boundary_tolerance() -> None:
    # sigma for Moon is 2.0000000000000018 in float; still consistent at k=2.
    out = decide(2.02, 0.20)
    assert out["state"] == "fits:Moon"
    assert out["consistent"] == ["Moon"]
    # Just past the boundary it stops fitting; k < 1 means a fast clip.
    out = decide(2.03, 0.20)
    assert out["state"] == "none_fits"
    assert out["k"] is not None and out["k"] < 1


# Probe 3: track_quality on a synthetic moving disc.
def test_track_quality_flags_gap_jump_split() -> None:
    n = 40
    track = moving_disc_track(n)
    frames = np.arange(n)
    track[10] = False
    track[11] = False
    track[20] = disc(64, 64, 32.0, 32.0, 14.0)  # ~1.9x the area of r=10
    main = track[30]
    blob = np.zeros_like(main)
    blob[50:56, 50:58] = True  # 48 px second blob, far from the main disc
    assert blob.sum() / main.sum() < 0.2  # below split_ratio, so no split here
    track[30] = main | blob
    out = track_quality(track, frames)
    assert 10 in out["gaps"] and 11 in out["gaps"]
    jumped = [f for f, _ in out["area_jumps"]]
    assert 20 in jumped
    assert 30 not in out["splits"]
    assert isinstance(out["summary"], str) and out["summary"]


def test_track_quality_split_and_clean() -> None:
    n = 40
    track = moving_disc_track(n)
    frames = np.arange(n)
    main = track[30]
    area = int(main.sum())
    want = int(round(0.3 * area))  # second blob exactly 30 % of the main one
    side = int(np.ceil(np.sqrt(want)))
    blob = np.zeros_like(main)
    full = want // side
    rest = want % side
    blob[50 : 50 + full, 50 : 50 + side] = True
    blob[50 + full, 50 : 50 + rest] = True
    assert abs(blob.sum() / area - 0.3) < 0.02
    assert not (blob & main).any()
    track[30] = main | blob
    out = track_quality(track, frames)
    assert out["splits"] == [30]
    clean = track_quality(moving_disc_track(n), frames)
    assert clean["gaps"] == [] and clean["area_jumps"] == [] and clean["splits"] == []
    assert "clean" in clean["summary"]


# Probe 4: mask_stats.bottom_y and largest_component.
def test_mask_stats_bottom_y() -> None:
    mask = np.zeros((16, 16), dtype=bool)
    mask[5:10, 3:8] = True
    track = np.stack([mask, np.zeros((16, 16), dtype=bool)])
    stats = mask_stats(track)
    assert stats[0] is not None and stats[0]["bottom_y"] == 9
    assert stats[0]["top_y"] == 5
    assert stats[0]["left_x"] == 3 and stats[0]["right_x"] == 7
    assert stats[0]["area"] == 5 * 5
    assert stats[0]["bbox"] == [3, 5, 8, 10]
    assert stats[1] is None


def test_largest_component_drops_small_blob() -> None:
    mask = np.zeros((16, 16), dtype=bool)
    mask[2:8, 2:8] = True
    mask[12:14, 12:14] = True
    kept = largest_component(mask)
    assert kept.sum() == 36
    assert not kept[12:14, 12:14].any()
    assert kept[2:8, 2:8].all()
    assert largest_component(np.zeros((4, 4), dtype=bool)).sum() == 0


def test_spans_round_trip() -> None:
    mask = np.zeros((4, 6), dtype=bool)
    mask[1, 1:4] = True
    mask[2, 0:2] = True
    mask[2, 4:6] = True
    assert spans_of(mask) == [[1, 1, 4], [2, 0, 2], [2, 4, 6]]
    track = np.stack([mask, np.zeros((4, 6), dtype=bool)])
    assert spans_of_track(track, [7, 9]) == {7: spans_of(mask), 9: []}


# Probe 5: save/load round-trip and clear TypeErrors.
def test_masks_round_trip(tmp_path: Path) -> None:
    rng = np.random.default_rng(3)
    n, h, w = 4, 8, 8
    frames = np.array([0, 1, 2, 5], dtype=np.int32)
    ids = np.array([3, 7], dtype=np.int32)
    masks = rng.random((n, 2, h, w)) < 0.3
    path = tmp_path / "masks.npz"
    save_masks(path, frames, ids, masks, [0.9, 0.5])
    got = load_masks(path)
    assert isinstance(got, MaskSet)
    np.testing.assert_array_equal(got.frames, frames)
    np.testing.assert_array_equal(got.ids, ids)
    np.testing.assert_array_equal(got.masks, masks)
    np.testing.assert_array_equal(got.present, masks.any(axis=(2, 3)))
    np.testing.assert_array_equal(got.confidence, np.array([0.9, 0.5], dtype=np.float32))
    np.testing.assert_array_equal(got.of(3), masks[:, 0])
    np.testing.assert_array_equal(got.of(7), masks[:, 1])
    with pytest.raises(KeyError):
        got.of(9)


def test_masks_wrong_types_raise_clear_errors(tmp_path: Path) -> None:
    track = moving_disc_track(4)
    frames = np.arange(4)
    ms = MaskSet(
        frames=frames.astype(np.int32),
        ids=np.array([1], dtype=np.int32),
        masks=track[:, None],
        present=np.ones((4, 1), dtype=bool),
        confidence=np.array([1.0], dtype=np.float32),
    )
    with pytest.raises(TypeError, match="single-object"):
        mask_stats(ms)
    with pytest.raises(TypeError, match="single-object"):
        mask_stats({1: track})
    with pytest.raises(TypeError, match="single"):
        largest_component(ms)
    with pytest.raises(TypeError, match="single"):
        spans_of({1: track[0]})
    with pytest.raises(TypeError, match="single-object"):
        track_quality(ms, frames)
    with pytest.raises(TypeError, match="single-object"):
        spans_of_track(ms, frames)
    # The other way round: a single-object array where the whole set goes.
    with pytest.raises(TypeError, match="multi-object"):
        save_masks(tmp_path / "x.npz", frames, [1], track, [1.0])
    with pytest.raises(TypeError, match="int object id"):
        ms.of(track)  # type: ignore[arg-type]


# Probe 6: hand-computed scale example.
def test_scale_hand_computed() -> None:
    # 120 +- 2 px for 1.50 +- 0.03 m: 80 px/m,
    # rel = sqrt((2/120)^2 + (0.03/1.5)^2) = 0.026038, err = 2.0830 px/m.
    px_per_m, err = scale_from_reference(120.0, 2.0, 1.50, 0.03)
    assert px_per_m == pytest.approx(80.0)
    assert err == pytest.approx(2.0830, abs=0.001)
    # g = 800 px/s^2 at that scale is 10 m/s^2; to_metres divides and
    # combines the relative errors in quadrature the same way.
    g, g_err = to_metres(800.0, 16.0, px_per_m, err)
    assert g == pytest.approx(10.0)
    assert g_err == pytest.approx(10.0 * np.sqrt(0.02**2 + (err / px_per_m) ** 2))


# Probe 7: every public function documents shapes and units.
UNIT_WORDS = ("px", "frame", "second", "metre", "meter", "m/s", "unit-free")


def test_docstrings_mention_shapes_and_units() -> None:
    funcs = [
        (name, obj)
        for name, obj in vars(blocks).items()
        if name in blocks.__all__ and inspect.isfunction(obj)
    ]
    assert len(funcs) >= 10
    for name, func in funcs:
        doc = inspect.getdoc(func)
        assert doc, name
        assert "shape" in doc.lower(), name
        assert any(u in doc.lower() for u in UNIT_WORDS), name
    assert "shape" in inspect.getdoc(blocks.MaskSet.of).lower()


def test_top_level_shim_reexports() -> None:
    sys.path.insert(0, str(ROOT))
    try:
        import blocks as shim  # noqa: PLC0415

        for name in blocks.__all__:
            assert getattr(shim, name) is getattr(blocks, name), name
    finally:
        sys.path.remove(str(ROOT))

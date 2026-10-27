"""M6. Verified physics blocks, also importable as plain ``import blocks``.

Every number on the analysis page comes from code in this module (SPEC
principle 5). Pixel geometry uses image coordinates: x grows right and y
grows down, both in px. Time ``t = frame / fps`` is in seconds, lengths for
the scale are in m, and gravity is in m/s^2 (px/s^2 before conversion).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage

from physics_proof.video import probe as _probe
from physics_proof.video import read_frames as _video_read_frames

__all__ = [
    "MaskSet",
    "save_masks",
    "load_masks",
    "video_info",
    "read_frames",
    "mask_stats",
    "largest_component",
    "spans_of",
    "spans_of_track",
    "track_quality",
    "fit_parabola",
    "scale_from_reference",
    "to_metres",
    "decide",
]

# 4-connected neighbourhood for component labelling.
_FOUR = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=int)

_DEFAULT_WORLDS = {"Earth": 9.81, "Moon": 1.62}
_MARS_G = 3.71


def _is_set_like(value: Any) -> bool:
    """True for a whole multi-object set where one object's array was wanted."""
    return isinstance(value, (MaskSet, dict))


def _need_single(name: str, value: Any, want: str) -> None:
    """Raise a clear TypeError when a MaskSet/dict is passed as one array."""
    if isinstance(value, MaskSet):
        raise TypeError(
            name
            + ": expected "
            + want
            + "; got a MaskSet. Use MaskSet.of(object_id) to select one object first."
        )
    if isinstance(value, dict):
        raise TypeError(
            name
            + ": expected "
            + want
            + "; got a dict of per-object arrays. Select one object's array first."
        )


def _as_bool_2d(name: str, value: Any) -> np.ndarray:
    """Validate a single-frame mask; shape [H, W] bool, units px on/off."""
    _need_single(name, value, "a single-object mask array with shape [H, W]")
    arr = np.asarray(value)
    if arr.ndim != 2:
        raise TypeError(
            name
            + ": expected a single 2D frame mask with shape [H, W]; got shape "
            + repr(arr.shape)
            + "."
        )
    return np.asarray(arr, dtype=bool)


def _as_bool_3d(name: str, value: Any) -> np.ndarray:
    """Validate a single-object track; shape [N, H, W] bool, units px on/off."""
    _need_single(name, value, "a single-object mask array with shape [N, H, W]")
    arr = np.asarray(value)
    if arr.ndim != 3:
        raise TypeError(
            name
            + ": expected a single-object mask array with shape [N, H, W] "
            + "(N frames of H rows by W cols); got shape "
            + repr(arr.shape)
            + ". For a whole MaskSet use MaskSet.of(object_id) first."
        )
    return np.asarray(arr, dtype=bool)


@dataclass(frozen=True, eq=False)
class MaskSet:
    """Per-object segmentation masks for a run of frames.

    Shapes: frames int32 [N] (frame indices), ids int32 [K] (object ids),
    masks bool [N, K, H, W] (pixel is True when covered, units px),
    present bool [N, K] (True when the object has any pixel that frame),
    confidence float32 [K] (SAM score per object, unit-free 0..1).
    """

    frames: np.ndarray
    ids: np.ndarray
    masks: np.ndarray
    present: np.ndarray
    confidence: np.ndarray

    def of(self, obj_id: int) -> np.ndarray:
        """Return one object's masks with shape [N, H, W] bool, units px.

        Argument shape: obj_id is a single int object id (one of ids).
        Returns: bool array with shape [N, H, W]. Raises TypeError when
        obj_id is an array, MaskSet or dict instead of an int, and
        KeyError for an unknown id.
        """
        if isinstance(obj_id, bool) or not isinstance(obj_id, (int, np.integer)):
            raise TypeError(
                "MaskSet.of: expected an int object id; got "
                + type(obj_id).__name__
                + "."
            )
        where = np.flatnonzero(self.ids == int(obj_id))
        if where.size == 0:
            raise KeyError(
                "unknown object id " + str(int(obj_id)) + "; have "
                + str([int(v) for v in self.ids])
            )
        return np.asarray(self.masks[:, int(where[0])], dtype=bool)


def save_masks(
    path: str | Path,
    frames: Any,
    ids: Any,
    masks: Any,
    confidence: Any,
) -> Path:
    """Save masks to one compressed .npz file; returns the path.

    Argument shapes: frames int [N] (frame indices), ids int [K] (object
    ids), masks bool [N, K, H, W] (px on/off; a dict {object id: bool
    [N, H, W]} is also accepted), confidence float [K] (unit-free 0..1).
    Returns: the file path. The archive holds frames, ids, masks, present
    ([N, K] bool, derived as masks.any over H and W) and confidence.
    Raises TypeError when masks is a MaskSet, or a single-object [N, H, W]
    array where the multi-object [N, K, H, W] set was expected.
    """
    if _is_set_like(frames):
        raise TypeError("save_masks: expected frames as int array with shape [N].")
    if _is_set_like(ids):
        raise TypeError("save_masks: expected ids as int array with shape [K].")
    out = Path(path)
    frames_arr = np.asarray(frames, dtype=np.int32).reshape(-1)
    ids_arr = np.asarray(ids, dtype=np.int32).reshape(-1)
    n, k = frames_arr.size, ids_arr.size
    if isinstance(masks, MaskSet):
        raise TypeError(
            "save_masks: expected masks as a bool array with shape [N, K, H, W] "
            + "or a dict {object id: [N, H, W]}; got a MaskSet."
        )
    if isinstance(masks, dict):
        try:
            stacked = [np.asarray(masks[int(v)], dtype=bool) for v in ids_arr]
        except KeyError as exc:
            raise KeyError("masks dict is missing object id " + str(exc)) from exc
        masks_arr = np.stack(stacked, axis=1) if stacked else np.zeros((n, 0, 0, 0))
    else:
        masks_arr = np.asarray(masks)
        if masks_arr.ndim == 3:
            raise TypeError(
                "save_masks: expected a multi-object mask array with shape "
                + "[N, K, H, W] (or a dict {object id: [N, H, W]}); got a "
                + "single-object array with shape " + repr(masks_arr.shape) + "."
            )
        if masks_arr.ndim != 4:
            raise ValueError(
                "save_masks: masks must have shape [N, K, H, W]; got "
                + repr(masks_arr.shape)
                + "."
            )
        masks_arr = np.asarray(masks_arr, dtype=bool)
    if masks_arr.shape[0] != n or masks_arr.shape[1] != k:
        raise ValueError(
            "save_masks: masks shape " + repr(masks_arr.shape)
            + " does not match " + str(n) + " frames and " + str(k) + " ids."
        )
    conf_arr = np.asarray(confidence, dtype=np.float32).reshape(-1)
    if conf_arr.shape != (k,):
        raise ValueError(
            "save_masks: confidence must have shape [" + str(k) + "]; got "
            + repr(conf_arr.shape) + "."
        )
    present = np.asarray(masks_arr.any(axis=(2, 3)), dtype=bool)
    if out.parent != Path(""):
        out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        frames=np.asarray(frames_arr, dtype=np.int32),
        ids=np.asarray(ids_arr, dtype=np.int32),
        masks=np.asarray(masks_arr, dtype=bool),
        present=present,
        confidence=np.asarray(conf_arr, dtype=np.float32),
    )
    return out


def load_masks(path: str | Path) -> MaskSet:
    """Load a .npz mask file written by save_masks into a MaskSet.

    Argument shapes: path is a single file path. Returns: a MaskSet with
    frames int32 [N], ids int32 [K], masks bool [N, K, H, W] in px,
    present bool [N, K] and confidence float32 [K].
    """
    data = np.load(Path(path), allow_pickle=False)
    for key in ("frames", "ids", "masks", "present", "confidence"):
        if key not in data:
            raise ValueError("mask file is missing key " + repr(key))
    frames = np.asarray(data["frames"], dtype=np.int32).reshape(-1)
    ids = np.asarray(data["ids"], dtype=np.int32).reshape(-1)
    masks = np.asarray(data["masks"], dtype=bool)
    present = np.asarray(data["present"], dtype=bool)
    confidence = np.asarray(data["confidence"], dtype=np.float32).reshape(-1)
    n, k = frames.size, ids.size
    if masks.ndim != 4 or masks.shape[0] != n or masks.shape[1] != k:
        raise ValueError("mask file has inconsistent masks shape " + repr(masks.shape))
    if present.shape != (n, k) or confidence.shape != (k,):
        raise ValueError("mask file has inconsistent present/confidence shapes")
    return MaskSet(
        frames=frames, ids=ids, masks=masks, present=present, confidence=confidence
    )


def video_info(path: str | Path) -> Any:
    """Measure a video file (re-export of physics_proof.video.probe).

    Argument shapes: path is a single video file path. Returns: a VideoInfo
    with scalar fields; width/height in px, fps as an exact Fraction in
    frames/s, frame_count in frames, duration in s, SAR/DAR as Fractions.
    """
    return _probe(path)


def read_frames(path: str | Path, indices: Any) -> dict[int, np.ndarray]:
    """Read exact frames by 0-based index (re-export of video.read_frames).

    Argument shapes: path is a single video file path, indices holds frame
    numbers in frames. Returns: dict {frame index: HxWx3 uint8 RGB array},
    H/W in px. Frame N is the N-th decoded frame, whatever the timestamps.
    """
    return _video_read_frames(path, indices)


def mask_stats(obj_masks: Any) -> list[dict[str, Any] | None]:
    """Per-frame stats for one object's track.

    Argument shapes: obj_masks is a single-object bool array with shape
    [N, H, W] (px on/off), one entry per frame. Returns: a list of N dicts
    (None for empty frames) with area in px, bbox [x1, y1, x2, y2] in px
    (x2/y2 exclusive), centroid [x, y] in px (float), top_y/bottom_y/left_x/
    right_x in px rows/cols; bottom_y is the lowest mask row (feet, rule 3).
    Raises TypeError for a MaskSet/dict instead of the single-object array.
    """
    track = _as_bool_3d("mask_stats", obj_masks)
    out: list[dict[str, Any] | None] = []
    for frame in track:
        ys, xs = np.flatnonzero(frame.any(axis=1)), np.flatnonzero(frame.any(axis=0))
        if ys.size == 0:
            out.append(None)
            continue
        y1, y2 = int(ys[0]), int(ys[-1])
        x1, x2 = int(xs[0]), int(xs[-1])
        sel = frame[y1 : y2 + 1, x1 : x2 + 1]
        yy, xx = np.nonzero(sel)
        out.append(
            {
                "area": int(frame.sum()),
                "bbox": [x1, y1, x2 + 1, y2 + 1],
                "centroid": [float(xx.mean() + x1), float(yy.mean() + y1)],
                "top_y": y1,
                "bottom_y": y2,
                "left_x": x1,
                "right_x": x2,
            }
        )
    return out


def _label_sizes(mask: np.ndarray) -> list[int]:
    """4-connected component pixel sizes, largest first; shape [H, W] bool."""
    lab, count = ndimage.label(mask, structure=_FOUR)
    if count == 0:
        return []
    sizes = np.bincount(lab.ravel())[1:]
    return sorted((int(v) for v in sizes), reverse=True)


def largest_component(mask: Any) -> np.ndarray:
    """Keep only the largest 4-connected component of one frame mask.

    Argument shapes: mask is a single 2D bool array with shape [H, W] (px
    on/off). Returns: bool array with shape [H, W]; empty in, empty out.
    Raises TypeError for a MaskSet/dict instead of the 2D array.
    """
    single = _as_bool_2d("largest_component", mask)
    lab, count = ndimage.label(single, structure=_FOUR)
    if count == 0:
        return np.zeros_like(single, dtype=bool)
    sizes = np.bincount(lab.ravel())[1:]
    return np.asarray(lab == (int(np.argmax(sizes)) + 1), dtype=bool)


def spans_of(mask: Any) -> list[list[int]]:
    """Compact row runs of one frame mask for drawing on the page.

    Argument shapes: mask is a single 2D bool array with shape [H, W] (px
    on/off). Returns: a list of [y, x0, x1] int runs in px, x1 exclusive,
    rows top to bottom, runs left to right. Raises TypeError for a
    MaskSet/dict instead of the 2D array.
    """
    single = _as_bool_2d("spans_of", mask)
    spans: list[list[int]] = []
    for y in range(single.shape[0]):
        cols = np.flatnonzero(single[y])
        if cols.size == 0:
            continue
        cuts = np.flatnonzero(np.diff(cols) > 1)
        starts = np.concatenate(([cols[0]], cols[cuts + 1]))
        ends = np.concatenate((cols[cuts], [cols[-1]])) + 1
        for x0, x1 in zip(starts, ends):
            spans.append([int(y), int(x0), int(x1)])
    return spans


def spans_of_track(obj_masks: Any, frames: Any) -> dict[int, list[list[int]]]:
    """Row runs for every frame of one object's track.

    Argument shapes: obj_masks is a single-object bool array with shape
    [N, H, W] (px on/off); frames holds N frame indices in frames.
    Returns: dict {frame index: spans_of(frame) list} in px. Raises
    TypeError for a MaskSet/dict instead of the single-object array.
    """
    track = _as_bool_3d("spans_of_track", obj_masks)
    _need_single("spans_of_track.frames", frames, "a sequence of N frame indices")
    ids = [int(v) for v in np.asarray(frames).reshape(-1)]
    if len(ids) != track.shape[0]:
        raise ValueError(
            "spans_of_track: got " + str(len(ids)) + " frame indices for "
            + str(track.shape[0]) + " masks."
        )
    return {frame: spans_of(track[i]) for i, frame in enumerate(ids)}


def track_quality(
    obj_masks: Any, frames: Any, *, area_jump: float = 1.5, split_ratio: float = 0.2
) -> dict[str, Any]:
    """Flag suspicious frames in one object's track.

    Argument shapes: obj_masks is a single-object bool array with shape
    [N, H, W] (px on/off); frames holds N frame indices in frames; area_jump
    and split_ratio are unit-free thresholds. Returns: dict with gaps (frame
    indices with an empty mask, plus indices missing from the frame range, in
    frames), area_jumps ([frame, ratio] pairs, ratio unit-free, for neighbour
    area changes beyond area_jump x), splits (frames where the second-largest
    4-connected component reaches split_ratio of the largest) and a one-line
    summary. Raises TypeError for a MaskSet/dict as obj_masks.
    """
    track = _as_bool_3d("track_quality", obj_masks)
    _need_single("track_quality.frames", frames, "a sequence of N frame indices")
    ids = [int(v) for v in np.asarray(frames).reshape(-1)]
    if len(ids) != track.shape[0]:
        raise ValueError(
            "track_quality: got " + str(len(ids)) + " frame indices for "
            + str(track.shape[0]) + " masks."
        )
    areas = [int(frame.sum()) for frame in track]
    empty = {f for f, a in zip(ids, areas) if a == 0}
    missing = set(range(min(ids), max(ids) + 1)) - set(ids) if ids else set()
    gaps = sorted(empty | missing)
    jumps: list[list[Any]] = []
    for i in range(1, len(ids)):
        prev, now = areas[i - 1], areas[i]
        if prev > 0 and now > 0:
            ratio = now / prev
            if ratio > area_jump or ratio < 1.0 / area_jump:
                jumps.append([ids[i], ratio])
    splits = []
    for f, frame in zip(ids, track):
        if frame.any():
            sizes = _label_sizes(frame)
            if len(sizes) >= 2 and sizes[1] >= split_ratio * sizes[0]:
                splits.append(f)
    span = "frames " + str(ids[0]) + ".." + str(ids[-1]) if ids else "no frames"
    if not gaps and not jumps and not splits:
        summary = "track of " + str(len(ids)) + " " + span + ": clean, no gaps, jumps or splits"
    else:
        summary = (
            "track of " + str(len(ids)) + " " + span + ": " + str(len(gaps))
            + " gap(s), " + str(len(jumps)) + " area jump(s), " + str(len(splits))
            + " split(s)"
        )
    return {"gaps": gaps, "area_jumps": jumps, "splits": splits, "summary": summary}


def fit_parabola(frames: Any, y_px: Any, fps: Any) -> dict[str, Any]:
    """Fit y = a*t^2 + b*t + c to a free-flight track (least squares).

    Argument shapes: frames holds N frame indices in frames, y_px holds N
    pixel rows in px (image y grows down, so falling gives a > 0), fps is the
    frame rate in frames/s; time is t = frame / fps in s. Needs at least 5
    points. Returns: dict with g_px = 2a in px/s^2, g_px_err in px/s^2 (from
    the fit covariance), rms in px, residuals ([N] in px), apex_t in s,
    apex_y in px, v0_px in px/s (velocity at t = 0), n, and window
    {first, last} in frames. Raises TypeError for a MaskSet/dict input.
    """
    _need_single("fit_parabola.frames", frames, "a sequence of N frame indices")
    _need_single("fit_parabola.y_px", y_px, "a sequence of N pixel rows")
    f = np.asarray(frames, dtype=float).reshape(-1)
    y = np.asarray(y_px, dtype=float).reshape(-1)
    rate = float(fps)
    if f.size != y.size:
        raise ValueError("fit_parabola: frames and y_px must have the same length.")
    if f.size < 5:
        raise ValueError("fit_parabola: need at least 5 points.")
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("fit_parabola: fps must be positive.")
    t = f / rate
    design = np.column_stack([t * t, t, np.ones_like(t)])
    coef, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    if rank < 3:
        raise ValueError("fit_parabola: degenerate frame times.")
    a, b, c = (float(v) for v in coef)
    pred = design @ coef
    resid = y - pred
    n = int(f.size)
    rss = float(resid @ resid)
    dof = n - 3
    var_scale = rss / dof
    try:
        cov = var_scale * np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError:
        cov = var_scale * np.linalg.pinv(design.T @ design)
    g_px = 2.0 * a
    g_px_err = 2.0 * math.sqrt(max(float(cov[0, 0]), 0.0))
    if a == 0.0:
        apex_t: float | None = None
        apex_y: float | None = None
    else:
        apex_t = -b / (2.0 * a)
        apex_y = a * apex_t * apex_t + b * apex_t + c
    return {
        "g_px": g_px,
        "g_px_err": g_px_err,
        "rms": math.sqrt(rss / n),
        "residuals": np.asarray(resid, dtype=float),
        "apex_t": apex_t,
        "apex_y": apex_y,
        "v0_px": b,
        "n": n,
        "window": {"first": int(f[0]), "last": int(f[-1])},
    }


def scale_from_reference(
    length_px: float, length_px_err: float, size_m: float, size_m_err: float
) -> tuple[float, float]:
    """Pixel scale from a reference object of known size.

    Argument shapes: all four are scalars; lengths in px, sizes in m, errors
    are standard errors in the same units. Returns: (px_per_m in px/m,
    err in px/m); relative errors are added in quadrature.
    """
    for name, value in (
        ("length_px", length_px),
        ("length_px_err", length_px_err),
        ("size_m", size_m),
        ("size_m_err", size_m_err),
    ):
        if not math.isfinite(float(value)):
            raise ValueError("scale_from_reference: " + name + " must be finite.")
    length_px, size_m = float(length_px), float(size_m)
    if length_px <= 0 or size_m <= 0:
        raise ValueError("scale_from_reference: lengths must be positive.")
    px_per_m = length_px / size_m
    rel = math.sqrt((float(length_px_err) / length_px) ** 2 + (float(size_m_err) / size_m) ** 2)
    return px_per_m, px_per_m * rel


def to_metres(
    g_px: float, g_px_err: float, px_per_m: float, px_per_m_err: float
) -> tuple[float, float]:
    """Convert an acceleration from px/s^2 to m/s^2.

    Argument shapes: all four are scalars; g_px in px/s^2, px_per_m in px/m,
    errors are standard errors in the same units. Returns: (g in m/s^2,
    g_err in m/s^2); relative errors are added in quadrature.
    """
    for name, value in (
        ("g_px", g_px),
        ("g_px_err", g_px_err),
        ("px_per_m", px_per_m),
        ("px_per_m_err", px_per_m_err),
    ):
        if not math.isfinite(float(value)):
            raise ValueError("to_metres: " + name + " must be finite.")
    px_per_m = float(px_per_m)
    if px_per_m <= 0:
        raise ValueError("to_metres: px_per_m must be positive.")
    g = float(g_px) / px_per_m
    rel = math.sqrt((float(g_px_err) / float(g_px)) ** 2 + (float(px_per_m_err) / px_per_m) ** 2)
    return g, abs(g) * rel


def decide(
    g: float, g_err: float, worlds: dict[str, float] | None = None, *, k_sigma: float = 2.0
) -> dict[str, Any]:
    """Verdict: which worlds (if any) the measured gravity fits.

    Argument shapes: g and g_err are scalars in m/s^2; worlds maps world
    names to g in m/s^2 (default Earth 9.81 and Moon 1.62; pass Mars 3.71
    explicitly to include it); k_sigma is a unit-free threshold. For each
    world sigma = (g - g_world) / g_err; a world is consistent when
    |sigma| <= k_sigma (with a 1e-9 tolerance). Returns: dict with state
    ("fits:<World>", "undetermined" or "none_fits"), world (the fitting
    world or None), consistent (list), sigmas (dict, unit-free), nearest
    (smallest |ln(g / g_world)|), k = sqrt(g_world / g) for the nearest
    world (k > 1: the clip runs slow by x k; k < 1: it runs fast), and a
    one-sentence English text for the page.
    """
    g, g_err, k_sigma = float(g), float(g_err), float(k_sigma)
    if not math.isfinite(g) or not math.isfinite(g_err) or g_err <= 0:
        raise ValueError("decide: need a finite g and a positive g_err.")
    if not math.isfinite(k_sigma) or k_sigma <= 0:
        raise ValueError("decide: k_sigma must be positive.")
    table = dict(_DEFAULT_WORLDS) if worlds is None else dict(worlds)
    if not table:
        raise ValueError("decide: worlds must not be empty.")
    for name, value in table.items():
        if not math.isfinite(float(value)) or float(value) <= 0:
            raise ValueError("decide: world " + repr(name) + " must be positive.")
    sigmas = {name: (g - float(w)) / g_err for name, w in table.items()}
    consistent = [name for name, s in sigmas.items() if abs(s) <= k_sigma + 1e-9]
    if g > 0:
        nearest = min(table, key=lambda name: abs(math.log(g / float(table[name]))))
    else:
        nearest = min(sigmas, key=lambda name: abs(sigmas[name]))
    k = math.sqrt(float(table[nearest]) / g) if g > 0 else None
    if len(consistent) == 1:
        state, world = "fits:" + consistent[0], consistent[0]
    elif len(consistent) >= 2:
        state, world = "undetermined", None
    else:
        state, world = "none_fits", None
    shown = f"{k_sigma:g}"
    if state.startswith("fits:"):
        text = (
            "The measured g of " + f"{g:.2f}" + " ± " + f"{g_err:.2f}"
            + " m/s^2 fits " + str(world) + " (" + f"{float(table[str(world)]):.2f}"
            + " m/s^2) within " + shown + " sigma."
        )
    elif state == "undetermined":
        text = (
            "The measured g of " + f"{g:.2f}" + " ± " + f"{g_err:.2f}"
            + " m/s^2 is consistent with more than one world ("
            + ", ".join(consistent) + "), so the verdict is undetermined."
        )
    else:
        pace = "runs slow by x" + f"{k:.3f}" if k is not None and k >= 1 else (
            "runs fast by x" + f"{1 / k:.3f}" if k else "has an unknown time scale"
        )
        text = (
            "The measured g of " + f"{g:.2f}" + " ± " + f"{g_err:.2f}"
            + " m/s^2 fits no listed world; the nearest is " + str(nearest)
            + ", which would need the clip to " + pace + "."
        )
    return {
        "state": state,
        "world": world,
        "consistent": consistent,
        "sigmas": sigmas,
        "nearest": nearest,
        "k": k,
        "text": text,
        "g": g,
        "g_err": g_err,
        "k_sigma": k_sigma,
    }

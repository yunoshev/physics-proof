# generated from brief/09 · part 09 owns this file
"""Verified mask statistics and point tracks (part 09).

Pure functions over numpy arrays: per-frame statistics, the largest
connected piece, mask → tracked point, track quality flags, and
scene-relative tracks. Image coordinates: ``x`` grows right, ``y``
grows downward in pixels; the flip to metres-up happens in exactly
one place (:func:`src.helpers.physics.track_to_metres`), never here.
"""

from __future__ import annotations

import math

__all__ = [
    "find_still_patches",
    "largest_component",
    "mask_stats",
    "relative_track",
    "still_track",
    "track_point",
    "track_quality",
]

#: Pixels of clearance around a candidate still patch (and around a
#: tracked box): a box qualifies only if, grown by this margin on
#: every side, it does not meet any mover's bounding box.
_STILL_CLEARANCE_PX = 20

#: A second-largest component above this fraction of the largest marks
#: a split (posture split or a second object bleeding in).
_SPLIT_FRAC = 0.25

try:  # Single source of limits (part 04); fall back to spec values.
    from src.config import IDENTITY_SWAP_IOU as _CONFIG_SWAP_IOU
except (ImportError, AttributeError):  # pragma: no cover
    _CONFIG_SWAP_IOU = None

#: Frame-to-frame self-IoU below this while cross-IoU exceeds it marks
#: an identity swap (SAM object ids are unstable when objects overlap,
#: so a flagged segment must be re-tracked or excluded, never trusted).
IDENTITY_SWAP_IOU_FALLBACK = 0.4


def _swap_threshold():
    if isinstance(_CONFIG_SWAP_IOU, (int, float)):
        return float(_CONFIG_SWAP_IOU)
    return IDENTITY_SWAP_IOU_FALLBACK


def _as_mask(mask):
    """A 2-D bool array, or ``ValueError`` (``"bad_mask"``)."""
    import numpy as np

    arr = np.asarray(mask)
    if arr.ndim != 2:
        raise ValueError(
            f"bad_mask: need a 2-D mask, got {arr.ndim}-D")
    return arr.astype(bool)


def _nonempty(mask):
    """The bool mask, or ``ValueError`` (``"empty_mask"``)."""
    arr = _as_mask(mask)
    if not arr.any():
        raise ValueError("empty_mask")
    return arr


def mask_stats(mask):
    """Statistics for one frame's mask.

    Returns ``{"top", "bottom", "left", "right", "height", "width",
    "area", "centroid"}``: the extreme occupied rows/columns (ints,
    inclusive), ``height = bottom - top + 1``, ``width = right - left
    + 1``, the occupied pixel count, and ``centroid`` as ``{"x",
    "y"}`` floats (mean occupied column/row). Raises ``ValueError``
    (``"empty_mask"``) on an empty mask — never zeros that look like a
    measurement at the origin.
    """
    import numpy as np

    arr = _nonempty(mask)
    ys, xs = np.nonzero(arr)
    return {"top": int(ys.min()), "bottom": int(ys.max()),
            "left": int(xs.min()), "right": int(xs.max()),
            "height": int(ys.max() - ys.min() + 1),
            "width": int(xs.max() - xs.min() + 1),
            "area": int(arr.sum()),
            "centroid": {"x": float(xs.mean()),
                         "y": float(ys.mean())}}


def largest_component(mask):
    """Keep the largest connected piece of a mask.

    OpenCV connected components; returns a bool array with only the
    largest component set. A stray blob must not move "the bottom of
    the body". Raises ``ValueError`` (``"empty_mask"``) on an empty
    mask.
    """
    import cv2
    import numpy as np

    arr = _nonempty(mask)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        arr.astype(np.uint8), connectivity=8)
    if count <= 1:
        raise ValueError("empty_mask")
    areas = stats[1:, cv2.CC_STAT_AREA]
    best = int(areas.argmax()) + 1
    return np.asarray(labels == best, dtype=bool)


def _point_for(arr, mode):
    """The tracked pixel for one mask under ``mode``."""
    import numpy as np

    ys, xs = np.nonzero(arr)
    if mode == "centroid":
        return float(xs.mean()), float(ys.mean())
    if mode == "bottom_centre":
        return float(xs.mean()), float(ys.max())
    if mode == "top_centre":
        return float(xs.mean()), float(ys.min())
    bottom = arr[ys.max()]
    cols = np.nonzero(bottom)[0]
    return float(cols.mean()), float(ys.max())


#: The modes :func:`track_point` understands (the mode is recorded on
#: every row, because part 08 R-M2 cares *which* point was tracked).
TRACK_MODES = ("centroid", "bottom_centre", "top_centre",
               "lowest_point")


def track_point(masks, mode, timestamps=None):
    """Per-frame track of a chosen point.

    ``masks`` maps ``frame_index`` to a mask; ``mode`` is one of
    ``centroid``, ``bottom_centre`` (mean-x at the bottom row),
    ``top_centre`` (mean-x at the top row) or ``lowest_point`` (the
    bottom-most occupied pixel; ties averaged). ``timestamps`` maps
    ``frame_index`` to video seconds; when omitted, ``t`` is the
    frame index as a float.

    Returns ``{"frame", "t", "x_px", "y_px", "mode"}`` rows sorted by
    frame. Empty frames are skipped (the gap shows up in
    :func:`track_quality`); when no frame yields a point, raises
    ``ValueError`` (``"empty_mask"``). An unknown mode raises
    ``ValueError`` (``"bad_mode"``).
    """
    if mode not in TRACK_MODES:
        raise ValueError(
            f"bad_mode: {mode!r} is not one of {list(TRACK_MODES)}")
    try:
        items = sorted(masks.items())
    except AttributeError as exc:
        raise ValueError(
            f"bad_masks: masks must map frame_index to a mask: "
            f"{exc}") from exc
    rows = []
    for frame, mask in items:
        if isinstance(frame, bool):
            raise ValueError(f"bad_frame: frame key {frame!r} "
                             "must be an int")
        try:
            frame_index = int(frame)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"bad_frame: frame key {frame!r} must be an int: "
                f"{exc}") from exc
        try:
            arr = _as_mask(mask)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if not arr.any():
            continue
        x_px, y_px = _point_for(arr, mode)
        if timestamps is None:
            moment = float(frame_index)
        else:
            try:
                moment = float(timestamps[frame_index])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"bad_timestamps: no video time for frame "
                    f"{frame_index}: {exc}") from exc
        rows.append({"frame": frame_index, "t": moment,
                     "x_px": float(x_px), "y_px": float(y_px),
                     "mode": mode})
    if not rows:
        raise ValueError("empty_mask")
    return rows


def _iou(first, second):
    """Intersection over union of two bool arrays (0.0 on empty)."""
    import numpy as np

    a = np.asarray(first, dtype=bool)
    b = np.asarray(second, dtype=bool)
    if a.shape != b.shape:
        return 0.0
    union = bool((a | b).any())
    if not union:
        return 0.0
    return float((a & b).sum()) / float((a | b).sum())


def _components(mask):
    """Areas of the connected components (background excluded)."""
    import cv2
    import numpy as np

    arr = np.asarray(mask, dtype=bool)
    if not arr.any():
        return []
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        arr.astype(np.uint8), connectivity=8)
    if count <= 1:
        return []
    return [int(area) for area in stats[1:, cv2.CC_STAT_AREA]]


def track_quality(track, masks_by_object,
                  jump_heights_per_frame=1.0):
    """Quality flags for a track against its masks.

    ``track`` is :func:`track_point` rows; ``masks_by_object`` maps
    ``object_id`` to ``{frame_index: mask}``. The tracked object is
    the rows' ``"object_id"`` when present, else the sole object;
    when several objects are present and the rows name none, split
    flags are evaluated over every object.

    Returns ``{"gaps", "jumps", "splits", "identity_swaps", "ok"}``:

    - **gaps:** frames missing between the first and last tracked
      frame;
    - **jumps:** frames whose displacement from the previous tracked
      frame exceeds ``jump_heights_per_frame`` mask-heights per frame
      (normalised by the frame gap, so a gap is not itself a jump);
    - **splits:** frames where the second-largest component exceeds
      25% of the largest (posture split or a second object bleeding
      in);
    - **identity_swaps:** frames where some object's self-IoU with
      its previous mask drops below the identity-swap threshold while
      its IoU with another object's previous mask exceeds the
      self-IoU — SAM object ids are unstable when objects overlap, so
      a flagged segment must be re-tracked or excluded, not trusted.

    ``"ok"`` is true when every flag list is empty.
    """
    rows = sorted(track or [], key=lambda row: int(row["frame"]))
    frames = [int(row["frame"]) for row in rows]
    gaps = []
    if frames:
        have = set(frames)
        gaps = [f for f in range(frames[0], frames[-1] + 1)
                if f not in have]
    jumps = []
    if len(rows) >= 2:
        heights = _mask_heights(masks_by_object)
        typical = 0.0
        count = 0
        for xs in heights.values():
            for height in xs.values():
                typical += height
                count += 1
        typical = typical / count if count else 0.0
        for prev, row in zip(rows, rows[1:]):
            frame = int(row["frame"])
            step = frame - int(prev["frame"])
            if step <= 0:
                continue
            displacement = math.hypot(
                float(row["x_px"]) - float(prev["x_px"]),
                float(row["y_px"]) - float(prev["y_px"]))
            height = heights.get(_track_object(rows, masks_by_object),
                                 {}).get(frame, typical)
            if height and displacement / step > (
                    jump_heights_per_frame * height):
                jumps.append(frame)
    splits = []
    for object_id, per_frame in _split_scope(rows, masks_by_object):
        for frame in frames:
            mask = per_frame.get(frame)
            if mask is None:
                continue
            areas = sorted(_components(mask), reverse=True)
            if len(areas) >= 2 and areas[0] > 0 and (
                    areas[1] > _SPLIT_FRAC * areas[0]):
                splits.append(frame)
    identity_swaps = _identity_swaps(masks_by_object)
    splits = sorted(set(splits))
    flags = {"gaps": gaps, "jumps": sorted(set(jumps)),
             "splits": splits,
             "identity_swaps": sorted(set(identity_swaps))}
    flags["ok"] = not any(flags.values())
    return flags


def _track_object(rows, masks_by_object):
    """The tracked object id, or None when ambiguous."""
    named = {row.get("object_id") for row in rows
             if "object_id" in row}
    if len(named) == 1:
        (only,) = named
        return only
    if len(masks_by_object) == 1:
        (only,) = masks_by_object
        return only
    return None


def _split_scope(rows, masks_by_object):
    """Objects whose masks are split-checked for this track."""
    object_id = _track_object(rows, masks_by_object)
    if object_id is not None and object_id in masks_by_object:
        return [(object_id, masks_by_object[object_id])]
    return list(masks_by_object.items())


def _mask_heights(masks_by_object):
    """``{object_id: {frame: mask height}}`` for jump normalisation."""
    heights = {}
    for object_id, per_frame in (masks_by_object or {}).items():
        own = {}
        for frame, mask in (per_frame or {}).items():
            try:
                stats = mask_stats(mask)
            except ValueError:
                continue
            try:
                own[int(frame)] = float(stats["height"])
            except (TypeError, ValueError):
                continue
        heights[object_id] = own
    return heights


def _identity_swaps(masks_by_object):
    """Frames where an object looks more like another's past self."""
    threshold = _swap_threshold()
    objects = {oid: {int(f): m for f, m in (per or {}).items()}
               for oid, per in (masks_by_object or {}).items()}
    ids = sorted(objects, key=str)
    flagged = []
    for pos, object_id in enumerate(ids):
        for other in ids:
            if other == object_id:
                continue
            own_frames = objects[object_id]
            other_frames = objects[other]
            for frame in sorted(own_frames):
                prev = frame - 1
                if prev not in own_frames or prev not in other_frames:
                    continue
                try:
                    import numpy as np

                    current = np.asarray(
                        own_frames[frame], dtype=bool)
                    self_past = np.asarray(
                        own_frames[prev], dtype=bool)
                    cross_past = np.asarray(
                        other_frames[prev], dtype=bool)
                except (TypeError, ValueError):
                    continue
                if current.shape != self_past.shape or (
                        current.shape != cross_past.shape):
                    continue
                self_iou = _iou(current, self_past)
                cross_iou = _iou(current, cross_past)
                if (self_iou < threshold
                        and cross_iou > self_iou
                        and cross_iou >= threshold):
                    flagged.append(frame)
    return flagged


def relative_track(track_a, track_b):
    """A's positions minus B's, aligned on common frames.

    For a wall run this is the runner relative to a track fixed on
    the wall, which enforces R-M3 mechanically. Returns ``{"frame",
    "t", "x_px", "y_px"}`` rows (``t`` from A) sorted by frame.
    Raises ``ValueError`` (``"no_common_frames"``) when the tracks
    share no frame.
    """
    by_b = {}
    for row in track_b or []:
        by_b[int(row["frame"])] = row
    rows = []
    for row in track_a or []:
        frame = int(row["frame"])
        if frame not in by_b:
            continue
        other = by_b[frame]
        rows.append({"frame": frame, "t": float(row.get(
            "t", float(other.get("t", frame)))),
            "x_px": float(row["x_px"]) - float(other["x_px"]),
            "y_px": float(row["y_px"]) - float(other["y_px"])})
    if not rows:
        raise ValueError("no_common_frames")
    rows.sort(key=lambda row: row["frame"])
    return rows


def _check_frames_list(frames):
    """A non-empty list of int frame indices, or ``ValueError``."""
    try:
        items = list(frames)
    except TypeError as exc:
        raise ValueError(
            f"bad_frames: frames must hold frame indices: {exc}") from exc
    if not items:
        raise ValueError("bad_frames: frames must be non-empty")
    wanted = []
    for original in items:
        if isinstance(original, bool):
            raise ValueError(
                "bad_frames: frames must hold frame indices")
        try:
            wanted.append(int(original))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "bad_frames: frames must hold frame indices: "
                f"{exc}") from exc
    return wanted


def _mask_bboxes_on_frame(avoid, frame):
    """``[(object_id, (x0, y0, x1_excl, y1_excl))]`` for masks on ``frame``.

    Masks that do not cover ``frame`` (or are empty) contribute no box:
    frames a mask does not cover are not checked for that mask.
    """
    import numpy as np

    boxes = []
    for object_id, per_frame in (avoid or {}).items():
        if not isinstance(per_frame, dict) or frame not in per_frame:
            continue
        try:
            arr = np.asarray(per_frame[frame], dtype=bool)
        except (TypeError, ValueError):
            continue
        if arr.ndim != 2 or not arr.any():
            continue
        ys, xs = np.nonzero(arr)
        boxes.append((object_id, (int(xs.min()), int(ys.min()),
                                 int(xs.max()) + 1, int(ys.max()) + 1)))
    return boxes


def _box_meets_mover(box, avoid, frame, margin=_STILL_CLEARANCE_PX):
    """The id of the first mover the grown box meets, or None."""
    x, y, w, h = box
    grown = (x - margin, y - margin, x + w + margin, y + h + margin)
    for object_id, (bx0, by0, bx1, by1) in _mask_bboxes_on_frame(
            avoid, frame):
        if grown[0] < bx1 and bx0 < grown[2] and (
                grown[1] < by1 and by0 < grown[3]):
            return object_id
    return None


def _read_grey(video_path, indices):
    """Grey frames for ``indices``, in order, plus ``(width, height)``.

    Raises ``ValueError`` (``"no_such_video"``, ``"unreadable_frame"``).
    """
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(
            f"no_such_video: {video_path} cannot be opened")
    try:
        grey = []
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, float(index))
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError(
                    f"unreadable_frame: frame {index} of {video_path} "
                    "cannot be decoded")
            grey.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    if grey:
        height, width = grey[0].shape[:2]
    return grey, (width, height)


def find_still_patches(video_path, frames, avoid=None, size=64, count=3):
    """Boxes of background that no moving thing crosses.

    Returns up to ``count`` boxes ``(x, y, w, h)`` of ``size``×``size``
    pixels. A box qualifies only if, grown by 20 px on every side, it
    does not meet the bounding box of any mask in ``avoid`` (masks by
    object, as :func:`src.helpers.masks_io.load_masks` returns them)
    on any of ``frames``. Frames that a mask does not cover are not
    checked for that mask. Among the qualifying boxes on the first of
    ``frames``, the ones with the most texture (variance of the
    Laplacian of the grey image) are returned, with centres at least
    ``2·size`` apart (greedy, most textured first). When nothing
    qualifies, returns ``[]``.

    How to use this for ``camera.still``: pass every frame of the fit
    window and the masks of every moving thing as ``avoid``; take the
    first box returned here, track it with :func:`still_track`, save
    the rows as a workspace JSON file and cite that file as
    ``reference_track_artifact``. A template tracked by hand next to
    a moving thing follows it and reads as camera motion — these
    patches are clear of every mover by construction instead.

    Raises ``ValueError`` (``"no_such_video"``,
    ``"unreadable_frame"``, ``"bad_frames"``, ``"bad_box"``) on
    unusable inputs.
    """
    import cv2
    import numpy as np

    wanted = _check_frames_list(frames)
    try:
        edge = int(size)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_box: size must be a positive int, got {size!r}: "
            f"{exc}") from exc
    if isinstance(size, bool) or edge <= 0:
        raise ValueError(
            f"bad_box: size must be a positive int, got {size!r}")
    try:
        want = int(count)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_box: count must be a positive int, got {count!r}: "
            f"{exc}") from exc
    if isinstance(count, bool) or want <= 0:
        raise ValueError(
            f"bad_box: count must be a positive int, got {count!r}")
    grey, (width, height) = _read_grey(video_path, [wanted[0]])
    first = grey[0]
    if edge > width or edge > height:
        raise ValueError(
            f"bad_box: size {edge} exceeds the {width}x{height} frame")
    frame_boxes = {frame: _mask_bboxes_on_frame(avoid, frame)
                   for frame in wanted}

    def _clear(x, y):
        grown = (x - _STILL_CLEARANCE_PX, y - _STILL_CLEARANCE_PX,
                 x + edge + _STILL_CLEARANCE_PX,
                 y + edge + _STILL_CLEARANCE_PX)
        for boxes in frame_boxes.values():
            for _, (bx0, by0, bx1, by1) in boxes:
                if grown[0] < bx1 and bx0 < grown[2] and (
                        grown[1] < by1 and by0 < grown[3]):
                    return False
        return True

    stride = max(1, edge // 2)
    xs = list(range(0, width - edge + 1, stride))
    if xs[-1] != width - edge:
        xs.append(width - edge)
    ys = list(range(0, height - edge + 1, stride))
    if ys[-1] != height - edge:
        ys.append(height - edge)
    textured = []
    for y in ys:
        for x in xs:
            if not _clear(x, y):
                continue
            roi = first[y:y + edge, x:x + edge]
            lap = cv2.Laplacian(roi, cv2.CV_64F)
            textured.append((float(np.var(lap)), x, y))
    textured.sort(key=lambda item: item[0], reverse=True)
    picked = []
    for _, x, y in textured:
        cx, cy = x + edge / 2.0, y + edge / 2.0
        if all(math.hypot(cx - (px + edge / 2.0),
                          cy - (py + edge / 2.0)) >= 2 * edge
               for _, px, py in picked):
            picked.append((_, x, y))
            if len(picked) >= want:
                break
    return [(x, y, edge, edge) for _, x, y in picked]


def still_track(video_path, frames, box, avoid=None):
    """Track a fixed background patch across frames.

    ``box`` is ``(x, y, w, h)`` — usually the first box from
    :func:`find_still_patches`. Returns one row per frame in
    ``frames``, in order, with exactly the keys ``frame``, ``x_px``
    and ``y_px`` (the same row format as a
    ``reference_track_artifact``): the box centre on the first of
    ``frames`` plus, per frame, the shift of the box's grey patch from
    the first of ``frames`` measured by phase correlation with a Hann
    window (sub-pixel).

    The box is first checked with the same ``avoid`` test as
    :func:`find_still_patches` (grown by 20 px on every side against
    every mover's bounding box on each of ``frames``); when the box
    meets a mover, raises ``ValueError`` (``"mover_overlap"``) naming
    the object and the frame, for example ``"mover_overlap: box meets
    object 'pole' on frame 12"``.

    How to use this for ``camera.still``: pass every frame of the fit
    window and the masks of every moving thing as ``avoid``; save the
    returned rows as a workspace JSON file and cite that file as
    ``reference_track_artifact``. A template tracked by hand next to
    a moving thing follows it and reads as camera motion — this
    measures the patch the library verified is clear of movers.

    Raises ``ValueError`` (``"no_such_video"``,
    ``"unreadable_frame"``, ``"bad_frames"``, ``"bad_box"``,
    ``"mover_overlap"``) on unusable inputs.
    """
    import cv2
    import numpy as np

    wanted = _check_frames_list(frames)
    try:
        x, y, w, h = (float(v) for v in box)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_box: box must be (x, y, w, h) numbers, got "
            f"{box!r}: {exc}") from exc
    if not all(math.isfinite(v) for v in (x, y, w, h)):
        raise ValueError(
            f"bad_box: box must be finite, got {box!r}")
    if w <= 0 or h <= 0:
        raise ValueError(
            f"bad_box: box width and height must be positive, got "
            f"{box!r}")
    xi, yi, wi, hi = int(round(x)), int(round(y)), int(round(w)), \
        int(round(h))
    if wi <= 0 or hi <= 0:
        raise ValueError(
            f"bad_box: box rounds to nothing, got {box!r}")
    for frame in wanted:
        hit = _box_meets_mover((xi, yi, wi, hi), avoid, frame)
        if hit is not None:
            raise ValueError(
                f"mover_overlap: box meets object {hit!r} on frame "
                f"{frame}")
    grey, (width, height) = _read_grey(video_path, wanted)
    if xi < 0 or yi < 0 or xi + wi > width or yi + hi > height:
        raise ValueError(
            f"bad_box: box {(xi, yi, wi, hi)} lies outside the "
            f"{width}x{height} frame")
    centre_x = xi + wi / 2.0
    centre_y = yi + hi / 2.0
    ref = np.asarray(
        grey[0][yi:yi + hi, xi:xi + wi], dtype=np.float64)
    hann = np.outer(np.hanning(hi), np.hanning(wi)).astype(np.float64)
    rows = []
    for frame, patch in zip(wanted, grey):
        cur = np.asarray(
            patch[yi:yi + hi, xi:xi + wi], dtype=np.float64)
        try:
            (dx, dy), _response = cv2.phaseCorrelate(ref, cur, hann)
        except cv2.error:
            dx, dy = 0.0, 0.0
        rows.append({"frame": int(frame),
                     "x_px": float(centre_x + dx),
                     "y_px": float(centre_y + dy)})
    return rows

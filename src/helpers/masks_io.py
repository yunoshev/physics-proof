# generated from brief/09 · part 09 owns this file
"""Verified mask I/O and timing facts (part 09).

The single decode/re-encode point for masks: SAM returns masks
compressed per frame, and this module is where they are stored and
reloaded. Agent code never parses ``.npz`` files itself.

It also owns the only sanctioned way for agent code to learn timing
(:func:`clip_facts`, enforces R-T1): frame count, measured fps, the
per-frame timestamp array, duplicate runs and cut indices — never a
container fps.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    "clip_facts",
    "load_masks",
    "read_frames",
    "save_masks",
]

#: npz entry holding the JSON index (object ids, frames, array keys).
_INDEX_KEY = "__helpers_index__"


def _check_mask_array(array, object_id, frame):
    """A 2-D bool array, or a ``ValueError`` naming the problem."""
    import numpy as np

    arr = np.asarray(array)
    if arr.ndim != 2:
        raise ValueError(f"bad_mask: object {object_id!r} frame {frame!r} "
                         f"is {arr.ndim}-D, need a 2-D mask")
    return arr.astype(bool)


def save_masks(path, masks):
    """Save ``masks`` as one compressed ``.npz`` file.

    ``masks`` maps ``object_id`` (int or str) to ``{frame_index: bool
    array}``. Every array must be 2-D; dtype is normalised to bool, so
    a ``{object_id: {frame: bool array}}`` mapping round-trips
    losslessly through :func:`load_masks` (same object ids with the
    same int/str type, same int frame indices, identical pixels).

    Raises ``ValueError`` (``"bad_masks"``, ``"bad_mask"``) on a
    non-mapping input or a non-2-D array. Missing parent directories
    are created.
    """
    import numpy as np

    if not isinstance(masks, dict):
        raise ValueError("bad_masks: masks must map object_id to "
                         "{frame_index: bool array}")
    index = []
    arrays = {}
    for position, (object_id, frames) in enumerate(masks.items()):
        if isinstance(object_id, bool) or not isinstance(
                object_id, (int, str)):
            raise ValueError(
                f"bad_masks: object id {object_id!r} must be int or str")
        if not isinstance(frames, dict):
            raise ValueError(
                f"bad_masks: object {object_id!r} must map frame_index "
                "to a bool array")
        for frame, mask in frames.items():
            if isinstance(frame, bool) or not isinstance(frame, int):
                raise ValueError(
                    f"bad_masks: object {object_id!r} frame key "
                    f"{frame!r} must be an int")
            arr = _check_mask_array(mask, object_id, frame)
            key = f"m{position}_{len(index)}"
            arrays[key] = arr
            index.append({"oid": str(object_id),
                          "int_oid": isinstance(object_id, int),
                          "frame": int(frame), "key": key,
                          "shape": [int(arr.shape[0]),
                                    int(arr.shape[1])]})
    target = Path(str(path))
    if target.parent and str(target.parent):
        target.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(arrays)
    payload[_INDEX_KEY] = np.asarray(json.dumps(index))
    np.savez_compressed(str(target), **payload)


def load_masks(path):
    """Load a ``.npz`` written by :func:`save_masks`.

    Returns ``{object_id: {frame_index: bool array}}`` with int object
    ids restored as int (evidence carries them as strings; the helpers
    preserve int ids) and int frame indices. Arrays are bool dtype.

    Raises ``OSError`` when the file is missing and ``ValueError``
    (``"bad_masks_npz"``) when it is not a masks file.
    """
    import numpy as np

    try:
        with np.load(str(path), allow_pickle=False) as bundle:
            if _INDEX_KEY not in bundle:
                raise ValueError(
                    f"bad_masks_npz: {path} holds no mask index")
            try:
                index = json.loads(str(bundle[_INDEX_KEY]))
            except ValueError as exc:
                raise ValueError(
                    f"bad_masks_npz: {path} holds a bad mask index: "
                    f"{exc}") from exc
            if not isinstance(index, list):
                raise ValueError(
                    f"bad_masks_npz: {path} holds a bad mask index")
            out: dict = {}
            for entry in index:
                try:
                    key = entry["key"]
                    arr = np.asarray(bundle[key]).astype(bool)
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"bad_masks_npz: {path} entry "
                        f"{entry!r} is unreadable: {exc}") from exc
                if arr.ndim != 2:
                    raise ValueError(
                        f"bad_masks_npz: {path} entry {key!r} is not 2-D")
                object_id: object = entry["oid"]
                if entry.get("int_oid"):
                    object_id = int(entry["oid"])
                out.setdefault(object_id, {})[int(entry["frame"])] = arr
            return out
    except OSError:
        raise
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            f"bad_masks_npz: {path} is not a masks file: {exc}") from exc


def clip_facts(timing_path):
    """The sanctioned timing facts for agent code (enforces R-T1).

    Reads the part-05 timing report and returns ``{"frame_count",
    "measured_fps", "timestamps", "duplicate_runs", "cut_indices"}``:
    the frame count, the measured (never container) fps, the
    per-frame timestamp array in seconds (a numpy array), duplicate
    runs (each a sorted list of frame indices) and cut indices (a
    sorted list).

    Tolerates the report's key variants (``fps`` for ``measured_fps``,
    ``confirmed_duplicates`` for ``duplicate_runs``, ``cuts`` for
    ``cut_indices``). Raises ``OSError`` when the file is missing and
    ``ValueError`` (``"bad_timing"``) when it is malformed.
    """
    import numpy as np

    try:
        with open(str(timing_path), encoding="utf-8") as handle:
            report = json.load(handle)
    except OSError:
        raise
    except ValueError as exc:
        raise ValueError(
            f"bad_timing: {timing_path} is not JSON: {exc}") from exc
    if not isinstance(report, dict):
        raise ValueError(f"bad_timing: {timing_path} holds no report")
    try:
        frame_count = int(report["frame_count"])
        stamps = [float(v) for v in report["timestamps"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_timing: {timing_path} needs frame_count and "
            f"timestamps: {exc}") from exc
    if frame_count <= 0 or len(stamps) != frame_count:
        raise ValueError(
            f"bad_timing: {timing_path} timestamps do not match "
            "frame_count")
    measured = report.get("measured_fps", report.get("fps"))
    if isinstance(measured, dict):
        for key in ("median", "value", "fps"):
            if key in measured:
                measured = measured[key]
                break
    try:
        fps = float(measured)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_timing: {timing_path} measured_fps unusable: "
            f"{exc}") from exc
    if not fps > 0:
        raise ValueError(
            f"bad_timing: {timing_path} measured_fps is not positive")
    runs = report.get("duplicate_runs")
    if runs is None:
        confirmed = report.get("confirmed_duplicates",
                               report.get("duplicates", []))
        if confirmed and all(isinstance(item, (list, tuple))
                             for item in confirmed):
            runs = [sorted(int(i) for i in run) for run in confirmed]
        else:
            flat = []
            for item in confirmed or []:
                if isinstance(item, dict):
                    item = item.get("frame")
                try:
                    flat.append(int(item))
                except (TypeError, ValueError):
                    continue
            runs = [sorted(flat)] if flat else []
    else:
        cleaned_runs = []
        for run in runs:
            try:
                cleaned_runs.append(sorted(int(i) for i in run))
            except TypeError:
                try:
                    cleaned_runs.append([int(run)])
                except (TypeError, ValueError):
                    continue
        runs = cleaned_runs
    cuts = report.get("cut_indices", report.get("cuts", []))
    try:
        cut_list = sorted(int(v) for v in cuts)
    except TypeError as exc:
        raise ValueError(
            f"bad_timing: {timing_path} cut indices unusable: "
            f"{exc}") from exc
    return {"frame_count": frame_count, "measured_fps": fps,
            "timestamps": np.asarray(stamps, dtype=float),
            "duplicate_runs": runs, "cut_indices": cut_list}


def read_frames(video_path, indices):
    """Decoded frames as arrays, in the order requested.

    ``indices`` are frame indices into the video; returns a list of
    ``uint8`` BGR arrays (OpenCV decode), one per requested index, in
    the same order. Raises ``ValueError`` (``"no_such_video"``,
    ``"unreadable_frame"``) when the video cannot be opened or an
    index cannot be decoded — never a neighbouring frame relabelled
    as the requested one.
    """
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"no_such_video: {video_path} cannot be opened")
    try:
        wanted = [int(i) for i in indices]
    except (TypeError, ValueError) as exc:
        capture.release()
        raise ValueError(
            f"unreadable_frame: indices must be ints: {exc}") from exc
    frames = []
    try:
        for index in wanted:
            capture.set(cv2.CAP_PROP_POS_FRAMES, float(index))
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError(
                    f"unreadable_frame: frame {index} of {video_path} "
                    "cannot be decoded")
            frames.append(frame)
    finally:
        capture.release()
    return frames

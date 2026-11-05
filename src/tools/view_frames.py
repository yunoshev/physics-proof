# generated from brief/07 · part 07 owns this file
"""``view_frames`` — the agent's only eyes (part 07 §2).

Contact-sheet JPEGs under ``artifacts/`` plus a text index mapping
each cell to its frame number and measured timestamp (from
``input/timing.json`` — never a container fps claim). Frame indices
out of range, and ranges spanning a confirmed cut, are reported, not
silently served.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import config as _config

from .common import append_produced, next_artifact, run_path
from .result import err_result, ok_result
from .timing import find_clip, load_timing

__all__ = [
    "view_frames",
    "resolve_frames",
]

#: Cells per contact sheet (grid chunks) and strip length (sequence).
_GRID_CELLS = 16
_GRID_COLS = 4
_STRIP_CELLS = 8

#: Longest side of one sheet cell in pixels.
_CELL_MAX = 320


def _check_args(frame_start, frame_end, stride, frame_indices, crop,
                layout) -> str:
    """Argument rejection reason, or ``""`` when usable."""
    if frame_indices is not None:
        if (not isinstance(frame_indices, (list, tuple))
                or not frame_indices):
            return "frame_indices must be a non-empty list of ints"
        for value in frame_indices:
            if isinstance(value, bool) or not isinstance(value, int):
                return ("frame_indices must hold ints, got "
                        f"{value!r}")
    else:
        for name, value in (("frame_start", frame_start),
                            ("frame_end", frame_end)):
            if isinstance(value, bool) or not isinstance(value, int):
                return f"{name} must be an int, got {value!r}"
        if frame_end < frame_start:
            return (f"frame_end ({frame_end}) is before frame_start "
                    f"({frame_start})")
    if stride is not None and (
            isinstance(stride, bool) or not isinstance(stride, int)
            or stride < 1):
        return f"stride must be an int >= 1, got {stride!r}"
    if crop is not None:
        if not isinstance(crop, dict):
            return f"crop must be an object, got {crop!r}"
        try:
            x0, y0, x1, y1 = (float(crop["x0"]), float(crop["y0"]),
                              float(crop["x1"]), float(crop["y1"]))
        except (KeyError, TypeError, ValueError):
            return ("crop needs numeric x0/y0/x1/y1, got "
                    f"{crop!r}")
        if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
            return (f"crop must satisfy 0 <= x0 < x1 <= 1 and "
                    f"0 <= y0 < y1 <= 1, got {crop!r}")
    if layout is not None and layout not in ("grid", "sequence"):
        return f"layout must be 'grid' or 'sequence', got {layout!r}"
    return ""


def resolve_frames(frame_start, frame_end, stride, frame_indices,
                   frame_count: int) -> tuple:
    """``(wanted, out_of_range)`` frame lists for one request."""
    if frame_indices is not None:
        wanted = [int(v) for v in frame_indices]
    else:
        step = int(stride) if stride is not None else 1
        wanted = list(range(int(frame_start), int(frame_end) + 1, step))
    good = [f for f in wanted if 0 <= f < frame_count]
    bad = [f for f in wanted if not (0 <= f < frame_count)]
    return good, bad


def _read_frame(capture, index: int):
    """Decode one exact frame (``None`` when unreadable)."""
    import cv2

    capture.set(cv2.CAP_PROP_POS_FRAMES, float(index))
    ok, frame = capture.read()
    if not ok or frame is None:
        return None
    return frame


def _apply_crop(frame, crop):
    if crop is None:
        return frame
    height, width = frame.shape[:2]
    x0 = max(0, int(float(crop["x0"]) * width))
    y0 = max(0, int(float(crop["y0"]) * height))
    x1 = min(width, int(round(float(crop["x1"]) * width)))
    y1 = min(height, int(round(float(crop["y1"]) * height)))
    if x1 <= x0 or y1 <= y0:
        return frame
    return frame[y0:y1, x0:x1]


def _scale_cell(frame):
    import cv2

    height, width = frame.shape[:2]
    scale = min(1.0, _CELL_MAX / max(1, max(height, width)))
    if scale < 1.0:
        frame = cv2.resize(frame, (max(1, int(width * scale)),
                                   max(1, int(height * scale))),
                           interpolation=cv2.INTER_AREA)
    return frame


def _sheet(cells, cols: int):
    """Tile BGR cells into one contact sheet (white-padded)."""
    import numpy as np

    height = max(cell.shape[0] for cell in cells)
    width = max(cell.shape[1] for cell in cells)
    rows = (len(cells) + cols - 1) // cols
    canvas = np.full((rows * height, cols * width, 3), 255,
                     dtype=np.uint8)
    for position, cell in enumerate(cells):
        row, col = divmod(position, cols)
        canvas[row * height:row * height + cell.shape[0],
               col * width:col * width + cell.shape[1]] = cell
    return canvas


def view_frames(run_dir, turn, frame_start=None, frame_end=None,
                stride=None, frame_indices=None, crop=None,
                layout=None) -> dict:
    """Serve one contact-sheet request; always name the files.

    Returns the JPEG sheet(s) plus ``metrics.index`` mapping each
    cell to ``{cell, frame, t_s}`` from measured timestamps.
    """
    import cv2

    problem = _check_args(frame_start, frame_end, stride,
                          frame_indices, crop, layout)
    if problem:
        return err_result("bad_range", problem,
                          metrics={"timing_source": "input/timing.json"})
    try:
        facts = load_timing(run_dir)
    except ValueError as exc:
        return err_result("missing_timing", f"missing_timing: {exc}",
                          metrics={"timing_source": "input/timing.json"})
    frame_count = facts["frame_count"]
    wanted, bad = resolve_frames(frame_start, frame_end, stride,
                                 frame_indices, frame_count)
    if not wanted:
        return err_result(
            "bad_range",
            f"no in-range frames requested (frame_count={frame_count})",
            metrics={"frames_requested": list(frame_indices or []),
                     "out_of_range": list(bad),
                     "frame_count": frame_count,
                     "timing_source": "input/timing.json"})
    cuts = sorted(c for c in facts["cuts"]
                  if min(wanted) < c <= max(wanted))
    dups = sorted(f for f in wanted if f in facts["dups"])
    try:
        clip = find_clip(run_dir)
    except ValueError as exc:
        return err_result("no_clip", str(exc),
                          metrics={"timing_source": "input/timing.json"})
    capture = cv2.VideoCapture(str(clip))
    if not capture.isOpened():
        return err_result("no_clip",
                          f"cannot open clip {clip.name}",
                          metrics={"timing_source": "input/timing.json"})
    try:
        grids = []
        unreadable = []
        for index in wanted:
            frame = _read_frame(capture, index)
            if frame is None:
                unreadable.append(index)
                continue
            grids.append((index, _scale_cell(_apply_crop(frame, crop))))
    finally:
        capture.release()
    if not grids:
        return err_result(
            "unreadable_frames",
            f"decoded 0 of {len(wanted)} requested frames",
            metrics={"frames_requested": wanted,
                     "out_of_range": bad,
                     "unreadable": unreadable,
                     "frame_count": frame_count,
                     "timing_source": "input/timing.json"})
    mode = layout or "grid"
    chunk = _STRIP_CELLS if mode == "sequence" else _GRID_CELLS
    cols = 1 if mode == "sequence" else _GRID_COLS
    files: list = []
    index: list = []
    cell_no = 0
    sheet_no = 0
    for at in range(0, len(grids), chunk):
        piece = grids[at:at + chunk]
        sheet = _sheet([grid for _, grid in piece], cols)
        rel = next_artifact(run_dir, turn, "view_frames", ".jpg",
                            start=sheet_no)
        out = run_path(run_dir, rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(out), sheet,
                           [int(cv2.IMWRITE_JPEG_QUALITY), 88]):
            return err_result("write_failed",
                              f"could not write {rel}",
                              metrics={"timing_source": "input/timing.json"})
        files.append(rel)
        for frame_index, _ in piece:
            index.append({"cell": cell_no, "sheet": rel,
                          "frame": frame_index,
                          "t_s": facts["timestamps"][frame_index]})
            cell_no += 1
        sheet_no += 1
    index_rel = next_artifact(run_dir, turn, "view_frames", ".json",
                              start=sheet_no)
    index_path = run_path(run_dir, index_rel)
    index_path.write_text(json.dumps(index, indent=2) + "\n",
                          encoding="utf-8")
    files.append(index_rel)
    append_produced(run_dir, files)
    notes = []
    if bad:
        notes.append(f"{len(bad)} out-of-range index/indices ignored: "
                     + ",".join(str(f) for f in bad[:12]))
    if cuts:
        notes.append("range spans confirmed cut(s) at frame(s) "
                     + ",".join(str(c) for c in cuts)
                     + " — do not fit across them")
    if dups:
        notes.append(f"{len(dups)} confirmed duplicate frame(s) in range "
                     "(excluded from fits per the measuring rules)")
    if unreadable:
        notes.append(f"{len(unreadable)} frame(s) failed to decode")
    summary = (f"{len(grids)} frames as {len(files) - 1} contact "
               f"sheet(s) (frames {wanted[0]}..{wanted[-1]}); "
               "timestamps are measured per-frame values")
    if notes:
        summary += "; " + "; ".join(notes)
    return ok_result(
        summary, files=files,
        metrics={"frames_requested": wanted,
                 "frames_served": [f for f, _ in grids],
                 "out_of_range": bad,
                 "unreadable": unreadable,
                 "cuts_spanned": cuts,
                 "duplicates_in_range": dups,
                 "index": index,
                 "index_artifact": index_rel,
                 "frame_count": frame_count,
                 "measured_fps": facts["fps"],
                 "timing_source": "input/timing.json"})

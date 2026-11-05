# generated from brief/07 · part 07 owns this file
"""``segment`` — SAM 3.1 by phrase over a frame range (part 07 §3).

Billing reality enforced in code: every call bills at least 50
frames. Ranges under 50 frames are refused unless the agent
explicitly confirms (``confirm_small_range``); the ledger is
debited ``max(50, frames)`` and the result carries both billed and
requested counts. The tool reports *what pixels*, never *what
object*.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import config as _config
from src.helpers import masks_io

from .common import append_produced, next_artifact, run_path
from .result import err_result, ok_result
from .timing import find_clip, load_timing

__all__ = [
    "segment",
    "cache_key",
]

#: Preview overlays are drawn for at most this many spread frames.
_MAX_PREVIEWS = 6


def cache_key(clip_stat, phrase: str, frame_start: int,
              frame_end: int) -> str:
    """Run-only cache identity: clip bytes, phrase, and range."""
    size, mtime = clip_stat
    return (f"{size}:{mtime}:{phrase.strip().lower()}"
            f":{int(frame_start)}:{int(frame_end)}")


def _read_range(clip, indices):
    """Decode exact frames; returns ``(grids, unreadable)``."""
    import cv2

    capture = cv2.VideoCapture(str(clip))
    if not capture.isOpened():
        raise ValueError(f"cannot open clip {Path(clip).name}")
    grids: list = []
    unreadable: list = []
    try:
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, float(index))
            ok, frame = capture.read()
            if not ok or frame is None:
                unreadable.append(index)
            else:
                grids.append(frame)
    finally:
        capture.release()
    return grids, unreadable


def _overlay(grid, masks_by_oid):
    """BGR preview: union tint plus one box per object."""
    import cv2
    import numpy as np

    canvas = np.asarray(grid).copy()
    colours = [(86, 180, 52), (60, 120, 235), (200, 160, 40),
               (190, 60, 190), (50, 200, 200), (120, 120, 220)]
    for position, (oid, mask) in enumerate(masks_by_oid.items()):
        colour = colours[position % len(colours)]
        hit = np.asarray(mask, dtype=bool)
        if hit.shape[:2] != canvas.shape[:2]:
            continue
        tint = canvas.copy()
        tint[hit] = colour
        canvas = cv2.addWeighted(canvas, 0.62, tint, 0.38, 0)
        ys, xs = np.nonzero(hit)
        if len(xs):
            cv2.rectangle(canvas, (int(xs.min()), int(ys.min())),
                          (int(xs.max()), int(ys.max())), colour, 1)
            cv2.putText(canvas, str(oid)[:12],
                        (int(xs.min()), max(0, int(ys.min()) - 3)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, colour, 1)
    return canvas


def _frame_stats(mask, frame: int, t_s):
    """Area/bbox/centroid row for one object on one frame."""
    import numpy as np

    hit = np.asarray(mask, dtype=bool)
    area = int(hit.sum())
    if not area:
        return {"frame": frame, "t_s": t_s, "area_px": 0,
                "bbox": None, "centroid": None}
    ys, xs = np.nonzero(hit)
    return {"frame": frame, "t_s": t_s, "area_px": area,
            "bbox": {"x0": int(xs.min()), "y0": int(ys.min()),
                     "x1": int(xs.max()), "y1": int(ys.max())},
            "centroid": {"x": float(xs.mean()),
                         "y": float(ys.mean())}}


def segment(run_dir, turn, phrase=None, frame_start=None,
            frame_end=None, confirm_small_range=False, *,
            sam_client=None, ledger=None, cache=None) -> dict:
    """Segment one phrase; bill ``max(50, frames)``; name every file."""
    if not isinstance(phrase, str) or not phrase.strip():
        return err_result("bad_phrase",
                          "phrase must be one non-empty noun phrase")
    for name, value in (("frame_start", frame_start),
                        ("frame_end", frame_end)):
        if isinstance(value, bool) or not isinstance(value, int):
            return err_result("bad_range",
                              f"{name} must be an int, got {value!r}")
    if frame_end < frame_start:
        return err_result("bad_range",
                          f"frame_end ({frame_end}) is before frame_start "
                          f"({frame_start})")
    frames = frame_end - frame_start + 1
    if frames < int(_config.SAM_MIN_BILLED_FRAMES) and not confirm_small_range:
        return err_result(
            "small_range_requires_confirm",
            f"range holds {frames} frames but every SAM call bills "
            f"at least {int(_config.SAM_MIN_BILLED_FRAMES)}; re-call with "
            "confirm_small_range=true to accept the charge, or widen "
            "the range",
            metrics={"frames_requested": frames,
                     "frames_billed": max(int(_config.SAM_MIN_BILLED_FRAMES), frames),
                     "minimum_billed_frames": int(_config.SAM_MIN_BILLED_FRAMES)})
    try:
        facts = load_timing(run_dir)
    except FileNotFoundError as exc:
        return err_result("missing_timing", f"missing_timing: {exc}")
    except ValueError as exc:
        return err_result("missing_timing", f"missing_timing: {exc}")
    frame_count = facts["frame_count"]
    if frame_start < 0 or frame_end >= frame_count:
        return err_result(
            "bad_range",
            f"range [{frame_start}, {frame_end}] leaves the clip "
            f"(frame_count={frame_count})",
            metrics={"frames_requested": frames,
                     "frame_count": frame_count})
    if sam_client is None:
        return err_result("sam_unavailable",
                          "no SAM backend is wired for this run",
                          metrics={"frames_requested": frames,
                                   "frames_billed": max(50, frames)})
    try:
        clip = find_clip(run_dir)
    except (ValueError, FileNotFoundError) as exc:
        return err_result("no_clip", str(exc))
    cuts = sorted(c for c in facts["cuts"]
                  if frame_start < c <= frame_end)
    store = cache if isinstance(cache, dict) else {}
    try:
        stat = (clip.stat().st_size, clip.stat().st_mtime_ns)
    except OSError:
        stat = (0, 0)
    key = cache_key(stat, phrase, frame_start, frame_end)
    if key in store:
        cached = dict(store[key])
        cached["metrics"] = dict(cached.get("metrics") or {})
        cached["metrics"]["cache_hit"] = True
        return cached
    indices = list(range(frame_start, frame_end + 1))
    try:
        grids, unreadable = _read_range(clip, indices)
    except ValueError as exc:
        return err_result("no_clip", str(exc))
    if len(grids) != len(indices):
        return err_result(
            "unreadable_frames",
            f"decoded {len(grids)} of {len(indices)} frames",
            metrics={"frames_requested": frames,
                     "unreadable": unreadable,
                     "frame_count": frame_count})
    try:
        masks = sam_client(phrase.strip(), indices, grids)
    except Exception as exc:  # noqa: BLE001 — a SAM death is a tool error
        return err_result("sam_failed",
                          f"{type(exc).__name__}: {exc}",
                          metrics={"phrase": phrase.strip(),
                                   "frames_requested": frames,
                                   "frames_billed": max(50, frames)})
    if not isinstance(masks, dict) or not masks:
        return err_result("sam_empty",
                          "SAM returned no objects for this phrase/range",
                          metrics={"phrase": phrase.strip(),
                                   "frames_requested": frames,
                                   "frames_billed": max(50, frames)})
    cleaned: dict = {}
    for oid, seq in masks.items():
        oid_key = oid if isinstance(oid, (int, str)) \
            and not isinstance(oid, bool) else str(oid)
        if not isinstance(seq, (list, tuple)) or len(seq) != len(indices):
            return err_result(
                "sam_malformed",
                f"SAM object {oid_key!r} holds "
                f"{len(seq) if isinstance(seq, (list, tuple)) else '?'} "
                f"masks for {len(indices)} frames",
                metrics={"phrase": phrase.strip(),
                         "frames_requested": frames,
                         "frames_billed": max(50, frames)})
        import numpy as np

        per_frame = {}
        for frame_index, grid in zip(indices, seq):
            arr = np.asarray(grid, dtype=bool)
            if arr.shape[:2] != np.asarray(grids[0]).shape[:2]:
                return err_result(
                    "sam_malformed",
                    f"SAM object {oid_key!r} frame {frame_index} has "
                    f"shape {arr.shape}, expected "
                    f"{np.asarray(grids[0]).shape[:2]}",
                    metrics={"phrase": phrase.strip(),
                             "frames_requested": frames,
                             "frames_billed": max(50, frames)})
            per_frame[int(frame_index)] = arr
        cleaned[oid_key] = per_frame
    billed = max(int(_config.SAM_MIN_BILLED_FRAMES), frames)
    if ledger is not None:
        try:
            ledger.debit_sam(int(turn), frames)
        except (TypeError, ValueError):
            pass
    masks_rel = next_artifact(run_dir, turn, "segment", ".npz")
    masks_io.save_masks(run_path(run_dir, masks_rel), cleaned)
    files = [masks_rel]
    step = max(1, len(indices) // _MAX_PREVIEWS)
    preview_positions = list(range(0, len(indices), step))[:_MAX_PREVIEWS]
    previews: list = []
    import cv2

    for position in preview_positions:
        frame_index = indices[position]
        per_oid = {oid: cleaned[oid][frame_index] for oid in cleaned}
        preview = _overlay(grids[position], per_oid)
        rel = next_artifact(run_dir, turn, "segment_preview", ".jpg")
        out = run_path(run_dir, rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), preview,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        files.append(rel)
        previews.append({"frame": frame_index, "artifact": rel})
    table = []
    for frame_index in indices:
        row = {"frame": frame_index,
               "t_s": facts["timestamps"][frame_index], "objects": {}}
        for oid in cleaned:
            row["objects"][str(oid)] = _frame_stats(
                cleaned[oid][frame_index], frame_index,
                facts["timestamps"][frame_index])
        table.append(row)
    stats_rel = next_artifact(run_dir, turn, "segment_stats", ".json")
    stats_path = run_path(run_dir, stats_rel)
    stats_path.write_text(json.dumps(table, indent=2) + "\n",
                          encoding="utf-8")
    files.append(stats_rel)
    append_produced(run_dir, files)
    note = ""
    if cuts:
        note = ("; range spans confirmed cut(s) at frame(s) "
                + ",".join(str(c) for c in cuts)
                + " — do not fit across them")
    if frames < int(_config.SAM_MIN_BILLED_FRAMES):
        note += (f"; small-range charge confirmed: billed {billed} "
                 f"for {frames} requested")
    summary = (f"segmented {phrase.strip()!r} over {frames} frames "
               f"(billed {billed}); {len(cleaned)} object(s): "
               + ", ".join(str(o) for o in cleaned) + note)
    result = ok_result(
        summary, files=files,
        metrics={"phrase": phrase.strip(),
                 "frames_requested": frames,
                 "frames_billed": billed,
                 "minimum_billed_frames": int(_config.SAM_MIN_BILLED_FRAMES),
                 "object_ids": [str(o) for o in cleaned],
                 "masks_artifact": masks_rel,
                 "previews": previews,
                 "stats_artifact": stats_rel,
                 "cuts_spanned": cuts,
                 "frame_count": frame_count,
                 "cache_hit": False,
                 "timing_source": "input/timing.json"})
    store[key] = result
    return result

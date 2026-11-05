# generated from brief/07 · part 07 owns this file
"""``motion_overview`` — the trajectories of what SAM found (part 07 §21).

The Apollo clip has two jumps of the same figure; runs measured one
and never listed the other — or measured the second and never the
first — after looking at contact sheets by eye. Even a run that had
segmented the figure over the whole clip never saw the jumps in its
own masks. The agent had no tool that showed it the trajectories.
R-M4 (part 08) asks for every repetition; the agent could not see
them.

This tool turns a :mod:`src.tools.segment` result into trajectories
the agent can look at. It is local computation: no API call, no
price, and it never says "jump" — a candidate is a pixel fact, not
a decision.

Per object and frame (from part 09 :func:`largest_component` and
:func:`mask_stats`): bottom, top and centroid y, centroid x, height
and area, on measured timestamps. The support level at a frame is
the lowest bottom position (largest y) within ±1 s; rise = support
− bottom, in pixels. A candidate is a maximal run of at least 4
frames where the rise is at least ``max(3 px, 4 % of the object's
median mask height)``. For each candidate the tool reports its id
(F1, F2, … in frame order), first and last frame, start and end
time, airtime, peak rise in pixels and in median mask heights, the
curvature of a parabola fitted to the centroid y over the run (its
sign and R²), and mask flags inside the run ±3 frames: area jumps
(a frame whose area differs by more than 25 % from the median of
its ±3 neighbours), frame-edge contact, and splits (part 09
:func:`track_quality`).

Outputs, all named in the result (§1): a JSON table of the
per-frame values and the candidates; a chart image (one row per
object; time on x; the bottom and the centroid drawn with up as
up; the support level dashed; the area as a thin line on its own
scale; each candidate shaded and labelled with its id and
airtime); one strip image per candidate (6 frames in time order:
takeoff − 3, takeoff, the frame of peak rise, the frame halfway
between peak and landing, landing, landing + 3 — with the object's
outline drawn, each cell labelled with its frame number and time;
``metrics.strip_frames[<id>]`` lists each strip's frames). Ids are
unique over the whole result (F1, F2, … in order of first frame
over all objects). The images ride to Spark as images the same way
``view_frames`` sheets do (``.png`` suffixes, named in ``files``).
The chart draws height in the picture: a smaller image y is drawn
higher, so a flight is a hump above the dashed support line.

Part 07 §24: a raw above-threshold run is cut to its own takeoff
and landing, found from the bottom's motion inside the run. The
bottom's vertical speed per frame is the central difference on
measured timestamps over 3 frames (down positive). Landing is the
first frame after the peak whose downward speed falls below 25 %
of the largest downward speed after the peak and stays below for
3 frames; takeoff is the last quiet frame before upward motion
starts (upward speed below 25 % of the largest upward speed
before the peak). Frames outside ``[takeoff, landing]`` leave the
candidate; the remainder of the run is re-examined with support
recomputed from frames after the landing, so a later flight rises
from the new level. Airtime, peak rise, curvature, R² and the
flags are computed on the cut range; the table records the uncut
range as ``raw_frames`` beside the cut one.
"""

from __future__ import annotations

import json
import math
import statistics

from .common import (
    append_produced,
    next_artifact,
    reject_path,
    run_path,
)
from .result import err_result, ok_result
from .timing import find_clip, load_timing

__all__ = [
    "motion_overview",
    "RISE_MIN_PX",
    "RISE_MIN_FRAC",
    "MIN_FLIGHT_FRAMES",
    "AREA_JUMP_FRAC",
    "SUPPORT_HALF_WINDOW_S",
]

#: A candidate frame rises at least this many pixels …
RISE_MIN_PX = 3.0
#: … or this fraction of the object's median mask height, whichever
#: is larger (§21: ``max(3 px, 4 % of the median mask height)``).
RISE_MIN_FRAC = 0.04
#: A candidate is a maximal run of at least this many frames.
MIN_FLIGHT_FRAMES = 4
#: An area jump: the frame's area differs by more than this fraction
#: from the median of its ±3 neighbours.
AREA_JUMP_FRAC = 0.25
#: Support window half-width in seconds (§21: ±1 s).
SUPPORT_HALF_WINDOW_S = 1.0


def _object_key(oid) -> str:
    """Display key of a mask object id (int-safe)."""
    if isinstance(oid, bool):
        return str(oid)
    return str(oid)


def _match_object(masks: dict, wanted) -> str | None:
    """Stored key of ``wanted`` (int/str tolerant), or ``None``."""
    for key in masks:
        if key == wanted or _object_key(key) == _object_key(wanted):
            return key
    return None


def _per_frame_values(per_frame: dict, stamps: list) -> tuple:
    """``(rows, skipped)`` measured rows for one object (part 09)."""
    from src.helpers import tracks

    rows: list = []
    skipped: list = []
    for frame in sorted(per_frame):
        raw = per_frame[frame]
        try:
            import numpy as np

            arr = np.asarray(raw, dtype=bool)
        except (TypeError, ValueError):
            skipped.append(int(frame))
            continue
        if not arr.any():
            skipped.append(int(frame))
            continue
        try:
            big = tracks.largest_component(arr)
            stats = tracks.mask_stats(big)
        except ValueError:
            skipped.append(int(frame))
            continue
        try:
            moment = float(stamps[int(frame)])
        except (IndexError, TypeError, ValueError):
            skipped.append(int(frame))
            continue
        rows.append({
            "frame": int(frame),
            "t_s": moment,
            "bottom_y": int(stats["bottom"]),
            "top_y": int(stats["top"]),
            "centroid_x": float(stats["centroid"]["x"]),
            "centroid_y": float(stats["centroid"]["y"]),
            "height_px": int(stats["height"]),
            "area_px": int(stats["area"]),
        })
    return rows, skipped


def _support_and_rise(rows: list) -> None:
    """Fill ``support_y``/``rise_px`` on each row, in place (±1 s)."""
    for position, row in enumerate(rows):
        moment = float(row["t_s"])
        level = int(row["bottom_y"])
        for other in rows:
            if abs(float(other["t_s"]) - moment) \
                    <= SUPPORT_HALF_WINDOW_S:
                if int(other["bottom_y"]) > level:
                    level = int(other["bottom_y"])
        row["support_y"] = level
        row["rise_px"] = float(level - int(row["bottom_y"]))


def _find_runs(rows: list, threshold: float) -> list:
    """Maximal runs of ≥4 consecutive frames above ``threshold``."""
    runs: list = []
    current: list = []
    for row in rows:
        if float(row["rise_px"]) >= threshold:
            if current and int(row["frame"]) != current[-1] + 1:
                runs.append(current)
                current = []
            current.append(int(row["frame"]))
        else:
            if current:
                runs.append(current)
                current = []
    if current:
        runs.append(current)
    return [run for run in runs if len(run) >= MIN_FLIGHT_FRAMES]


#: Fraction of the largest one-sided speed that still counts as
#: quiet when cutting a raw run to its takeoff/landing (§24).
SPEED_QUIET_FRAC = 0.25

#: Frames the stillness after a landing must hold (§24).
STILL_HOLD_FRAMES = 3


def _bottom_speeds(rows: list) -> dict:
    """Vertical speed of the mask bottom per frame, px/s (§24).

    Central difference on measured timestamps over 3 frames
    (``(y(f+1) − y(f−1)) / (t(f+1) − t(f−1))``), one-sided at the
    edges or beside gaps. Down (larger image y) is positive, so an
    upward speed is the negation.
    """
    by_frame = {int(row["frame"]): row for row in rows}
    speeds: dict = {}
    for frame in sorted(by_frame):
        row = by_frame[frame]
        moment = float(row["t_s"])
        prev = by_frame.get(int(frame) - 1)
        nxt = by_frame.get(int(frame) + 1)
        if prev is not None and nxt is not None:
            span = float(nxt["t_s"]) - float(prev["t_s"])
            if span != 0.0:
                speeds[int(frame)] = (
                    float(nxt["bottom_y"]) - float(prev["bottom_y"])
                ) / span
            else:
                speeds[int(frame)] = 0.0
        elif nxt is not None and float(nxt["t_s"]) != moment:
            speeds[int(frame)] = (
                float(nxt["bottom_y"]) - float(row["bottom_y"])
            ) / (float(nxt["t_s"]) - moment)
        elif prev is not None and moment != float(prev["t_s"]):
            speeds[int(frame)] = (
                float(row["bottom_y"]) - float(prev["bottom_y"])
            ) / (moment - float(prev["t_s"]))
        else:
            speeds[int(frame)] = 0.0
    return speeds


def _cut_to_flight(rows: list, run: list,
                   rise_of: dict | None = None) -> tuple:
    """``(takeoff, landing)`` cut of one raw above-threshold run (§24).

    ``rise_of`` maps frame to rise in pixels (default: the rows'
    own ``rise_px``); the peak is the first frame of maximal rise.
    Takeoff is the last quiet frame before upward motion starts
    (upward speed below ``SPEED_QUIET_FRAC`` of the largest upward
    speed before the peak); landing is the first frame after the
    frame of largest downward speed whose downward speed stays
    below that fraction for ``STILL_HOLD_FRAMES`` frames. Either
    side falls back to the raw run bound, and a degenerate cut
    falls back to the whole run.
    """
    by_frame = {int(row["frame"]): row for row in rows}
    run = [int(f) for f in run]
    if rise_of is None:
        rise_of = {int(row["frame"]): float(row["rise_px"])
                   for row in rows}
    peak = max(run, key=lambda f: float(rise_of.get(int(f), 0.0)))
    speeds = _bottom_speeds(rows)

    def _up(frame: int) -> float:
        return max(0.0, -float(speeds.get(int(frame), 0.0)))

    def _down(frame: int) -> float:
        return max(0.0, float(speeds.get(int(frame), 0.0)))

    before = [f for f in run if f < peak]
    ups = [_up(f) for f in before]
    largest_up = max(ups) if ups else 0.0
    if largest_up <= 0.0 or not before:
        takeoff = run[0]
    else:
        anchor = before[next(
            index for index, value in enumerate(ups)
            if value >= largest_up)]
        quiet = [f for f in sorted(by_frame)
                 if f < anchor and _up(f) < SPEED_QUIET_FRAC * largest_up]
        takeoff = max(quiet) if quiet else run[0]

    after = [f for f in run if f > peak]
    downs = [_down(f) for f in after]
    largest_down = max(downs) if downs else 0.0
    landing: int | None = None
    if largest_down > 0.0 and after:
        anchor = after[next(
            index for index, value in enumerate(downs)
            if value >= largest_down)]
        limit = SPEED_QUIET_FRAC * largest_down
        frame = int(anchor) + 1
        last_row = max(by_frame)
        while frame <= last_row:
            window = [frame + offset
                      for offset in range(STILL_HOLD_FRAMES)]
            if all(f in by_frame and _down(f) < limit for f in window):
                landing = frame
                break
            frame += 1
    if landing is None:
        landing = run[-1]

    takeoff = max(run[0], min(int(takeoff), peak))
    landing = min(run[-1], max(int(landing), peak))
    if takeoff > landing:
        takeoff, landing = run[0], run[-1]
    return takeoff, landing


def _fit_parabola(xs: list, ys: list) -> tuple:
    """``(curvature, sign, r_squared)`` of ``y = a t² + b t + c``.

    Curvature is ``2a`` (pixels/s² in pixel-y, where down is
    positive, so a positive curvature accelerates downward, as
    gravity does). ``R²`` is 1 − SSres/SStot (1.0 on a perfectly
    flat track, 0.0 when the fit explains nothing of a spread).
    """
    import numpy as np

    t = np.asarray([float(v) for v in xs], dtype=float)
    y = np.asarray([float(v) for v in ys], dtype=float)
    span = float(t.max() - t.min()) if len(t) else 0.0
    if len(t) < 3 or span <= 0.0:
        return 0.0, "zero", 0.0
    centre = float(t.mean())
    tc = t - centre
    try:
        a, _b, _c = np.polyfit(tc, y, 2)
    except (TypeError, ValueError):
        return 0.0, "zero", 0.0
    fitted = a * tc * tc + _b * tc + _c
    residual = float(np.sum((y - fitted) ** 2))
    spread = float(np.sum((y - float(y.mean())) ** 2))
    if spread <= 0.0:
        r_squared = 1.0 if residual <= 0.0 else 0.0
    else:
        r_squared = max(0.0, min(1.0, 1.0 - residual / spread))
    curvature = float(2.0 * a)
    if curvature > 0.0:
        sign = "positive"
    elif curvature < 0.0:
        sign = "negative"
    else:
        sign = "zero"
    return curvature, sign, float(r_squared)


def _area_jumps(rows: list) -> list:
    """Frames whose area differs >25 % from the median of ±3 neighbours."""
    by_frame = {int(row["frame"]): float(row["area_px"]) for row in rows}
    flagged: list = []
    for row in rows:
        frame = int(row["frame"])
        neighbours = [by_frame[other] for other in range(
            frame - 3, frame + 4)
            if other != frame and other in by_frame]
        if not neighbours:
            continue
        median = float(statistics.median(neighbours))
        if median <= 0.0:
            continue
        if abs(float(row["area_px"]) - median) / median > AREA_JUMP_FRAC:
            flagged.append(frame)
    return sorted(flagged)


def _edge_contact(per_frame: dict, frames: list) -> list:
    """Frames of ``frames`` whose mask touches the frame border."""
    import numpy as np

    flagged: list = []
    for frame in frames:
        mask = per_frame.get(frame)
        if mask is None:
            continue
        try:
            arr = np.asarray(mask, dtype=bool)
        except (TypeError, ValueError):
            continue
        if not arr.any() or arr.ndim != 2:
            continue
        if (bool(arr[0, :].any()) or bool(arr[-1, :].any())
                or bool(arr[:, 0].any()) or bool(arr[:, -1].any())):
            flagged.append(int(frame))
    return sorted(flagged)


def _split_frames(oid, per_frame: dict, rows: list,
                  frames: list) -> list:
    """Frames of ``frames`` flagged split by part 09 ``track_quality``."""
    from src.helpers import tracks

    wanted = set(int(f) for f in frames)
    try:
        point_rows = tracks.track_point(
            {int(f): per_frame[f] for f in sorted(per_frame)
             if int(f) in {int(r["frame"]) for r in rows}},
            "centroid")
        quality = tracks.track_quality(point_rows, {oid: per_frame})
    except ValueError:
        return []
    splits = quality.get("splits") if isinstance(quality, dict) else []
    try:
        return sorted(int(f) for f in (splits or [])
                      if int(f) in wanted)
    except (TypeError, ValueError):
        return []


def _describe_candidate(rows: list, run: list,
                        median_height: float,
                        raw_frames: list | None = None) -> dict:
    """Candidate record for one cut ``[takeoff, landing]`` range (§24).

    Airtime, peak rise, curvature, R² and the flags are computed on
    the cut range; ``raw_frames`` is the uncut above-threshold run
    the cut came from.
    """
    by_frame = {int(row["frame"]): row for row in rows}
    first, last = int(run[0]), int(run[-1])
    peak_frame = max(run, key=lambda f: float(by_frame[int(f)]["rise_px"]))
    peak_rise = float(by_frame[int(peak_frame)]["rise_px"])
    xs = [float(by_frame[int(f)]["t_s"]) for f in run]
    ys = [float(by_frame[int(f)]["centroid_y"]) for f in run]
    curvature, sign, r_squared = _fit_parabola(xs, ys)
    airtime = float(xs[-1] - xs[0]) if len(xs) > 1 else 0.0
    return {
        "frame_start": first,
        "frame_end": last,
        "t_start_s": float(xs[0]),
        "t_end_s": float(xs[-1]),
        "airtime_s": airtime,
        "peak_frame": int(peak_frame),
        "peak_rise_px": peak_rise,
        "peak_rise_heights": (peak_rise / median_height
                              if median_height > 0 else 0.0),
        "centroid_curvature_px_s2": curvature,
        "curvature_sign": sign,
        "centroid_r_squared": r_squared,
        "frames": [int(f) for f in run],
        "raw_frames": [int(f) for f in
                       (raw_frames if raw_frames is not None else run)],
    }


def _draw_chart(path, objects: list) -> None:
    """One row per object: bottom/centroid (up as up), support, area."""
    import cv2
    import numpy as np

    width = 960
    left, right, top, bottom_pad = 64, 20, 30, 26
    row_h = 230
    gap = 44
    plot_w = width - left - right
    height = top + row_h * max(1, len(objects)) \
        + gap * max(0, len(objects) - 1) + bottom_pad
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    for position, entry in enumerate(objects):
        rows = entry["rows"]
        origin = top + position * (row_h + gap)
        label = f"object {entry['key']}"
        cv2.putText(canvas, label, (8, origin + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1,
                    cv2.LINE_AA)
        if not rows:
            cv2.putText(canvas, "no measured frames",
                        (left, origin + row_h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (120, 120, 120), 1, cv2.LINE_AA)
            continue
        times = [float(r["t_s"]) for r in rows]
        t_min, t_max = min(times), max(times)
        if t_max <= t_min:
            t_min -= 0.5
            t_max += 0.5

        def _x(moment: float) -> int:
            return int(left + (float(moment) - t_min)
                       / (t_max - t_min) * plot_w)

        vals = ([float(r["bottom_y"]) for r in rows]
                + [float(r["centroid_y"]) for r in rows]
                + [float(r["support_y"]) for r in rows])
        v_min, v_max = min(vals), max(vals)
        if v_max <= v_min:
            v_min -= 1.0
            v_max += 1.0
        plot_h = row_h - 52

        def _y(value: float) -> int:
            # Height in the picture: a smaller image y is drawn
            # higher (smaller row), so a flight rising off its
            # support reads as a hump above the dashed support
            # line, never a dip (§21.1).
            frac = (float(value) - v_min) / (v_max - v_min)
            return int(origin + 26 + frac * plot_h)

        for cand in entry["candidates"]:
            x0 = _x(cand["t_start_s"])
            x1 = _x(cand["t_end_s"])
            shade = canvas.copy()
            cv2.rectangle(shade, (x0, origin + 20),
                          (max(x0 + 1, x1), origin + 26 + plot_h),
                          (120, 230, 255), -1)
            canvas = cv2.addWeighted(canvas, 0.72, shade, 0.28, 0)
            cv2.putText(canvas,
                        f"{cand['id']} {cand['airtime_s']:.2f}s",
                        (x0 + 3, origin + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0),
                        1, cv2.LINE_AA)
        support = [(_x(float(r["t_s"])), _y(float(r["support_y"])))
                   for r in rows]
        for index in range(len(support) - 1):
            if (index // 3) % 2 == 0:
                cv2.line(canvas, support[index], support[index + 1],
                         (150, 150, 150), 1, cv2.LINE_AA)
        bottom = [(_x(float(r["t_s"])), _y(float(r["bottom_y"])))
                  for r in rows]
        centroid = [(_x(float(r["t_s"])), _y(float(r["centroid_y"])))
                    for r in rows]
        for index in range(len(bottom) - 1):
            cv2.line(canvas, bottom[index], bottom[index + 1],
                     (200, 80, 40), 2, cv2.LINE_AA)
            cv2.line(canvas, centroid[index], centroid[index + 1],
                     (50, 170, 50), 2, cv2.LINE_AA)
        areas = [float(r["area_px"]) for r in rows]
        a_min, a_max = min(areas), max(areas)
        band_top = origin + 26 + plot_h
        band_h = 22
        for index in range(len(rows) - 1):
            frac0 = ((areas[index] - a_min) / (a_max - a_min)
                     if a_max > a_min else 0.5)
            frac1 = ((areas[index + 1] - a_min) / (a_max - a_min)
                     if a_max > a_min else 0.5)
            p0 = (_x(times[index]),
                  int(band_top + band_h - frac0 * band_h))
            p1 = (_x(times[index + 1]),
                  int(band_top + band_h - frac1 * band_h))
            cv2.line(canvas, p0, p1, (60, 170, 200), 1, cv2.LINE_AA)
        cv2.putText(canvas, f"higher in frame ({v_min:.0f}px)",
                    (4, _y(v_min)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.35, (90, 90, 90), 1, cv2.LINE_AA)
        cv2.putText(canvas, f"lower in frame ({v_max:.0f}px)",
                    (4, _y(v_max) + 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.35, (90, 90, 90), 1, cv2.LINE_AA)
        cv2.putText(canvas, "bottom", (left, origin + row_h - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 80, 40),
                    1, cv2.LINE_AA)
        cv2.putText(canvas, "centroid", (left + 80, origin + row_h - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (50, 170, 50),
                    1, cv2.LINE_AA)
        cv2.putText(canvas, "area", (left + 180, origin + row_h - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 170, 200),
                    1, cv2.LINE_AA)
        cv2.rectangle(canvas, (left, origin + 20),
                      (left + plot_w, origin + 26 + plot_h + band_h),
                      (200, 200, 200), 1)
    cv2.imwrite(str(path), canvas)


def _read_frames(clip, indices: list):
    """Decode exact frames; ``(grids, unreadable)`` like segment."""
    import cv2

    capture = cv2.VideoCapture(str(clip))
    if not capture.isOpened():
        raise ValueError(f"cannot open clip {clip.name}")
    grids: list = []
    unreadable: list = []
    try:
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, float(index))
            ok, frame = capture.read()
            if not ok or frame is None:
                unreadable.append(int(index))
            else:
                grids.append(frame)
    finally:
        capture.release()
    return grids, unreadable


def _draw_strip(path, clip, candidate: dict, per_frame: dict,
                stamps: list, frame_count: int) -> list:
    """Six labelled cells with the object's outline drawn.

    Cells go in time order (§21.1): takeoff − 3, takeoff, the
    frame of peak rise, the frame halfway between peak and
    landing, landing, landing + 3. Returns the drawn frame list.
    """
    import cv2
    import numpy as np

    first, last = int(candidate["frame_start"]), int(candidate["frame_end"])
    peak = int(candidate["peak_frame"])
    halfway = (peak + last) // 2
    wanted = [first - 3, first, peak, halfway, last, last + 3]
    wanted = [min(max(0, f), frame_count - 1) for f in wanted]
    grids, _unreadable = _read_frames(clip, wanted)
    cell_w = 300
    bar_h = 30
    cells = []
    for frame, grid in zip(wanted, grids):
        scale = cell_w / max(1, grid.shape[1])
        small = cv2.resize(grid, (cell_w, max(1, int(
            round(grid.shape[0] * scale)))),
            interpolation=cv2.INTER_AREA)
        mask = per_frame.get(int(frame))
        if mask is not None:
            try:
                blob = (np.asarray(mask, dtype=bool).astype("uint8")
                        * 255)
                if blob.shape[:2] == small.shape[:2] or True:
                    full = cv2.resize(
                        blob, (small.shape[1], small.shape[0]),
                        interpolation=cv2.INTER_NEAREST)
                    contours, _ = cv2.findContours(
                        full, cv2.RETR_EXTERNAL,
                        cv2.CHAIN_APPROX_SIMPLE)
                    cv2.drawContours(small, contours, -1,
                                     (60, 220, 60), 2)
            except (TypeError, ValueError):
                pass
        bar = np.zeros((bar_h, cell_w, 3), dtype=np.uint8)
        try:
            moment = float(stamps[int(frame)])
            caption = f"f{frame} t={moment:.3f}s"
        except (IndexError, TypeError, ValueError):
            caption = f"f{frame}"
        cv2.putText(bar, caption, (6, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (255, 255, 255), 1, cv2.LINE_AA)
        cells.append(np.vstack([bar, small]))
    cell_h = max(cell.shape[0] for cell in cells)
    divider = np.full((cell_h, 6, 3), 40, dtype=np.uint8)
    row = cells[0]
    if row.shape[0] < cell_h:
        row = np.vstack([row, np.zeros(
            (cell_h - row.shape[0], cell_w, 3), dtype=np.uint8)])
    for cell in cells[1:]:
        if cell.shape[0] < cell_h:
            cell = np.vstack([cell, np.zeros(
                (cell_h - cell.shape[0], cell_w, 3), dtype=np.uint8)])
        row = np.hstack([row, divider, cell])
    cv2.imwrite(str(path), row)
    return [int(f) for f in wanted]


def motion_overview(run_dir, turn, masks_artifact=None,
                    object_ids=None, **extra) -> dict:
    """Trajectories of what SAM found: rise, candidates, chart, strips.

    ``masks_artifact`` is a run-relative ``artifacts/…npz`` path from
    :func:`src.tools.segment.segment`; ``object_ids`` is an optional
    list of object ids (default: every object in the file). Local
    computation only: no API call, no ledger price.
    """
    if extra:
        return err_result(
            "bad_arguments",
            "unexpected argument(s) "
            f"{', '.join(sorted(extra))}; expected masks_artifact, "
            "object_ids",
            metrics={"masks_artifact": masks_artifact})
    if not isinstance(masks_artifact, str) or not masks_artifact:
        return err_result(
            "bad_masks",
            "masks_artifact must be the run-relative artifacts path "
            f"of a segment masks file, got {masks_artifact!r}",
            metrics={"masks_artifact": masks_artifact})
    problem = reject_path(masks_artifact)
    if problem:
        return err_result("path_rejected", problem,
                          metrics={"masks_artifact": masks_artifact})
    try:
        facts = load_timing(run_dir)
    except (FileNotFoundError, ValueError) as exc:
        return err_result("missing_timing", f"missing_timing: {exc}",
                          metrics={"masks_artifact": masks_artifact})
    stamps = facts["timestamps"]
    frame_count = int(facts["frame_count"])
    try:
        from src.helpers import masks_io

        masks = masks_io.load_masks(run_path(run_dir, masks_artifact))
    except OSError as exc:
        return err_result("bad_masks",
                          f"cannot read {masks_artifact}: {exc}",
                          metrics={"masks_artifact": masks_artifact})
    except ValueError as exc:
        return err_result("bad_masks", str(exc),
                          metrics={"masks_artifact": masks_artifact})
    if not isinstance(masks, dict) or not masks:
        return err_result("bad_masks",
                          f"{masks_artifact} holds no objects",
                          metrics={"masks_artifact": masks_artifact})
    if object_ids is None:
        wanted = sorted(masks, key=_object_key)
    else:
        if (not isinstance(object_ids, (list, tuple))
                or not object_ids):
            return err_result(
                "bad_object",
                "object_ids must be a non-empty list of object ids "
                f"or null for every object, got {object_ids!r}",
                metrics={"masks_artifact": masks_artifact})
        wanted = []
        for oid in object_ids:
            if isinstance(oid, bool) or not isinstance(oid, (int, str)):
                return err_result(
                    "bad_object",
                    f"object id {oid!r} must be an int or a string",
                    metrics={"masks_artifact": masks_artifact})
            key = _match_object(masks, oid)
            if key is None:
                return err_result(
                    "unknown_object",
                    f"object {oid!r} is not in {masks_artifact}; "
                    "available: "
                    + ", ".join(sorted(_object_key(k) for k in masks)),
                    metrics={"masks_artifact": masks_artifact})
            if key not in wanted:
                wanted.append(key)
    try:
        clip = find_clip(run_dir)
    except (FileNotFoundError, ValueError) as exc:
        return err_result("no_clip", str(exc),
                          metrics={"masks_artifact": masks_artifact})
    objects: list = []
    for key in wanted:
        per_frame = masks[key]
        if not isinstance(per_frame, dict):
            return err_result(
                "bad_masks",
                f"object {_object_key(key)!r} holds no frame map",
                metrics={"masks_artifact": masks_artifact})
        rows, skipped = _per_frame_values(per_frame, stamps)
        median_height = (float(statistics.median(
            [float(r["height_px"]) for r in rows])) if rows else 0.0)
        threshold = max(RISE_MIN_PX, RISE_MIN_FRAC * median_height)
        candidates: list = []
        if rows:
            _support_and_rise(rows)
            runs = _find_runs(rows, threshold)
            area_flags = _area_jumps(rows)
            area_set = set(area_flags)
            for run in runs:
                # Cut the raw run to its own takeoff/landing (§24);
                # the remainder is re-examined with support recomputed
                # from frames after the landing, so a later flight
                # rises from the new level.
                queue: list = [(list(run), None)]
                while queue:
                    current, current_rise = queue.pop(0)
                    if current_rise is None:
                        current_rise = {
                            int(row["frame"]): float(row["rise_px"])
                            for row in rows}
                    takeoff, landing = _cut_to_flight(
                        rows, current, current_rise)
                    cut = list(range(takeoff, landing + 1))
                    record = _describe_candidate(
                        rows, cut, median_height,
                        raw_frames=current)
                    window = set()
                    for frame in record["frames"]:
                        for other in range(int(frame) - 3,
                                          int(frame) + 4):
                            window.add(other)
                    window &= {int(r["frame"]) for r in rows}
                    record["flags"] = {
                        "area_jumps": sorted(area_set & window),
                        "edge_contact": _edge_contact(
                            per_frame, sorted(window)),
                        "splits": _split_frames(key, per_frame, rows,
                                                sorted(window)),
                    }
                    candidates.append(record)
                    rest = [dict(row) for row in rows
                            if landing < int(row["frame"])
                            <= int(current[-1])]
                    if len(rest) >= MIN_FLIGHT_FRAMES:
                        _support_and_rise(rest)
                        rest_rise = {
                            int(row["frame"]): float(row["rise_px"])
                            for row in rest}
                        for sub in _find_runs(rest, threshold):
                            queue.append((list(sub), rest_rise))
        objects.append({
            "key": _object_key(key),
            "store_key": key,
            "rows": rows,
            "skipped_empty_frames": sorted(skipped),
            "median_height_px": median_height,
            "rise_threshold_px": threshold,
            "candidates": candidates,
        })
    # Ids are unique over the whole result (§21.1): F1, F2, … in
    # order of first frame over all objects, ties by object id.
    ordered: list = sorted(
        ((int(c["frame_start"]), entry["key"], entry, c)
         for entry in objects for c in entry["candidates"]),
        key=lambda item: (item[0], item[1]))
    for number, (_first, _key, _entry, record) in enumerate(
            ordered, start=1):
        record["id"] = f"F{number}"
    for entry in objects:
        entry["candidates"].sort(key=lambda c: int(c["frame_start"]))
    table_rel = next_artifact(run_dir, turn, "motion_overview", ".json")
    table = {
        "masks_artifact": masks_artifact,
        "timing_source": "input/timing.json",
        "objects": [
            {
                "object_id": entry["key"],
                "median_height_px": entry["median_height_px"],
                "rise_threshold_px": entry["rise_threshold_px"],
                "skipped_empty_frames": entry["skipped_empty_frames"],
                "frames": entry["rows"],
                "candidates": entry["candidates"],
            }
            for entry in objects
        ],
    }
    try:
        table_path = run_path(run_dir, table_rel)
        table_path.parent.mkdir(parents=True, exist_ok=True)
        table_path.write_text(json.dumps(table, indent=2) + "\n",
                              encoding="utf-8")
    except OSError as exc:
        return err_result("write_failed",
                          f"could not write {table_rel}: {exc}",
                          metrics={"masks_artifact": masks_artifact})
    chart_rel = next_artifact(run_dir, turn, "motion_overview_chart",
                              ".png")
    try:
        _draw_chart(run_path(run_dir, chart_rel), objects)
    except ValueError as exc:
        return err_result("write_failed",
                          f"could not draw {chart_rel}: {exc}",
                          metrics={"masks_artifact": masks_artifact,
                                   "table_artifact": table_rel})
    files = [table_rel, chart_rel]
    strips: dict = {}
    strip_frames: dict = {}
    for entry in objects:
        for candidate in entry["candidates"]:
            strip_rel = next_artifact(
                run_dir, turn, "motion_overview_strip", ".png")
            try:
                drawn = _draw_strip(
                    run_path(run_dir, strip_rel), clip,
                    candidate, masks[entry["store_key"]],
                    stamps, frame_count)
            except ValueError as exc:
                return err_result(
                    "unreadable_frames",
                    f"strip for {candidate['id']} failed: {exc}",
                    metrics={"masks_artifact": masks_artifact,
                             "table_artifact": table_rel,
                             "chart_artifact": chart_rel})
            files.append(strip_rel)
            strips[candidate["id"]] = strip_rel
            strip_frames[candidate["id"]] = [int(f) for f in drawn]
    append_produced(run_dir, files)
    total = sum(len(entry["candidates"]) for entry in objects)
    bits = []
    for entry in objects:
        if entry["candidates"]:
            spans = ", ".join(
                f"{c['id']} {c['frame_start']}..{c['frame_end']} "
                f"({c['airtime_s']:.2f}s)" for c in entry["candidates"])
            bits.append(f"object {entry['key']}: "
                        f"{len(entry['candidates'])} candidate(s) "
                        f"{spans}")
        else:
            bits.append(f"object {entry['key']}: no flight candidate")
    summary = (f"motion overview of {masks_artifact}: "
               f"{len(objects)} object(s), {total} flight "
               f"candidate(s); " + "; ".join(bits)
               + ". Candidates are pixel facts, not decisions: "
               "measure each one before claiming a free flight")
    flat = [
        {"object_id": entry["key"],
         **{k: c[k] for k in c if k != "frames"},
         "frames": c["frames"]}
        for entry in objects for c in entry["candidates"]
    ]
    flat.sort(key=lambda c: int(c["id"][1:]))
    return ok_result(
        summary, files=files,
        metrics={"masks_artifact": masks_artifact,
                 "table_artifact": table_rel,
                 "chart_artifact": chart_rel,
                 "strip_artifacts": strips,
                 "strip_frames": strip_frames,
                 "object_ids": [entry["key"] for entry in objects],
                 "candidate_counts":
                     {entry["key"]: len(entry["candidates"])
                      for entry in objects},
                 "candidates": flat,
                 "timing_source": "input/timing.json"})

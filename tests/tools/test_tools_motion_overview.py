# generated from brief/07 · part 07 owns this file
"""``motion_overview``: trajectories of what SAM found (part 07 §21)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from src.helpers import masks_io
from src.tools import motion_overview, schemas

#: The planted fixture flights (frames) in fake-1 object "1".
_FAKE1_FLIGHTS = ((101, 113), (136, 150))


def _planted_masks(frames=60, width=160, height=120, hops=(),
                   wide_frames=(), wide_extra=40):
    """Rectangle walking level, then parabolic hops at ``hops``.

    ``hops`` holds ``(takeoff, landing, peak_px)`` triples; the
    rectangle (40 wide, 60 tall) stands with its bottom at y=100 and
    rises by ``4*peak*u*(1-u)`` inside each hop. ``wide_frames``
    widens the rectangle there (a planted area jump, no rise).
    """
    masks = {}
    for frame in range(frames):
        rise = 0.0
        for takeoff, landing, peak in hops:
            if takeoff <= frame <= landing:
                u = ((frame - takeoff) / (landing - takeoff)
                     if landing > takeoff else 0.0)
                rise = max(rise, 4.0 * peak * u * (1.0 - u))
        bottom = int(round(100 - rise))
        extra = wide_extra if frame in set(wide_frames) else 0
        grid = np.zeros((height, width), dtype=bool)
        x = (5 + 2 * frame) % 110
        grid[bottom - 60:bottom, x:x + 40 + extra] = True
        masks[frame] = grid
    return masks


def _overview_run(make_run, masks, turn=7, object_ids=None,
                  frames=60):
    """A run dir whose clip matches ``masks``, with an overview call."""
    run = make_run(frames=frames)
    rel = f"artifacts/t{turn}_segment_0.npz"
    masks_io.save_masks(run / rel, {"sq": masks})
    result = motion_overview.motion_overview(
        str(run), turn, masks_artifact=rel, object_ids=object_ids)
    return run, rel, result


def test_two_hops_found_within_one_frame(make_run):
    hops = ((20, 28, 20), (40, 48, 20))
    run, _rel, result = _overview_run(
        make_run, _planted_masks(hops=hops))
    assert result["ok"], result
    candidates = result["metrics"]["candidates"]
    assert len(candidates) == 2
    first, second = candidates
    assert first["id"] == "F1" and second["id"] == "F2"
    for candidate, (takeoff, landing, _peak) in zip(candidates, hops):
        assert abs(candidate["frame_start"] - takeoff) <= 1
        assert abs(candidate["frame_end"] - landing) <= 1
        assert candidate["airtime_s"] > 0
        assert candidate["peak_rise_px"] > 0
        assert candidate["peak_rise_heights"] > 0
        assert candidate["curvature_sign"] == "positive"
        assert candidate["centroid_curvature_px_s2"] > 0
        assert candidate["centroid_r_squared"] >= 0.95
        assert candidate["flags"] == {"area_jumps": [],
                                      "edge_contact": [],
                                      "splits": []}


def test_area_jumps_flagged_not_confused(make_run):
    hops = ((20, 28, 20),)
    masks = _planted_masks(hops=hops, wide_frames=(5, 6, 7))
    run, _rel, result = _overview_run(make_run, masks)
    assert result["ok"], result
    candidates = result["metrics"]["candidates"]
    assert len(candidates) == 1
    assert not (candidates[0]["frame_start"] <= 5
                and candidates[0]["frame_end"] >= 7)
    table = json.loads((run / result["metrics"][
        "table_artifact"]).read_text(encoding="utf-8"))
    rows = table["objects"][0]["frames"]
    assert {r["frame"] for r in rows} == set(range(60))
    row = {r["frame"]: r for r in rows}[0]
    for key in ("bottom_y", "top_y", "centroid_y", "centroid_x",
                "height_px", "area_px", "support_y", "rise_px",
                "t_s"):
        assert key in row, key


def test_area_jump_inside_a_hop_is_flagged(make_run):
    hops = ((20, 28, 20),)
    masks = _planted_masks(hops=hops, wide_frames=(24,))
    _run, _rel, result = _overview_run(make_run, masks)
    assert result["ok"], result
    candidates = result["metrics"]["candidates"]
    assert len(candidates) == 1
    assert 24 in candidates[0]["flags"]["area_jumps"]


def test_fake1_two_flights(tmp_path):
    source = Path("fixtures/source/fake-1")
    run = tmp_path / "run"
    (run / "input").mkdir(parents=True)
    (run / "artifacts").mkdir(parents=True)
    (run / "workspace").mkdir(parents=True)
    shutil.copy(source / "input" / "timing.json",
                run / "input" / "timing.json")
    shutil.copy(source / "input" / "clip.mp4",
                run / "input" / "clip.mp4")
    shutil.copy(source / "artifacts" / "t9_segment_0.npz",
                run / "artifacts" / "t9_segment_0.npz")
    result = motion_overview.motion_overview(
        str(run), 9, masks_artifact="artifacts/t9_segment_0.npz",
        object_ids=["1"])
    assert result["ok"], result
    candidates = [c for c in result["metrics"]["candidates"]
                  if c["object_id"] == "1"]
    for takeoff, landing in _FAKE1_FLIGHTS:
        covering = [c for c in candidates
                    if abs(c["frame_start"] - takeoff) <= 2
                    and abs(c["frame_end"] - landing) <= 2]
        assert len(covering) == 1, (takeoff, landing, candidates)
        assert covering[0]["curvature_sign"] == "positive"
        assert covering[0]["centroid_r_squared"] >= 0.9


def test_chart_and_strips_named_and_nonempty(make_run):
    hops = ((20, 28, 20), (40, 48, 20))
    run, _rel, result = _overview_run(
        make_run, _planted_masks(hops=hops))
    assert result["ok"], result
    files = result["files"]
    table_rel = result["metrics"]["table_artifact"]
    chart_rel = result["metrics"]["chart_artifact"]
    assert table_rel in files and chart_rel in files
    assert table_rel.startswith("artifacts/t7_motion_overview_")
    assert chart_rel.startswith("artifacts/t7_motion_overview_chart_")
    assert chart_rel.endswith(".png")
    strips = result["metrics"]["strip_artifacts"]
    assert len(strips) == 2
    for rel in [chart_rel, *strips.values()]:
        assert rel in files
        assert rel.endswith((".png", ".jpg", ".jpeg"))
        path = run / rel
        assert path.is_file() and path.stat().st_size > 0
        assert cv2.imread(str(path)) is not None
    table = json.loads((run / table_rel).read_text(encoding="utf-8"))
    assert table["masks_artifact"].endswith(".npz")
    assert table["timing_source"] == "input/timing.json"
    assert len(table["objects"]) == 1
    assert len(table["objects"][0]["candidates"]) == 2


def test_bad_inputs_rejected(make_run):
    run = make_run(frames=40)
    rel = "artifacts/t0_segment_0.npz"
    masks_io.save_masks(run / rel, {"sq": _planted_masks(frames=40)})
    missing = motion_overview.motion_overview(
        str(run), 0, masks_artifact="artifacts/nope.npz")
    assert not missing["ok"]
    assert missing["error"]["code"] == "bad_masks"
    escaped = motion_overview.motion_overview(
        str(run), 0, masks_artifact="../secret.npz")
    assert not escaped["ok"]
    assert escaped["error"]["code"] == "path_rejected"
    absolute = motion_overview.motion_overview(
        str(run), 0, masks_artifact="/tmp/x.npz")
    assert not absolute["ok"]
    assert absolute["error"]["code"] == "path_rejected"
    unknown = motion_overview.motion_overview(
        str(run), 0, masks_artifact=rel, object_ids=["ghost"])
    assert not unknown["ok"]
    assert unknown["error"]["code"] == "unknown_object"
    assert "sq" in unknown["error"]["detail"]
    empty = motion_overview.motion_overview(
        str(run), 0, masks_artifact=rel, object_ids=[])
    assert not empty["ok"]
    assert empty["error"]["code"] == "bad_object"
    extra = motion_overview.motion_overview(
        str(run), 0, masks_artifact=rel, image=b"nope")
    assert not extra["ok"]
    assert extra["error"]["code"] == "bad_arguments"


def test_object_ids_filter_to_one_object(make_run):
    run = make_run(frames=60)
    rel = "artifacts/t2_segment_0.npz"
    both = {"sq": _planted_masks(hops=((20, 28, 20),)),
            "still": _planted_masks(hops=())}
    masks_io.save_masks(run / rel, both)
    result = motion_overview.motion_overview(
        str(run), 2, masks_artifact=rel, object_ids=["still"])
    assert result["ok"], result
    assert result["metrics"]["object_ids"] == ["still"]
    assert result["metrics"]["candidate_counts"] == {"still": 0}
    assert "F1" not in result["metrics"]["strip_artifacts"]


def _bottom_rows(chart, x, y_top, y_bottom):
    """Median row of bottom-line-colour pixels in column ``x``."""
    import numpy as np

    rows = []
    height, width = chart.shape[:2]
    for dx in (-1, 0, 1):
        column = int(x) + dx
        if column < 0 or column >= width:
            continue
        for row in range(max(0, y_top), min(height, y_bottom + 1)):
            pixel = chart[row, column]
            if (abs(int(pixel[0]) - 200) <= 40
                    and abs(int(pixel[1]) - 80) <= 40
                    and abs(int(pixel[2]) - 40) <= 40):
                rows.append(row)
    assert rows, f"no bottom line found in chart column {x}"
    return sorted(rows)[len(rows) // 2]


def test_chart_draws_flight_as_hump(make_run):
    hops = ((30, 38, 20), (50, 58, 20))
    run, _rel, result = _overview_run(
        make_run, _planted_masks(frames=70, hops=hops), frames=70)
    assert result["ok"], result
    candidates = result["metrics"]["candidates"]
    assert len(candidates) == 2
    table = json.loads((run / result["metrics"]["table_artifact"])
                       .read_text(encoding="utf-8"))
    rows = table["objects"][0]["frames"]
    by_frame = {r["frame"]: r for r in rows}
    times = [r["t_s"] for r in rows]
    t_min, t_max = min(times), max(times)
    plot_w = 960 - 64 - 20

    def _x(frame):
        return int(round(64 + (by_frame[frame]["t_s"] - t_min)
                         / (t_max - t_min) * plot_w))

    chart = cv2.imread(str(run / result["metrics"]["chart_artifact"]))
    assert chart is not None
    y_top, y_bottom = 30 + 26, 30 + 26 + (230 - 52)
    walking = candidates[0]["frame_start"] - 25
    assert walking in by_frame, (walking, candidates)
    walking_row = _bottom_rows(chart, _x(walking), y_top, y_bottom)
    for candidate in candidates:
        peak_row = _bottom_rows(
            chart, _x(candidate["peak_frame"]), y_top, y_bottom)
        assert peak_row < walking_row, (candidate, peak_row, walking_row)


def test_ids_unique_across_objects_and_two_strips(make_run):
    run = make_run(frames=60)
    rel = "artifacts/t4_segment_0.npz"
    both = {"a": _planted_masks(hops=((20, 28, 20),)),
            "b": _planted_masks(hops=((40, 48, 20),))}
    masks_io.save_masks(run / rel, both)
    result = motion_overview.motion_overview(str(run), 4, masks_artifact=rel)
    assert result["ok"], result
    candidates = result["metrics"]["candidates"]
    assert [c["id"] for c in candidates] == ["F1", "F2"]
    strips = result["metrics"]["strip_artifacts"]
    assert set(strips) == {"F1", "F2"}
    assert len(set(strips.values())) == 2
    for rel_path in strips.values():
        assert rel_path in result["files"]
        assert rel_path.endswith(".png")
        path = run / rel_path
        assert path.is_file() and path.stat().st_size > 0


def test_strip_frames_in_time_order(make_run):
    hops = ((20, 28, 20), (40, 48, 20))
    run, _rel, result = _overview_run(
        make_run, _planted_masks(hops=hops))
    assert result["ok"], result
    frames_by_id = result["metrics"]["strip_frames"]
    for candidate in result["metrics"]["candidates"]:
        frames = frames_by_id[candidate["id"]]
        assert len(frames) == 6, (candidate["id"], frames)
        assert all(b >= a for a, b in zip(frames, frames[1:])), frames
        run_len = candidate["frame_end"] - candidate["frame_start"] + 1
        if run_len >= 6:
            assert all(b > a for a, b in zip(frames, frames[1:])), frames
        assert frames[0] == max(0, candidate["frame_start"] - 3)
        assert frames[1] == candidate["frame_start"]
        assert frames[2] == candidate["peak_frame"]
        assert frames[3] == (candidate["peak_frame"]
                             + candidate["frame_end"]) // 2
        assert frames[4] == candidate["frame_end"]


def test_fake1_strip_frames_in_time_order(tmp_path):
    import shutil
    from pathlib import Path

    source = Path("fixtures/source/fake-1")
    run = tmp_path / "run"
    (run / "input").mkdir(parents=True)
    (run / "artifacts").mkdir(parents=True)
    (run / "workspace").mkdir(parents=True)
    shutil.copy(source / "input" / "timing.json",
                run / "input" / "timing.json")
    shutil.copy(source / "input" / "clip.mp4",
                run / "input" / "clip.mp4")
    shutil.copy(source / "artifacts" / "t9_segment_0.npz",
                run / "artifacts" / "t9_segment_0.npz")
    result = motion_overview.motion_overview(
        str(run), 9, masks_artifact="artifacts/t9_segment_0.npz",
        object_ids=["1"])
    assert result["ok"], result
    for candidate in result["metrics"]["candidates"]:
        frames = result["metrics"]["strip_frames"][candidate["id"]]
        assert len(frames) == 6
        assert all(b >= a for a, b in zip(frames, frames[1:])), frames


def _planted_offset_masks(frames=90, takeoff=25, landing=33,
                          peak_px=70, stand=110, new_level=50,
                          height=200, width=160):
    """A rectangle stands, hops once, and lands higher in the frame.

    The body stands with its bottom at ``stand``, makes one
    parabolic hop of ``peak_px`` pixels over
    ``[takeoff, landing]``, and stands after at ``new_level``
    (``stand - new_level`` pixels higher in the frame, the §24
    street-jump shape). The landing frame already stands on the new
    level. The rectangle is 40 wide and 30 tall.
    """
    masks = {}
    for frame in range(frames):
        rise = 0.0
        if takeoff <= frame <= landing:
            u = ((frame - takeoff) / (landing - takeoff)
                 if landing > takeoff else 0.0)
            rise = 4.0 * peak_px * u * (1.0 - u)
        level = stand if frame < landing else new_level
        bottom = int(round(level - rise))
        grid = np.zeros((height, width), dtype=bool)
        x = (5 + 2 * frame) % 110
        grid[max(0, bottom - 30):bottom, x:x + 40] = True
        masks[frame] = grid
    return masks


def test_flight_cut_to_takeoff_landing_above_takeoff_level(make_run):
    takeoff, landing = 25, 33
    run = make_run(frames=90)
    rel = "artifacts/t7_segment_0.npz"
    masks_io.save_masks(
        run / rel, {"sq": _planted_offset_masks(takeoff=takeoff,
                                                landing=landing)})
    result = motion_overview.motion_overview(
        str(run), 7, masks_artifact=rel)
    assert result["ok"], result
    candidates = result["metrics"]["candidates"]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert abs(candidate["frame_start"] - takeoff) <= 2
    assert abs(candidate["frame_end"] - landing) <= 2
    assert candidate["curvature_sign"] == "positive"
    assert candidate["centroid_r_squared"] >= 0.95
    assert candidate["frames"] == list(range(candidate["frame_start"],
                                            candidate["frame_end"] + 1))
    assert len(candidate["raw_frames"]) > len(candidate["frames"])
    assert (candidate["raw_frames"][0]
            == min(candidate["raw_frames"]))
    assert candidate["frame_start"] in candidate["raw_frames"]


def test_cut_records_raw_frames_on_level_hops(make_run):
    hops = ((20, 28, 20), (40, 48, 20))
    run, _rel, result = _overview_run(
        make_run, _planted_masks(hops=hops))
    assert result["ok"], result
    for candidate in result["metrics"]["candidates"]:
        assert candidate["frames"] == list(
            range(candidate["frame_start"],
                  candidate["frame_end"] + 1))
        assert set(candidate["frames"]) <= set(candidate["raw_frames"])
        assert (candidate["raw_frames"][0]
                <= candidate["frame_start"])
        assert (candidate["frame_end"]
                <= candidate["raw_frames"][-1])


def test_published_in_schemas():
    assert "motion_overview" in schemas.TOOL_NAMES
    assert (schemas.TOOL_SCHEMAS[-2]["name"] == "motion_overview"
            ), "submit stays last (its test pins TOOL_SCHEMAS[-1])"
    params = schemas.TOOL_SCHEMAS[-2]["parameters"]
    assert set(params["properties"]) == {"masks_artifact", "object_ids"}
    blob = params["description"].lower()
    assert "no api call" in blob
    assert "never says jump" in blob  # the pixel-fact line

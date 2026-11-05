# generated from brief/07 · part 07 owns this file
"""``view_frames``: measured timestamps, ranges, cuts, crops."""

from __future__ import annotations

import json

from src.tools import view_frames


def test_index_uses_measured_timestamps(make_run):
    run = make_run(frames=40)
    result = view_frames.view_frames(str(run), 0, frame_start=5,
                                     frame_end=12)
    assert result["ok"], result
    assert result["files"][0].startswith("artifacts/t0_view_frames_")
    index = result["metrics"]["index"]
    assert [row["frame"] for row in index] == list(range(5, 13))
    timing = json.loads((run / "input" / "timing.json").read_text(
        encoding="utf-8"))
    for row in index:
        assert row["t_s"] == timing["timestamps"][row["frame"]]
    assert result["metrics"]["timing_source"] == "input/timing.json"
    assert result["metrics"]["measured_fps"] == 25.0


def test_explicit_indices_and_stride(make_run):
    run = make_run(frames=40)
    result = view_frames.view_frames(str(run), 1,
                                     frame_indices=[0, 10, 20, 30])
    assert result["ok"], result
    assert result["metrics"]["frames_served"] == [0, 10, 20, 30]
    assert "artifacts/t1_view_frames_" in result["files"][0]


def test_out_of_range_reported_not_served(make_run):
    run = make_run(frames=40)
    result = view_frames.view_frames(str(run), 0, frame_start=38,
                                     frame_end=45)
    assert result["ok"], result
    assert result["metrics"]["out_of_range"] == [40, 41, 42, 43, 44, 45]
    assert result["metrics"]["frames_served"] == [38, 39]


def test_all_out_of_range_is_an_error(make_run):
    run = make_run(frames=40)
    result = view_frames.view_frames(str(run), 0, frame_start=50,
                                     frame_end=55)
    assert not result["ok"]
    assert result["error"]["code"] == "bad_range"


def test_cut_spanning_reported(make_run):
    run = make_run(frames=40, cuts=[20])
    result = view_frames.view_frames(str(run), 0, frame_start=10,
                                     frame_end=30)
    assert result["ok"], result
    assert result["metrics"]["cuts_spanned"] == [20]
    assert "cut" in result["summary"]


def test_duplicates_flagged(make_run):
    run = make_run(frames=40, dups=[[7, 8]])
    result = view_frames.view_frames(str(run), 0, frame_start=5,
                                     frame_end=10)
    assert result["ok"], result
    assert result["metrics"]["duplicates_in_range"] == [7, 8]


def test_crop_and_sequence_layout(make_run):
    run = make_run(frames=40)
    result = view_frames.view_frames(
        str(run), 2, frame_start=0, frame_end=7,
        crop={"x0": 0.0, "y0": 0.0, "x1": 0.5, "y1": 0.5},
        layout="sequence")
    assert result["ok"], result
    assert len(result["metrics"]["index"]) == 8


def test_bad_arguments_rejected(make_run):
    run = make_run(frames=40)
    assert not view_frames.view_frames(
        str(run), 0, frame_start=10, frame_end=5)["ok"]
    assert not view_frames.view_frames(
        str(run), 0, frame_start=0, frame_end=5,
        stride=0)["ok"]
    assert not view_frames.view_frames(
        str(run), 0, frame_start=0, frame_end=5,
        crop={"x0": 0.9, "y0": 0.0, "x1": 0.1,
              "y1": 1.0})["ok"]
    assert not view_frames.view_frames(
        str(run), 0, frame_start=0, frame_end=5,
        layout="filmstrip")["ok"]
    missing = view_frames.view_frames(str(run), 0)
    assert not missing["ok"]

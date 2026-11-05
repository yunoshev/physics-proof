# generated from brief/07 · part 07 owns this file
"""``timing``: measured time base and clip access (part 07 §§2–3, §10)."""

from __future__ import annotations

import json

import pytest

from src.tools.timing import find_clip, load_timing, normalise_timing


def test_load_timing_validates_shape(make_run):
    run_dir = make_run(frames=25)
    timing = load_timing(run_dir)
    assert timing["frame_count"] == 25
    assert timing["measured_fps"] == 25.0
    assert timing["timestamps"] == [
        pytest.approx(i / 25.0) for i in range(25)]
    assert timing["confirmed_duplicates"] == []
    assert timing["cuts"] == []


def test_load_timing_rejects_mismatch(make_run):
    run_dir = make_run(frames=25)
    timing_path = run_dir / "input" / "timing.json"
    report = json.loads(timing_path.read_text(encoding="utf-8"))
    report["timestamps"] = report["timestamps"][:-1]
    timing_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        load_timing(run_dir)


def test_load_timing_missing_report(make_run):
    run_dir = make_run(frames=10)
    (run_dir / "input" / "timing.json").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        load_timing(run_dir)


def test_find_clip_needs_clip_glob(make_run):
    run_dir = make_run(frames=10)
    assert find_clip(run_dir).name == "clip.mp4"
    (run_dir / "input" / "clip.mp4").unlink()
    with pytest.raises(FileNotFoundError):
        find_clip(run_dir)


def test_normalise_timing_tolerates_variants():
    base = {"frame_count": 3, "timestamps": [0.0, 0.5, 1.0],
            "measured_fps": 2.0, "confirmed_duplicates": [2],
            "cut_indices": [1]}
    facts = normalise_timing(base)
    assert facts["dups"] == {2}
    assert facts["cuts"] == [1]
    assert facts["confirmed_duplicates"] == [2]
    legacy = {"frame_count": 2, "timestamps": [0.0, 1.0],
              "measured_fps": {"median": 1.0}}
    assert normalise_timing(legacy)["fps"] == 1.0
    with pytest.raises(ValueError):
        normalise_timing({"frame_count": 0, "timestamps": []})

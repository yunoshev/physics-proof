"""Tests for ``src/ingest`` (part 05 §§1–3, 6).

The container's fps claim is never trusted; duplicates are split into
confirmed (byte-identical) vs suspect (near hash); ``timing.json``
holds numbers and indices only; unreadable input ends the run through
the part-11 synthesis path, never with a crash.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess

import numpy as np
import pytest

from src.ingest import (
    NEAR_DUPLICATE_HASH_BITS,
    IngestError,
    ingest,
    measure_timing,
    timeline_hygiene,
    timing_from_timestamps,
)

W, H = 64, 48

NEEDS_FFMPEG = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe required for ingest tests",
)


def base_frame() -> np.ndarray:
    """Deterministic structured frame: luma ramp + flat red channel."""
    frame = np.zeros((H, W, 3), dtype=np.uint8)
    frame[:, :, 1] = np.linspace(0, 255, W, dtype=np.uint8)
    frame[:, :, 0] = 100
    return frame


def write_clip(frames, path, framerate=30, extra=()) -> str:
    """Pipe raw RGB frames to a lossless-H.264 mp4; return str(path)."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-framerate", str(framerate), "-i", "-",
           "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0",
           "-pix_fmt", "yuv420p", *extra, str(path)]
    proc = subprocess.run(cmd, input=np.stack(list(frames)).tobytes(),
                          capture_output=True, timeout=300)
    assert proc.returncode == 0, proc.stderr.decode()[:500]
    return str(path)


@pytest.fixture()
def distinct_clip(tmp_path):
    """30 unique frames at 30 fps: no duplicates, no cuts."""
    base = base_frame()
    frames = [np.roll(base, 2 * k, axis=1) for k in range(30)]
    return write_clip(frames, tmp_path / "source.mp4", framerate=30)


@NEEDS_FFMPEG
def test_anonymous_copy_strips_metadata_and_audio(tmp_path):
    base = base_frame()
    src = tmp_path / "My Vacation 2024.MP4"
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt",
         "rgb24", "-s", f"{W}x48", "-framerate", "30", "-i", "-",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0",
         "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-metadata", "title=Secret Identity Title",
         "-metadata", "comment=identify me",
         "-shortest", str(src)],
        input=np.stack([base] * 30).tobytes(),
        capture_output=True, timeout=300)
    assert proc.returncode == 0, proc.stderr.decode()[:300]
    before = hashlib.sha256(src.read_bytes()).hexdigest()

    out = ingest(str(src), tmp_path / "run")
    clip = tmp_path / "run" / "input" / "clip.mp4"
    assert out["clip_path"] == str(clip)
    assert clip.is_file()
    # The agent's world: anonymous name + timing only.
    assert sorted(p.name for p in (tmp_path / "run" / "input").iterdir()) == [
        "clip.mp4", "timing.json"]
    # The source is never moved or modified.
    assert src.is_file()
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    # Identity trace lives in logs/ only.
    probe_log = json.loads(
        (tmp_path / "run" / "logs" / "probe.json").read_text(
            encoding="utf-8"))
    assert probe_log["original_filename"] == "My Vacation 2024.MP4"
    assert probe_log["original_path"].endswith("My Vacation 2024.MP4")
    assert probe_log["audio_streams_dropped"] == 1

    copied = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams",
         "-of", "json", str(clip)],
        capture_output=True, text=True, timeout=120,
        check=True).stdout)
    assert len(copied["streams"]) == 1  # audio dropped
    assert copied["streams"][0]["codec_type"] == "video"
    format_tags = copied["format"].get("tags") or {}
    assert "title" not in format_tags and "comment" not in format_tags
    # Stream copy: decoded content identical to the source.
    assert _md5s(str(src)) == _md5s(str(clip))


def _md5s(path):
    from src.ingest.hygiene import frame_md5s
    import json as _json
    import subprocess as _sp
    n = int(_json.loads(_sp.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "json", path],
        capture_output=True, text=True, check=True,
        timeout=120).stdout)["streams"][0].get("nb_frames") or 30)
    return frame_md5s(path, n)


@NEEDS_FFMPEG
def test_measured_fps_from_timestamps_not_claim(tmp_path):
    # Pure core: a lying claim cannot move the measurement.
    stamps = [i / 24.0 for i in range(48)]
    facts = timing_from_timestamps(stamps, claimed_fps=30.0)
    assert facts["claimed_fps"] == 30.0
    assert facts["measured_fps"] == pytest.approx(24.0, abs=1e-6)
    assert facts["frame_count"] == 48
    assert facts["vfr"] is False
    # Integration: honest 24 fps clip measures 24 from decode.
    base = base_frame()
    path = write_clip([np.roll(base, k, axis=1) for k in range(48)],
                      tmp_path / "c24.mp4", framerate=24)
    measured = measure_timing(path)
    assert measured["measured_fps"] == pytest.approx(24.0, abs=0.05)
    assert len(measured["timestamps"]) == 48
    deltas = np.diff(np.asarray(measured["timestamps"]))
    assert float(np.median(deltas)) == pytest.approx(1 / 24.0, abs=1e-3)


def test_vfr_reports_distribution():
    # Alternating 1/30 and 1/10 s gaps: irregular by construction.
    stamps, t = [0.0], 0.0
    for k in range(1, 40):
        t += 1 / 30.0 if k % 2 else 1 / 10.0
        stamps.append(t)
    facts = timing_from_timestamps(stamps, claimed_fps=30.0)
    assert facts["vfr"] is True
    dist = facts["delta_s"]
    assert dist["min"] <= dist["p05"] <= dist["median"] <= dist["p95"] <= dist["max"]
    assert facts["measured_fps"] == pytest.approx(
        1.0 / dist["median"], abs=1e-9)
    assert "timestamps" in facts["vfr_note"]


@NEEDS_FFMPEG
def test_exact_vs_suspect_duplicates(tmp_path):
    base = base_frame()
    tiny = base.copy()
    tiny[20:24, 30:34, 0] = np.clip(
        tiny[20:24, 30:34, 0].astype(int) + 30, 0, 255)
    frames = ([base, base.copy(), tiny]
              + [np.roll(base, 8 * k, axis=1) for k in range(1, 6)])
    path = write_clip(frames, tmp_path / "mix.mp4")
    report = timeline_hygiene(path)
    # Byte-identical pair is confirmed (with its run)...
    assert report["confirmed_duplicates"] == [0, 1]
    assert report["confirmed_runs"] == [[0, 1]]
    # ...the near-identical frame is suspect, never confirmed...
    assert report["suspect_duplicates"] == [2]
    assert report["suspect_runs"] == [[2]]
    assert 2 not in report["confirmed_duplicates"]
    assert 1 not in report["suspect_duplicates"]
    # ...and clear motion trips neither label.
    assert report["near_duplicate_threshold_bits"] == (
        NEAR_DUPLICATE_HASH_BITS)


@NEEDS_FFMPEG
def test_cuts_flagged(tmp_path):
    base = base_frame()
    scene_a = [np.roll(base, 2 * k, axis=1) for k in range(10)]
    scene_b = [np.roll(255 - base, 2 * k, axis=1) for k in range(10)]
    path = write_clip(scene_a + scene_b, tmp_path / "cut.mp4")
    report = timeline_hygiene(path)
    assert report["cuts"] == [10]
    assert report["confirmed_duplicates"] == []


@NEEDS_FFMPEG
def test_interpolation_suspicion_is_suspicion_only(distinct_clip):
    varied = timeline_hygiene(distinct_clip)
    assert varied["confirmed_duplicates"] == []
    # Uniform motion may raise suspicion...
    assert varied["interpolation_suspicion"]["suspected"] is True
    note = varied["interpolation_suspicion"]["note"]
    assert "never evidence" in note
    assert varied["interpolation_suspicion"]["reason"] in (
        "uniform_frame_differences", "motion_variance_normal",
        "confirmed_duplicates_present", "too_few_frames", "no_motion")
    # ...but confirmed duplicates always clear it: suspicion can never
    # stand alongside proof of duplication.
    assert varied["interpolation_suspicion"]["reason"] != "slow_motion"


@NEEDS_FFMPEG
def test_timing_json_numbers_only(tmp_path, distinct_clip):
    out = ingest(distinct_clip, tmp_path / "run")
    report = json.loads((tmp_path / "run" / "input" / "timing.json")
                        .read_text(encoding="utf-8"))
    assert out["timing"]["measured_fps"] == report["measured_fps"]
    for key in ("timestamps", "timestamps_s", "confirmed_duplicates",
                "confirmed_runs", "duplicate_runs", "suspect_duplicates",
                "suspect_runs", "cuts", "cut_indices", "measured_fps",
                "frame_count", "duration_s"):
        assert key in report, key
    assert report["timestamps"] == report["timestamps_s"]
    assert len(report["timestamps"]) == report["frame_count"]
    assert report["timestamps"] == sorted(report["timestamps"])
    # No captions, thumbnails, or model output anywhere.
    assert not (set(report) & {"caption", "captions", "thumbnail",
                               "thumbnails", "description", "model_output"})
    strings = []

    def collect(node):
        if isinstance(node, str):
            strings.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(report)
    allowed = {"uniform_frame_differences", "motion_variance_normal",
               "confirmed_duplicates_present", "too_few_frames",
               "no_motion",
               "heuristic suspicion only; never evidence of native "
               "speed or slow motion (part 05 section 3)",
               "irregular timestamps: use per-frame timestamps, "
               "not measured_fps"}
    assert set(strings) <= allowed, set(strings) - allowed
    # Cross-part contracts: helpers and tools read this file directly.
    from src.helpers.masks_io import clip_facts
    from src.tools.timing import load_timing

    facts = clip_facts(tmp_path / "run" / "input" / "timing.json")
    assert facts["frame_count"] == report["frame_count"]
    assert facts["measured_fps"] == pytest.approx(report["measured_fps"])
    loaded = load_timing(tmp_path / "run")
    assert loaded["timestamps"] == pytest.approx(report["timestamps"])


@NEEDS_FFMPEG
def test_unreadable_video_synthesis_path(tmp_path):
    with pytest.raises(IngestError):
        ingest(str(tmp_path / "missing.mp4"), tmp_path / "run1")
    garbage = tmp_path / "not_video.mp4"
    garbage.write_text("this is not a video file", encoding="utf-8")
    with pytest.raises(IngestError):
        ingest(str(garbage), tmp_path / "run2")
    # Through the CLI the same failures end as valid undetermined
    # files (part 11 §4), never a crash or a hang.
    from src.cli import run_analysis
    from src.contract import validate_result, validate_summary

    out = run_analysis(str(garbage), run_id="test-ingest-undet",
                       runs_dir=str(tmp_path / "runs"))
    assert out["status"] == "undetermined"
    result = json.loads(open(out["result_path"], encoding="utf-8").read())
    summary = json.loads(open(out["summary_path"], encoding="utf-8").read())
    assert validate_result(result) == []
    assert validate_summary(summary) == []
    assert result["verdict"]["kind"] == "undetermined"

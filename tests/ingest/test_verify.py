"""Tests for ``src.ingest.verify`` (part 05 §4).

Generation is not trusted: clips A and B pass the same duplicate check
after generation. A has zero confirmed duplicates; B has zero confirmed
duplicates and the same measured fps as A. The known constant-framerate
failure is caught, never analysed.
"""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.ingest import FPS_MATCH_REL_TOL, verify_generated_clip

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


@NEEDS_FFMPEG
def test_cfr_forced_encode_caught(tmp_path):
    # The known failure (part 05 §4): forcing a constant frame rate on
    # encode duplicates frames to fill the rate.
    base = base_frame()
    raw = [np.clip(base.astype(int) + 10 * k, 0, 255).astype(np.uint8)
           for k in range(10)]
    forced = tmp_path / "cfr.mp4"
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt",
         "rgb24", "-s", f"{W}x48", "-framerate", "10", "-i", "-",
         "-r", "30", "-c:v", "libx264", "-preset", "ultrafast",
         "-qp", "0", "-pix_fmt", "yuv420p", str(forced)],
        input=np.stack(raw).tobytes(), capture_output=True, timeout=300)
    assert proc.returncode == 0, proc.stderr.decode()[:300]
    verdict = verify_generated_clip(str(forced))
    assert verdict["ok"] is False
    assert verdict["reason"] == "confirmed_duplicates_present"
    assert verdict["frame_count"] == 30
    assert len(verdict["confirmed_duplicates"]) > 0


@NEEDS_FFMPEG
def test_generated_clips_verify_zero_dups(tmp_path):
    # Clip A: original timing, distinct frames, constant rate.
    base = base_frame()
    clip_a = write_clip([np.roll(base, 2 * k, axis=1) for k in range(30)],
                        tmp_path / "a.mp4", framerate=30)
    verdict_a = verify_generated_clip(clip_a)
    assert verdict_a["ok"] is True
    assert verdict_a["reason"] is None
    assert verdict_a["confirmed_duplicates"] == []
    # Clip B: different frames and duration, same measured fps as A.
    clip_b = write_clip([np.roll(255 - base, 3 * k, axis=1)
                         for k in range(45)],
                        tmp_path / "b.mp4", framerate=30)
    verdict_b = verify_generated_clip(
        clip_b, expected_fps=verdict_a["measured_fps"])
    assert verdict_b["ok"] is True
    assert verdict_b["confirmed_duplicates"] == []
    assert verdict_b["fps_match"] is True
    assert abs(verdict_b["measured_fps"] - verdict_a["measured_fps"]) / (
        verdict_a["measured_fps"]) <= FPS_MATCH_REL_TOL
    # A wrong fps expectation fails instead of passing silently.
    mismatch = verify_generated_clip(clip_b, expected_fps=12.0)
    assert mismatch["ok"] is False
    assert mismatch["reason"] == "fps_mismatch"
    assert mismatch["fps_match"] is False

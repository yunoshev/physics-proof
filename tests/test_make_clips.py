# generated from brief/03 · spec-sha256:a66623e9ea850f11828f324b0c775f574e5879bdb22ec1cf39bb06385188a3d0 · plan-sha256:2d4a2718f3d74cac2e14a853ff4a8c3b7053edecd6fe6c4545e341ae5b11e35e
"""Tests for scripts/make_clips.py (owned by part 03, per PLAN.md section 3).

Clip generation is exercised on small synthetic sources (no network): a
moving test pattern with an audio track and identifying container metadata
stands in for the Apollo download. Production values (352x240, 466 frames,
29.97 fps) flow through the same code paths via the function defaults.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "make_clips.py"

_spec = importlib.util.spec_from_file_location("make_clips_under_test", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
make_clips = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_clips)

FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg/ffprobe not on PATH")

# Small synthetic geometry: fast to encode, still exercises every check.
T_W, T_H = 96, 72
T_FPS = 30
T_A_FRAMES = 48
T_B_FRAMES = 72  # 48 x 1.5
T_PRESET = "ultrafast"
T_CRF = 23


def _make_synth_source(path: Path, frames: int = 64) -> Path:
    """Moving pattern + audio tone + identifying metadata (download stand-in)."""
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={T_W}x{T_H}:rate={T_FPS}:duration={frames / T_FPS}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={frames / T_FPS}",
        "-metadata",
        "title=identifying source title",
        "-metadata",
        "comment=identifying source comment",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, f"synthetic source failed: {result.stderr[-500:]}"
    return path


@pytest.fixture(scope="module")
def pair(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Build one synthetic A/B pair shared by the clip-content tests."""
    needs_ffmpeg_check()
    work = tmp_path_factory.mktemp("clips")
    src = _make_synth_source(work / "source.mp4")
    clip_a = work / "a.mp4"
    clip_b = work / "b.mp4"
    make_clips.make_clip_a(
        source=src,
        out_path=clip_a,
        width=T_W,
        height=T_H,
        frames=T_A_FRAMES,
        fps_num=T_FPS,
        fps_den=1,
        preset=T_PRESET,
        crf=T_CRF,
    )
    make_clips.make_clip_b(
        clip_a,
        out_path=clip_b,
        slow_factor=1.5,
        out_frames=T_B_FRAMES,
        fps_num=T_FPS,
        fps_den=1,
        preset=T_PRESET,
        crf=T_CRF,
    )
    return {"a": clip_a, "b": clip_b}


def needs_ffmpeg_check() -> None:
    if not FFMPEG:
        pytest.skip("ffmpeg/ffprobe not on PATH")


@needs_ffmpeg
def test_a_metadata_stripped_and_probed(pair: dict) -> None:
    """Clip A: right size/count, measured (not claimed) fps, no audio, no tags."""
    clip_a = pair["a"]
    assert clip_a.exists()

    probe = make_clips.probe_streams(clip_a)
    assert (probe["width"], probe["height"]) == (T_W, T_H)
    assert probe["audio_streams"] == 0
    assert make_clips.identifying_tags_present(clip_a) == []

    stats = make_clips.verify_clip_a(
        clip_a,
        width=T_W,
        height=T_H,
        frames=T_A_FRAMES,
        fps_num=T_FPS,
        fps_den=1,
    )
    assert stats["frame_count"] == T_A_FRAMES
    assert stats["confirmed_duplicates"] == []
    assert abs(stats["measured_fps"] - T_FPS) / T_FPS < 0.02
    assert abs(stats["duration_s"] - T_A_FRAMES / T_FPS) < 0.05


@needs_ffmpeg
def test_b_slowed_1p5_same_fps_no_dups(pair: dict) -> None:
    """Clip B: 0 confirmed dups in both clips, same measured fps, x1.5 frames."""
    stats_a = make_clips.verify_clip_a(
        pair["a"], width=T_W, height=T_H, frames=T_A_FRAMES,
        fps_num=T_FPS, fps_den=1,
    )
    stats_b = make_clips.verify_clip_b(
        pair["b"], pair["a"], slow_factor=1.5, out_frames=T_B_FRAMES,
        fps_num=T_FPS, fps_den=1,
    )
    assert stats_a["confirmed_duplicates"] == []
    assert stats_b["confirmed_duplicates"] == []
    assert stats_b["frame_count"] == T_B_FRAMES
    fps_a = stats_a["measured_fps"]
    fps_b = stats_b["measured_fps"]
    assert abs(fps_b - fps_a) / fps_a < 0.01
    ratio = stats_b["frame_count"] / stats_a["frame_count"]
    assert abs(ratio - 1.5) < 0.1


@needs_ffmpeg
def test_a_b_differ_only_frames_duration(pair: dict) -> None:
    """A and B are indistinguishable except through the motion itself."""
    probe_a = make_clips.probe_streams(pair["a"])
    probe_b = make_clips.probe_streams(pair["b"])
    for key in ("width", "height", "codec", "pix_fmt"):
        assert probe_b[key] == probe_a[key], f"A/B differ in {key}"
    assert probe_b["audio_streams"] == 0
    assert probe_a["format_tags"] == probe_b["format_tags"]
    assert probe_a["video_stream_tags"] == probe_b["video_stream_tags"]
    fps_a = make_clips.measured_fps(pair["a"])
    fps_b = make_clips.measured_fps(pair["b"])
    assert abs(fps_b - fps_a) / fps_a < 0.01
    dur_a = T_A_FRAMES / fps_a
    dur_b = T_B_FRAMES / fps_b
    assert dur_b > dur_a
    assert abs(dur_b / dur_a - 1.5) / 1.5 < 0.05


_MODULE_NAME_RE = re.compile(r"(?<![\w.])make_clips(?![\w])")


def _import_and_path_refs(tree: ast.AST) -> list[str]:
    refs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in ("make_clips", "scripts") or mod.startswith(("scripts.", "tests.")):
                refs.append(f"from-import {mod}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("make_clips", "scripts") or alias.name.startswith(
                    ("scripts.", "tests.")
                ):
                    refs.append(f"import {alias.name}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            # The bare module name as a word (not test_make_clips); a runtime
            # string that names the prep module is a read of the answers.
            if _MODULE_NAME_RE.search(val) or "tests/acceptance" in val:
                refs.append(f"path literal {val[:80]!r}")
    return refs


def test_runtime_cannot_import_make_clips() -> None:
    """Structural boundary (brief part 03 section 5): no reachability either way.

    The analysis runtime (src/) must not import or read the clip-preparation
    script or the test harness; the script itself must not import src/tests.
    """
    offenders: list[str] = []
    src_root = ROOT / "src"
    assert src_root.is_dir()
    for path in sorted(src_root.rglob("*.py")):
        refs = _import_and_path_refs(ast.parse(path.read_text(encoding="utf-8")))
        offenders.extend(f"{path.relative_to(ROOT)}: {ref}" for ref in refs)
    script_refs = _import_and_path_refs(
        ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    )
    offenders.extend(f"scripts/make_clips.py: {ref}" for ref in script_refs)
    assert not offenders, (
        "runtime/test-prep boundary violated:\n" + "\n".join(offenders)
    )

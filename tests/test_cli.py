# generated from brief/04 · part 04 owns this file
"""CLI tests (part 04 §6, PLAN.md): the one command in, files out."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def _write_garbage(tmp_path: Path) -> Path:
    garbage = tmp_path / "not_video.mp4"
    garbage.write_text("this is not a video file", encoding="utf-8")
    return garbage


def test_one_command_creates_run_layout(tmp_path):
    pytest.importorskip("cv2", reason="needs opencv for ingest decode")
    try:
        import shutil

        if shutil.which("ffmpeg") is None:
            pytest.skip("needs ffmpeg for the clip fixture")
        from src.cli import run_analysis
        from src.contract import validate_result, validate_summary
    except ImportError as exc:
        pytest.skip(f"unavailable: {exc}")
    clip = tmp_path / "clip_src.mp4"
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=64x64:rate=10:duration=1",
         "-pix_fmt", "yuv420p", "-an", str(clip)],
        capture_output=True, timeout=120)
    if proc.returncode != 0 or not clip.is_file():
        pytest.skip("ffmpeg could not build the clip fixture")
    out = run_analysis(str(clip), run_id="test-cli-layout",
                       runs_dir=str(tmp_path / "runs"),
                       clients={})
    base = Path(out["run_dir"])
    assert (base / "input").is_dir()
    assert (base / "workspace").is_dir()
    assert (base / "artifacts").is_dir()
    assert (base / "logs").is_dir()
    assert out["status"] == "undetermined"
    assert json.loads(Path(out["result_path"]).read_text(
        encoding="utf-8"))["verdict"]["kind"] == "undetermined"
    assert validate_result(json.loads(Path(out["result_path"]).read_text(
        encoding="utf-8"))) == []
    assert validate_summary(json.loads(Path(out["summary_path"]).read_text(
        encoding="utf-8"))) == []


def test_every_exit_yields_valid_result(tmp_path):
    from src.cli import run_analysis
    from src.contract import validate_result, validate_summary

    garbage = _write_garbage(tmp_path)
    out = run_analysis(str(garbage), run_id="test-cli-undet",
                       runs_dir=str(tmp_path / "runs"))
    assert out["status"] == "undetermined"
    result = json.loads(Path(out["result_path"]).read_text(
        encoding="utf-8"))
    summary = json.loads(Path(out["summary_path"]).read_text(
        encoding="utf-8"))
    assert validate_result(result) == []
    assert validate_summary(summary) == []
    assert result["verdict"]["kind"] == "undetermined"
    # A missing file is the same exit, not a crash.
    out2 = run_analysis(str(tmp_path / "missing.mp4"),
                        run_id="test-cli-missing",
                        runs_dir=str(tmp_path / "runs"))
    assert out2["status"] == "undetermined"
    assert validate_result(json.loads(Path(out2["result_path"]).read_text(
        encoding="utf-8"))) == []


def test_run_id_carries_no_identity(tmp_path):
    from src.cli import generate_run_id, run_analysis

    seen = {generate_run_id() for _ in range(5)}
    assert len(seen) == 5, "run IDs must be unique"
    garbage = _write_garbage(tmp_path)
    out = run_analysis(str(garbage), runs_dir=str(tmp_path / "runs"))
    name = Path(out["run_dir"]).name
    assert "not_video" not in name
    assert garbage.stem not in name
    assert out["run_id"] == name


def test_no_key_means_no_model_configured(tmp_path):
    from src.cli import read_api_key, run_analysis

    assert read_api_key(env={}) is None
    assert read_api_key(env={"MODEL_API_KEY": "k"}) == "k"
    assert read_api_key(env={"META_API_KEY": "a",
                             "MODEL_API_KEY": "b"}) == "a"
    garbage = _write_garbage(tmp_path)
    out = run_analysis(str(garbage), run_id="test-cli-nokey",
                       runs_dir=str(tmp_path / "runs"))
    assert out["status"] == "undetermined"


def test_key_never_reaches_run_folder(tmp_path, monkeypatch):
    from src.cli import run_analysis

    sentinel = "sentinel-key-xyz-123"
    monkeypatch.setenv("META_API_KEY", sentinel)
    garbage = _write_garbage(tmp_path)
    # Prebuilt (empty) clients: no network, but the env key exists.
    out = run_analysis(str(garbage), run_id="test-cli-keyleak",
                       runs_dir=str(tmp_path / "runs"), clients={})
    blob = "".join(p.read_text(encoding="utf-8", errors="replace")
                   for p in Path(out["run_dir"]).rglob("*")
                   if p.is_file())
    assert sentinel not in blob

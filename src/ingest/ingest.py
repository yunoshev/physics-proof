"""Anonymised ingest (part 05 §§1, 6).

``ingest()`` is the only entry point the CLI uses. From the moment the
CLI receives one filesystem path:

1. The file is **copied** (never moved, never modified) into
   ``runs/<run-id>/input/`` under the fixed anonymous name
   ``clip.<ext>``; the original filename, path, and container metadata
   are recorded in ``logs/`` only.
2. Container metadata is **stripped** from the copy (ffmpeg stream copy
   with metadata mapping disabled; re-encode where stripping requires
   it) and audio is dropped (``-an``): the product is silent, and audio
   is an identity leak channel.
3. The agent's world begins at ``input/clip.<ext>`` and
   ``input/timing.json``. Nothing else about the file — no directory
   listing, no sibling files — is visible to the agent.

No transcoding for analysis (the agent gets the metadata-stripped
original encoding, including HEVC); no frame extraction at ingest
(choosing frames is the agent's job, part 07); no content description
of any kind (``timing.json`` holds numbers and indices only).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from .hygiene import timeline_hygiene
from .measure import measure_timing
from .probe import IngestError, probe

__all__ = ["IngestError", "ingest", "anonymous_name", "write_timing_json",
           "write_probe_json"]


def anonymous_name(video_path: str | Path, probe_info: dict | None = None) -> str:
    """Fixed anonymous copy name: ``clip.<ext>`` (part 05 §1).

    The extension follows the source container (so the copy stays
    playable), sanitised to a short alphanumeric suffix; anything odd
    falls back to ``mp4``. The stem carries no identity.
    """
    ext = Path(video_path).suffix.lower().lstrip(".")
    if not re.fullmatch(r"[a-z0-9]{1,5}", ext):
        ext = "mp4"
    return f"clip.{ext}"


def write_timing_json(timing: dict, hygiene: dict, path: str | Path) -> dict:
    """Write ``timing.json``: numbers and indices only, no content text.

    Merges the measured timing with the hygiene report under the key
    variants every consumer reads (``timestamps`` for part 09's
    ``clip_facts``, ``timestamps_s`` for part 07's tools,
    ``confirmed_duplicates`` for parts 08/11, ``duplicate_runs`` for
    part 09, ``cuts``/``cut_indices`` for all of them).
    """
    report = {
        "claimed_fps": timing.get("claimed_fps"),
        "measured_fps": timing.get("measured_fps"),
        "delta_s": timing.get("delta_s"),
        "vfr": timing.get("vfr"),
        "vfr_note": timing.get("vfr_note"),
        "frame_count": timing.get("frame_count"),
        "duration_s": timing.get("duration_s"),
        "timestamps": list(timing.get("timestamps") or []),
        "timestamps_s": list(timing.get("timestamps") or []),
        "confirmed_duplicates": list(
            hygiene.get("confirmed_duplicates") or []),
        "confirmed_runs": [list(run) for run in
                           hygiene.get("confirmed_runs") or []],
        "duplicate_runs": [list(run) for run in
                           hygiene.get("confirmed_runs") or []],
        "suspect_duplicates": list(
            hygiene.get("suspect_duplicates") or []),
        "suspect_runs": [list(run) for run in
                         hygiene.get("suspect_runs") or []],
        "near_duplicate_threshold_bits": hygiene.get(
            "near_duplicate_threshold_bits"),
        "cuts": list(hygiene.get("cuts") or []),
        "cut_indices": list(hygiene.get("cuts") or []),
        "scene_change_threshold": hygiene.get("scene_change_threshold"),
        "interpolation_suspicion": dict(
            hygiene.get("interpolation_suspicion") or {}),
    }
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def write_probe_json(source: str | Path, probe_info: dict, dest: str | Path,
                     copied_to: str, run_id: str) -> dict:
    """Write ``logs/probe.json``: operator-only source trace.

    Records the original filename, the path as passed, the source
    sha256, and the container metadata — everything identity-shaped
    lives here, never in ``input/``.
    """
    src = Path(source)
    digest = hashlib.sha256()
    with open(src, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    record = {
        "run_id": run_id,
        "original_filename": src.name,
        "original_path": str(src.resolve()),
        "source_sha256": digest.hexdigest(),
        "container": probe_info.get("format"),
        "video_stream": probe_info.get("video_stream"),
        "audio_streams_dropped": probe_info.get("audio_streams"),
        "claimed_fps": probe_info.get("claimed_fps"),
        "copied_to": copied_to,
    }
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def _stream_copy(source: str | Path, dest: str | Path) -> None:
    """Metadata-stripped, audio-dropped stream copy (no re-encode)."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise IngestError("unreadable video: required tool 'ffmpeg' not found")
    cmd = [ffmpeg, "-y", "-v", "error", "-i", str(source),
           "-map", "0:v:0", "-c:v", "copy",
           "-map_metadata", "-1", "-map_metadata:s:v", "-1",
           "-an", str(dest)]
    try:
        subprocess.run(cmd, capture_output=True, timeout=600, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            OSError) as exc:
        raise IngestError(
            f"unreadable video: anonymised copy failed: {exc}") from exc


def _reencode_copy(source: str | Path, dest: str | Path) -> None:
    """Fallback where stream-copy stripping is impossible.

    Re-encodes with passthrough frame timing (never a forced constant
    frame rate, which would silently duplicate frames — part 05 §4).
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise IngestError("unreadable video: required tool 'ffmpeg' not found")
    cmd = [ffmpeg, "-y", "-v", "error", "-i", str(source),
           "-map", "0:v:0", "-c:v", "libx264", "-preset", "veryfast",
           "-pix_fmt", "yuv420p", "-fps_mode", "passthrough",
           "-map_metadata", "-1", "-an", str(dest)]
    try:
        subprocess.run(cmd, capture_output=True, timeout=1200, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            OSError) as exc:
        raise IngestError(
            f"unreadable video: anonymised re-encode failed: {exc}") from exc


def ingest(video_path: str | Path, run_dir: str | Path) -> dict:
    """Ingest one video file into a run directory (part 05 §§1–2, 6).

    Copies the source to ``input/clip.<ext>`` (metadata-stripped,
    audio-dropped), measures timing from decoded timestamps, runs the
    timeline hygiene report, and writes ``input/timing.json`` plus
    ``logs/probe.json``.

    Returns ``{"clip_path", "timing_path", "probe_path", "timing",
    "run_id"}``. Raises :class:`IngestError` when probing or decoding
    fails — the caller ends the run through the part-11 synthesis path
    (``undetermined: unreadable video``), never with a crash or hang.
    """
    src = Path(video_path)
    base = Path(run_dir)
    run_id = base.name
    input_dir = base / "input"
    logs_dir = base / "logs"
    input_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    if not src.is_file():
        raise IngestError(f"unreadable video: no such file: {src}")
    info = probe(src)  # raises IngestError when unprobable
    name = anonymous_name(src, info)
    clip_path = input_dir / name
    try:
        _stream_copy(src, clip_path)
    except IngestError:
        clip_path = input_dir / "clip.mp4"
        _reencode_copy(src, clip_path)

    timing = measure_timing(clip_path, info)  # raises IngestError
    hygiene = timeline_hygiene(clip_path, timing)  # raises IngestError

    timing_path = input_dir / "timing.json"
    report = write_timing_json(timing, hygiene, timing_path)
    probe_path = logs_dir / "probe.json"
    write_probe_json(src, info, probe_path,
                     copied_to=f"input/{clip_path.name}", run_id=run_id)
    return {
        "clip_path": str(clip_path),
        "timing_path": str(timing_path),
        "probe_path": str(probe_path),
        "timing": report,
        "run_id": run_id,
    }

"""Container probing (part 05 §2).

``probe()`` runs ffprobe over the source file and returns the container
facts the ingest writes to ``logs/probe.json``. The claimed fps is
reported here for the discrepancy log only — it is never used as a
time base (that always comes from decoded timestamps, part 05 §2).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

__all__ = ["IngestError", "probe", "parse_fps"]


class IngestError(RuntimeError):
    """Unreadable or unusable input video.

    The CLI catches this and ends the run through the part-11 synthesis
    path (``undetermined: unreadable video``), never with a crash.
    """


def _need(exe: str) -> str:
    path = shutil.which(exe)
    if path is None:
        raise IngestError(f"unreadable video: required tool {exe!r} not found")
    return path


def parse_fps(text) -> float | None:
    """Parse an ffprobe ``avg_frame_rate`` / ``r_frame_rate`` value.

    Accepts ``"30/1"``, ``"30000/1001"``, or a plain number; returns
    None for ``"0/0"``, empty, or unparsable values.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    try:
        if "/" in s:
            num, _, den = s.partition("/")
            fps = float(num) / float(den)
        else:
            fps = float(s)
    except (ValueError, ZeroDivisionError):
        return None
    if not (fps == fps and fps > 0):  # NaN or non-positive
        return None
    return fps


def probe(video_path: str | Path) -> dict:
    """Probe one container; return format/stream facts plus the fps claim.

    Returns a JSON-serialisable dict with ``format`` (container facts),
    ``video_stream`` (codec, dimensions, fps claims), ``audio_streams``
    (count only — audio is dropped from the agent copy, part 05 §1),
    and ``claimed_fps`` (container claim, discrepancy log only).

    Raises:
        IngestError: ffprobe fails or the file has no video stream.
    """
    src = Path(video_path)
    if not src.is_file():
        raise IngestError(f"unreadable video: no such file: {src}")
    ffprobe = _need("ffprobe")
    try:
        raw = subprocess.run(
            [ffprobe, "-v", "error", "-show_format", "-show_streams",
             "-of", "json", str(src)],
            capture_output=True, text=True, timeout=120, check=True,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            OSError) as exc:
        raise IngestError(f"unreadable video: ffprobe failed: {exc}") from exc
    try:
        info = json.loads(raw)
    except ValueError as exc:
        raise IngestError(
            f"unreadable video: ffprobe output unparsable: {exc}") from exc
    streams = info.get("streams") or []
    video = next((s for s in streams
                  if s.get("codec_type") == "video"), None)
    if video is None:
        raise IngestError("unreadable video: no video stream in container")
    audio = sum(1 for s in streams if s.get("codec_type") == "audio")
    claimed = parse_fps(video.get("avg_frame_rate"))
    if claimed is None:
        claimed = parse_fps(video.get("r_frame_rate"))
    fmt = info.get("format") or {}
    return {
        "format": {
            "format_name": fmt.get("format_name"),
            "duration": fmt.get("duration"),
            "size": fmt.get("size"),
            "bit_rate": fmt.get("bit_rate"),
            "tags": dict(fmt.get("tags") or {}),
        },
        "video_stream": {
            "index": video.get("index"),
            "codec_name": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "pix_fmt": video.get("pix_fmt"),
            "avg_frame_rate": video.get("avg_frame_rate"),
            "r_frame_rate": video.get("r_frame_rate"),
            "duration": video.get("duration"),
            "nb_frames": video.get("nb_frames"),
            "tags": dict(video.get("tags") or {}),
        },
        "audio_streams": audio,
        "claimed_fps": claimed,
    }

"""M2. Video probing, exact frame reads, diffs, contact sheets, normalisation.

Time is measured, not assumed (SPEC section 4, rule 4): fps comes from the
stream's average frame rate as an exact rational, and frames are counted by
decoding when the container does not report a count.
"""

from __future__ import annotations

import json
import math
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

__all__ = [
    "VideoInfo",
    "probe",
    "read_frames",
    "frame_diffs",
    "duplicate_runs",
    "contact_sheet",
    "normalize",
]

_FFPROBE = "ffprobe"
_FFMPEG = "ffmpeg"

# Overlay hook for contact sheets: receives (frame_index, tile image in RGB,
# scale factor from original pixels to tile pixels) and may draw in place or
# return a replacement image.
Overlay = Callable[[int, Image.Image, float], Image.Image | None]

# Decoded-frame cache for short clips: key -> list of HxWx3 uint8 RGB frames.
_FRAME_CACHE: dict[str, list[np.ndarray]] = {}


@dataclass(frozen=True)
class VideoInfo:
    """Basic facts about a video file measured with ffprobe."""

    width: int
    height: int
    fps: Fraction
    frame_count: int
    sar: Fraction
    dar: Fraction
    duration: float
    codec: str
    pix_fmt: str


def _parse_ratio(text: str | None) -> Fraction | None:
    """Parse an ffprobe ratio like "30000/1001" or "16:9" to a Fraction."""
    if not text:
        return None
    sep = "/" if "/" in text else (":" if ":" in text else None)
    if sep is None:
        return None
    num, _, den = text.partition(sep)
    try:
        frac = Fraction(int(num), int(den))
    except (ValueError, ZeroDivisionError):
        return None
    if frac <= 0:
        return None
    return frac


def _run(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run a command, raising a clear error on failure."""
    try:
        proc = subprocess.run(cmd, capture_output=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("command not found: " + cmd[0])
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        detail = tail[-1] if tail else "exit " + str(proc.returncode)
        raise RuntimeError("command failed: " + " ".join(cmd) + ": " + detail)
    return proc


def _decode_count(path: Path, width: int, height: int) -> int:
    """Count frames by decoding the whole video stream."""
    cmd = [
        _FFMPEG,
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-fps_mode",
        "passthrough",
        "-",
    ]
    proc = _run(cmd)
    frame_bytes = width * height * 3
    if len(proc.stdout) % frame_bytes != 0:
        raise RuntimeError("decoder output is not a whole number of frames")
    return len(proc.stdout) // frame_bytes


def probe(path: str | Path) -> VideoInfo:
    """Measure a video file with ffprobe.

    fps is the stream's average frame rate as an exact Fraction. The frame
    count comes from the container when it reports one, otherwise by decoding.
    """
    path = Path(path)
    cmd = [
        _FFPROBE,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,nb_frames,duration,"
        "codec_name,pix_fmt,sample_aspect_ratio,display_aspect_ratio",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    info = json.loads(_run(cmd).stdout.decode("utf-8"))
    streams = info.get("streams", [])
    if not streams:
        raise RuntimeError("no video stream in " + str(path))
    stream = streams[0]
    width = int(stream["width"])
    height = int(stream["height"])
    fps = _parse_ratio(stream.get("avg_frame_rate"))
    if fps is None:
        raise RuntimeError("stream has no usable average frame rate")
    sar = _parse_ratio(stream.get("sample_aspect_ratio")) or Fraction(1, 1)
    dar = _parse_ratio(stream.get("display_aspect_ratio"))
    if dar is None:
        dar = Fraction(width * sar.numerator, height * sar.denominator)
    try:
        frame_count = int(stream.get("nb_frames", ""))
    except (TypeError, ValueError):
        frame_count = _decode_count(path, width, height)
    duration_text = stream.get("duration") or info.get("format", {}).get("duration")
    try:
        duration = float(duration_text)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        duration = frame_count / float(fps)
    return VideoInfo(
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        sar=sar,
        dar=dar,
        duration=duration,
        codec=str(stream.get("codec_name", "")),
        pix_fmt=str(stream.get("pix_fmt", "")),
    )


def _cache_key(path: Path) -> str:
    stat = path.stat()
    return str(path.resolve()) + "@" + str(stat.st_mtime_ns) + ":" + str(stat.st_size)


def _decode_all(path: Path, info: VideoInfo) -> list[np.ndarray]:
    """Decode every frame to HxWx3 uint8 RGB; cache short clips (<= 2 min)."""
    if info.duration <= 120:
        key = _cache_key(path)
        cached = _FRAME_CACHE.get(key)
        if cached is not None:
            return cached
    cmd = [
        _FFMPEG,
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-fps_mode",
        "passthrough",
        "-",
    ]
    raw = _run(cmd).stdout
    frame_bytes = info.width * info.height * 3
    if len(raw) % frame_bytes != 0 or not raw:
        raise RuntimeError("decoder output is not a whole number of frames")
    count = len(raw) // frame_bytes
    frames = [
        np.frombuffer(raw[i * frame_bytes : (i + 1) * frame_bytes], dtype=np.uint8)
        .reshape(info.height, info.width, 3)
        .copy()
        for i in range(count)
    ]
    if info.duration <= 120:
        _FRAME_CACHE[_cache_key(path)] = frames
    return frames


def read_frames(path: str | Path, indices: Sequence[int]) -> dict[int, np.ndarray]:
    """Read exact frames by 0-based index as HxWx3 uint8 RGB arrays.

    Frame N is the N-th decoded frame, whatever the timestamps; frames are
    never sought by time.
    """
    path = Path(path)
    info = probe(path)
    frames = _decode_all(path, info)
    out: dict[int, np.ndarray] = {}
    for index in indices:
        if index < 0 or index >= len(frames):
            raise IndexError("frame index out of range: " + str(index))
        out[index] = frames[index].copy()
    return out


def frame_diffs(path: str | Path) -> np.ndarray:
    """Mean absolute difference between consecutive frames (length frames - 1)."""
    path = Path(path)
    info = probe(path)
    frames = _decode_all(path, info)
    diffs = np.empty(max(len(frames) - 1, 0), dtype=np.float64)
    for i in range(len(frames) - 1):
        diffs[i] = float(
            np.abs(frames[i].astype(np.int16) - frames[i + 1].astype(np.int16)).mean()
        )
    return diffs


def duplicate_runs(
    diffs: np.ndarray | Sequence[float], threshold: float = 1.0
) -> list[tuple[int, int]]:
    """Find maximal runs of near-duplicate frames.

    diffs[i] is the mean difference between frames i and i+1. A run (a, b)
    with b > a means every diff in diffs[a:b] is below threshold, i.e. frames
    a..b form one near-identical chain.
    """
    values = [float(v) for v in diffs]
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, value in enumerate(values):
        if value < threshold:
            if start is None:
                start = i
        else:
            if start is not None:
                runs.append((start, i))
                start = None
    if start is not None:
        runs.append((start, len(values)))
    return runs


def _label_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def contact_sheet(
    path: str | Path,
    frames: Sequence[int],
    *,
    out: str | Path,
    tile_width: int = 320,
    columns: int | None = None,
    crop: tuple[int, int, int, int] | None = None,
    overlay: Overlay | None = None,
) -> Path:
    """Build a labelled grid of up to 30 frame tiles.

    crop is (x1, y1, x2, y2) in original pixel coordinates, applied before
    resizing. Labels are drawn after the final resize. overlay, when given,
    is called with (frame_index, tile image, original-to-tile scale) and may
    draw masks or points on the tile before the label goes on. Tiles are
    laid out left to right, top to bottom in `columns` columns (default
    ceil(sqrt(n))) with no gaps, each exactly tile_width pixels wide.
    """
    wanted = list(frames)
    if len(wanted) > 30:
        raise ValueError("contact sheets hold at most 30 tiles")
    if not wanted:
        raise ValueError("no frames requested")
    if tile_width < 1:
        raise ValueError("tile_width must be positive")
    path = Path(path)
    info = probe(path)
    decoded = read_frames(path, wanted)

    if crop is None:
        x1, y1, x2, y2 = 0, 0, info.width, info.height
    else:
        x1, y1, x2, y2 = crop
    if not (0 <= x1 < x2 <= info.width and 0 <= y1 < y2 <= info.height):
        raise ValueError("crop is outside the frame: " + repr(crop))
    crop_w, crop_h = x2 - x1, y2 - y1
    tile_h = max(1, round(crop_h * tile_width / crop_w))
    scale = tile_width / crop_w

    count = len(wanted)
    cols = columns or math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    sheet = Image.new("RGB", (cols * tile_width, rows * tile_h), (0, 0, 0))
    font = _label_font(18)
    probe_draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))

    for pos, index in enumerate(wanted):
        tile = Image.fromarray(decoded[index][y1:y2, x1:x2]).resize(
            (tile_width, tile_h), Image.BILINEAR
        )
        if overlay is not None:
            replacement = overlay(index, tile, scale)
            if replacement is not None:
                tile = replacement
        label = "f" + str(index)
        box = probe_draw.textbbox((0, 0), label, font=font)
        pad = 5
        box_w = box[2] - box[0] + 2 * pad
        box_h = box[3] - box[1] + 2 * pad
        draw = ImageDraw.Draw(tile)
        draw.rectangle([0, 0, box_w, box_h], fill=(0, 0, 0))
        draw.text((pad - box[0], pad - box[1]), label, font=font, fill=(255, 255, 255))
        sheet.paste(tile, ((pos % cols) * tile_width, (pos // cols) * tile_h))

    out_path = Path(out)
    if out_path.parent != Path(""):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path


def normalize(src: str | Path, dst: str | Path) -> VideoInfo:
    """Re-encode to H.264 (libx264, yuv420p, CFR at the source rate).

    Keeps every frame in order, the stored pixel grid (odd sizes gain one
    padded pixel on the right/bottom), and the source SAR exactly. Drops
    audio and container metadata.
    """
    src_path, dst_path = Path(src), Path(dst)
    info = probe(src_path)
    rate = str(info.fps.numerator) + "/" + str(info.fps.denominator)
    # The setsar filter re-rationalises to denominator <= 100 (200/219 would
    # become 21/23), so the exact SAR goes straight to the encoder instead.
    sar = "sar=" + str(info.sar.numerator) + "\\:" + str(info.sar.denominator)
    cmd = [
        _FFMPEG,
        "-y",
        "-v",
        "error",
        "-i",
        str(src_path),
        "-map",
        "0:v:0",
        "-vf",
        "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-fps_mode",
        "cfr",
        "-r",
        rate,
        "-c:v",
        "libx264",
        "-x264-params",
        sar,
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-an",
        "-map_metadata",
        "-1",
        str(dst_path),
    ]
    _run(cmd)
    return probe(dst_path)

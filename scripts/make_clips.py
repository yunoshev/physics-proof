# generated from brief/03 · spec-sha256:a66623e9ea850f11828f324b0c775f574e5879bdb22ec1cf39bb06385188a3d0 · plan-sha256:2d4a2718f3d74cac2e14a853ff4a8c3b7053edecd6fe6c4545e341ae5b11e35e
"""Clip preparation for test clips A and B (part 03).

Produces the two Apollo clips stored in the repo:
- Clip A: original "jump salute", 352x240, 29.97 fps measured, 466 frames,
  metadata stripped, no audio.
- Clip B: A slowed x1.5 with motion interpolation back to the same frame
  rate (697 frames), otherwise identical provenance to A.

Ground-truth parameters (source URL, slow-down factor, frame counts) live
ONLY in this script. The analysis runtime (src/) and the agent prompt must
never import or read this module (structural test in
tests/test_make_clips.py enforces the boundary; see brief part 03 section 5).

Clip C (wall run) is third-party, rights-encumbered, and is NEVER stored in
the repo; it is passed to the analysis and harness by local path only.

Method notes (skills/video-ffmpeg.md):
- Never trust the container fps; verification measures fps from decoded
  packet timestamps (median inter-frame delta).
- Never force a constant frame rate with -r / fps= filters during
  generation: Clip A is built by piping raw frames one-frame-in/one-frame-out
  at the source timing and only labelling the output rate.
- Clip B uses motion-compensated interpolation (minterpolate, mci), so it
  has no duplicated frames and a normal fps; only physics plus an
  independent clock can tell it is slowed (brief parts 02 section 5, 08 R-T3).
- Both outputs drop audio (-an) and container metadata (-map_metadata -1).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# --- Ground truth (harness/test-clip parameters; never importable by src/) ---

ALSJ_PAGE_URL = "https://www.apollojournals.org/alsj/a16/video16.html"
ALSJ_SOURCE_URL = "https://www.apollojournals.org/alsj/a16/a16salute.mpg"

CLIP_A_FILENAME = "clip_a.mp4"
CLIP_B_FILENAME = "clip_b.mp4"

A_WIDTH = 352
A_HEIGHT = 240
A_FPS_NUM = 30000
A_FPS_DEN = 1001  # 29.97 fps measured
A_FRAMES = 466  # ~= 15.5 s at 29.97 fps

SLOW_FACTOR = 1.5
B_FRAMES = 697  # ~= 15.5 x 1.5 s at 29.97 fps

# Extra stretched frames generated before trimming B to its exact target
# count. minterpolate's output length is duration-boundary-sensitive (off by
# one or two frames depending on rounding), so B is generated slightly long
# and cut to exactly `out_frames` with -frames:v (no padding, no duplicates).
TRIM_MARGIN_FRAMES = 3

# Verification tolerances (generation-side only, not acceptance criteria).
FPS_TOLERANCE_FRAC = 0.02  # A measured fps must be within 2% of nominal
AB_FPS_MATCH_FRAC = 0.01  # B measured fps must match A within 1%
AB_DURATION_RATIO_TOL = 0.05  # B/A duration must equal SLOW_FACTOR +/- 5%

# Near-duplicate ("suspect") definition shared with part 05's timeline
# hygiene report: average-hash Hamming distance at or below this threshold
# on 8x8 luminance thumbnails. Labelled suspicion only, never evidence.
NEAR_DUP_HAMMING_THRESHOLD = 5

DEFAULT_CRF = 18
DEFAULT_PRESET = "medium"

IDENTIFYING_TAG_KEYS = frozenset(
    {
        "title",
        "comment",
        "description",
        "artist",
        "author",
        "album",
        "genre",
        "creation_time",
        "creation-time",
        "year",
        "date",
        "location",
        "com.apple.quicktime.location.iso6709",
    }
)


class ClipPrepError(RuntimeError):
    """Raised when a clip cannot be downloaded, generated, or verified."""


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise ClipPrepError(
            f"required tool {name!r} not found on PATH; install ffmpeg"
        )
    return path


def _run(cmd: list[str], timeout_s: float = 600.0) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise ClipPrepError(f"command timed out: {cmd[0]} {' '.join(cmd[1:4])}…") from exc


def _check(result: subprocess.CompletedProcess, what: str) -> None:
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-5:]
        raise ClipPrepError(f"{what} failed: {' | '.join(tail)}")


def fps_rate(num: int = A_FPS_NUM, den: int = A_FPS_DEN) -> str:
    """ffmpeg rate string, e.g. '30000/1001'."""
    return f"{num}/{den}"


def nominal_fps(num: int = A_FPS_NUM, den: int = A_FPS_DEN) -> float:
    """Nominal frame rate as a float."""
    return num / den


def download_source(url: str = ALSJ_SOURCE_URL, dest: Path | str | None = None) -> Path:
    """Download the Apollo source file; returns the local path.

    Raises ClipPrepError on network or HTTP failure.
    """
    _require_tool("ffmpeg")  # fail fast before a long download
    if dest is None:
        tmp = tempfile.NamedTemporaryFile(
            prefix="a16salute-", suffix=".mpg", delete=False
        )
        tmp.close()
        dest = Path(tmp.name)
    dest = Path(dest)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as fh:
            shutil.copyfileobj(resp, fh)
    except Exception as exc:
        raise ClipPrepError(f"could not download {url}: {exc}") from exc
    if dest.stat().st_size == 0:
        raise ClipPrepError(f"downloaded empty file from {url}")
    return dest


def ffprobe_json(path: Path | str) -> dict:
    """Full ffprobe stream/format report as a dict."""
    _require_tool("ffprobe")
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
    )
    _check(result, f"ffprobe {path}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ClipPrepError(f"ffprobe returned invalid JSON for {path}") from exc


def probe_streams(path: Path | str) -> dict:
    """Container-level facts: sizes, codecs, audio presence, metadata tags."""
    info = ffprobe_json(path)
    video = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    audio = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not video:
        raise ClipPrepError(f"no video stream in {path}")
    v0 = video[0]
    return {
        "width": int(v0["width"]),
        "height": int(v0["height"]),
        "codec": v0.get("codec_name"),
        "pix_fmt": v0.get("pix_fmt"),
        "video_stream_tags": dict(v0.get("tags") or {}),
        "format_tags": dict((info.get("format") or {}).get("tags") or {}),
        "audio_streams": len(audio),
        "duration_s": float((info.get("format") or {}).get("duration") or "nan"),
    }


def identifying_tags_present(path: Path | str) -> list[str]:
    """Identifying metadata tag keys found on the file (empty when stripped)."""
    probe = probe_streams(path)
    found = []
    for scope, tags in (
        ("format", probe["format_tags"]),
        ("video-stream", probe["video_stream_tags"]),
    ):
        for key in tags:
            if key.lower() in IDENTIFYING_TAG_KEYS:
                found.append(f"{scope}:{key}")
    return found


def measured_fps(path: Path | str) -> float:
    """Measured frame rate: 1 / median(sorted packet PTS delta).

    Uses decoded packet timestamps, never the container's claimed fps
    (skills/video-ffmpeg.md, brief part 05 section 2).
    """
    _require_tool("ffprobe")
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "packet=pts_time",
            "-of",
            "csv=p=0",
            str(path),
        ]
    )
    _check(result, f"ffprobe packets {path}")
    pts = sorted(float(line) for line in result.stdout.split() if line.strip())
    deltas = [b - a for a, b in zip(pts, pts[1:]) if b - a > 0]
    if not deltas:
        raise ClipPrepError(f"could not measure fps of {path}: no PTS deltas")
    return 1.0 / statistics.median(deltas)


def _decode_raw(
    path: Path | str, width: int, height: int, pix_fmt: str, vf: str | None = None
) -> tuple[bytes, int, int]:
    """Decode to raw frames; returns (all bytes, frame bytes, frame count)."""
    _require_tool("ffmpeg")
    cmd = ["ffmpeg", "-v", "error", "-i", str(path)]
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-f", "rawvideo", "-pix_fmt", pix_fmt, "-"]
    proc = subprocess.run(cmd, capture_output=True, timeout=600.0, check=False)
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-5:]
        raise ClipPrepError(f"decode {path} failed: {' | '.join(tail)}")
    channels = 3 if pix_fmt == "rgb24" else 1
    frame_bytes = width * height * channels
    data = proc.stdout
    if len(data) % frame_bytes != 0:
        raise ClipPrepError(f"decode {path}: byte count not a frame multiple")
    return data, frame_bytes, len(data) // frame_bytes


def _average_hash(thumb: bytes) -> int:
    """64-bit average hash of 64 luminance bytes."""
    mean = sum(thumb) / 64.0
    bits = 0
    for i, px in enumerate(thumb):
        if px > mean:
            bits |= 1 << i
    return bits


def duplicate_report(
    path: Path | str, width: int, height: int
) -> dict[str, object]:
    """Shared duplicate definition (brief part 05 section 4).

    - 'confirmed': indices i>0 whose decoded bytes exactly equal frame i-1.
    - 'suspect': indices i>0 whose 8x8-luminance average hash is within
      NEAR_DUP_HAMMING_THRESHOLD bits but bytes differ (slow genuine motion
      must never be reported as duplicated, so these stay suspicion only).
    """
    data, frame_bytes, n = _decode_raw(path, width, height, "rgb24")
    confirmed: list[int] = []
    prev = data[:frame_bytes]
    for i in range(1, n):
        cur = data[i * frame_bytes : (i + 1) * frame_bytes]
        if cur == prev:
            confirmed.append(i)
        prev = cur
    thumbs, thumb_bytes, tn = _decode_raw(
        path, 8, 8, "gray", vf="scale=8:8,format=gray"
    )
    assert tn == n, f"thumbnail decode mismatch: {tn} vs {n}"
    hashes = [_average_hash(thumbs[i * thumb_bytes : (i + 1) * thumb_bytes]) for i in range(n)]
    suspect: list[int] = []
    for i in range(1, n):
        if i in confirmed:
            continue
        if bin(hashes[i] ^ hashes[i - 1]).count("1") <= NEAR_DUP_HAMMING_THRESHOLD:
            suspect.append(i)
    return {"frame_count": n, "confirmed": confirmed, "suspect": suspect}


def _encode_args(
    out_path: Path, preset: str, crf: int
) -> list[str]:
    """Shared output encoding: H.264, no audio, no metadata."""
    return [
        "-an",
        "-map_metadata",
        "-1",
        "-fflags",
        "+bitexact",
        "-flags:v",
        "+bitexact",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        str(crf),
        "-preset",
        preset,
        "-movflags",
        "+faststart",
        str(out_path),
    ]


def make_clip_a(
    source: Path | str | None = None,
    out_path: Path | str = CLIP_A_FILENAME,
    width: int = A_WIDTH,
    height: int = A_HEIGHT,
    frames: int = A_FRAMES,
    fps_num: int = A_FPS_NUM,
    fps_den: int = A_FPS_DEN,
    preset: str = DEFAULT_PRESET,
    crf: int = DEFAULT_CRF,
) -> Path:
    """Build Clip A: first `frames` source frames at `width`x`height`.

    The source is decoded to raw frames (one-frame-in/one-frame-out at the
    source timing, no -r / fps= rate forcing) and piped into the encoder,
    which only labels the output rate. When `source` is None the Apollo
    source is downloaded first. The output is verified before return.
    """
    _require_tool("ffmpeg")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cleanup_source = source is None
    src = Path(source) if source is not None else download_source()
    try:
        decode_cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(src),
            "-vf",
            f"scale={width}:{height}",
            "-frames:v",
            str(frames),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
        encode_cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-framerate",
            fps_rate(fps_num, fps_den),
            "-i",
            "-",
        ] + _encode_args(out_path, preset, crf)
        decoder = subprocess.Popen(
            decode_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            encoder = subprocess.run(
                encode_cmd,
                stdin=decoder.stdout,
                capture_output=True,
                timeout=900.0,
                check=False,
            )
        finally:
            if decoder.stdout is not None:
                decoder.stdout.close()
            decoder.wait(timeout=60)
        if decoder.returncode != 0:
            tail = (decoder.stderr.read().decode("utf-8", "replace").strip().splitlines() or [""])[
                -5:
            ]
            raise ClipPrepError(f"clip A decode failed: {' | '.join(tail)}")
        if encoder.returncode != 0:
            tail = encoder.stderr.decode("utf-8", "replace").strip().splitlines()[-5:]
            raise ClipPrepError(f"clip A encode failed: {' | '.join(tail)}")
    finally:
        if cleanup_source:
            src.unlink(missing_ok=True)
    verify_clip_a(
        out_path, width=width, height=height, frames=frames,
        fps_num=fps_num, fps_den=fps_den,
    )
    return out_path


def make_clip_b(
    clip_a: Path | str,
    out_path: Path | str = CLIP_B_FILENAME,
    slow_factor: float = SLOW_FACTOR,
    out_frames: int | None = B_FRAMES,
    fps_num: int = A_FPS_NUM,
    fps_den: int = A_FPS_DEN,
    preset: str = DEFAULT_PRESET,
    crf: int = DEFAULT_CRF,
) -> Path:
    """Build Clip B: Clip A slowed x`slow_factor` with motion interpolation.

    setpts stretches timestamps, then minterpolate (motion-compensated)
    synthesises intermediate frames back at the same frame rate, so B has no
    duplicated frames, the same measured fps as A, and no metadata hint that
    it was slowed. The output is verified before return.
    """
    _require_tool("ffmpeg")
    clip_a = Path(clip_a)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    probe_a = probe_streams(clip_a)
    dup_a = duplicate_report(clip_a, probe_a["width"], probe_a["height"])
    n_in = int(dup_a["frame_count"])
    if n_in == 0:
        raise ClipPrepError(f"clip A {clip_a} decoded to zero frames")
    if out_frames is None:
        out_frames = round(n_in * slow_factor)
    if abs(out_frames / n_in - slow_factor) / slow_factor > 0.05:
        raise ClipPrepError(
            f"target {out_frames} frames from {n_in} is not a x{slow_factor} slow-down"
        )
    # Stretch slightly past the target so the boundary-sensitive
    # minterpolate length always covers it; -frames:v then cuts exactly.
    stretch = (out_frames + TRIM_MARGIN_FRAMES) / n_in
    filt = (
        f"setpts={stretch}*PTS,"
        f"minterpolate=fps={fps_rate(fps_num, fps_den)}"
        ":mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
    )
    cmd = (
        ["ffmpeg", "-v", "error", "-y", "-i", str(clip_a), "-vf", filt,
         "-frames:v", str(out_frames)]
        + _encode_args(out_path, preset, crf)
    )
    result = _run(cmd, timeout_s=1800.0)
    _check(result, "clip B retime encode")
    verify_clip_b(
        out_path, clip_a, slow_factor=slow_factor, out_frames=out_frames,
        fps_num=fps_num, fps_den=fps_den,
    )
    return out_path


def verify_clip_a(
    path: Path | str,
    width: int = A_WIDTH,
    height: int = A_HEIGHT,
    frames: int = A_FRAMES,
    fps_num: int = A_FPS_NUM,
    fps_den: int = A_FPS_DEN,
) -> dict[str, object]:
    """Assert Clip A properties; returns the measured stats dict."""
    probe = probe_streams(path)
    if (probe["width"], probe["height"]) != (width, height):
        raise ClipPrepError(
            f"clip A size {probe['width']}x{probe['height']}, expected {width}x{height}"
        )
    if probe["audio_streams"] != 0:
        raise ClipPrepError("clip A must have no audio stream")
    leaked = identifying_tags_present(path)
    if leaked:
        raise ClipPrepError(f"clip A leaks metadata tags: {leaked}")
    fps = measured_fps(path)
    if abs(fps - nominal_fps(fps_num, fps_den)) / nominal_fps(fps_num, fps_den) > FPS_TOLERANCE_FRAC:
        raise ClipPrepError(
            f"clip A measured fps {fps:.4f} not within {FPS_TOLERANCE_FRAC:.0%} "
            f"of {nominal_fps(fps_num, fps_den):.4f}"
        )
    dup = duplicate_report(path, width, height)
    if int(dup["frame_count"]) != frames:
        raise ClipPrepError(
            f"clip A has {dup['frame_count']} frames, expected {frames}"
        )
    if dup["confirmed"]:
        raise ClipPrepError(
            f"clip A has confirmed duplicates at {dup['confirmed'][:8]}"
        )
    return {
        "width": width,
        "height": height,
        "frame_count": dup["frame_count"],
        "measured_fps": fps,
        "duration_s": int(dup["frame_count"]) / fps,
        "confirmed_duplicates": dup["confirmed"],
        "suspect_near_duplicates": dup["suspect"],
        "audio_streams": 0,
        "identifying_tags": leaked,
    }


def verify_clip_b(
    path: Path | str,
    clip_a: Path | str,
    slow_factor: float = SLOW_FACTOR,
    out_frames: int | None = B_FRAMES,
    fps_num: int = A_FPS_NUM,
    fps_den: int = A_FPS_DEN,
) -> dict[str, object]:
    """Assert Clip B properties against Clip A; returns stats dict."""
    probe_b = probe_streams(path)
    probe_a = probe_streams(clip_a)
    for key in ("width", "height", "codec", "pix_fmt"):
        if probe_b[key] != probe_a[key]:
            raise ClipPrepError(
                f"clip B {key} {probe_b[key]!r} differs from clip A {probe_a[key]!r}: "
                "A and B must differ only through motion"
            )
    if probe_b["audio_streams"] != 0:
        raise ClipPrepError("clip B must have no audio stream")
    leaked = identifying_tags_present(path)
    if leaked:
        raise ClipPrepError(f"clip B leaks metadata tags: {leaked}")
    if dict(probe_b["format_tags"]) != dict(probe_a["format_tags"]):
        raise ClipPrepError("clip B container tags differ from clip A")
    if dict(probe_b["video_stream_tags"]) != dict(probe_a["video_stream_tags"]):
        raise ClipPrepError("clip B stream tags differ from clip A")
    fps_b = measured_fps(path)
    fps_a = measured_fps(clip_a)
    if abs(fps_b - fps_a) / fps_a > AB_FPS_MATCH_FRAC:
        raise ClipPrepError(
            f"clip B measured fps {fps_b:.4f} does not match clip A {fps_a:.4f}"
        )
    if abs(fps_b - nominal_fps(fps_num, fps_den)) / nominal_fps(fps_num, fps_den) > FPS_TOLERANCE_FRAC:
        raise ClipPrepError(f"clip B measured fps {fps_b:.4f} off nominal rate")
    dup = duplicate_report(path, probe_b["width"], probe_b["height"])
    if out_frames is not None and int(dup["frame_count"]) != out_frames:
        raise ClipPrepError(
            f"clip B has {dup['frame_count']} frames, expected {out_frames}"
        )
    if dup["confirmed"]:
        raise ClipPrepError(
            f"clip B has confirmed duplicates at {dup['confirmed'][:8]}"
        )
    dur_b = int(dup["frame_count"]) / fps_b
    dur_a = probe_a["duration_s"]
    if not math.isnan(dur_a) and dur_a > 0:
        ratio = dur_b / dur_a
        if abs(ratio - slow_factor) / slow_factor > AB_DURATION_RATIO_TOL:
            raise ClipPrepError(
                f"clip B/A duration ratio {ratio:.4f} != slow factor {slow_factor}"
            )
    return {
        "width": probe_b["width"],
        "height": probe_b["height"],
        "frame_count": dup["frame_count"],
        "measured_fps": fps_b,
        "duration_s": dur_b,
        "confirmed_duplicates": dup["confirmed"],
        "suspect_near_duplicates": dup["suspect"],
        "audio_streams": 0,
        "identifying_tags": leaked,
    }


def main(argv: list[str] | None = None) -> dict[str, object]:
    """CLI: download (or reuse --source) the Apollo file, build A then B.

    Writes <out-dir>/clip_a.mp4 and <out-dir>/clip_b.mp4 (production spec
    values) and prints a JSON summary. Raises ClipPrepError on any failure.
    """
    parser = argparse.ArgumentParser(
        description="Prepare test clips A (original) and B (x1.5 interpolated slow)."
    )
    parser.add_argument("--out-dir", default="clips", help="output directory")
    parser.add_argument(
        "--source",
        default=None,
        help="local source file to use instead of downloading the ALSJ file",
    )
    parser.add_argument("--preset", default=DEFAULT_PRESET)
    parser.add_argument("--crf", type=int, default=DEFAULT_CRF)
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clip_a = out_dir / CLIP_A_FILENAME
    clip_b = out_dir / CLIP_B_FILENAME

    make_clip_a(
        source=args.source, out_path=clip_a, preset=args.preset, crf=args.crf
    )
    make_clip_b(clip_a, out_path=clip_b, preset=args.preset, crf=args.crf)

    stats_a = verify_clip_a(clip_a)
    stats_b = verify_clip_b(clip_b, clip_a)
    summary = {
        "clip_a": str(clip_a),
        "clip_b": str(clip_b),
        "source": args.source or ALSJ_SOURCE_URL,
        "stats_a": stats_a,
        "stats_b": stats_b,
    }
    print(json.dumps(summary, indent=2, default=str))
    return summary


if __name__ == "__main__":
    try:
        main()
    except ClipPrepError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

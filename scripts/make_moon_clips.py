"""E1. Download the Apollo 16 salute clip and build the A/B acceptance clips.

Source: Apollo Lunar Surface Journal page for Apollo 16 video (SPEC 5),
file ``a16salute.mpg`` linked from that page. The script downloads it once,
checks size and decodability, then writes ``examples/moon/A.mp4`` (H.264
re-encode at the probe-measured frame rate) and ``examples/moon/B.mp4``
(the same clip slowed x1.5 with motion interpolation back to A's rate),
plus ``examples/moon/SOURCE.md`` with the source and exact commands.

Encoder flags are fixed, so running twice gives bit-identical files.
``--dry-run`` prints the ffmpeg commands without touching the network.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "examples" / "moon"
PAGE_URL = "https://www.apollojournals.org/alsj/a16/video16.html"
SOURCE_URL = "https://www.apollojournals.org/alsj/a16/a16salute.mpg"
SOURCE_NAME = "a16salute.mpg"
SLOWDOWN = 1.5
#: Lower bound for the download: the page advertises ~2.7 MB, so anything
#: much smaller is an error page, not the clip.
MIN_BYTES = 2_000_000
#: Rate and SAR measured 2026-10-27; the real run re-measures both with
#: video.probe and --dry-run shows these values. They must equal the probe
#: result or the dry-run output is stale.
DRY_RUN_FPS = Fraction(30000, 1001)
DRY_RUN_SAR = (200, 219)

_FFMPEG = "ffmpeg"
_FFPROBE = "ffprobe"


def _need_tool(name: str) -> None:
    """Exit with a clear message when an external tool is missing."""
    if shutil.which(name) is None:
        print("missing required tool: " + name, flush=True)
        raise SystemExit(3)


def measured_fps(src: Path) -> Fraction:
    """Frame rate of src via physics_proof.video.probe (SPEC 5: measured)."""
    from physics_proof.video import probe

    fps = probe(src).fps
    return Fraction(fps.numerator, fps.denominator)


def build_a_cmd(src: Path, dst: Path, fps: Fraction,
                sar: tuple[int, int]) -> list[str]:
    """ffmpeg command for clip A: H.264 re-encode at the measured rate."""
    rate = str(fps.numerator) + "/" + str(fps.denominator)
    sar_text = "sar=" + str(sar[0]) + "\\:" + str(sar[1])
    return [
        _FFMPEG, "-y", "-v", "error",
        "-i", str(src),
        "-map", "0:v:0",
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-fps_mode", "cfr",
        "-r", rate,
        "-c:v", "libx264",
        "-x264-params", sar_text,
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "medium",
        "-an",
        "-map_metadata", "-1",
        str(dst),
    ]


def build_b_cmd(src: Path, dst: Path, fps: Fraction) -> list[str]:
    """ffmpeg command for clip B: slowed xSLOWDOWN, interpolated to fps."""
    rate = str(fps.numerator) + "/" + str(fps.denominator)
    filters = "setpts=" + str(SLOWDOWN) + "*PTS,minterpolate=fps=" + rate + ":mi_mode=mci"
    return [
        _FFMPEG, "-y", "-v", "error",
        "-i", str(src),
        "-vf", filters,
        "-fps_mode", "cfr",
        "-r", rate,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "medium",
        "-an",
        "-map_metadata", "-1",
        str(dst),
    ]


def source_sar(src: Path) -> tuple[int, int]:
    """Sample aspect ratio of src from physics_proof.video.probe."""
    from physics_proof.video import probe

    sar = probe(src).sar
    return sar.numerator, sar.denominator


def run(cmd: list[str]) -> None:
    """Run cmd, printing it first; raise SystemExit(3) on failure."""
    print("+ " + " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = proc.stderr.strip().splitlines()
        detail = tail[-1] if tail else "exit " + str(proc.returncode)
        print("command failed: " + detail, flush=True)
        raise SystemExit(3)


def download(url: str, dst: Path) -> int:
    """Fetch url to dst; return the byte count."""
    print("downloading " + url, flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "physics-proof/E1"})
    with urllib.request.urlopen(request) as response, open(dst, "wb") as handle:
        shutil.copyfileobj(response, handle)
    size = dst.stat().st_size
    print("downloaded " + str(size) + " bytes", flush=True)
    return size


def check_download(path: Path) -> None:
    """Refuse tiny downloads, then refuse files that do not decode."""
    from physics_proof.video import probe, read_frames

    size = path.stat().st_size
    if size < MIN_BYTES:
        print("download too small (" + str(size) + " bytes); not the clip", flush=True)
        raise SystemExit(3)
    info = probe(path)
    frames = read_frames(path, [0, info.frame_count - 1])
    for index, frame in frames.items():
        if frame.size == 0:
            print("frame " + str(index) + " decoded empty", flush=True)
            raise SystemExit(3)
    print("source ok: " + str(info.width) + "x" + str(info.height) + " "
          + str(info.fps) + " fps, " + str(info.frame_count) + " frames", flush=True)


def sha256(path: Path) -> str:
    """Hex sha256 of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ffmpeg_version() -> str:
    """One-line ffmpeg version for SOURCE.md."""
    proc = subprocess.run([_FFMPEG, "-version"], capture_output=True, text=True)
    return proc.stdout.splitlines()[0] if proc.returncode == 0 else "unknown"


def shell_quote(cmd: list[str]) -> str:
    """Render a command with minimal shell quoting for SOURCE.md."""
    parts = []
    for arg in cmd:
        needs = any(char in arg for char in " :*=")
        parts.append("'" + arg + "'" if needs else arg)
    return " ".join(parts)


def write_source_md(out_dir: Path, fps: Fraction, a_frames: int,
                    b_frames: int, a_cmd: list[str], b_cmd: list[str]) -> Path:
    """Write SOURCE.md with the source, note and exact commands."""
    text = (
        "# Source of examples/moon\n"
        "\n"
        "Source file: `" + SOURCE_NAME + "` from the Apollo Lunar Surface Journal,\n"
        "Apollo 16 Video Library page " + PAGE_URL + " (direct file " + SOURCE_URL + ").\n"
        "The page offers \"a short, 2.7 MB MPEG-1 clip of better resolution and at\n"
        "29.97 fps, showing only the two jumps\" of John Young's jump salute\n"
        "(Apollo 16, 21 April 1972).\n"
        "\n"
        "Rights: NASA footage; the ALSJ page states its video clips are in the\n"
        "public domain (\"The video clips are in the public domain\").\n"
        "Transcript/commentary on that site is separately copyrighted and is\n"
        "not reproduced here.\n"
        "\n"
        "## How A.mp4 and B.mp4 were made\n"
        "\n"
        "A.mp4 re-encodes the download to H.264 (yuv420p, CRF 18), no audio,\n"
        "no metadata (`-map_metadata -1`), at the frame rate measured by\n"
        "`physics_proof.video.probe`: " + str(fps) + " fps (" + str(a_frames) + " frames).\n"
        "B.mp4 slows A by x" + str(SLOWDOWN) + " (`setpts=" + str(SLOWDOWN) + "*PTS`) and\n"
        "interpolates (`minterpolate`) back to A's rate (" + str(b_frames) + " frames).\n"
        "\n"
        "Exact commands (run from the repository root):\n"
        "\n"
        "    " + shell_quote(a_cmd) + "\n"
        "    " + shell_quote(b_cmd) + "\n"
        "\n"
        "Built with: " + ffmpeg_version() + "\n"
        "Encoder flags are fixed, so re-running this script gives bit-identical\n"
        "files on the same ffmpeg build (verified by comparing sha256).\n"
    )
    path = out_dir / "SOURCE.md"
    path.write_text(text, encoding="utf-8")
    return path


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Build the E1 Moon clips.")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the ffmpeg commands without downloading")
    parser.add_argument("--out-dir", default=str(OUT_DIR),
                        help="directory for A.mp4, B.mp4, SOURCE.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: download, check, encode A and B, write SOURCE.md."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    _need_tool(_FFMPEG)
    _need_tool(_FFPROBE)
    out_dir = Path(args.out_dir)
    if args.dry_run:
        print("# dry run: no download, no files written", flush=True)
        print("# rate/sar shown are the probe-measured values for this source",
              flush=True)
        a_cmd = build_a_cmd(Path(SOURCE_NAME), out_dir / "A.mp4",
                            DRY_RUN_FPS, DRY_RUN_SAR)
        b_cmd = build_b_cmd(out_dir / "A.mp4", out_dir / "B.mp4", DRY_RUN_FPS)
        for cmd in (a_cmd, b_cmd):
            print("+ " + " ".join(cmd), flush=True)
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="moon-src-") as tmp:
        src = Path(tmp) / SOURCE_NAME
        download(SOURCE_URL, src)
        check_download(src)
        fps = measured_fps(src)
        a_cmd = build_a_cmd(src, out_dir / "A.mp4", fps, source_sar(src))
        run(a_cmd)
        b_cmd = build_b_cmd(out_dir / "A.mp4", out_dir / "B.mp4", fps)
        run(b_cmd)
    from physics_proof.video import probe

    a_info = probe(out_dir / "A.mp4")
    b_info = probe(out_dir / "B.mp4")
    write_source_md(out_dir, fps, a_info.frame_count, b_info.frame_count,
                    a_cmd, b_cmd)
    print("A.mp4: " + str(a_info.fps) + " fps, " + str(a_info.frame_count)
          + " frames, sha256 " + sha256(out_dir / "A.mp4"), flush=True)
    print("B.mp4: " + str(b_info.fps) + " fps, " + str(b_info.frame_count)
          + " frames, sha256 " + sha256(out_dir / "B.mp4"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

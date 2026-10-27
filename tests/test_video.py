"""M2 probes (offline): synthetic clips with burned-in frame numbers."""

from __future__ import annotations

import math
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from physics_proof import video
from physics_proof.video import VideoInfo

FPS = Fraction(30000, 1001)
N_FRAMES = 120
W, H = 320, 240
MAD_LIMIT = 5.0


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def _digit_pngs(directory: Path, count: int = N_FRAMES) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=100)
    for i in range(count):
        img = Image.new("RGB", (W, H), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((W // 2, H // 2), str(i), font=font, fill=(0, 0, 0), anchor="mm")
        img.save(directory / ("frame_%03d.png" % i))
    return directory


def _png(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"))


def _mad(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


@pytest.fixture(scope="session")
def clips(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Build the synthetic clips once per session."""
    root = tmp_path_factory.mktemp("m2")
    pngs = _digit_pngs(root / "pngs")
    clip = root / "clip.mp4"
    _ffmpeg(
        "-framerate", "30000/1001", "-i", str(pngs / "frame_%03d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-fps_mode", "cfr", "-r", "30000/1001", str(clip),
    )
    # This ffmpeg's setsar filter rounds 200/219 to 21/23, so the exact SAR
    # is stamped with the h264_metadata bitstream filter instead.
    sar = root / "sar.mp4"
    _ffmpeg(
        "-i", str(clip), "-c:v", "copy",
        "-bsf:v", "h264_metadata=sample_aspect_ratio=200/219", str(sar),
    )
    # MPEG-2 only stores a fixed table of aspects, so this source is 1:1.
    mpeg2 = root / "clip.mpg"
    _ffmpeg(
        "-i", str(clip),
        "-c:v", "mpeg2video", "-pix_fmt", "yuv420p",
        "-fps_mode", "cfr", "-r", "30000/1001", str(mpeg2),
    )
    mjpeg = root / "clip.avi"
    _ffmpeg(
        "-i", str(clip), "-c:v", "mjpeg",
        "-fps_mode", "cfr", "-r", "30000/1001", str(mjpeg),
    )
    dup_dir = root / "dup_pngs"
    dup_dir.mkdir()
    for i in range(40):
        j = 30 if i in (31, 32) else i
        color = ((j * 37) % 210 + 20, (j * 91) % 210 + 20, (j * 53) % 210 + 20)
        Image.new("RGB", (160, 120), color).save(dup_dir / ("f_%02d.png" % i))
    dup = root / "dup.mp4"
    _ffmpeg(
        "-framerate", "24", "-i", str(dup_dir / "f_%02d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-fps_mode", "cfr", "-r", "24", str(dup),
    )
    odd_dir = root / "odd_pngs"
    odd_dir.mkdir()
    for i in range(10):
        Image.new("RGB", (319, 239), (i * 20 % 256, 40, 90)).save(
            odd_dir / ("o_%02d.png" % i)
        )
    odd = root / "odd.mov"
    _ffmpeg(
        "-framerate", "24", "-i", str(odd_dir / "o_%02d.png"),
        "-c:v", "png", "-fps_mode", "cfr", "-r", "24", str(odd),
    )
    return {
        "pngs": pngs,
        "clip": clip,
        "sar": sar,
        "mpeg2": mpeg2,
        "mjpeg": mjpeg,
        "dup": dup,
        "odd": odd,
        "root": root,
    }


def test_read_frames_show_digits(clips: dict[str, Path]) -> None:
    """Probe 1: every 10th decoded frame shows its own index."""
    indices = list(range(0, N_FRAMES, 10))
    frames = video.read_frames(clips["clip"], indices)
    assert set(frames) == set(indices)
    for i in indices:
        assert frames[i].shape == (H, W, 3)
        assert frames[i].dtype == np.uint8
        assert _mad(frames[i], _png(clips["pngs"] / ("frame_%03d.png" % i))) < MAD_LIMIT


def test_probe_fps_count_duration(clips: dict[str, Path]) -> None:
    """Probe 2: exact fps, frame count, duration within one frame."""
    info = video.probe(clips["clip"])
    assert isinstance(info, VideoInfo)
    assert info.fps == FPS
    assert info.frame_count == N_FRAMES
    assert info.width == W and info.height == H
    assert info.codec == "h264"
    expected = N_FRAMES * 1001 / 30000
    assert abs(info.duration - expected) <= (1001 / 30000)
    assert info.sar == Fraction(1, 1)
    assert info.dar == Fraction(4, 3)


def test_probe_sar(clips: dict[str, Path]) -> None:
    """Probe 3: non-square pixels report SAR and the matching DAR."""
    info = video.probe(clips["sar"])
    assert info.sar == Fraction(200, 219)
    assert info.dar == info.sar * info.width / info.height


def test_normalize_mpeg2(clips: dict[str, Path], tmp_path: Path) -> None:
    """Probe 4: MPEG-2 in, H.264 out, same frames in the same order."""
    dst = tmp_path / "norm_mpeg2.mp4"
    info = video.normalize(clips["mpeg2"], dst)
    assert info.codec == "h264"
    assert info.pix_fmt == "yuv420p"
    assert info.frame_count == N_FRAMES
    assert (info.width, info.height) == (W, H)
    assert info.fps == FPS
    assert info.sar == Fraction(1, 1)
    frames = video.read_frames(dst, list(range(0, N_FRAMES, 10)))
    for i in range(0, N_FRAMES, 10):
        assert _mad(frames[i], _png(clips["pngs"] / ("frame_%03d.png" % i))) < MAD_LIMIT


def test_normalize_preserves_sar(clips: dict[str, Path], tmp_path: Path) -> None:
    """Probe 4: an exact non-square SAR survives normalize untouched."""
    dst = tmp_path / "norm_sar.mp4"
    info = video.normalize(clips["sar"], dst)
    assert info.sar == Fraction(200, 219)
    assert info.dar == info.sar * info.width / info.height
    assert info.frame_count == N_FRAMES
    assert (info.width, info.height) == (W, H)


def test_normalize_mjpeg(clips: dict[str, Path], tmp_path: Path) -> None:
    """Probe 4: MJPEG in, H.264 out, same frame count and digits."""
    dst = tmp_path / "norm_mjpeg.mp4"
    info = video.normalize(clips["mjpeg"], dst)
    assert info.codec == "h264"
    assert info.frame_count == N_FRAMES
    assert (info.width, info.height) == (W, H)
    assert info.fps == FPS
    frames = video.read_frames(dst, list(range(0, N_FRAMES, 10)))
    for i in range(0, N_FRAMES, 10):
        assert _mad(frames[i], _png(clips["pngs"] / ("frame_%03d.png" % i))) < MAD_LIMIT


def test_normalize_pads_odd_size(clips: dict[str, Path], tmp_path: Path) -> None:
    """Odd sizes gain one padded pixel; every frame survives."""
    dst = tmp_path / "norm_odd.mp4"
    info = video.normalize(clips["odd"], dst)
    assert (info.width, info.height) == (320, 240)
    assert info.frame_count == 10


def test_duplicate_runs_exact(clips: dict[str, Path]) -> None:
    """Probe 5: planted duplicates (frames 30-32) are found exactly."""
    diffs = video.frame_diffs(clips["dup"])
    assert len(diffs) == 39
    assert video.duplicate_runs(diffs) == [(30, 32)]


def test_duplicate_runs_unit() -> None:
    assert video.duplicate_runs(np.array([])) == []
    assert video.duplicate_runs(np.array([5.0, 6.0]), threshold=1.0) == []
    assert video.duplicate_runs([0.1, 0.2, 9.0, 0.0, 0.3]) == [(0, 2), (3, 5)]


def _tile(sheet: np.ndarray, pos: int, tile_w: int, tile_h: int, cols: int) -> np.ndarray:
    return sheet[
        (pos // cols) * tile_h : (pos // cols + 1) * tile_h,
        (pos % cols) * tile_w : (pos % cols + 1) * tile_w,
    ]


def test_contact_sheet_labels(clips: dict[str, Path], tmp_path: Path) -> None:
    """Probe 6a: 30 tiles, each with a legible label box >= 14 px tall."""
    indices = list(range(0, N_FRAMES, 4))[:30]
    out = tmp_path / "sheet.png"
    result = video.contact_sheet(clips["clip"], indices, out=out, tile_width=160)
    assert result == out and out.exists()
    sheet = np.asarray(Image.open(out).convert("RGB"))
    cols = math.ceil(math.sqrt(len(indices)))
    tile_w, tile_h = 160, round(H * 160 / W)
    assert sheet.shape == (5 * tile_h, cols * tile_w, 3)
    for pos in range(len(indices)):
        tile = _tile(sheet, pos, tile_w, tile_h, cols)
        dark_rows = (tile[:60].max(axis=2) < 50).any(axis=1)
        box_h = 0
        for present in dark_rows:
            if present:
                box_h += 1
            else:
                break
        assert box_h >= 14
        box = tile[:box_h, :100]
        assert (box.max(axis=2) > 200).any(), "no bright label pixels"
        assert (box.min(axis=2) < 50).any(), "no dark label box"


def test_contact_sheet_crop(clips: dict[str, Path], tmp_path: Path) -> None:
    """Probe 6b: crop shows only the cropped region; overlay hook works."""
    crop = (40, 30, 280, 210)
    seen: list[tuple[int, float]] = []

    def overlay(index: int, tile: Image.Image, scale: float) -> None:
        seen.append((index, scale))

    out = tmp_path / "crop.png"
    indices = [0, 40, 80]
    video.contact_sheet(
        clips["clip"], indices, out=out, tile_width=160, crop=crop, overlay=overlay
    )
    assert [index for index, _ in seen] == indices
    assert seen[0][1] == pytest.approx(160 / (crop[2] - crop[0]))
    sheet = np.asarray(Image.open(out).convert("RGB"))
    tile_w, tile_h = 160, round((crop[3] - crop[1]) * 160 / (crop[2] - crop[0]))
    frame = video.read_frames(clips["clip"], [80])[80][crop[1] : crop[3], crop[0] : crop[2]]
    want = np.asarray(Image.fromarray(frame).resize((tile_w, tile_h), Image.BILINEAR))
    got = _tile(sheet, 2, tile_w, tile_h, 2)[40:, :]
    assert _mad(got, want[40:, :]) < MAD_LIMIT


def test_read_frames_rejects_bad_index(clips: dict[str, Path]) -> None:
    with pytest.raises(IndexError):
        video.read_frames(clips["clip"], [N_FRAMES])
    with pytest.raises(IndexError):
        video.read_frames(clips["clip"], [-1])


def test_contact_sheet_rejects_too_many(clips: dict[str, Path], tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        video.contact_sheet(
            clips["clip"], list(range(31)), out=tmp_path / "x.png", tile_width=160
        )

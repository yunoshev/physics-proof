"""M3 probes: frame-accurate cut, cache, budget, result, phrases (offline).

Plus one opt-in live call (``-m api``, about $0.01) on the synthetic
red-square clip. The fake client serves synthetic masks and records every
call so cache and budget probes can assert that no API call was made.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

from physics_proof import video
from physics_proof.blocks import load_masks
from physics_proof.config import Settings
from physics_proof.ledger import Ledger
from physics_proof.meta_client import MetaClient, SamObject, SamResult
from physics_proof.sam_tool import SamBudgetError, SamTool, check_phrase

W, H, N_FRAMES, FPS = 320, 240, 70, 24


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def _png(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"))


def _mad(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


@pytest.fixture(scope="module")
def digit_clip(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Synthetic digit clip, same style as the M2 fixtures."""
    root = tmp_path_factory.mktemp("m3")
    pngs = root / "pngs"
    pngs.mkdir()
    font = ImageFont.load_default(size=100)
    for i in range(N_FRAMES):
        img = Image.new("RGB", (W, H), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((W // 2, H // 2), str(i), font=font, fill=(0, 0, 0), anchor="mm")
        img.save(pngs / ("frame_%03d.png" % i))
    clip = root / "clip.mp4"
    _ffmpeg(
        "-framerate", str(FPS), "-i", str(pngs / "frame_%03d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-fps_mode", "cfr", "-r", str(FPS), str(clip),
    )
    return {"pngs": pngs, "clip": clip}


def _rect_mask(w: int, h: int, x: int, y: int, s: int) -> np.ndarray:
    """Full-frame bool mask with one s×s square at (x, y)."""
    mask = np.zeros((h, w), dtype=bool)
    mask[y : y + s, x : x + s] = True
    return mask


def _obj(oid: str, mask: np.ndarray, conf: float = 0.9) -> SamObject:
    ys, xs = np.nonzero(mask)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    return SamObject(id=oid, box=box, confidence=conf, mask=mask)


class FakeSam:
    """Fake SAM client: serves synthetic masks, records every call."""

    def __init__(self, paint) -> None:
        self.paint = paint
        self.calls: list[tuple[str, str]] = []
        self.seen: dict[str, object] = {}

    def sam_video(self, video_path: str, phrase: str, **kwargs) -> SamResult:
        self.calls.append((video_path, phrase))
        info = video.probe(video_path)
        n = info.frame_count
        first = video.read_frames(video_path, [0])[0]
        self.seen = {"n": n, "w": info.width, "h": info.height, "frame0": first}
        frames = self.paint(n, info.width, info.height)
        return SamResult(
            frames=frames,
            frames_processed=n,
            cost_usd=n * 0.20 / 1000.0,
        )


def _paint_one(n: int, w: int, h: int) -> dict[int, list[SamObject]]:
    """One 40×40 square gliding right, one frame entry per cut frame."""
    return {i: [_obj("0", _rect_mask(w, h, 10 + i, 100, 40))] for i in range(n)}


def _paint_swap(n: int, w: int, h: int, at: int = 5) -> dict[int, list[SamObject]]:
    """Two 20×20 squares exchanging places at cut frame ``at``."""
    out = {}
    for i in range(n):
        left, right = (10, 120) if i < at else (120, 10)
        out[i] = [
            _obj("1", _rect_mask(w, h, left, 30, 20)),
            _obj("2", _rect_mask(w, h, right, 30, 20)),
        ]
    return out


def _tool(clip: Path, tmp_path: Path, fake: FakeSam, **kwargs) -> SamTool:
    return SamTool(
        fake,
        tmp_path / "ws",
        clip,
        cache_dir=tmp_path / "cache",
        **kwargs,
    )


def test_frame_accurate_cut(digit_clip: dict[str, Path], tmp_path: Path) -> None:
    """Probe 1: cutting 30..60 sends 30 frames; cut frame 0 shows digit 30."""
    fake = FakeSam(_paint_one)
    tool = _tool(digit_clip["clip"], tmp_path, fake)
    result = tool.run("red square", 30, 60)
    assert fake.seen["n"] == 30
    assert (fake.seen["w"], fake.seen["h"]) == (W, H)
    want = _png(digit_clip["pngs"] / "frame_030.png")
    assert _mad(fake.seen["frame0"], want) < 5.0
    stored = load_masks(result.npz)
    assert list(stored.frames) == list(range(30, 60))
    assert list(stored.ids) == [0]
    assert stored.masks.shape == (30, 1, H, W)


def test_cache_hit_and_subrange(digit_clip: dict[str, Path], tmp_path: Path) -> None:
    """Probe 2: repeat and sub-range calls make no client call."""
    fake = FakeSam(_paint_one)
    tool = _tool(digit_clip["clip"], tmp_path, fake)
    first = tool.run("red square", 30, 60)
    assert not first.cached and len(fake.calls) == 1
    second = tool.run("red square", 30, 60)
    assert second.cached and len(fake.calls) == 1
    assert second.frames_billed == 0 and second.cost_usd == 0.0
    for key in ("frames", "ids", "masks", "present", "confidence"):
        assert np.array_equal(np.asarray(load_masks(first.npz).__getattribute__(key)),
                              np.asarray(load_masks(second.npz).__getattribute__(key)))
    sub = tool.run("red square", 40, 50)
    assert sub.cached and len(fake.calls) == 1
    assert list(load_masks(sub.npz).frames) == list(range(40, 50))
    full = load_masks(first.npz).of(0)
    assert np.array_equal(load_masks(sub.npz).of(0), full[10:20])


def test_budget_refuses(digit_clip: dict[str, Path], tmp_path: Path) -> None:
    """Probe 3: a 60-frame then a 50-frame call on a 100-frame budget."""
    fake = FakeSam(_paint_one)
    tool = _tool(digit_clip["clip"], tmp_path, fake, budget_frames=100)
    tool.run("red square", 0, 60)
    assert tool.frames_used == 60
    with pytest.raises(SamBudgetError) as excinfo:
        tool.run("blue box", 0, 50)
    assert "\n" not in str(excinfo.value)
    assert "budget" in str(excinfo.value).lower()
    assert len(fake.calls) == 1
    assert tool.frames_used == 60


def test_result_summary_and_swap(digit_clip: dict[str, Path], tmp_path: Path) -> None:
    """Probe 4: npz round-trip, sheet, bbox match, planted swap flagged."""
    fake = FakeSam(lambda n, w, h: _paint_swap(n, w, h, at=5))
    tool = _tool(digit_clip["clip"], tmp_path, fake)
    result = tool.run("red square", 30, 40)
    assert result.frames_billed == 50
    assert result.billed_minimum
    assert "minimum of 50 frames" in result.text()
    assert len(result.text()) <= 1500
    stored = load_masks(result.npz)
    assert list(stored.frames) == list(range(30, 40))
    assert sorted(int(v) for v in stored.ids) == [1, 2]
    assert result.sheet.exists() and result.sheet.stat().st_size > 0
    assert set(result.objects) == {1, 2}
    for oid, info in result.objects.items():
        track = stored.of(oid)
        ys, xs = np.nonzero(track.any(axis=0))
        union = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
        assert info["bbox"] == union
        assert info["present"] == 10 and info["total"] == 10
        assert info["median_area"] == 400.0
    assert 35 in result.identity_swaps


def test_phrase_validation(digit_clip: dict[str, Path], tmp_path: Path) -> None:
    """Probe 5: bad phrases are rejected before any client call."""
    fake = FakeSam(_paint_one)
    tool = _tool(digit_clip["clip"], tmp_path, fake)
    for bad in ("", "a b c d e", "car; rm -rf", "   ", "red_square", "a!"):
        with pytest.raises(ValueError):
            tool.run(bad, 0, 10)
    assert fake.calls == []
    assert check_phrase("  red   square ") == "red square"
    assert check_phrase("person-walking fast") == "person-walking fast"


@pytest.mark.api
def test_live_sam_tool_call(tmp_path: Path, fixtures_dir: Path) -> None:
    """API probe: one real 6-frame call, billed 50, then served from cache."""
    ledger = Ledger(tmp_path / "run.jsonl", tmp_path / "global.jsonl")
    client = MetaClient(settings=Settings(), ledger=ledger, run="m3-api")
    tool = SamTool(client, tmp_path / "ws", fixtures_dir / "sam_clip.mp4",
                   cache_dir=tmp_path / "cache")
    first = tool.run("red square", 2, 8)
    print(f"\nSAM tool: billed={first.frames_billed} cost=${first.cost_usd:.6f}", flush=True)
    print(first.text(), flush=True)
    assert not first.cached
    assert first.frames_billed == 50
    stored = load_masks(first.npz)
    assert list(stored.frames) == [2, 3, 4, 5, 6, 7]
    for frame in (2, 3, 4, 5, 6, 7):
        row = list(stored.frames).index(frame)
        assert stored.masks[row].any(), f"frame {frame} has no mask"
    lines_before = (tmp_path / "run.jsonl").read_text().count("\n")
    assert any('"kind": "sam"' in line for line in (tmp_path / "run.jsonl").read_text().splitlines())
    second = tool.run("red square", 2, 8)
    assert second.cached
    assert second.frames_billed == 0
    assert (tmp_path / "run.jsonl").read_text().count("\n") == lines_before

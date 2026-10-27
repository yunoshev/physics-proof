"""M3. SAM 3.1 tool: ``sam(phrase, start, stop)`` with cache and budget.

The agent calls ``SamTool.run(phrase, start, stop)`` to segment one short
noun phrase over frames ``start..stop-1``. Only that range is sent to SAM
(a frame-accurate ffmpeg cut, never a time seek), frame numbers map back
by ``+start``, and masks are saved at the original clip size. Identical
and sub-range calls are served from a content-keyed cache; per-clip spend
is capped by ``budget_frames``.
"""

from __future__ import annotations

import hashlib
import operator
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from . import video
from .blocks import load_masks, mask_stats, save_masks, track_quality
from .config import REPO_ROOT
from .meta_client import SamResult

__all__ = [
    "DEFAULT_BUDGET_FRAMES",
    "MIN_BILLED_FRAMES",
    "SHEET_MAX_TILES",
    "SamBudgetError",
    "SamTool",
    "SamToolResult",
    "check_phrase",
    "cut_frames",
    "phrase_slug",
]

#: SAM bills at least this many frames per request (measured 2026-10-27).
MIN_BILLED_FRAMES = 50
#: Overlay sheet holds at most this many tiles.
SHEET_MAX_TILES = 24
#: Default per-clip budget in frames (counted as stop - start).
DEFAULT_BUDGET_FRAMES = 1500

_WORD_RE = re.compile(r"[A-Za-z-]*[A-Za-z][A-Za-z-]*")
_CACHE_RE = re.compile(r"^([0-9a-f]{64})__(.+)__(\d+)-(\d+)\.npz$")

_PALETTE = [
    (230, 57, 70),
    (46, 204, 113),
    (66, 135, 245),
    (255, 200, 40),
    (178, 102, 255),
    (0, 200, 200),
    (255, 140, 0),
    (150, 150, 150),
]


class SamBudgetError(RuntimeError):
    """A sam() call would exceed the per-clip frame budget. No API call made."""


def check_phrase(phrase: str) -> str:
    """Validate a SAM noun phrase; returns the canonical single-spaced form.

    Argument shapes: phrase is one string. Returns: the phrase with runs
    of whitespace collapsed. Raises ValueError unless it is 1-4 words of
    letters, spaces and hyphens only.
    """
    if not isinstance(phrase, str):
        raise ValueError("sam phrase must be 1-4 words of letters/spaces/hyphens")
    canon = " ".join(phrase.split())
    words = canon.split(" ") if canon else []
    ok = 1 <= len(words) <= 4 and all(_WORD_RE.fullmatch(w) for w in words)
    if not ok:
        raise ValueError(
            "sam phrase must be 1-4 words of letters/spaces/hyphens, got " + repr(phrase)
        )
    return canon


def phrase_slug(phrase: str) -> str:
    """Filename stem for a canonical phrase: spaces become underscores."""
    return check_phrase(phrase).replace(" ", "_")


def _sha256(path: Path) -> str:
    """Hex sha256 of a file's bytes, streamed in 1 MB chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cut_frames(src: str | Path, dst: str | Path, start: int, stop: int) -> Path:
    """Cut frames ``start..stop-1`` to a new clip, frame-accurately.

    Argument shapes: src/dst are paths, start/stop are frame indices in
    frames with ``0 <= start < stop``. Selects by decoded frame number
    (never seeks by time) and re-encodes. Returns dst; raises
    RuntimeError when the cut does not hold exactly ``stop - start`` frames.
    """
    filt = "select='between(n," + str(start) + "," + str(stop - 1) + ")',setpts=N/FRAME_RATE/TB"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(src),
        "-map", "0:v:0",
        "-vf", filt,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "veryfast",
        "-an",
        str(dst),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required for frame-accurate cuts") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError("ffmpeg cut failed: " + (detail[-1] if detail else "exit 1"))
    out = Path(dst)
    got = video.probe(out).frame_count
    if got != stop - start:
        raise RuntimeError(
            "ffmpeg cut gave " + str(got) + " frames, wanted " + str(stop - start)
        )
    return out


@dataclass
class SamToolResult:
    """One sam() call: files, per-object summary, billing, cache state."""

    phrase: str
    start: int
    stop: int
    npz: Path
    sheet: Path
    objects: dict[int, dict[str, Any]]
    identity_swaps: list[int]
    frames_billed: int
    cost_usd: float
    cached: bool
    billed_minimum: bool

    def text(self) -> str:
        """Compact plain-text summary for the agent (at most 1500 chars)."""
        n = self.stop - self.start
        lines = [
            "sam(" + repr(self.phrase) + ", " + str(self.start) + ", " + str(self.stop) + "): "
            + str(len(self.objects)) + " object(s), " + str(n) + " frames"
        ]
        for oid in sorted(self.objects):
            info = self.objects[oid]
            lines.append(
                "id " + str(oid) + ": conf " + ("%.2f" % info["confidence"]) + ", "
                + str(info["present"]) + "/" + str(info["total"]) + " frames, median area "
                + ("%.0f" % info["median_area"]) + " px, bbox " + repr(info["bbox"])
            )
            lines.append("track id " + str(oid) + ": " + str(info["track_quality"]))
        if self.identity_swaps:
            lines.append("likely id swaps at frames: " + repr(self.identity_swaps))
        else:
            lines.append("likely id swaps at frames: none")
        if self.cached:
            lines.append("served from cache: no API call, 0 frames billed")
        else:
            lines.append(
                "billed " + str(self.frames_billed) + " frames ($"
                + ("%.6f" % self.cost_usd) + ")"
            )
            if self.billed_minimum:
                lines.append(
                    "note: SAM bills a minimum of 50 frames per request; this "
                    + str(n) + "-frame range was billed as 50 frames"
                )
        joined = "\n".join(lines)
        return joined if len(joined) <= 1500 else joined[:1497] + "..."


def _int_ids(ids: list[str]) -> dict[str, int]:
    """Map SAM string object ids to ints; falls back to sorted order."""
    try:
        return {v: int(v) for v in ids}
    except ValueError:
        return {v: i for i, v in enumerate(sorted(ids))}


class SamTool:
    """The agent's ``sam(phrase, start, stop)`` entry point for one clip."""

    def __init__(
        self,
        client: Any,
        workspace: str | Path,
        clip_path: str | Path,
        *,
        budget_frames: int = DEFAULT_BUDGET_FRAMES,
        cache_dir: str | Path | None = None,
    ) -> None:
        """Bind a client, a run workspace and a clip; reads clip geometry."""
        self.client = client
        self.workspace = Path(workspace)
        self.clip_path = Path(clip_path)
        self.budget_frames = int(budget_frames)
        info = video.probe(self.clip_path)
        self.width = info.width
        self.height = info.height
        self.clip_frames = info.frame_count
        self.cache_dir = Path(cache_dir) if cache_dir is not None else REPO_ROOT / "cache" / "sam"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sam_dir = self.workspace / "sam"
        self.sam_dir.mkdir(parents=True, exist_ok=True)
        self._frames_used = 0

    @property
    def frames_used(self) -> int:
        """Non-cached frames spent so far against the budget."""
        return self._frames_used

    def _check_range(self, start: int, stop: int) -> tuple[int, int]:
        """Validate frame bounds; returns plain ints or raises ValueError."""
        try:
            if isinstance(start, bool) or isinstance(stop, bool):
                raise TypeError("bool is not a frame index")
            start_i = operator.index(start)
            stop_i = operator.index(stop)
        except TypeError as exc:
            raise ValueError("sam range must be two frame indices") from exc
        if not 0 <= start_i < stop_i <= self.clip_frames:
            raise ValueError(
                "sam range [" + str(start) + ", " + str(stop) + ") is outside 0.."
                + str(self.clip_frames)
            )
        return start_i, stop_i

    def _cache_candidates(self, sha: str, slug: str) -> list[tuple[int, int, Path]]:
        """Cached (start, stop, path) entries for this clip and phrase."""
        found: list[tuple[int, int, Path]] = []
        for path in sorted(self.cache_dir.glob("*.npz")):
            match = _CACHE_RE.match(path.name)
            if match is None or match.group(1) != sha or match.group(2) != slug:
                continue
            found.append((int(match.group(3)), int(match.group(4)), path))
        return found

    def _from_cache(
        self, sha: str, slug: str, start: int, stop: int
    ) -> tuple[Any, list[int]] | None:
        """Load a cached MaskSet covering [start, stop), sliced to it."""
        best: tuple[int, int, Path] | None = None
        for entry in self._cache_candidates(sha, slug):
            if entry[0] <= start and stop <= entry[1]:
                if best is None or (entry[1] - entry[0]) < (best[1] - best[0]):
                    best = entry
        if best is None:
            return None
        try:
            cached = load_masks(best[2])
        except (ValueError, KeyError, OSError):
            return None
        pos = {int(f): i for i, f in enumerate(cached.frames)}
        if any(f not in pos for f in range(start, stop)):
            return None
        rows = [pos[f] for f in range(start, stop)]
        return cached, rows

    def run(self, phrase: str, start: int, stop: int) -> SamToolResult:
        """Segment phrase over frames start..stop-1; see module docstring."""
        canon = check_phrase(phrase)
        start_i, stop_i = self._check_range(start, stop)
        n = stop_i - start_i
        slug = canon.replace(" ", "_")
        sha = _sha256(self.clip_path)
        stem = slug + "." + str(start_i) + "-" + str(stop_i)
        npz_path = self.sam_dir / (stem + ".npz")
        sheet_path = self.sam_dir / (stem + ".png")

        cached_rows: list[int] | None = None
        cached_set = None
        hit = self._from_cache(sha, slug, start_i, stop_i)
        if hit is not None:
            cached_set, cached_rows = hit

        frames_billed = 0
        cost_usd = 0.0
        used_cache = cached_set is not None
        if used_cache:
            assert cached_set is not None and cached_rows is not None
            frames_idx = list(range(start_i, stop_i))
            ids = [int(v) for v in cached_set.ids]
            masks = np.asarray(cached_set.masks[cached_rows], dtype=bool)
            conf = [float(v) for v in cached_set.confidence]
        else:
            if self._frames_used + n > self.budget_frames:
                raise SamBudgetError(
                    "sam budget exceeded: this " + str(n) + "-frame call ["
                    + str(start_i) + ", " + str(stop_i) + ") would pass the "
                    + str(self.budget_frames) + "-frame budget (" + str(self._frames_used)
                    + " used)"
                )
            cut_path = self.sam_dir / (".cut_" + stem + ".mp4")
            try:
                cut_frames(self.clip_path, cut_path, start_i, stop_i)
                result: SamResult = self.client.sam_video(str(cut_path), canon)
            finally:
                cut_path.unlink(missing_ok=True)
            raw_ids = sorted({obj.id for objs in result.frames.values() for obj in objs})
            id_map = _int_ids(raw_ids)
            ids = sorted(id_map.values())
            slot = {v: k for k, v in enumerate(ids)}
            frames_idx = list(range(start_i, stop_i))
            masks = np.zeros((n, len(ids), self.height, self.width), dtype=bool)
            conf: list[float] = []
            for sid in raw_ids:
                vals = [
                    obj.confidence
                    for objs in result.frames.values()
                    for obj in objs
                    if obj.id == sid and obj.confidence is not None
                ]
                conf.append(float(sum(vals) / len(vals)) if vals else 0.0)
            for cut_frame, objs in result.frames.items():
                row = int(cut_frame)
                if row < 0 or row >= n:
                    continue
                for obj in objs:
                    patch = np.asarray(obj.mask, dtype=bool)
                    h = min(patch.shape[0], self.height)
                    w = min(patch.shape[1], self.width)
                    masks[row, slot[id_map[obj.id]], :h, :w] |= patch[:h, :w]
            frames_billed = max(n, int(result.frames_processed), MIN_BILLED_FRAMES)
            cost_usd = float(result.cost_usd)
            self._frames_used += n
            cache_path = self.cache_dir / (sha + "__" + slug + "__" + str(start_i) + "-" + str(stop_i) + ".npz")
            save_masks(cache_path, frames_idx, ids, masks, conf)

        save_masks(npz_path, frames_idx, ids, masks, conf)
        sheet_frames = self._sheet_frames(start_i, stop_i)
        self._overlay_sheet(sheet_frames, start_i, masks, ids, sheet_path)
        objects = self._summarize(frames_idx, ids, masks, conf)
        swaps = self._identity_swaps(frames_idx, ids, masks)
        return SamToolResult(
            phrase=canon,
            start=start_i,
            stop=stop_i,
            npz=npz_path,
            sheet=sheet_path,
            objects=objects,
            identity_swaps=swaps,
            frames_billed=frames_billed,
            cost_usd=cost_usd,
            cached=used_cache,
            billed_minimum=(not used_cache and n < MIN_BILLED_FRAMES),
        )

    def _sheet_frames(self, start: int, stop: int) -> list[int]:
        """Up to SHEET_MAX_TILES frame indices spread evenly over the range."""
        n = stop - start
        count = min(SHEET_MAX_TILES, n)
        picked = np.linspace(start, stop - 1, count).astype(int)
        return sorted(int(v) for v in dict.fromkeys(int(v) for v in picked))

    def _overlay_sheet(
        self,
        sheet_frames: list[int],
        start: int,
        masks: np.ndarray,
        ids: list[int],
        out: Path,
    ) -> Path:
        """Tint each object in its own colour with its id on the sheet."""
        colors = {oid: _PALETTE[k % len(_PALETTE)] for k, oid in enumerate(ids)}
        stats = {oid: mask_stats(np.asarray(masks[:, k], dtype=bool)) for k, oid in enumerate(ids)}

        def overlay(index: int, tile: Image.Image, scale: float) -> Image.Image | None:
            row = index - start
            img = tile.convert("RGB")
            if row < 0 or row >= masks.shape[0]:
                return img
            arr = np.asarray(img).astype(np.float64)
            for k, oid in enumerate(ids):
                full = np.asarray(masks[row, k], dtype=bool)
                if not full.any():
                    continue
                small = np.asarray(
                    Image.fromarray(full).resize(img.size, Image.NEAREST), dtype=bool
                )
                tint = np.asarray(colors[oid], dtype=np.float64)
                arr[small] = 0.5 * arr[small] + 0.5 * tint
            img = Image.fromarray(np.asarray(arr, dtype=np.uint8))
            draw = ImageDraw.Draw(img)
            for oid in ids:
                entry = stats[oid][row]
                if entry is None:
                    continue
                x1, y1 = entry["bbox"][0] * scale, entry["bbox"][1] * scale
                draw.text(
                    (max(0.0, x1), max(0.0, y1)),
                    str(oid),
                    fill=(255, 255, 255),
                    stroke_width=2,
                    stroke_fill=(0, 0, 0),
                )
            return img

        return video.contact_sheet(
            self.clip_path, sheet_frames, out=out, tile_width=320, overlay=overlay
        )

    def _summarize(
        self, frames_idx: list[int], ids: list[int], masks: np.ndarray, conf: list[float]
    ) -> dict[int, dict[str, Any]]:
        """Per-object stats: confidence, present/total, area, bbox, quality."""
        out: dict[int, dict[str, Any]] = {}
        for k, oid in enumerate(ids):
            track = np.asarray(masks[:, k], dtype=bool)
            entries = mask_stats(track)
            present = [e for e in entries if e is not None]
            if present:
                areas = [int(e["area"]) for e in present]
                median_area = float(np.median(np.asarray(areas, dtype=np.float64)))
                bbox = [
                    min(int(e["bbox"][0]) for e in present),
                    min(int(e["bbox"][1]) for e in present),
                    max(int(e["bbox"][2]) for e in present),
                    max(int(e["bbox"][3]) for e in present),
                ]
            else:
                median_area = 0.0
                bbox = [0, 0, 0, 0]
            quality = track_quality(track, frames_idx)
            out[oid] = {
                "confidence": float(conf[k]),
                "present": len(present),
                "total": len(frames_idx),
                "median_area": median_area,
                "bbox": bbox,
                "track_quality": str(quality["summary"]),
            }
        return out

    def _identity_swaps(
        self, frames_idx: list[int], ids: list[int], masks: np.ndarray
    ) -> list[int]:
        """Frames where an object's centroid jumps past its own bbox diagonal."""
        swaps: set[int] = set()
        for k in range(len(ids)):
            entries = mask_stats(np.asarray(masks[:, k], dtype=bool))
            by_frame = dict(zip(frames_idx, entries))
            for prev, cur in zip(frames_idx[:-1], frames_idx[1:]):
                if cur != prev + 1:
                    continue
                first, second = by_frame[prev], by_frame[cur]
                if first is None or second is None:
                    continue
                dist = float(np.hypot(
                    second["centroid"][0] - first["centroid"][0],
                    second["centroid"][1] - first["centroid"][1],
                ))
                wide = first["bbox"][2] - first["bbox"][0]
                tall = first["bbox"][3] - first["bbox"][1]
                diag = float(np.hypot(wide, tall))
                if diag > 0 and dist > diag:
                    swaps.add(cur)
        return sorted(swaps)

"""M7. Mask check: a context-free second pair of eyes on a reference mask.

The agent calls ``MaskCheck.run(npz, object_id, frames, claim)`` to ask
Spark — with no context of the run — what a mask really covers. Each
requested frame is cropped around the object's bbox and rendered as a
``plain | tinted + outlined`` pair; the pairs are stacked into one sheet
that is kept for the page. One Spark call with the fixed instruction in
``config/prompts/mask_check.txt``, the sheet and the claim returns a
strict-schema verdict on the claim. Every check is logged to
``workspace/mask_checks.jsonl`` and remembered so ``finish`` can gate on
``has_check``. Per-run checks are capped (default 4); the next one is
refused without an API call.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from . import video
from .blocks import load_masks, mask_stats
from .config import REPO_ROOT
from .meta_client import raise_if_incomplete

__all__ = [
    "MASK_CHECK_SCHEMA",
    "MAX_FRAMES",
    "MAX_SHEET_WIDTH",
    "MAX_TEXT_CHARS",
    "PROMPT_PATH",
    "VERDICTS",
    "MaskCheck",
    "MaskCheckLimitError",
    "MaskCheckResult",
    "check_frames",
    "crop_for",
    "parse_answer",
]

#: Fixed instruction for the context-free Spark call (no run context).
PROMPT_PATH = REPO_ROOT / "config" / "prompts" / "mask_check.txt"

#: Allowed verdicts on the agent's claim.
VERDICTS = ("agrees", "covers_more", "covers_less", "different_object", "cannot_tell")

#: Strict schema for the Spark answer: what is in/out, what it covers, verdict.
MASK_CHECK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "inside": {"type": "string"},
        "outside": {"type": "string"},
        "covers": {"type": "string"},
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "reason": {"type": "string"},
    },
    "required": ["inside", "outside", "covers", "verdict", "reason"],
    "additionalProperties": False,
}

#: At most this many frames per check (1..MAX_FRAMES).
MAX_FRAMES = 4
#: Default per-run check budget; the next check is refused without an API call.
DEFAULT_CHECK_LIMIT = 4
#: Each plain|tinted pair is scaled so it is at most this wide in px.
MAX_SHEET_WIDTH = 1024
#: Compact agent text is at most this long.
MAX_TEXT_CHARS = 800
#: Crop padding: this fraction of the bbox size, at least this many px.
PAD_FRAC = 0.25
PAD_MIN_PX = 32
#: Tint and outline colours for the highlighted half (RGB).
TINT_RGB = (0, 255, 255)
OUTLINE_RGB = (255, 255, 0)


class MaskCheckLimitError(RuntimeError):
    """A mask_check() call past the per-run limit. No API call was made."""


def _prompt() -> str:
    """Load the fixed mask-check instruction (once) from ``mask_check.txt``."""
    text = PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("mask check instruction is empty: " + str(PROMPT_PATH))
    return text


def _frame_list(frames: Any) -> list[int]:
    """Validate 1..MAX_FRAMES distinct frame numbers; plain ints or nothing."""
    if isinstance(frames, bool):
        raise ValueError("mask check needs 1..4 frame numbers, got a bool")
    try:
        items = list(frames)
    except TypeError as exc:
        raise ValueError("mask check needs 1..4 frame numbers") from exc
    if not 1 <= len(items) <= MAX_FRAMES:
        raise ValueError(
            "mask check needs 1.." + str(MAX_FRAMES) + " frames, got " + str(len(items))
        )
    out: list[int] = []
    for item in items:
        if isinstance(item, bool) or not isinstance(item, (int, np.integer)):
            raise ValueError("mask check frame numbers must be ints, got " + repr(item))
        out.append(int(item))
    if len(set(out)) != len(out):
        raise ValueError("mask check frame numbers must be distinct, got " + repr(out))
    return out


def check_frames(frames: Any, present: Any) -> list[int]:
    """Validate frame numbers against the npz's frame list.

    Argument shapes: frames holds 1..4 frame numbers in frames; present
    holds the npz's frame numbers in frames. Returns: the plain int list.
    Raises ValueError for 0 or 5+ frames, non-ints, duplicates, or frames
    missing from the npz.
    """
    wanted = _frame_list(frames)
    have = {int(v) for v in np.asarray(present).reshape(-1)}
    missing = [f for f in wanted if f not in have]
    if missing:
        raise ValueError(
            "mask check frames " + repr(missing) + " are not in the mask file "
            "(have frames " + repr(sorted(have)) + ")"
        )
    return wanted


def crop_for(bbox: list[int], width: int, height: int) -> tuple[int, int, int, int]:
    """Crop around a bbox: pad 25 % of its size (at least 32 px), clip.

    Argument shapes: bbox is [x1, y1, x2, y2] in px (x2/y2 exclusive);
    width/height are the frame size in px. Returns: (x1, y1, x2, y2) of the
    crop in px, clipped to the frame.
    """
    x1, y1, x2, y2 = (int(v) for v in bbox)
    pad_x = max(PAD_FRAC * (x2 - x1), PAD_MIN_PX)
    pad_y = max(PAD_FRAC * (y2 - y1), PAD_MIN_PX)
    cx1 = max(0, int(x1 - pad_x))
    cy1 = max(0, int(y1 - pad_y))
    cx2 = min(width, int(x2 + pad_x + 1))
    cy2 = min(height, int(y2 + pad_y + 1))
    if cx2 <= cx1 or cy2 <= cy1:
        raise ValueError("mask check crop is empty for bbox " + repr(bbox))
    return cx1, cy1, cx2, cy2


def _edge(mask: np.ndarray) -> np.ndarray:
    """One-pixel ring each side of the mask boundary, shape [H, W] bool."""
    full = np.asarray(mask, dtype=bool)
    if not full.any():
        return np.zeros_like(full, dtype=bool)
    grown = ndimage.binary_dilation(full, structure=np.ones((3, 3)))
    shrunk = ndimage.binary_erosion(full, structure=np.ones((3, 3)))
    return np.asarray(grown ^ shrunk, dtype=bool)


def _highlight(crop: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Blend a cyan tint over masked px and draw a yellow outline (RGB)."""
    tint = np.asarray(TINT_RGB, dtype=np.float64)
    base = np.asarray(crop, dtype=np.float64)
    small = np.asarray(mask, dtype=bool)
    base[small] = 0.5 * base[small] + 0.5 * tint
    out = np.asarray(base, dtype=np.uint8)
    out[_edge(small)] = np.asarray(OUTLINE_RGB, dtype=np.uint8)
    return out


def _label_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=14)
    except TypeError:
        return ImageFont.load_default()


def _label(half: Image.Image, frame: int) -> None:
    """Draw the same frame tag on one half of a pair (identical both sides)."""
    if half.width < 50 or half.height < 24:
        return
    draw = ImageDraw.Draw(half)
    draw.rectangle([0, 0, 44, 20], fill=(0, 0, 0))
    draw.text((5, 3), "f" + str(frame), font=_label_font(), fill=(255, 255, 255))


def _strip_fences(payload: str) -> str:
    """Remove one Markdown code fence around a JSON payload, if present."""
    text = payload.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_answer(payload: str) -> dict[str, str]:
    """Parse one mask-check answer into its five fields, fail loudly.

    Spark may wrap the schema JSON in prose, so a whole-payload
    ``json.loads`` is tried first; failing that, each ``{`` position is
    decoded until one yields an object holding a ``verdict``. Raises
    ValueError when no usable object is found or a field is wrong.
    """
    text = _strip_fences(str(payload))
    data: Any = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict) or "verdict" not in data:
        decoder = json.JSONDecoder()
        data = None
        for match in re.finditer(r"\{", text):
            try:
                candidate, _ = decoder.raw_decode(text[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and "verdict" in candidate:
                data = candidate
                break
    if not isinstance(data, dict):
        snippet = " ".join(text.split())[:120]
        raise ValueError("mask check answer holds no JSON object: " + repr(snippet))
    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in VERDICTS:
        raise ValueError(
            "mask check verdict is not one of " + repr(list(VERDICTS))
            + ", got " + repr(data.get("verdict"))
        )
    answer = {
        "inside": data.get("inside", ""),
        "outside": data.get("outside", ""),
        "covers": data.get("covers", ""),
        "verdict": verdict,
        "reason": data.get("reason", ""),
    }
    for key in ("inside", "outside", "covers", "reason"):
        if not isinstance(answer[key], str):
            raise ValueError("mask check field " + repr(key) + " is not a string")
    for key in ("inside", "covers", "reason"):
        if not str(answer[key]).strip():
            raise ValueError("mask check field " + repr(key) + " is empty")
        answer[key] = str(answer[key]).strip()
    answer["outside"] = str(answer["outside"]).strip()
    return answer


@dataclass
class MaskCheckResult:
    """One mask_check() call: the answer, the sheet, the cost."""

    inside: str
    outside: str
    covers: str
    verdict: str
    reason: str
    sheet: Path
    cost_usd: float

    def text(self) -> str:
        """Compact agent text (at most 800 chars) with verdict and cost."""
        body = (
            "mask check: " + self.verdict + " (" + self.covers + "). "
            + self.reason + " [sheet " + self.sheet.name + ", $"
            + ("%.6f" % self.cost_usd) + "]"
        )
        body = " ".join(body.split())
        return body if len(body) <= MAX_TEXT_CHARS else body[: MAX_TEXT_CHARS - 3] + "..."


class MaskCheck:
    """The agent's ``mask_check(file, object, frames, claim)`` entry point."""

    def __init__(
        self,
        client: Any,
        workspace: str | Path,
        clip_path: str | Path,
        *,
        limit: int = DEFAULT_CHECK_LIMIT,
    ) -> None:
        """Bind a Spark client, a run workspace and the clip under check."""
        self.client = client
        self.workspace = Path(workspace)
        self.clip_path = Path(clip_path)
        self.limit = int(limit)
        if self.limit < 1:
            raise ValueError("mask check limit must be at least 1")
        self.sheet_dir = self.workspace / "mask_checks"
        self.sheet_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.workspace / "mask_checks.jsonl"
        self._checks: list[dict[str, Any]] = self._load_log()

    def _load_log(self) -> list[dict[str, Any]]:
        """Reload earlier checks from the workspace log (resume-safe)."""
        if not self.log_path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and "npz" in record and "object" in record:
                out.append(record)
        return out

    @property
    def checks_made(self) -> int:
        """Checks completed so far against the per-run limit."""
        return len(self._checks)

    def has_check(self, npz: str | Path, object_id: int) -> bool:
        """True when this npz + object was already checked (for ``finish``)."""
        want = Path(npz).name
        for entry in self._checks:
            if Path(str(entry["npz"])).name == want and int(entry["object"]) == int(
                object_id
            ):
                return True
        return False

    def _sheet_name(self, npz: str | Path, object_id: int) -> Path:
        """Next sheet path: ``<npz-stem>.<object>.<n>.png`` (1-based n)."""
        stem = Path(npz).stem
        return self.sheet_dir / (stem + "." + str(int(object_id)) + "." + str(len(self._checks) + 1) + ".png")

    def _render_sheet(
        self, frames: list[int], masks: np.ndarray, bboxes: list[list[int]], out: Path
    ) -> Path:
        """Stack one plain|tinted pair per frame; each pair is <= 1024 px."""
        decoded = video.read_frames(self.clip_path, frames)
        rows: list[Image.Image] = []
        for pos, frame in enumerate(frames):
            img = decoded[frame]
            height, width = img.shape[0], img.shape[1]
            cx1, cy1, cx2, cy2 = crop_for(bboxes[pos], width, height)
            plain = np.asarray(img[cy1:cy2, cx1:cx2]).copy()
            small = np.asarray(masks[pos][cy1:cy2, cx1:cx2], dtype=bool)
            tinted = _highlight(plain, small)
            pair_w = 2 * (cx2 - cx1)
            scale = min(1.0, MAX_SHEET_WIDTH / pair_w)
            left = Image.fromarray(plain).resize(
                (max(1, round((cx2 - cx1) * scale)), max(1, round((cy2 - cy1) * scale))),
                Image.BILINEAR,
            )
            right = Image.fromarray(tinted).resize(left.size, Image.BILINEAR)
            _label(left, frame)
            _label(right, frame)
            pair = Image.new("RGB", (2 * left.width, left.height), (0, 0, 0))
            pair.paste(left, (0, 0))
            pair.paste(right, (left.width, 0))
            rows.append(pair)
        sheet_w = max(row.width for row in rows)
        sheet_h = sum(row.height for row in rows)
        sheet = Image.new("RGB", (sheet_w, sheet_h), (0, 0, 0))
        top = 0
        for row in rows:
            sheet.paste(row, (0, top))
            top += row.height
        out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out)
        return out

    def _image_part(self, sheet: Path) -> dict[str, Any]:
        """Build an input_image part for the sheet via the client helper."""
        helper = getattr(self.client, "image_part", None)
        if callable(helper):
            return dict(helper(sheet))
        return {"type": "input_image", "image_url": str(sheet)}

    def _log(
        self,
        npz: str | Path,
        object_id: int,
        frames: list[int],
        claim: str,
        answer: dict[str, str],
        sheet: Path,
        cost_usd: float,
    ) -> None:
        """Append one JSON line per check and remember it for ``has_check``."""
        record = {
            "npz": str(npz),
            "object": int(object_id),
            "frames": [int(f) for f in frames],
            "claim": claim,
            "answer": dict(answer),
            "sheet": str(sheet),
            "cost_usd": float(cost_usd),
        }
        self._checks.append(record)
        with open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def run(
        self, npz: str | Path, object_id: int, frames: Any, claim: str
    ) -> MaskCheckResult:
        """Check one claim about one object's mask on 1..4 frames.

        Raises ValueError for bad frames (0 or 5+, unknown, not in the
        npz), an unknown object id, an empty claim, or an unusable Spark
        answer — all before any API call. Raises MaskCheckLimitError past
        the per-run limit, also with no API call.
        """
        if isinstance(object_id, bool) or not isinstance(object_id, (int, np.integer)):
            raise ValueError("mask check object id must be an int, got " + repr(object_id))
        oid = int(object_id)
        if not isinstance(claim, str) or not claim.strip():
            raise ValueError("mask check claim must be a non-empty sentence")
        clean_claim = " ".join(claim.split())
        mask_set = load_masks(npz)
        have_ids = [int(v) for v in mask_set.ids]
        if oid not in have_ids:
            raise ValueError(
                "unknown object id " + str(oid) + "; have " + repr(have_ids)
            )
        wanted = check_frames(frames, mask_set.frames)
        if len(self._checks) >= self.limit:
            raise MaskCheckLimitError(
                "mask check limit reached (" + str(len(self._checks)) + " of "
                + str(self.limit) + " used); this check was not sent and no API call was made"
            )
        track = mask_set.of(oid)
        stats = mask_stats(track)
        by_frame = {int(f): stats[i] for i, f in enumerate(mask_set.frames)}
        full_masks: list[np.ndarray] = []
        bboxes: list[list[int]] = []
        for frame in wanted:
            entry = by_frame[frame]
            if entry is None:
                raise ValueError(
                    "object " + str(oid) + " has an empty mask on frame " + str(frame)
                )
            row = int(np.flatnonzero(mask_set.frames == frame)[0])
            full_masks.append(np.asarray(track[row], dtype=bool))
            bboxes.append([int(v) for v in entry["bbox"]])
        sheet = self._render_sheet(
            wanted, np.stack(full_masks), bboxes, self._sheet_name(npz, oid)
        )
        user_text = "Claim: " + clean_claim
        content: list[dict[str, Any]] = [
            {"type": "input_text", "text": user_text},
            self._image_part(sheet),
        ]
        response = self.client.respond(
            [{"role": "user", "content": content}],
            instructions=_prompt(),
            json_schema=MASK_CHECK_SCHEMA,
            note="mask-check",
        )
        raise_if_incomplete(response)
        answer = parse_answer(response.text)
        cost = float(response.cost_usd)
        self._log(npz, oid, wanted, clean_claim, answer, sheet, cost)
        return MaskCheckResult(
            inside=answer["inside"],
            outside=answer["outside"],
            covers=answer["covers"],
            verdict=answer["verdict"],
            reason=answer["reason"],
            sheet=sheet,
            cost_usd=cost,
        )

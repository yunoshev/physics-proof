"""M7 probes: sheet geometry, tint locality, errors, limit, parsing (offline).

Plus one opt-in live call (``-m api``, under $0.01) on the synthetic
fixtures: a red box with a blue handle, mask (a) = box + handle and
mask (b) = box only. The fake client serves canned answers wrapped in
prose and records every ``respond`` call so the error and limit probes
can assert that no API call was made.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from PIL import Image
from scipy import ndimage

from physics_proof.blocks import load_masks, mask_stats
from physics_proof.mask_check import (
    MASK_CHECK_SCHEMA,
    MAX_SHEET_WIDTH,
    PROMPT_PATH,
    MaskCheck,
    MaskCheckLimitError,
    MaskCheckResult,
    check_frames,
    crop_for,
    parse_answer,
)

PROMPT_TEXT = PROMPT_PATH.read_text(encoding="utf-8").strip()
CLAIM = "the mask covers only the red box"


class FakeSpark:
    """Fake Spark client: prose-wrapped JSON answers, records respond calls."""

    def __init__(self, verdict: str = "covers_more", cost: float = 0.0015) -> None:
        self.verdict = verdict
        self.cost = cost
        self.calls: list[tuple[Any, dict]] = []

    def image_part(self, path: Path) -> dict:
        return {"type": "input_image", "image_url": "data:image/png;base64,FAKE"}

    def respond(self, messages: Any, **kwargs: Any) -> SimpleNamespace:
        self.calls.append((messages, kwargs))
        assert kwargs.get("json_schema") == MASK_CHECK_SCHEMA
        assert kwargs.get("instructions") == PROMPT_TEXT
        assert kwargs.get("note") == "mask-check"
        payload = (
            "Here is my assessment: "
            + json.dumps(
                {
                    "inside": "red box and a blue handle on top",
                    "outside": "grey background around the box",
                    "covers": "the main red box and the upper blue handle",
                    "verdict": self.verdict,
                    "reason": "the tint covers the box plus the handle",
                }
            )
            + " Hope that helps."
        )
        return SimpleNamespace(text=payload, cost_usd=self.cost)


def _tool(
    tmp_path: Path, fixtures: Path, fake: FakeSpark, **kwargs: Any
) -> MaskCheck:
    return MaskCheck(fake, tmp_path / "ws", fixtures / "maskcheck_clip.mp4", **kwargs)


def test_sheet_geometry_and_tint_locality(
    tmp_path: Path, fixtures_dir: Path
) -> None:
    """Probe 1: 4-frame sheet exists, is narrow, tint stays inside the mask."""
    npz = fixtures_dir / "maskcheck_a.npz"
    fake = FakeSpark()
    tool = _tool(tmp_path, fixtures_dir, fake)
    result = tool.run(npz, 1, [0, 2, 4, 6], CLAIM)
    assert isinstance(result, MaskCheckResult)
    assert result.sheet.exists()
    assert result.sheet.name == "maskcheck_a.1.1.png"
    sheet = np.asarray(Image.open(result.sheet).convert("RGB"))
    assert sheet.shape[1] <= MAX_SHEET_WIDTH
    assert len(result.text()) <= 800

    mask_set = load_masks(npz)
    track = mask_set.of(1)
    stats = mask_stats(track)
    by_frame = {int(f): stats[i] for i, f in enumerate(mask_set.frames)}
    height, width = 240, 320
    top = 0
    diff_total = 0
    for frame in (0, 2, 4, 6):
        cx1, cy1, cx2, cy2 = crop_for(by_frame[frame]["bbox"], width, height)
        cw, ch = cx2 - cx1, cy2 - cy1
        scale = min(1.0, MAX_SHEET_WIDTH / (2 * cw))
        half_w, pair_h = round(cw * scale), round(ch * scale)
        row = sheet[top : top + pair_h, : 2 * half_w]
        assert row.shape == (pair_h, 2 * half_w, 3), (frame, row.shape)
        left, right = row[:, :half_w], row[:, half_w:]
        small = np.asarray(
            Image.fromarray(track[int(np.flatnonzero(mask_set.frames == frame)[0])][cy1:cy2, cx1:cx2]).resize(
                (half_w, pair_h), Image.NEAREST
            ),
            dtype=bool,
        )
        edge = np.asarray(
            ndimage.binary_dilation(small, structure=np.ones((3, 3)))
            ^ ndimage.binary_erosion(small, structure=np.ones((3, 3))),
            dtype=bool,
        )
        allowed = ndimage.binary_dilation(small | edge, iterations=3)
        diff = np.asarray((left != right).any(axis=2))
        assert diff.any(), f"frame {frame}: tint changed nothing"
        assert not diff[~allowed].any(), f"frame {frame}: tint leaked outside mask"
        diff_total += int(diff.sum())
        top += pair_h
    assert top == sheet.shape[0]
    assert diff_total > 100
    assert len(fake.calls) == 1
    messages, _ = fake.calls[0]
    user_text = messages[0]["content"][0]["text"]
    assert CLAIM in user_text
    assert str(npz) not in user_text  # no run context beyond claim + sheet
    assert messages[0]["content"][1]["type"] == "input_image"


def test_bad_inputs_raise_without_api_call(
    tmp_path: Path, fixtures_dir: Path
) -> None:
    """Probe 2: bad frames, unknown object, empty claim fail before any call."""
    npz = fixtures_dir / "maskcheck_a.npz"
    fake = FakeSpark()
    tool = _tool(tmp_path, fixtures_dir, fake)
    with pytest.raises(ValueError):
        tool.run(npz, 1, [0, 1, 99], CLAIM)  # frame not in npz
    with pytest.raises(ValueError):
        tool.run(npz, 1, [], CLAIM)  # 0 frames
    with pytest.raises(ValueError):
        tool.run(npz, 1, [0, 1, 2, 3, 4], CLAIM)  # 5 frames
    with pytest.raises(ValueError):
        tool.run(npz, 7, [0], CLAIM)  # unknown object id
    with pytest.raises(ValueError):
        tool.run(npz, 1, [0], "   ")  # empty claim
    with pytest.raises(ValueError):
        check_frames([0, 0], [0, 1, 2])  # duplicates
    assert fake.calls == []
    assert tool.checks_made == 0


def test_limit_refuses_fifth_check(tmp_path: Path, fixtures_dir: Path) -> None:
    """Probe 3: the 5th check is refused with no client call; has_check works."""
    npz_a = fixtures_dir / "maskcheck_a.npz"
    npz_b = fixtures_dir / "maskcheck_b.npz"
    fake = FakeSpark()
    tool = _tool(tmp_path, fixtures_dir, fake, limit=4)
    assert tool.has_check(npz_a, 1) is False
    for n in range(4):
        result = tool.run(npz_a, 1, [n], CLAIM + " %d" % n)
        assert result.sheet.name == "maskcheck_a.1.%d.png" % (n + 1)
    assert tool.checks_made == 4
    assert tool.has_check(npz_a, 1) is True
    assert tool.has_check(npz_b, 1) is False
    assert tool.has_check(npz_a, 2) is False
    with pytest.raises(MaskCheckLimitError):
        tool.run(npz_b, 1, [0], CLAIM)
    assert len(fake.calls) == 4
    assert tool.checks_made == 4
    lines = (tmp_path / "ws" / "mask_checks.jsonl").read_text().splitlines()
    assert len(lines) == 4
    for line in lines:
        record = json.loads(line)
        assert set(("npz", "object", "frames", "claim", "answer", "cost_usd")) <= set(
            record
        )
        assert record["answer"]["verdict"] == "covers_more"
    assert tool.has_check(npz_b, 1) is False
    # A fresh tool on the same workspace sees the log too.
    assert _tool(tmp_path, fixtures_dir, fake, limit=4).has_check(npz_a, 1) is True


def test_prose_wrapped_answers_parse() -> None:
    """Probe 4: fences, chatter and padded verdicts still parse."""
    fenced = (
        "Sure thing!\n```json\n"
        + json.dumps(
            {
                "inside": "red box",
                "outside": "grey",
                "covers": "the red box",
                "verdict": "agrees",
                "reason": "matches exactly",
            }
        )
        + "\n```\nDone."
    )
    assert parse_answer(fenced)["verdict"] == "agrees"
    padded = json.dumps(
        {
            "inside": "box and handle",
            "outside": "grey",
            "covers": "box plus handle",
            "verdict": "  Covers_More ",
            "reason": "extra bit on top",
        }
    )
    assert parse_answer("analysis: " + padded)["verdict"] == "covers_more"
    with pytest.raises(ValueError):
        parse_answer("no json here at all")
    with pytest.raises(ValueError):
        parse_answer(json.dumps({"inside": "x", "verdict": "maybe"}))


@pytest.mark.api
def test_live_mask_check_call(tmp_path: Path, fixtures_dir: Path) -> None:
    """API probe: box+handle reads covers_more, box-only reads agrees (<$0.01)."""
    from physics_proof.config import Settings
    from physics_proof.ledger import Ledger
    from physics_proof.meta_client import MetaClient

    ledger = Ledger(tmp_path / "run.jsonl", tmp_path / "global.jsonl")
    client = MetaClient(settings=Settings(), ledger=ledger, run="m7-api")
    tool = MaskCheck(client, tmp_path / "ws", fixtures_dir / "maskcheck_clip.mp4")
    over = tool.run(fixtures_dir / "maskcheck_a.npz", 1, [1, 4, 7], CLAIM)
    print("\nmask check (a): " + over.text(), flush=True)
    assert over.verdict == "covers_more"
    blob = (over.covers + " " + over.inside).lower()
    assert "blue" in blob, over.text()  # the handle is the only blue part
    exact = tool.run(fixtures_dir / "maskcheck_b.npz", 1, [1, 4, 7], CLAIM)
    print("mask check (b): " + exact.text(), flush=True)
    assert exact.verdict == "agrees"
    total = over.cost_usd + exact.cost_usd
    print("mask check total cost: $%.6f" % total, flush=True)
    assert total < 0.01
    assert tool.has_check(fixtures_dir / "maskcheck_a.npz", 1) is True

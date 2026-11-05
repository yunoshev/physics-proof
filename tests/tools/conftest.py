# generated from brief/07 · part 07 owns this file
"""Shared fixtures for the part-07 tool tests.

Whole-suite rule (part 04 §3): a test module never imports this file
by name — helpers are pytest fixtures here, factories where a test
calls them with arguments. Nothing here touches the network; live
sandbox probes run only through the ``sandbox_live`` fixture, which
skips (never passes) when ``sandbox-exec`` cannot run a canary.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src.accounting import Ledger


@pytest.fixture
def make_run(tmp_path):
    """Factory: a minimal run dir with clip + timing.json.

    ``make_run(frames=40, cuts=(), dups=())`` writes
    ``input/clip.mp4`` (a moving white square, 160x120) and a
    matching ``input/timing.json`` with measured per-frame
    timestamps, plus empty ``workspace/``, ``artifacts/`` and
    ``logs/``. Each call returns a fresh directory.
    """
    counter = {"n": 0}

    def _make(frames=40, cuts=(), dups=(), fps=25.0):
        import cv2
        import numpy as np

        counter["n"] += 1
        base = tmp_path / f"run_{counter['n']}"
        (base / "input").mkdir(parents=True)
        (base / "workspace").mkdir(parents=True)
        (base / "artifacts").mkdir(parents=True)
        (base / "logs").mkdir(parents=True)
        clip = base / "input" / "clip.mp4"
        writer = cv2.VideoWriter(str(clip),
                                 cv2.VideoWriter_fourcc(*"mp4v"),
                                 float(fps), (160, 120))
        assert writer.isOpened(), "no mp4 writer for the fixture clip"
        try:
            for i in range(int(frames)):
                grid = np.zeros((120, 160, 3), dtype=np.uint8)
                x = (i * 3) % 120
                grid[40:80, x:x + 40] = 255
                writer.write(grid)
        finally:
            writer.release()
        stamps = [round(i / float(fps), 6) for i in range(int(frames))]
        timing = {"frame_count": int(frames), "measured_fps": float(fps),
                  "timestamps": stamps, "cuts": list(cuts),
                  "duplicate_runs": [list(d) for d in dups],
                  "duration_s": (stamps[-1] if stamps else 0.0)}
        (base / "input" / "timing.json").write_text(
            json.dumps(timing), encoding="utf-8")
        return base

    return _make


@pytest.fixture
def ledger():
    """A fresh part-14 ledger (no caps hit)."""
    return Ledger(run_id="test-run")


@pytest.fixture
def sandbox_live():
    """Canary gate for live ``sandbox-exec`` probes.

    Skips when ``sandbox-exec`` is missing or cannot apply even a
    trivial profile (e.g. the nested sandbox of a coding agent); a
    skipped live probe is reported as skipped, never as passed.
    """
    from src.tools.sandbox import build_profile, sandbox_available

    if not sandbox_available():
        pytest.skip("sandbox-exec not on PATH")
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tools-canary-") as tmp:
        profile = build_profile(tmp)
        try:
            completed = subprocess.run(
                ["sandbox-exec", "-p", profile, "/usr/bin/true"],
                capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            pytest.skip(f"sandbox-exec cannot run here: {exc}")
        if completed.returncode != 0:
            pytest.skip("sandbox-exec canary failed: "
                        + (completed.stderr.decode("utf-8", "replace")
                           [:200]))
    return True


@pytest.fixture
def fake_sam():
    """A scripted SAM backend: ``(phrase, indices, frames) -> masks``."""
    import numpy as np

    calls = {"n": 0}

    def _sam(phrase, frame_indices, frames):
        calls["n"] += 1
        grids = list(frames)
        height, width = np.asarray(grids[0]).shape[:2]
        seq = []
        for _ in frame_indices:
            mask = np.zeros((height, width), dtype=bool)
            mask[30:70, 20:60] = True
            seq.append(mask)
        return {"obj0": seq}

    _sam.calls = calls
    return _sam


@pytest.fixture
def blind_ok():
    """A blind backend recording its request; answering coverage."""
    seen = {}

    def _blind(request):
        seen.update(dict(request))
        return {"description": "covers the left half of the bright "
                               "region, excluding its right edge",
                "alternatives": ["covers the whole bright region"],
                "usage": {"input_tokens": 10, "cached_tokens": 0,
                          "output_tokens": 5, "reasoning_tokens": 0}}

    _blind.seen = seen
    return _blind


@pytest.fixture
def search_ok():
    """A search backend with the real client answer shape."""
    calls = []

    def _search(query):
        calls.append(query)
        return {"answer": [
            {"text": "life-support backpack height 0.66 m",
             "source_url": "https://example.com/plss",
             "quote": "backpack height 0.66 m"},
            {"text": "second fact",
             "source_url": "https://example.org/other",
             "quote": "other quote"}],
            "facts": [
                {"text": "life-support backpack height 0.66 m",
                 "source_url": "https://example.com/plss",
                 "quote": "backpack height 0.66 m"},
                {"text": "second fact",
                 "source_url": "https://example.org/other",
                 "quote": "other quote"}],
            "sources": ["https://example.com/plss",
                        "https://example.org/other"]}

    _search.calls = calls
    return _search

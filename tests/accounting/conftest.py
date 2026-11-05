# generated from brief/14 · part 14 owns this file
"""Shared fixtures for the part-14 accounting tests.

Whole-suite rule (part 04 §3): a test module never imports this file
by name — helpers are pytest fixtures here, factories where a test
calls them with arguments. Nothing here touches the network.
"""

from __future__ import annotations

import pytest

from src.accounting import Ledger


@pytest.fixture
def make_ledger():
    """Factory: a fresh part-14 ledger for a run id."""
    def _make(run_id="run"):
        return Ledger(run_id=run_id)

    return _make


@pytest.fixture
def make_run(tmp_path):
    """Factory: a fresh run directory with the part-04 §4 layout."""
    counter = {"n": 0}

    def _make():
        counter["n"] += 1
        base = tmp_path / f"run_{counter['n']}"
        for sub in ("input", "workspace", "artifacts", "logs"):
            (base / sub).mkdir(parents=True)
        return base

    return _make


@pytest.fixture
def usage():
    """Factory: a terminal-event usage block with explicit fields."""
    def _make(input_tokens=1000, cached_tokens=200, output_tokens=500,
              reasoning_tokens=100):
        return {"input_tokens": int(input_tokens),
                "cached_tokens": int(cached_tokens),
                "output_tokens": int(output_tokens),
                "reasoning_tokens": int(reasoning_tokens)}

    return _make

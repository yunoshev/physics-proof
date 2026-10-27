"""Shared fixtures for M1 tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def pytest_collection_modifyitems(config, items):
    markexpr = config.getoption("markexpr", "")
    if "api" not in markexpr:
        skip_api = pytest.mark.skip(reason="real API call; run with -m api")
        for item in items:
            if "api" in item.keywords:
                item.add_marker(skip_api)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES

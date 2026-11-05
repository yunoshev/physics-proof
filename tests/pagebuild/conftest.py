# generated from brief/13 · part 13 owns this file
"""Shared page-build fixtures for part 13's pagebuild tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def built_pages(tmp_path_factory):
    """Build clip-a / still-range / run-7 pages once per session."""
    from src.pagebuild import build_page

    out = {}
    jobs = {
        "clip-a": ("fixtures/clip-a/result.json",
                   "fixtures/clip-a/input/clip.mp4",
                   "fixtures/clip-a/summary.json"),
        "still-range": ("fixtures/still-range/result.json", None, None),
        "run-7": ("fixtures/run-7/result.json", None, None),
    }
    for name, (res, vid, summ) in jobs.items():
        dest = tmp_path_factory.mktemp("pg") / name
        build_page(str(ROOT / res),
                   str(ROOT / vid) if vid else None,
                   str(dest),
                   str(ROOT / summ) if summ else None,
                   slug=name)
        out[name] = dest
    return out


@pytest.fixture(scope="session")
def run22_page(tmp_path_factory):
    """Run 22's page (brief part 13 §42), built once per session."""
    from src.pagebuild import build_page

    dest = tmp_path_factory.mktemp("pg22") / "run-22"
    build_page(str(ROOT / "fixtures/source/run-22/result.json"),
               str(ROOT / "fixtures/source/run-22/input/clip.mp4"),
               str(dest),
               str(ROOT / "fixtures/source/run-22/summary.json"),
               slug="run-22")
    return dest


@pytest.fixture(scope="session")
def fake1_page(tmp_path_factory):
    """Sped-up Moon page (brief part 13 §45), built once per session."""
    from src.pagebuild import build_page

    dest = tmp_path_factory.mktemp("pg45") / "fake-1"
    build_page(str(ROOT / "fixtures/source/fake-1/result.json"),
               str(ROOT / "fixtures/source/fake-1/input/clip.mp4"),
               str(dest),
               str(ROOT / "fixtures/source/fake-1/summary.json"),
               slug="fake-1")
    return dest


@pytest.fixture(scope="session")
def clip_a_dir(built_pages):
    return built_pages["clip-a"]


def copy_fixture_tree(name: str, dest: Path) -> Path:
    """Copy a run-style fixture folder to *dest* for mutation."""
    shutil.copytree(ROOT / "fixtures" / name, dest / name)
    return dest / name

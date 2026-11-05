# generated from brief/15 · part 15 owns this file
"""Shared fixtures for the part-15 dev-loop tests.

Whole-suite rule (part 04 §3): a test module never imports this file
by name — helpers are pytest fixtures here, used by parameter.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent.parent


def _load_devloop():
    path = REPO / "tools" / "dev_loop"
    name = "dev_loop_under_test"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def devloop():
    """The part-15 dev_loop tool, loaded by path (it has no .py suffix)."""
    return _load_devloop()


@pytest.fixture
def make_repo(devloop, tmp_path):
    """Factory: a minimal fixture repo for dev_loop runs.

    ``make_repo(part="99", owned=[...], test_files={...})`` creates a
    root with ``tools/parts.json``, ``PLAN.md``, the part spec, one
    skill, and the given owned test files (``{rel: content}``). The
    manifest is sealed over the owned files so the hand-edit check
    passes. Returns the root path.
    """
    counter = {"n": 0}

    def _make(
        part="99",
        owned=None,
        spec_text="Fake part 99.\n",
        test_files=None,
        browser=False,
        extra_spec_lines="",
    ):
        counter["n"] += 1
        root = tmp_path / f"repo{counter['n']}"
        (root / "tools").mkdir(parents=True)
        (root / "brief").mkdir(parents=True)
        (root / "skills").mkdir(parents=True)
        owned = list(owned or ["tests/fake99/"])
        spec_rel = "brief/99-fake-part.md"
        (root / spec_rel).write_text(
            spec_text + extra_spec_lines, encoding="utf-8"
        )
        (root / "PLAN.md").write_text("Fake plan.\n", encoding="utf-8")
        (root / "brief" / "04-architecture-and-constraints.md").write_text(
            "Fake shared constraints.\n", encoding="utf-8"
        )
        (root / "skills" / "fake-skill.md").write_text(
            "Fake skill.\n", encoding="utf-8"
        )
        for rel, content in dict(test_files or {}).items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        config = {
            "defaults": {
                "model": "fake-model",
                "effort": "low",
                "max_attempts": 2,
                "max_model_steps": 5,
                "test_runner": [sys.executable, "-m", "pytest"],
            },
            "parts": {
                part: {
                    "model": "fake-model",
                    "effort": "low",
                    "max_model_steps": 5,
                    "owned_paths": owned,
                    "skills": ["skills/fake-skill.md"],
                    "spec": spec_rel,
                    "test_command": [
                        sys.executable, "-m", "pytest",
                        "tests/fake99/", "-q",
                    ],
                    "browser": browser,
                }
            },
        }
        (root / "tools" / "parts.json").write_text(
            json.dumps(config), encoding="utf-8"
        )
        manifest = root / "tools" / "manifest.json"
        manifest.write_text(
            json.dumps({"version": 1, "files": {}}), encoding="utf-8"
        )
        devloop.update_manifest(manifest, root, part, owned)
        return root

    return _make


@pytest.fixture
def run_args():
    """Factory: argparse-like args for ``devloop.cmd_part`` in a repo."""

    def _args(root, part="99"):
        return SimpleNamespace(
            root=str(root),
            part=part,
            config=str(root / "tools" / "parts.json"),
            manifest=str(root / "tools" / "manifest.json"),
            iterations=str(root / "ITERATIONS.md"),
            runs_dir="runs",
            out="pages",
            acceptance=False,
            pages=False,
        )

    return _args

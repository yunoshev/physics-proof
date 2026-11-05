# generated from brief/15 · part 15 owns this file
"""README follows every generation (brief part 15 §15).

Offline: the coding-agent call and every suite run are stubbed. The only
real subprocess is the part-15-owned `tools/make_readme` copied into the
fixture repo: it is pure local reads, no model calls, no network, no
money. `collect_test_functions` still shells to real `pytest
--collect-only` on tiny fixture repos.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent

PASS_TEST = "def test_f():\n    pass\n"

BASELINE_OK = (
    "tests/fake99/test_f.py::test_f PASSED\n"
    "tests/other/test_o.py::test_o PASSED\n"
)

PRICED_USAGE = {
    "models": [
        {
            "model": "muse-spark-1.3-contributor",
            "input_tokens": 1_000_000,
            "cached_tokens": 900_000,
            "output_tokens": 1_000_000,
            "calls": 3,
        }
    ],
    "calls": 3,
    "completed_calls": 3,
    "failed_calls": 0,
}

# (100k x $0.10 + 900k x $0.002 + 1M x $0.20) / 1M, reasoning already
# inside output_tokens.
PRICED_COST = (100_000 * 0.10 + 900_000 * 0.002 + 1_000_000 * 0.20) / 1_000_000


def _stub_muse(monkeypatch, devloop, behaviour):
    def fake_run_muse(
        *, model, effort, max_steps, workspace, prompt, browser=False
    ):
        return behaviour(Path(workspace))

    monkeypatch.setattr(devloop, "run_muse", fake_run_muse)


def _completed(root, usage=None, writes=None):
    for rel, content in dict(writes or {}).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return {
        "usage": usage or PRICED_USAGE,
        "terminal": {"terminal": "completed", "text": "stub generation"},
        "returncode": 0,
        "stderr": "",
        "stdout_text": '{"payload": {"kind": "other"}}',
    }


def _stub_suites(monkeypatch, devloop, part_results=(0, "1 passed"),
                 baselines=None, guards=None):
    baseline_outputs = list(baselines or [BASELINE_OK])
    guard_outputs = list(guards or [BASELINE_OK])

    def fake_part_tests(test_command, cwd, browser=False):
        code, output = part_results
        return code, output

    def fake_collection(test_runner, cwd, browser=False):
        return 0, ""

    state = {"count": 0}

    def fake_full_suite(test_runner, cwd, browser=False):
        state["count"] += 1
        if state["count"] == 1:
            return 0, baseline_outputs[0]
        return 0, guard_outputs[min(state["count"] - 2,
                                    len(guard_outputs) - 1)]

    def fake_one_test(test_runner, cwd, test_id, browser=False):
        return 0, ""

    monkeypatch.setattr(devloop, "run_part_tests", fake_part_tests)
    monkeypatch.setattr(devloop, "run_suite_collection", fake_collection)
    monkeypatch.setattr(devloop, "run_full_suite", fake_full_suite)
    monkeypatch.setattr(devloop, "run_one_test", fake_one_test)


def _with_make_readme(root):
    """Give a fixture repo the real make_readme script (copied, not moved)."""
    shutil.copyfile(REPO / "tools" / "make_readme", root / "tools" / "make_readme")


def _load_copy(root):
    name = "make_readme_copy_under_test"
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(
        name, str(root / "tools" / "make_readme")
    )
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _iterations_cost(root):
    line = (root / "ITERATIONS.md").read_text(encoding="utf-8").strip()
    match = re.search(r"cost \$([0-9]+\.[0-9]+)", line)
    assert match, f"no priced cost on the ITERATIONS.md line: {line!r}"
    return f"${match.group(1)}"


def test_generation_refreshes_readme_with_run_cost(
    devloop, make_repo, run_args, monkeypatch
):
    """§15: after a stubbed generation, README.md equals a fresh
    make_readme output and contains that generation's cost."""
    root = make_repo(test_files={"tests/fake99/test_f.py": PASS_TEST})
    _with_make_readme(root)
    _stub_muse(
        monkeypatch, devloop,
        lambda r: _completed(r, writes={"tests/fake99/test_f.py": PASS_TEST}),
    )
    _stub_suites(monkeypatch, devloop)
    assert devloop.cmd_part(run_args(root)) == 0

    readme_text = (root / "README.md").read_text(encoding="utf-8")
    fresh = _load_copy(root).build_readme(root)
    assert readme_text == fresh
    assert _iterations_cost(root) in readme_text


def test_failed_generation_still_refreshes_readme(
    devloop, make_repo, run_args, monkeypatch
):
    """§15: the red end also leaves README.md matching make_readme."""
    root = make_repo(test_files={"tests/fake99/test_f.py": PASS_TEST})
    _with_make_readme(root)
    _stub_muse(
        monkeypatch, devloop,
        lambda r: _completed(r, writes={"tests/fake99/test_f.py": PASS_TEST}),
    )
    _stub_suites(
        monkeypatch, devloop,
        part_results=(1, "FAILED tests/fake99/test_f.py::test_f - boom"),
    )
    assert devloop.cmd_part(run_args(root)) == 1

    readme_text = (root / "README.md").read_text(encoding="utf-8")
    assert readme_text == _load_copy(root).build_readme(root)


def test_broken_readme_refresh_fails_success_path(
    devloop, make_repo, run_args, monkeypatch, capsys
):
    """A make_readme that exits non-zero fails the run loudly instead of
    leaving a stale README behind."""
    root = make_repo(test_files={"tests/fake99/test_f.py": PASS_TEST})
    (root / "tools" / "make_readme").write_text(
        "#!/usr/bin/env python3\nimport sys\nsys.exit('boom')\n",
        encoding="utf-8",
    )
    _stub_muse(
        monkeypatch, devloop,
        lambda r: _completed(r, writes={"tests/fake99/test_f.py": PASS_TEST}),
    )
    _stub_suites(monkeypatch, devloop)
    assert devloop.cmd_part(run_args(root)) == 1
    assert "README refresh failed" in capsys.readouterr().err


def test_refresh_skipped_without_make_readme(devloop, tmp_path):
    """Fixture trees without tools/make_readme: quiet skip, not failure."""
    code, output = devloop.refresh_readme(tmp_path)
    assert code == 0
    assert "skipping" in output


def test_generation_without_make_readme_writes_no_readme(
    devloop, make_repo, run_args, monkeypatch
):
    """A repo without the script regenerates exactly as before: no
    README.md appears and the exit code is untouched."""
    root = make_repo(test_files={"tests/fake99/test_f.py": PASS_TEST})
    _stub_muse(
        monkeypatch, devloop,
        lambda r: _completed(r, writes={"tests/fake99/test_f.py": PASS_TEST}),
    )
    _stub_suites(monkeypatch, devloop)
    assert devloop.cmd_part(run_args(root)) == 0
    assert not (root / "README.md").exists()

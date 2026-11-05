"""Gate tests: contract, isolation, pass/fail, edits, caps (part 10 §2)."""
from __future__ import annotations

import subprocess
import sys

import pytest

from src.selfbuilt import gate
from src.selfbuilt import registry as reg
from tests.selfbuilt.conftest import (
    GOOD_MODULE,
    fail_executor,
    make_test,
    pass_executor,
)


def test_two_file_contract_and_sb_prefix(run_dir):
    rejected = gate.try_register(run_dir, "wall_line", GOOD_MODULE,
                                 make_test("sb_demo"), "no prefix", 1,
                                 executor=pass_executor)
    assert not rejected["ok"]
    assert rejected["error"]["code"] == "bad_tool_name"

    test_source = make_test("sb_wall_line")
    result = gate.try_register(run_dir, "sb_wall_line", GOOD_MODULE,
                               test_source, "fit wall line", 2,
                               executor=pass_executor)
    assert result["ok"]
    directory = run_dir / "workspace" / "selfbuilt"
    assert (directory / "sb_wall_line.py").read_text() == GOOD_MODULE
    assert (directory / "test_sb_wall_line.py").read_text() == test_source


@pytest.mark.parametrize("source", [
    "import requests\n",
    "import pandas as pd\n",
    "import flask\n",
    "import src.tools\n",
    "import src.config\n",
    "import src.loop\n",
    "from src.cli import main\n",
    "import importlib\n",
    "import importlib.util\n",
    "__import__('os')\n",
    "from . import sibling\n",
    "import sb_other_tool\n",
    "import pytest\n",
])
def test_module_import_allowlist_rejects(source):
    ok, detail = gate.check_module_imports(source)
    assert not ok, source
    assert detail


@pytest.mark.parametrize("source", [
    "import os\n",
    "import sys\nimport math\n",
    "import numpy as np\n",
    "import scipy.signal\n",
    "from scipy import stats\n",
    "import cv2\n",
    "from src.helpers import tracks\n",
    "import src.helpers.physics\n",
    "from __future__ import annotations\n",
])
def test_module_import_allowlist_accepts(source):
    assert gate.check_module_imports(source) == (True, None)


def test_check_module_imports_rejects_syntax_errors():
    ok, detail = gate.check_module_imports("def broken(:\n")
    assert not ok and "syntax" in detail


def test_test_file_may_import_sibling_and_pytest_only():
    sibling = "from sb_wall_line import fit\n"
    assert gate.check_module_imports(sibling, name="sb_wall_line",
                                     is_test=True) == (True, None)
    assert gate.check_module_imports("import pytest\n", is_test=True)[0]
    ok, _ = gate.check_module_imports("import sb_other_tool\n",
                                      name="sb_wall_line", is_test=True)
    assert not ok
    ok, _ = gate.check_module_imports("import requests\n", is_test=True)
    assert not ok
    ok, _ = gate.check_module_imports("import src.tools\n", is_test=True)
    assert not ok


def test_infra_failure_consumes_no_attempt(run_dir):
    def broken(test_path, isolated_dir, timeout_s):
        raise RuntimeError("boom")

    result = gate.try_register(run_dir, "sb_broken", GOOD_MODULE,
                               make_test("sb_broken"), "broken", 1,
                               executor=broken)
    assert result["error"]["code"] == "exec_failed"
    assert reg.load_registry(run_dir) == {"tools": []}

    def infra(test_path, isolated_dir, timeout_s):
        return {"returncode": 71, "stdout": "",
                "stderr": "sandbox-exec: sandbox_apply: Operation not "
                          "permitted",
                "timed_out": False, "infra_error": True}

    result = gate.try_register(run_dir, "sb_nosb", GOOD_MODULE,
                               make_test("sb_nosb"), "nosb", 1,
                               executor=infra)
    assert result["error"]["code"] == "sandbox_unavailable"
    assert reg.load_registry(run_dir) == {"tools": []}


def test_disallowed_import_consumes_no_attempt(run_dir):
    calls = []
    result = gate.try_register(run_dir, "sb_bad", "import requests\n",
                               make_test("sb_bad"), "bad", 1,
                               executor=lambda *a: (
                                   calls.append(a) or pass_executor(*a)))
    assert result["error"]["code"] == "disallowed_import"
    assert calls == []
    assert reg.load_registry(run_dir) == {"tools": []}


def test_test_runs_in_isolated_tmpdir_only(run_dir):
    seen = {}

    def recording(test_path, isolated_dir, timeout_s):
        seen["files"] = sorted(p.name for p in isolated_dir.iterdir())
        assert test_path.parent == isolated_dir
        return pass_executor(test_path, isolated_dir, timeout_s)

    result = gate.try_register(run_dir, "sb_iso", GOOD_MODULE,
                               make_test("sb_iso"), "isolation", 4,
                               executor=recording)
    assert result["ok"]
    assert seen["files"] == ["sb_iso.py", "test_sb_iso.py"]


def _real_executor(test_path, isolated_dir, timeout_s):
    from pathlib import Path
    isolated = Path(isolated_dir)
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
           "PYTHONPATH": str(isolated), "HOME": "/nonexistent"}
    try:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q",
                               Path(test_path).name],
                              capture_output=True, text=True,
                              timeout=timeout_s, env=env,
                              cwd=str(isolated), check=False)
    except subprocess.TimeoutExpired as exc:
        return {"returncode": None, "stdout": "", "stderr": str(exc),
                "timed_out": True}
    return {"returncode": proc.returncode, "stdout": proc.stdout,
            "stderr": proc.stderr, "timed_out": False}


SELF_CONTAINED_MODULE = "def add(a, b):\n    return a + b\n"
SELF_CONTAINED_TEST = ("from sb_add import add\n\n\n"
                       "def test_add():\n"
                       "    assert add(2, 3) == 5\n")


def test_isolated_run_passes_for_self_contained_pair(run_dir):
    result = gate.try_register(run_dir, "sb_add", SELF_CONTAINED_MODULE,
                               SELF_CONTAINED_TEST, "add numbers", 5,
                               executor=_real_executor)
    assert result["ok"], result


def test_isolated_run_cannot_reach_workspace(run_dir):
    decoy = run_dir / "workspace" / "artifacts" / "secret.txt"
    decoy.parent.mkdir(parents=True, exist_ok=True)
    decoy.write_text("the run's own numbers", encoding="utf-8")
    cheating_test = ("def test_cheat():\n"
                     "    assert open('../secret.txt').read() == 'x'\n")
    result = gate.try_register(run_dir, "sb_cheat", SELF_CONTAINED_MODULE,
                               cheating_test, "cheat", 6,
                               executor=_real_executor)
    assert not result["ok"]
    assert result["error"]["code"] == "test_failed"
    assert not gate.is_importable(run_dir, "sb_cheat")


def test_pass_registers_and_importable_fail_not(run_dir):
    assert gate.import_path_for_run(run_dir) is None
    passed = gate.try_register(run_dir, "sb_good", GOOD_MODULE,
                               make_test("sb_good"), "good tool", 7,
                               executor=pass_executor)
    assert passed["ok"]
    failed = gate.try_register(run_dir, "sb_bad", GOOD_MODULE,
                               "def test_x():\n    assert False\n",
                               "bad tool", 8, executor=fail_executor)
    assert not failed["ok"]
    assert failed["error"]["code"] == "test_failed"
    assert "assert" in failed["error"]["detail"]
    assert gate.is_importable(run_dir, "sb_good") is True
    assert gate.is_importable(run_dir, "sb_bad") is False
    assert gate.importable_names(run_dir) == ["sb_good"]
    assert gate.import_path_for_run(run_dir) == str(
        run_dir / "workspace" / "selfbuilt")


def test_edit_hash_mismatch_unimportable_until_retest(run_dir):
    gate.try_register(run_dir, "sb_edit", GOOD_MODULE, make_test("sb_edit"),
                      "editable", 9, executor=pass_executor)
    assert gate.is_importable(run_dir, "sb_edit") is True
    module = run_dir / "workspace" / "selfbuilt" / "sb_edit.py"
    module.write_text(GOOD_MODULE + "\n# silent mutation\n", encoding="utf-8")
    assert gate.is_importable(run_dir, "sb_edit") is False
    assert gate.import_path_for_run(run_dir) is None
    retry = gate.try_register(run_dir, "sb_edit", module.read_text(),
                              make_test("sb_edit"), "editable", 10,
                              executor=pass_executor)
    assert retry["ok"]
    assert retry["metrics"]["attempts"] == 2
    assert gate.is_importable(run_dir, "sb_edit") is True


def test_caps_4_tools_3_attempts(run_dir):
    calls = []

    def counting(pass_or_fail):
        def run(test_path, isolated_dir, timeout_s):
            calls.append(True)
            return pass_or_fail(test_path, isolated_dir, timeout_s)
        return run

    for i in range(3):
        result = gate.try_register(run_dir, f"sb_tool{i}", GOOD_MODULE,
                                   make_test(f"sb_tool{i}"), f"tool {i}", i,
                                   executor=counting(pass_executor))
        assert result["ok"], result
    for _ in range(3):
        failed = gate.try_register(run_dir, "sb_flaky", GOOD_MODULE,
                                   "def test_x():\n    assert False\n",
                                   "flaky", 10,
                                   executor=counting(fail_executor))
        assert failed["error"]["code"] == "test_failed"
    entry = reg.find_tool(reg.load_registry(run_dir), "sb_flaky")
    assert entry["attempts"] == 3
    before = len(calls)
    capped = gate.try_register(run_dir, "sb_flaky", GOOD_MODULE,
                               make_test("sb_flaky"), "flaky", 11,
                               executor=counting(pass_executor))
    assert not capped["ok"]
    assert capped["error"]["code"] == "too_many_attempts"
    assert len(calls) == before  # refused before any test execution
    # tool0..2 + sb_flaky fill the 4-tool cap; a fifth name is refused.
    fifth = gate.try_register(run_dir, "sb_tool3", GOOD_MODULE,
                              make_test("sb_tool3"), "one too many", 12,
                              executor=counting(pass_executor))
    assert not fifth["ok"]
    assert fifth["error"]["code"] == "too_many_tools"
    assert len(calls) == before

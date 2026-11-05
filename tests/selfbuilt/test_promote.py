"""Promote tests: retest, copy, refuse conflicts/modified (part 10 §5)."""
from __future__ import annotations

from src.selfbuilt.gate import try_register
from src.selfbuilt.promote import main, promote
from tests.selfbuilt.conftest import (
    GOOD_MODULE,
    fail_executor,
    make_test,
    pass_executor,
)

RUN_ID = "20261027-000000"


def _registered_run(tmp_path, executor=pass_executor, name="sb_wall_line"):
    runs = tmp_path / "runs"
    run_dir = runs / RUN_ID
    result = try_register(run_dir, name, GOOD_MODULE, make_test(name),
                          "fit wall line", 17, executor=executor)
    assert result["ok"] == (executor is pass_executor)
    return runs, run_dir


def test_promote_retests_copies(tmp_path):
    runs, _ = _registered_run(tmp_path)
    repo = tmp_path / "repo"
    seen = []

    def recording(test_path, isolated_dir, timeout_s):
        seen.append(sorted(p.name for p in isolated_dir.iterdir()
                           if not p.name.startswith("_")))
        return pass_executor(test_path, isolated_dir, timeout_s)

    result = promote(RUN_ID, "sb_wall_line", runs_dir=runs, repo_root=repo,
                     executor=recording)
    assert result["ok"], result
    assert seen == [["sb_wall_line.py", "test_sb_wall_line.py"]]
    module = repo / "src/helpers/promoted/sb_wall_line.py"
    test = repo / "tests/helpers/test_sb_wall_line.py"
    assert module.read_bytes() == GOOD_MODULE.encode()
    assert test.read_bytes() == make_test("sb_wall_line").encode()
    assert (repo / "src/helpers/promoted/__init__.py").is_file()
    assert result["files"] == ["src/helpers/promoted/sb_wall_line.py",
                               "tests/helpers/test_sb_wall_line.py"]


def test_promote_refuses_conflicts(tmp_path):
    runs, _ = _registered_run(tmp_path)
    repo = tmp_path / "repo"
    dest = repo / "src/helpers/promoted/sb_wall_line.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("# existing helper\n", encoding="utf-8")
    result = promote(RUN_ID, "sb_wall_line", runs_dir=runs, repo_root=repo,
                     executor=pass_executor)
    assert not result["ok"]
    assert result["error"]["code"] == "promote_conflict"

    dest.unlink()
    dest_test = repo / "tests/helpers/test_sb_wall_line.py"
    dest_test.parent.mkdir(parents=True, exist_ok=True)
    dest_test.write_text("# existing test\n", encoding="utf-8")
    result = promote(RUN_ID, "sb_wall_line", runs_dir=runs, repo_root=repo,
                     executor=pass_executor)
    assert not result["ok"]
    assert result["error"]["code"] == "promote_conflict"


def test_promote_refuses_modified(tmp_path):
    runs, run_dir = _registered_run(tmp_path)
    calls = []
    (run_dir / "workspace" / "selfbuilt" / "sb_wall_line.py").write_text(
        GOOD_MODULE + "\n# mutated\n", encoding="utf-8")
    result = promote(RUN_ID, "sb_wall_line", runs_dir=runs,
                     repo_root=tmp_path / "repo",
                     executor=lambda *a: calls.append(a) or
                     pass_executor(*a))
    assert not result["ok"]
    assert result["error"]["code"] == "modified_since_registration"
    assert calls == []


def test_promote_refuses_failed_retest_and_unpassed(tmp_path):
    runs, _ = _registered_run(tmp_path)
    repo = tmp_path / "repo"
    result = promote(RUN_ID, "sb_wall_line", runs_dir=runs, repo_root=repo,
                     executor=fail_executor)
    assert not result["ok"]
    assert result["error"]["code"] == "retest_failed"
    assert not (repo / "src/helpers/promoted/sb_wall_line.py").exists()

    _registered_run(tmp_path, executor=fail_executor, name="sb_flaky")
    result = promote(RUN_ID, "sb_flaky", runs_dir=runs, repo_root=repo,
                     executor=pass_executor)
    assert not result["ok"]
    assert result["error"]["code"] == "tool_not_passed"


def test_promote_refuses_unknown_tool_and_bad_name(tmp_path):
    runs, _ = _registered_run(tmp_path)
    repo = tmp_path / "repo"
    result = promote(RUN_ID, "sb_nope", runs_dir=runs, repo_root=repo,
                     executor=pass_executor)
    assert result["error"]["code"] == "unknown_tool"
    result = promote(RUN_ID, "wall_line", runs_dir=runs, repo_root=repo,
                     executor=pass_executor)
    assert result["error"]["code"] == "bad_tool_name"


def test_promote_main_reports_failure_without_writes(tmp_path, capsys):
    runs, _ = _registered_run(tmp_path)
    code = main([RUN_ID, "sb_nope", "--runs-dir", str(runs)])
    assert code == 1
    out = capsys.readouterr().out
    assert "unknown_tool" in out

"""Human-only promotion of a self-built tool (part 10 section 5).

There is deliberately no agent-facing promote action. The maintainer runs::

    python -m src.selfbuilt.promote <run-id> <sb_name> [--runs-dir runs]

which re-runs the tool's test standalone (must pass again, outside the
run), copies the module to ``src/helpers/promoted/<name>.py`` and the test
to ``tests/helpers/test_<name>.py``, refuses name conflicts, and refuses
files modified since registration — and stops there. Wiring the promoted
module into the documented helper set is a deliberate human edit of the
spec'd library, reviewed like any other change.

Promotion is the only path by which run-generated code outlives its run,
and it carries its synthetic test with it: a promoted tool that later
fails its test is demoted by the same rule as any helper (part 09 §3).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from src.selfbuilt.gate import SELFBUILT_TEST_TIMEOUT_S, _default_executor
from src.selfbuilt.registry import (
    STATUS_PASSED,
    find_tool,
    load_registry,
    module_filename,
    selfbuilt_dir,
    sha256_file,
    test_filename,
    validate_tool_name,
)

#: Promotion destinations, relative to the repo root.
PROMOTED_MODULE_DIR = Path("src/helpers/promoted")
PROMOTED_TEST_DIR = Path("tests/helpers")


def _repo_root():
    return Path(__file__).resolve().parent.parent.parent


def promote(run_id, sb_name, runs_dir="runs", repo_root=None, executor=None,
            timeout_s=None):
    """Promote a registered tool into the helper library (human only).

    Args:
        run_id: Run id under ``<runs_dir>/``.
        sb_name: Registered tool name (``sb_`` prefix mandatory).
        runs_dir: Directory holding runs (default ``"runs"``).
        repo_root: Repo root for destinations; defaults to this file's
            repo. Tests inject a temporary root.
        executor: Test executor (defaults to the sandboxed runner).
        timeout_s: Standalone re-test timeout override.

    Returns:
        Part-07-shaped result; ``metrics`` names the copied files.
    """
    from src.selfbuilt.gate import _err, _ok

    root = Path(repo_root) if repo_root is not None else _repo_root()
    run_dir = Path(runs_dir) / str(run_id)
    if not run_dir.is_absolute():
        run_dir = root / run_dir

    ok, code, detail = validate_tool_name(sb_name)
    if not ok:
        return _err(code, detail)

    try:
        registry = load_registry(run_dir)
    except ValueError as exc:
        return _err("registry_corrupt", str(exc))
    entry = find_tool(registry, sb_name)
    if entry is None:
        return _err("unknown_tool",
                    f"{sb_name!r} is not in run {run_id}'s registry")
    if entry.get("status") != STATUS_PASSED:
        return _err("tool_not_passed",
                    f"{sb_name!r} never passed its synthetic test "
                    f"(status {entry.get('status')!r})")

    directory = selfbuilt_dir(run_dir)
    module_src = directory / module_filename(sb_name)
    test_src = directory / test_filename(sb_name)
    if not (module_src.is_file() and test_src.is_file()):
        return _err("tool_files_missing",
                    f"{sb_name!r} files missing from {directory}")
    try:
        if (sha256_file(module_src) != entry["module_sha256"]
                or sha256_file(test_src) != entry["test_sha256"]):
            return _err("modified_since_registration",
                        f"{sb_name!r} was modified after registration; "
                        f"re-test it in the run before promoting")
    except OSError as exc:
        return _err("tool_files_missing", str(exc))

    dest_module = root / PROMOTED_MODULE_DIR / module_filename(sb_name)
    dest_test = root / PROMOTED_TEST_DIR / test_filename(sb_name)
    if dest_module.exists():
        return _err("promote_conflict",
                    f"refusing: {dest_module} already exists")
    if dest_test.exists():
        return _err("promote_conflict",
                    f"refusing: {dest_test} already exists")

    timeout = float(timeout_s if timeout_s is not None
                    else SELFBUILT_TEST_TIMEOUT_S)
    run_executor = executor or _default_executor
    with tempfile.TemporaryDirectory(prefix="sb_promote_") as tmp:
        isolated = Path(tmp)
        (isolated / module_src.name).write_bytes(module_src.read_bytes())
        isolated_test = isolated / test_src.name
        isolated_test.write_bytes(test_src.read_bytes())
        result = run_executor(isolated_test, isolated, timeout)
    if result.get("timed_out") or result.get("returncode") != 0:
        output = ((result.get("stdout") or "")
                  + ("\n" + result.get("stderr")
                     if result.get("stderr") else ""))
        return _err("retest_failed",
                    f"{sb_name!r} standalone re-test failed "
                    f"(exit {result.get('returncode')}, "
                    f"timed_out={bool(result.get('timed_out'))}); "
                    f"not promoted; output:\n{output[-4000:]}")

    (root / PROMOTED_MODULE_DIR).mkdir(parents=True, exist_ok=True)
    (root / PROMOTED_TEST_DIR).mkdir(parents=True, exist_ok=True)
    init = root / PROMOTED_MODULE_DIR / "__init__.py"
    if not init.exists():
        init.write_text('"""Promoted self-built tools (part 10 §5)."""\n',
                        encoding="utf-8")
    shutil.copy2(module_src, dest_module)
    shutil.copy2(test_src, dest_test)
    files = [os.path.relpath(dest_module, root),
             os.path.relpath(dest_test, root)]
    return _ok(f"promoted {sb_name!r} from run {run_id} "
               f"(standalone re-test passed); wire it into the documented "
               f"helper set by hand",
               files=files,
               metrics={"run_id": str(run_id), "tool": sb_name})


def main(argv=None) -> int:
    """Entry point for ``python -m src.selfbuilt.promote``."""
    parser = argparse.ArgumentParser(
        description="Promote a passed self-built tool into src/helpers "
                    "(human only; see part 10 §5).")
    parser.add_argument("run_id")
    parser.add_argument("sb_name")
    parser.add_argument("--runs-dir", default="runs")
    args = parser.parse_args(argv)
    result = promote(args.run_id, args.sb_name, runs_dir=args.runs_dir)
    print(result["summary"])
    for path in result["files"]:
        print(f"  wrote {path}")
    if not result["ok"]:
        print(f"error: {result['error']['code']}: "
              f"{result['error']['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

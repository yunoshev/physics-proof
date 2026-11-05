"""The self-built-tool gate (part 10 section 2).

:func:`try_register` is the only way a tool enters the registry:

1. Name check (``sb_`` prefix, no helper/stdlib shadow) and static import
   checks (module: stdlib + numpy/scipy/OpenCV + ``src/helpers`` only; the
   test is held tighter — it may additionally import only its sibling
   module and ``pytest``). Rejections here execute no test, so they consume
   no attempt.
2. Cap checks: at most 4 tools per run, at most 3 attempts each.
3. Both files are written to ``workspace/selfbuilt/`` and copied into a
   fresh temporary directory containing only the two files — analysis
   artifacts are physically unreachable, so a "test" that echoes the run's
   own numbers cannot pass.
4. The test runs under the same sandbox as ``run_python`` (part 07; the
   Seatbelt profile builder is imported lazily so this module never couples
   to :mod:`src.tools` at import time) with a short timeout.

On a pass the tool is registered (status ``passed``) and
:func:`import_path_for_run` exposes ``workspace/selfbuilt/`` to later
``run_python`` calls. On a fail the module is not importable and the
failure output is returned. Every test execution consumes an attempt, pass
or fail; at a cap the build is refused with a structured error and the run
proceeds with helpers only.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

from src.selfbuilt.registry import (
    MAX_ATTEMPTS_PER_TOOL,
    MAX_TOOLS_PER_RUN,
    STATUS_FAILED,
    STATUS_PASSED,
    entry_importable,
    find_tool,
    importable_names as _importable_names,
    load_registry,
    module_filename,
    save_registry,
    selfbuilt_dir,
    sha256_file,
    sha256_text,
    test_filename,
    validate_tool_name,
)

#: Short timeout for the synthetic test (vs the longer run_python cap).
SELFBUILT_TEST_TIMEOUT_S = 60.0

#: Third-party packages a module may import (plus any of their submodules).
_ALLOWED_THIRD_PARTY = frozenset({"numpy", "scipy", "cv2"})


def _ok(summary, files=None, metrics=None):
    """Part-07-shaped success envelope (kept local: no import-time coupling)."""
    return {"ok": True, "summary": str(summary),
            "files": [str(f) for f in (files or [])],
            "metrics": dict(metrics or {})}


def _err(code, detail, summary="", files=None, metrics=None):
    """Part-07-shaped structured error (never an exception to the agent)."""
    return {"ok": False, "summary": str(summary or detail),
            "files": [str(f) for f in (files or [])],
            "metrics": dict(metrics or {}),
            "error": {"code": str(code), "detail": str(detail)}}


def _stdlib_names():
    return sys.stdlib_module_names


def check_module_imports(source, name=None, is_test=False):
    """Statically check a file's imports against the §1 allowlist.

    Args:
        source: The file's Python source.
        name: Tool name; when ``is_test`` the test may import this
            sibling ``sb_`` module (and only this one).
        is_test: The test file is held tighter than the module in one
            direction (no new third-party packages) and looser in one
            (it may import its sibling module and ``pytest`` to run).

    Returns:
        ``(ok, detail)`` — ``detail`` is None on success.
    """
    allowed_extra = set()
    if is_test:
        allowed_extra.add("pytest")
        if name:
            allowed_extra.add(name)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, f"syntax error: {exc}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                hit = _classify_import(top, alias.name)
                if hit is None and top not in allowed_extra:
                    return False, _reject(alias.name, is_test)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                return False, f"relative import rejected: {ast.dump(node)}"
            top = (node.module or "").split(".")[0]
            if not top:
                return False, f"empty from-import rejected: {ast.dump(node)}"
            hit = _classify_import(top, node.module or top)
            if hit is None and top not in allowed_extra:
                return False, _reject(node.module or top, is_test)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "__import__":
                return False, "__import__() is rejected: declare imports statically"
    return True, None


def _classify_import(top, full):
    """Return True when an import is on the §1 allowlist, else None."""
    if top == "importlib":
        # Dynamic imports defeat the static allowlist; declare them instead.
        return None
    if top in _stdlib_names():
        return True
    if top in _ALLOWED_THIRD_PARTY:
        return True
    if top == "src":
        parts = full.split(".")
        if len(parts) >= 2 and parts[1] == "helpers":
            return True
        return None
    return None


def _reject(dotted, is_test):
    scope = "test" if is_test else "module"
    return (f"{scope} imports only stdlib, numpy/scipy/OpenCV, and "
            f"src/helpers (test may also import its sibling module and "
            f"pytest): rejected {dotted!r}")


def _default_executor(test_path, isolated_dir, timeout_s):
    """Run the test file under the part-07 sandbox profile.

    The isolated directory holds only the two files. ``src.helpers`` is
    made importable through a shim symlink (``_shim/src/helpers`` ->
    the repo helpers): the Seatbelt profile's read-only helpers allow
    covers the real files, while the shim directory itself sits inside
    the allowed isolated subtree, so no profile change is needed.
    Site-packages (the pytest runner) get a read-only allow inserted
    before the final network deny; nothing else is widened. Where
    ``sandbox-exec`` is unavailable the same command runs plain (still
    isolated by cwd + sys.path); tests inject fakes and never need it.
    """
    from src.tools.sandbox import build_profile, sandbox_available
    from src.tools.run_python import scrub_env

    isolated = Path(isolated_dir)
    shim = isolated / "_shim" / "src"
    shim.mkdir(parents=True, exist_ok=True)
    link = shim / "helpers"
    if not link.exists():
        helpers = (Path(__file__).resolve().parent.parent / "helpers")
        try:
            link.symlink_to(helpers, target_is_directory=True)
        except OSError:
            shutil.copytree(helpers, link)
    repo_root = str(Path(__file__).resolve().parent.parent.parent)
    env = scrub_env(os.environ)
    env["PYTHONPATH"] = (str(isolated) + os.pathsep + str(shim.parent)
                         + os.pathsep + repo_root
                         + (os.pathsep + env["PYTHONPATH"]
                            if env.get("PYTHONPATH") else ""))
    cmd = [sys.executable, "-m", "pytest", "-q", Path(test_path).name]
    if not sandbox_available():
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout_s, env=env,
                                  cwd=str(isolated), check=False)
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout if isinstance(exc.stdout, str) else ""
            err = exc.stderr if isinstance(exc.stderr, str) else ""
            return {"returncode": None, "stdout": out, "stderr": err,
                    "timed_out": True}
        return {"returncode": proc.returncode, "stdout": proc.stdout or "",
                "stderr": proc.stderr or "", "timed_out": False}
    profile = build_profile(str(isolated), sys.executable)
    lines = profile.splitlines()
    extra = []
    for key in ("purelib", "platlib"):
        try:
            site = sysconfig.get_paths()[key]
        except KeyError:
            continue
        if site and Path(site).is_dir() and site not in extra:
            extra.append(f'(allow file-read* (subpath "{site}"))')
    if lines and lines[-1].strip() == "(deny network*)":
        lines[-1:-1] = extra
        profile = "\n".join(lines) + "\n"
    cmd = ["sandbox-exec", "-p", profile] + cmd
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout_s, env=env,
                              cwd=str(isolated), check=False)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        err = exc.stderr if isinstance(exc.stderr, str) else ""
        return {"returncode": None, "stdout": out, "stderr": err,
                "timed_out": True, "infra_error": False}
    except OSError as exc:
        return {"returncode": None, "stdout": "", "stderr": str(exc),
                "timed_out": False, "infra_error": True}
    # sandbox-exec never returns a pytest exit code when the seatbelt
    # itself fails to apply (e.g. nested sandbox where sandbox-exec is
    # blocked): surface that as infrastructure, not as a test failure.
    err_text = proc.stderr or ""
    infra = (proc.returncode not in (0, 1)
             and ("sandbox_apply" in err_text or "sandbox-exec" in err_text
                  or "Operation not permitted" in err_text))
    return {"returncode": proc.returncode, "stdout": proc.stdout or "",
            "stderr": err_text, "timed_out": False, "infra_error": infra}


def try_register(run_dir, name, module_source, test_source, purpose, turn,
                 executor=None, timeout_s=None):
    """Build-or-retry a self-built tool through the isolated-test gate.

    Args:
        run_dir: Run root holding ``workspace/``.
        name: Tool name (``sb_`` prefix mandatory).
        module_source/test_source: The two file contents.
        purpose: The agent's one-line claim (non-empty string).
        turn: Ledger turn number, recorded as ``registered_at_turn``.
        executor: ``(test_path, isolated_dir, timeout_s) -> result``.
            Defaults to the sandboxed pytest runner; tests inject fakes.
        timeout_s: Test timeout override.

    Returns:
        Part-07-shaped result. On a pass the entry is registered and the
        files named; on a fail the module is not importable and the
        failure output is in the error detail. Every test execution
        consumes an attempt; caps refuse with ``too_many_tools`` /
        ``too_many_attempts`` and the run proceeds with helpers only.
    """
    if not isinstance(module_source, str) or not module_source.strip():
        return _err("bad_tool_source", "module source must be non-empty")
    if not isinstance(test_source, str) or not test_source.strip():
        return _err("bad_tool_source", "test source must be non-empty")
    if not isinstance(purpose, str) or not purpose.strip():
        return _err("bad_purpose", "purpose must be the agent's one-line claim")
    try:
        turn = int(turn)
    except (TypeError, ValueError):
        return _err("bad_turn", "turn must be an integer")

    try:
        registry = load_registry(run_dir)
    except ValueError as exc:
        return _err("registry_corrupt", str(exc))

    ok, code, detail = validate_tool_name(name, registry)
    if not ok:
        return _err(code, detail)
    ok, detail = check_module_imports(module_source)
    if not ok:
        return _err("disallowed_import", detail)
    ok, detail = check_module_imports(test_source, name=name, is_test=True)
    if not ok:
        return _err("disallowed_test_import", detail)

    entry = find_tool(registry, name)
    attempts = int(entry["attempts"]) if entry else 0
    if entry is None and len(registry["tools"]) >= MAX_TOOLS_PER_RUN:
        return _err("too_many_tools",
                    f"at most {MAX_TOOLS_PER_RUN} self-built tools per run; "
                    f"proceed with helpers only")
    if attempts >= MAX_ATTEMPTS_PER_TOOL:
        return _err("too_many_attempts",
                    f"{name!r} used all {MAX_ATTEMPTS_PER_TOOL} attempts; "
                    f"proceed with helpers only")

    directory = selfbuilt_dir(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    module_file = directory / module_filename(name)
    test_file = directory / test_filename(name)
    module_file.write_text(module_source, encoding="utf-8")
    test_file.write_text(test_source, encoding="utf-8")

    run_executor = executor or _default_executor
    timeout = float(timeout_s if timeout_s is not None
                    else SELFBUILT_TEST_TIMEOUT_S)
    try:
        with tempfile.TemporaryDirectory(prefix="sb_test_") as tmp:
            isolated = Path(tmp)
            (isolated / module_file.name).write_text(module_source,
                                                     encoding="utf-8")
            isolated_test = isolated / test_file.name
            isolated_test.write_text(test_source, encoding="utf-8")
            result = run_executor(isolated_test, isolated, timeout)
    except Exception as exc:  # noqa: BLE001 -- the gate never crashes
        return _err("exec_failed", f"test executor failed: {exc}; "
                    f"no attempt consumed; proceed with helpers only")
    if result.get("infra_error"):
        output = ((result.get("stdout") or "")
                  + ("\n" + result.get("stderr")
                     if result.get("stderr") else ""))
        return _err("sandbox_unavailable",
                    f"sandbox could not run {name!r}'s test "
                    f"(exit {result.get('returncode')}); no attempt "
                    f"consumed; proceed with helpers only; output:\n"
                    f"{output[-2000:]}")

    attempts += 1
    passed = (not result.get("timed_out")
              and result.get("returncode") == 0)
    new_entry = {"name": name,
                 "module_sha256": sha256_text(module_source),
                 "test_sha256": sha256_text(test_source),
                 "attempts": attempts,
                 "status": STATUS_PASSED if passed else STATUS_FAILED,
                 "purpose": purpose.strip(),
                 "registered_at_turn": turn}
    if entry is None:
        registry["tools"].append(new_entry)
    else:
        entry.update(new_entry)
    save_registry(run_dir, registry)

    rel = [f"workspace/selfbuilt/{module_file.name}",
           f"workspace/selfbuilt/{test_file.name}",
           "workspace/selfbuilt/registry.json"]
    metrics = {"attempts": attempts, "returncode": result.get("returncode"),
               "timed_out": bool(result.get("timed_out"))}
    if passed:
        return _ok(f"{name!r} passed its synthetic test "
                   f"(attempt {attempts}); importable for later run_python "
                   f"calls in this run", files=rel, metrics=metrics)
    output = ((result.get("stdout") or "")
              + ("\n" + result.get("stderr") if result.get("stderr") else ""))
    output = output[-4000:]
    if result.get("timed_out"):
        return _err("test_timeout",
                    f"{name!r} test timed out after {timeout:g}s "
                    f"(attempt {attempts}); module not importable; "
                    f"proceed with helpers only",
                    files=rel, metrics=metrics)
    return _err("test_failed",
                f"{name!r} test failed (attempt {attempts}, "
                f"exit {result.get('returncode')}); module not importable; "
                f"output:\n{output}",
                files=rel, metrics=metrics)


def import_path_for_run(run_dir):
    """Directory to add to the import path for later ``run_python`` calls.

    Returns the ``workspace/selfbuilt`` path when at least one tool is
    currently importable, else None. Per-tool authority stays with
    :func:`src.selfbuilt.registry.entry_importable` (re-checked by part
    11): a failed or edited tool's numbers stay invalid even though the
    directory is shared.
    """
    if not _importable_names(run_dir):
        return None
    return str(selfbuilt_dir(run_dir))


def is_importable(run_dir, name: str) -> bool:
    """True iff ``name`` is currently importable (passed, hashes match)."""
    try:
        registry = load_registry(run_dir)
    except ValueError:
        return False
    entry = find_tool(registry, name)
    return bool(entry) and entry_importable(run_dir, entry)


def importable_names(run_dir) -> list:
    """Names currently importable from this run's selfbuilt directory."""
    return _importable_names(run_dir)

# generated from brief/07 · part 07 owns this file
"""``run_python`` — sandboxed execution of agent-written code (part 07 §6).

The run directory is the working directory: ``input/clip.mp4``,
``input/timing.json``, ``workspace/`` and ``artifacts/`` mean the
same thing in the prompt, the tool descriptions, the results and
the agent's code. The agent imports the helpers with e.g.
``from helpers import masks_io`` (``tracks``, ``physics`` and
``clock`` ride the same package).

Read: only ``workspace/``, ``artifacts/``, ``input/``
(read-only), ``src/helpers/`` (read-only) and the sandbox
environment. Write: ``workspace/`` and ``artifacts/`` only.
Network: none. The environment is scrubbed (no API keys, no home
directory). CPU/wall timeout and memory cap come from config; memory
is enforced from the parent by watching RSS (no ``ulimit -v``
noise on stderr).

Honest feedback: elapsed time is measured, never the timeout;
stderr carries only the agent code's own output; stdout leads,
stderr follows, metrics last; full stdout is always saved to
``artifacts/t<turn>_run_python_<n>.stdout.txt``.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from src import config as _config

from .common import (
    append_produced,
    next_artifact,
    run_path,
)
from .result import err_result, ok_result
from .sandbox import (
    base_interpreter,
    build_profile,
    ensure_sandbox_env,
    run_sandboxed,
    sandbox_available,
)

__all__ = [
    "run_python",
    "scrub_env",
    "clean_output",
    "TRUNC_CHARS",
    "SUMMARY_STDOUT_CHARS",
    "SUMMARY_STDERR_CHARS",
]

#: Inline stdout/stderr carried in metrics (the full text is on disk).
TRUNC_CHARS = 6000

#: What the summary shows: stdout first, then stderr, both capped.
SUMMARY_STDOUT_CHARS = 3000
SUMMARY_STDERR_CHARS = 1000

#: Environment names never passed to the child (plus *KEY*/*TOKEN*/...).
_SCRUB_EXACT = frozenset({
    "VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH", "__PYVENV_LAUNCHER__",
    "PYTHONSTARTUP", "PYTHONSAFEPATH", "META_API_KEY", "MODEL_API_KEY",
})

_SCRUB_PARTS = ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "AUTH",
                "CREDENTIAL", "PRIVATE_KEY", "ACCESS_KEY")


def scrub_env(env) -> dict:
    """Scrubbed copy of ``env``: no keys, no tokens, no home.

    Drops API keys/tokens/secrets, the virtualenv pointers and
    ``PYTHONPATH`` (the caller sets its own), pins a minimal ``PATH``
    and quiet-YAML-free numeric defaults. ``HOME`` is dropped — the
    caller points it at a fresh directory inside the run.
    """
    cleaned: dict = {}
    for key, value in dict(env or {}).items():
        upper = str(key).upper()
        if key in _SCRUB_EXACT or any(
                part in upper for part in _SCRUB_PARTS):
            continue
        cleaned[str(key)] = str(value)
    cleaned.pop("HOME", None)
    cleaned["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    cleaned["PYTHONNOUSERSITE"] = "1"
    cleaned["PYTHONDONTWRITEBYTECODE"] = "1"
    cleaned["PYTHONIOENCODING"] = "utf-8"
    return cleaned


def clean_output(text: str, run_dir) -> str:
    """Replace absolute host paths with their run-relative form."""
    cleaned = str(text or "")
    try:
        real = str(Path(str(run_dir)).resolve())
    except OSError:
        real = ""
    for prefix in sorted({real, str(run_dir)}, key=len, reverse=True):
        if prefix and prefix != ".":
            cleaned = cleaned.replace(prefix + "/", "")
            cleaned = cleaned.replace(prefix, ".")
    return cleaned


def _snapshot(run_dir) -> dict:
    """``{rel: (size, mtime_ns)}`` under workspace/ and artifacts/."""
    state: dict = {}
    for top in (str(_config.WORKSPACE_DIR_NAME),
                str(_config.ARTIFACTS_DIR_NAME)):
        base = Path(str(run_dir)) / top
        try:
            entries = list(base.rglob("*"))
        except OSError:
            continue
        for path in entries:
            try:
                if path.is_file() and not path.is_symlink():
                    stat = path.stat()
                    state[str(path.relative_to(run_dir))] = (
                        stat.st_size, stat.st_mtime_ns)
            except OSError:
                continue
    return state


def _created_files(before: dict, after: dict) -> list:
    """Files created or modified between two snapshots."""
    out = []
    for rel, (size, mtime) in after.items():
        old = before.get(rel)
        if old is None or old != (size, mtime):
            out.append({"path": rel, "size_bytes": size})
    return sorted(out, key=lambda row: row["path"])


def _clamp_override(value, cap: float, name: str) -> float:
    """Agent-supplied ``timeout_s``/``memory_mb`` clamped to the cap."""
    if value is None:
        return float(cap)
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} must be a number, got {value!r}") from exc
    if not number > 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return min(number, float(cap))


def _next_workspace(run_dir, turn: int, stem: str, ext: str) -> str:
    """First unused ``workspace/t<turn>_<stem>_<n>.<ext>`` name."""
    n = 0
    while True:
        rel = f"workspace/t{int(turn)}_{stem}_{n}{ext}"
        if not (Path(str(run_dir)) / rel).exists():
            return rel
        n += 1


def _truncate(text: str, limit: int) -> tuple:
    """``(shown, was_truncated)`` cut at ``limit`` chars."""
    if len(text) <= limit:
        return text, False
    return text[:limit] + f"\n…[truncated {len(text) - limit} chars]", True


def run_python(run_dir, turn, code=None, timeout_s=None,
               memory_mb=None, *, executor=None, ledger=None) -> dict:
    """Execute agent-written ``code`` in the sandbox (§§6, 9, 10).

    ``timeout_s``/``memory_mb`` are agent overrides clamped to the
    config caps. ``executor`` is ``(code, *, cwd, env, timeout_s,
    memory_mb)`` returning ``{"returncode", "stdout", "stderr",
    "timed_out", ...}`` (tests inject a fake; the default is the
    live sandboxed path). The run directory is the child's working
    directory. Returns the honest feedback of §10: measured elapsed
    time, clean stderr, stdout before stderr before the metrics, and
    the full-stdout file.
    """
    if not isinstance(code, str) or not code.strip():
        return err_result("bad_arguments",
                          "run_python needs code as a non-empty string")
    base = Path(str(run_dir))
    try:
        (base / str(_config.WORKSPACE_DIR_NAME)).mkdir(parents=True,
                                                       exist_ok=True)
        (base / str(_config.ARTIFACTS_DIR_NAME)).mkdir(parents=True,
                                                       exist_ok=True)
    except OSError as exc:
        return err_result("run_unwritable", f"run dir unwritable: {exc}")
    try:
        limit_s = _clamp_override(
            timeout_s, float(_config.SANDBOX_EXEC_TIMEOUT_S), "timeout_s")
        limit_mb = _clamp_override(
            memory_mb, float(_config.SANDBOX_MEMORY_MB), "memory_mb")
    except ValueError as exc:
        return err_result("bad_arguments", str(exc))
    if not sandbox_available():
        return err_result(
            "sandbox_unavailable",
            "sandbox-exec is not available on this machine; agent code "
            "never runs unsandboxed")
    try:
        env_dir = ensure_sandbox_env()
    except Exception as exc:  # noqa: BLE001 — environment build is infra
        return err_result("sandbox_unavailable",
                          f"sandbox environment could not be built: {exc}")
    interpreter = base_interpreter()
    # No home directory: HOME points at a path that is never created,
    # so `~` and `~/.config` stay unreachable; TMPDIR is a fresh
    # workspace directory the agent may legitimately use.
    home = (base / str(_config.WORKSPACE_DIR_NAME)
            / f".no_home_{int(turn)}")
    tmp_home = (base / str(_config.WORKSPACE_DIR_NAME)
                / f".tmp_{int(turn)}")
    try:
        tmp_home.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return err_result("run_unwritable", f"run dir unwritable: {exc}")
    # The staged code lives under workspace/ so the artifacts
    # counter for ``t<turn>_run_python_<n>.stdout.txt`` starts at 0.
    code_rel = _next_workspace(run_dir, turn, "run_python", ".py")
    code_path = run_path(run_dir, code_rel)
    try:
        code_path.write_text(str(code), encoding="utf-8")
    except OSError as exc:
        return err_result("run_unwritable",
                          f"cannot stage agent code: {exc}")
    before = _snapshot(run_dir)
    env = scrub_env(os.environ)
    env["HOME"] = str(home)
    env["TMPDIR"] = str(tmp_home)
    env["PYTHONPATH"] = str(env_dir)
    # Part 07 §13: exactly the run's input/, workspace/ and
    # artifacts/ subtrees are readable — never the run root, so
    # logs/ and run-root files stay unreadable and the run
    # directory itself cannot be listed. The child's working
    # directory is still the run directory.
    profile = build_profile(str(base), interpreter,
                            sandbox_env=env_dir, run_layout=True)

    def _default_executor(program, *, cwd, env, timeout_s, memory_mb):
        return run_sandboxed([str(interpreter), str(code_path)],
                             cwd=cwd, env=env, timeout_s=timeout_s,
                             memory_mb=memory_mb, profile=profile)

    run = executor if executor is not None else _default_executor
    started = time.monotonic()
    try:
        outcome = run(str(code), cwd=str(base), env=dict(env),
                      timeout_s=limit_s, memory_mb=limit_mb)
    except Exception as exc:  # noqa: BLE001 — executor death is a tool error
        return err_result("exec_failed",
                          f"executor failed: {type(exc).__name__}: {exc}",
                          metrics={"code_artifact": code_rel,
                                   "timeout_s": limit_s})
    if not isinstance(outcome, dict) or outcome.get("infra_error"):
        detail = ("sandbox executor failed"
                  if not isinstance(outcome, dict)
                  else str(outcome.get("stderr") or "infra_error"))
        return err_result("sandbox_failed", detail,
                          metrics={"code_artifact": code_rel,
                                   "timeout_s": limit_s})
    after = _snapshot(run_dir)
    stdout = clean_output(outcome.get("stdout", ""), str(base))
    stderr = clean_output(outcome.get("stderr", ""), str(base))
    wall = time.monotonic() - started
    try:
        elapsed = float(outcome.get("elapsed_s", wall))
    except (TypeError, ValueError):
        elapsed = wall
    stdout_rel = next_artifact(run_dir, turn, "run_python", ".stdout.txt")
    stdout_path = run_path(run_dir, stdout_rel)
    try:
        stdout_path.write_text(stdout, encoding="utf-8")
    except OSError:
        pass
    after = _snapshot(run_dir)
    created = [row for row in _created_files(before, after)
               if row["path"] not in (code_rel, stdout_rel)]
    append_produced(run_dir, [code_rel, stdout_rel]
                    + [row["path"] for row in created])
    if ledger is not None:
        try:
            ledger.record_exec(int(turn), artifact=stdout_rel)
        except (TypeError, ValueError):
            pass
    files = [stdout_rel] + [row["path"] for row in created]
    metrics = {
        "exit_code": outcome.get("returncode"),
        "elapsed_s": round(elapsed, 3),
        "timeout_s": limit_s,
        "memory_mb": limit_mb,
        "timed_out": bool(outcome.get("timed_out")),
        "killed_for_memory": bool(outcome.get("killed_for_memory")),
        "peak_rss_mb": round(float(outcome.get("peak_rss_mb", 0.0)), 1),
        "sandboxed": bool(outcome.get("sandboxed", True)),
        "code_artifact": code_rel,
        "stdout_artifact": stdout_rel,
        "created_files": created,
    }
    killed = bool(outcome.get("killed_for_memory"))
    expired = bool(outcome.get("timed_out"))
    rc = outcome.get("returncode")
    if killed:
        metrics.update({"stdout": stdout[:TRUNC_CHARS],
                        "stderr": stderr[:TRUNC_CHARS]})
        return err_result(
            "exec_memory",
            f"agent code exceeded the {limit_mb:g} MiB cap after "
            f"{elapsed:.1f}s and was killed",
            summary=(f"exit killed-for-memory in {elapsed:.1f}s\n"
                     f"--- stdout ---\n{stdout[:SUMMARY_STDOUT_CHARS]}"
                     f"\n--- stderr ---\n{stderr[:SUMMARY_STDERR_CHARS]}"),
            files=files, metrics=metrics)
    if expired:
        metrics.update({"stdout": stdout[:TRUNC_CHARS],
                        "stderr": stderr[:TRUNC_CHARS]})
        return err_result(
            "exec_timeout",
            f"agent code exceeded the {limit_s:g}s wall timeout "
            f"(measured {elapsed:.1f}s) and was killed",
            summary=(f"exit timeout in {elapsed:.1f}s\n"
                     f"--- stdout ---\n{stdout[:SUMMARY_STDOUT_CHARS]}"
                     f"\n--- stderr ---\n{stderr[:SUMMARY_STDERR_CHARS]}"),
            files=files, metrics=metrics)
    lowered = (stderr or "").lower()
    if rc != 0 and ("operation not permitted" in lowered
                    or "sandbox" in lowered and "deny" in lowered):
        metrics.update({"stdout": stdout[:TRUNC_CHARS],
                        "stderr": stderr[:TRUNC_CHARS]})
        return err_result(
            "sandbox_failed",
            f"sandbox refused the run (exit {rc}): "
            f"{stderr[:500] or stdout[:500]}",
            files=files, metrics=metrics)
    shown_out, out_cut = _truncate(stdout, TRUNC_CHARS)
    shown_err, err_cut = _truncate(stderr, TRUNC_CHARS)
    metrics.update({"stdout": shown_out, "stderr": shown_err,
                    "stdout_truncated": out_cut,
                    "stderr_truncated": err_cut})
    if rc != 0:
        return err_result(
            "exec_failed", f"agent code exited {rc} in {elapsed:.1f}s",
            summary=(f"exit {rc} in {elapsed:.1f}s\n--- stdout ---\n"
                     f"{stdout[:SUMMARY_STDOUT_CHARS]}\n--- stderr ---\n"
                     f"{stderr[:SUMMARY_STDERR_CHARS]}"),
            files=files, metrics=metrics)
    return ok_result(
        (f"exit 0 in {elapsed:.1f}s"
         + (f", {len(created)} file(s) created/modified"
            if created else ", no files created")
         + f"\n--- stdout ---\n{stdout[:SUMMARY_STDOUT_CHARS]}"
         + (f"\n--- stderr ---\n{stderr[:SUMMARY_STDERR_CHARS]}"
            if stderr.strip() else "")),
        files=files, metrics=metrics)

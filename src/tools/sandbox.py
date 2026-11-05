# generated from brief/07 · part 07 owns this file
"""macOS Seatbelt sandbox for agent Python (part 07 §§6/9/10).

Deny-by-default with an explicit allow-list. File data may be read
only from:

- the run's ``input/``, ``workspace/``, ``artifacts/`` (never
  ``logs/``);
- ``src/helpers/`` (read-only);
- the sandbox environment (§9: a dedicated directory under the user
  cache holding the runtime libraries, reused across runs);
- the real paths of the base interpreter and its standard library
  (symlinks resolved);
- a short named list of system paths Python needs on macOS:
  ``/System/Library``, ``/usr/lib``, ``/usr/share``,
  ``/private/var/db/timezone``, ``/dev/null``, ``/dev/urandom``.

``file-read-metadata`` (stat) stays global so path resolution
works. Listing a directory needs read permission on it, so outside
the list nothing can even be listed: sibling runs, the runs
directory's parent, ``$TMPDIR``, ``$HOME``/``~/.config`` and the
repository are all unreadable. Network is denied last.

The sandboxed interpreter lives outside the repository: on first
use a dedicated environment is created under
``~/Library/Caches/physics-proof/sandbox-env-<hash>`` (the hash
covers the runtime dependency list and the Python version). It
holds the runtime libraries (copied from the running
environment — no network needed) plus a ``helpers`` symlink to the
repo's ``src/helpers/``, and is reused across runs.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import sysconfig
import threading
import time
from pathlib import Path

from src import config as _config

__all__ = [
    "SANDBOX_ENV_DEPS",
    "sandbox_available",
    "sandbox_env_hash",
    "ensure_sandbox_env",
    "default_sandbox_base",
    "repo_helpers_dir",
    "base_interpreter",
    "stdlib_dirs",
    "build_profile",
    "run_sandboxed",
]

#: Runtime libraries the sandbox environment holds (§9).
SANDBOX_ENV_DEPS = ("numpy", "scipy", "cv2")

#: Where per-call stdout/stderr redirect files live (inside workspace).
_TMP_PREFIX = ".tmp_exec_"


def sandbox_available() -> bool:
    """True when ``sandbox-exec`` can be launched on this machine."""
    return shutil.which("sandbox-exec") is not None


def default_sandbox_base() -> Path:
    """``~/Library/Caches/physics-proof`` (outside any repository)."""
    return Path.home() / "Library" / "Caches" / "physics-proof"


def repo_helpers_dir() -> Path:
    """The repo's ``src/helpers/`` (the one read-only exception, §6)."""
    return Path(__file__).resolve().parent.parent / "helpers"


def _dep_versions() -> dict:
    versions: dict = {}
    for name in SANDBOX_ENV_DEPS:
        try:
            if name == "cv2":
                import cv2  # noqa: PLC0415 — version probe only

                versions[name] = str(cv2.__version__)
                continue
            module = importlib.import_module(name)
            versions[name] = str(getattr(module, "__version__",
                                         "unknown"))
        except ImportError:
            versions[name] = "missing"
    return versions


def sandbox_env_hash(python_version: str | None = None,
                     versions: dict | None = None) -> str:
    """Short hash of the runtime dependency list + Python version (§9)."""
    stamp = "|".join(
        [python_version or sys.version.split()[0]]
        + [f"{name}=={(versions or _dep_versions()).get(name)}"
           for name in SANDBOX_ENV_DEPS])
    return hashlib.sha256(stamp.encode("utf-8")).hexdigest()[:12]


def _copy_package(name: str, dest: Path) -> None:
    spec = importlib.util.find_spec(name)
    if spec is None:
        raise RuntimeError(f"runtime dependency {name!r} is not "
                           "installed in this environment")
    locations = list(getattr(spec, "submodule_search_locations", ())
                     or [])
    if not locations:
        raise RuntimeError(f"runtime dependency {name!r} has no "
                           "package directory to copy")
    for location in locations:
        target = dest / Path(location).name
        if target.exists() or target.is_symlink():
            if target.is_symlink() or target.is_file():
                target.unlink()
            else:
                shutil.rmtree(target)
        shutil.copytree(location, target, symlinks=True)


def _helpers_digest() -> str:
    """Hash of the repo helper sources (a copy ships in the env)."""
    digest = hashlib.sha256()
    for path in sorted(repo_helpers_dir().glob("*.py")):
        try:
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
        except OSError:
            continue
    return digest.hexdigest()[:16]


def ensure_sandbox_env(base: Path | None = None) -> Path:
    """Create (once) and return the sandbox environment directory.

    Copies the runtime libraries from the running environment and
    links ``helpers`` to the repo's ``src/helpers/``. Reused across
    runs; rebuilt when the dependency/Python hash changes.
    """
    root = Path(base) if base is not None else default_sandbox_base()
    digest = sandbox_env_hash()
    helpers_digest = _helpers_digest()
    env = root / f"sandbox-env-{digest}"
    marker = env / "ENV_MARKER.txt"
    if env.is_dir() and marker.is_file():
        try:
            stamped = marker.read_text(encoding="utf-8").split()
        except OSError:
            stamped = []
        if len(stamped) >= 2 and stamped[1] == helpers_digest:
            return env
        shutil.rmtree(env, ignore_errors=True)
    if env.exists():
        shutil.rmtree(env)
    env.mkdir(parents=True, exist_ok=True)
    try:
        for name in SANDBOX_ENV_DEPS:
            _copy_package(name, env)
        # A real copy of the helpers: inside the sandbox ``src`` is
        # not importable, so the copy's package init is normalised to
        # relative imports (the repo originals are untouched, and the
        # profile still allows read-only access to them).
        helpers = env / "helpers"
        if helpers.exists() or helpers.is_symlink():
            if helpers.is_symlink() or helpers.is_file():
                helpers.unlink()
            else:
                shutil.rmtree(helpers)
        shutil.copytree(repo_helpers_dir(), helpers, symlinks=True)
        init = helpers / "__init__.py"
        text = init.read_text(encoding="utf-8")
        text = text.replace("from src.helpers import",
                            "from . import")
        init.write_text(text, encoding="utf-8")
        marker.write_text(f"{digest}\n{helpers_digest}\n{sys.version}\n",
                          encoding="utf-8")
    except Exception:
        shutil.rmtree(env, ignore_errors=True)
        raise
    return env


def base_interpreter() -> Path:
    """The interpreter binary outside the repository (symlinks kept).

    The repo-local ``.venv`` python is unusable inside the sandbox
    (the repository stays unreadable), so prefer the base prefix's
    binary and fall back to the fully resolved executable.
    """
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent
    candidate = (Path(sys.base_prefix) / "bin"
                 / f"python{sys.version_info[0]}."
                 f"{sys.version_info[1]}")
    try:
        if candidate.is_file() and not str(candidate.resolve()).startswith(
                str(repo_root)):
            return candidate
    except OSError:
        pass
    return Path(sys.executable).resolve()


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _outside_repo(path: str) -> bool:
    try:
        Path(path).resolve().relative_to(_repo_root())
    except (OSError, ValueError):
        return True
    return False


def stdlib_dirs() -> list:
    """Real stdlib/library directories the interpreter needs.

    Only directories outside the repository: the repo-local
    ``.venv`` is never allowed in (the repository stays unreadable —
    the base interpreter's own directories carry everything the
    child needs).
    """
    dirs: list = []
    candidates: list = []
    for key in ("stdlib", "platstdlib"):
        try:
            candidates.append(sysconfig.get_paths()[key])
        except KeyError:
            continue
    try:
        candidates.append(str(Path(sys.base_prefix).resolve()))
    except OSError:
        pass
    for path in candidates:
        try:
            resolved = str(Path(path).resolve())
        except OSError:
            continue
        if resolved not in dirs and _outside_repo(resolved):
            dirs.append(resolved)
    return dirs


def _q(path: str) -> str:
    return '"' + str(path).replace('"', "") + '"'


def build_profile(root, python_executable=None, *,
                  helpers_dir=None, sandbox_env=None,
                  extra_read_dirs=(), extra_write_dirs=(),
                  run_layout=False) -> str:
    """Seatbelt profile text: deny-by-default, explicit allow-list.

    Args:
        root: Directory the sandboxed code may read and write (an
            isolated temp dir for the self-built gate; the run
            directory for ``run_python`` only with ``run_layout``).
        python_executable: Interpreter binary (real paths allowed).
        helpers_dir: Read-only ``src/helpers`` (defaults to the repo's).
        sandbox_env: Read/exec runtime-library directory (§9).
        extra_read_dirs / extra_write_dirs: Additional subtree allows.
        run_layout: Allow exactly the run's ``input/`` (read-only),
            ``workspace/`` and ``artifacts/`` subtrees — never the run
            root itself, so ``logs/`` and files at the run root stay
            unreadable and the run directory cannot be listed (part 07
            §13). The working directory may still be the run
            directory; only the three subtrees are readable.
    """
    try:
        base = str(Path(root).resolve())
    except OSError:
        base = str(root)
    helpers = (str(Path(helpers_dir).resolve()) if helpers_dir is not None
               else str(repo_helpers_dir().resolve()))
    lines = [
        "(version 1)",
        "; part 07: deny-by-default; specific allows follow, the",
        "; network deny stays last (last matching rule wins).",
        "(deny default)",
        "(allow file-read-metadata)",
        # The loader stats the filesystem root itself at startup
        # (deny: file-read-data /); a literal allow covers only `/`,
        # never anything under it.
        "(allow file-read-data (literal \"/\"))",
        "(allow process-info*)",
        "(allow process-fork)",
        "(allow sysctl-read)",
        "(allow mach-lookup)",
    ]
    if run_layout:
        lines.append(f"(allow file-read* (subpath {_q(base + '/input')}))")
        lines.append(
            f"(allow file-read* file-write* (subpath {_q(base + '/workspace')}))")
        lines.append(
            f"(allow file-read* file-write* (subpath {_q(base + '/artifacts')}))")
    else:
        lines.append(f"(allow file-read* file-write* (subpath {_q(base)}))")
    lines.append(f"(allow file-read* (subpath {_q(helpers)}))")
    if sandbox_env is not None:
        try:
            env = str(Path(sandbox_env).resolve())
        except OSError:
            env = str(sandbox_env)
        lines.append(f"(allow file-read* (subpath {_q(env)}))")
    for directory in stdlib_dirs():
        lines.append(f"(allow file-read* (subpath {_q(directory)}))")
    exe = (str(Path(python_executable).resolve())
           if python_executable is not None
           else str(base_interpreter().resolve()))
    lines.append(f"(allow process-exec (literal {_q(exe)}))")
    # Homebrew's launcher re-executes a different binary
    # (Resources/Python.app/...); the interpreter's own directories
    # cover the re-exec target too (skill macos-sandbox).
    seen_exec: set = set()
    for directory in [str(Path(exe).parent)] + stdlib_dirs():
        if directory in seen_exec:
            continue
        seen_exec.add(directory)
        lines.append(f"(allow process-exec (subpath {_q(directory)}))")
    for directory in ("bin",):
        lines.append(f"(allow process-exec (subpath {_q('/usr/' + directory)}))")
        lines.append(f"(allow process-exec (subpath {_q('/' + directory)}))")
    for directory in extra_read_dirs or ():
        lines.append(f"(allow file-read* (subpath {_q(str(directory))}))")
    for directory in extra_write_dirs or ():
        lines.append(
            f"(allow file-read* file-write* (subpath {_q(str(directory))}))")
    for directory in ("/System/Library", "/usr/lib", "/usr/share",
                      "/private/var/db/timezone"):
        lines.append(f"(allow file-read* (subpath {_q(directory)}))")
    for literal in ("/dev/null", "/dev/urandom", "/dev/random",
                    "/etc/localtime"):
        lines.append(f"(allow file-read* (literal {_q(literal)}))")
    for literal in ("/dev/null", "/dev/stdout", "/dev/stderr"):
        lines.append(f"(allow file-write* (literal {_q(literal)}))")
    lines.append("(deny network*)")
    return "\n".join(lines) + "\n"


def _rss_mb(pid: int) -> float:
    """Resident size of ``pid`` in MiB (0 when unreadable)."""
    try:
        completed = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(int(pid))],
            capture_output=True, text=True, timeout=10)
    except (OSError, ValueError):
        return 0.0
    try:
        return max(0.0, float(completed.stdout.strip()) / 1024.0)
    except ValueError:
        return 0.0


def run_sandboxed(cmd, *, cwd, env, timeout_s: float,
                  memory_mb: float, profile: str | None = None) -> dict:
    """Run ``cmd`` under the sandbox (or plain when unavailable).

    Returns ``{"returncode", "stdout", "stderr", "timed_out",
    "killed_for_memory", "peak_rss_mb", "elapsed_s", "sandboxed"}``.
    Memory is enforced from the parent by watching the child's
    resident size and killing it over the cap — no ``ulimit -v``
    noise on stderr. Elapsed time is measured, never the timeout.
    """
    start = time.monotonic()
    use_sandbox = sandbox_available() and profile is not None
    full = ((["sandbox-exec", "-p", str(profile)] + list(cmd))
            if use_sandbox else list(cmd))
    tmp = Path(str(cwd)) / "workspace" / (
        _TMP_PREFIX + str(os.getpid()))
    tmp.mkdir(parents=True, exist_ok=True)
    out_path = tmp / "stdout.bin"
    err_path = tmp / "stderr.bin"
    killed_memory = False
    timed_out = False
    peak = 0.0
    rc = None
    try:
        with open(out_path, "wb") as out_fh, open(err_path, "wb") as err_fh:
            proc = subprocess.Popen(full, stdout=out_fh, stderr=err_fh,
                                    cwd=str(cwd), env=dict(env))
            try:
                while True:
                    rc = proc.poll()
                    rss = _rss_mb(proc.pid)
                    peak = max(peak, rss)
                    if rss > float(memory_mb) > 0:
                        killed_memory = True
                        proc.kill()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            pass
                        rc = proc.poll()
                        break
                    if rc is not None:
                        break
                    if time.monotonic() - start > float(timeout_s):
                        timed_out = True
                        proc.kill()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            pass
                        rc = proc.poll()
                        break
                    time.sleep(0.05)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
                    rc = proc.poll()
    except OSError as exc:
        elapsed = time.monotonic() - start
        shutil.rmtree(tmp, ignore_errors=True)
        return {"returncode": None, "stdout": "", "stderr": str(exc),
                "timed_out": False, "killed_for_memory": False,
                "peak_rss_mb": 0.0, "elapsed_s": elapsed,
                "sandboxed": use_sandbox, "infra_error": True}
    elapsed = time.monotonic() - start
    try:
        stdout = out_path.read_bytes().decode("utf-8", "replace")
    except OSError:
        stdout = ""
    try:
        stderr = err_path.read_bytes().decode("utf-8", "replace")
    except OSError:
        stderr = ""
    shutil.rmtree(tmp, ignore_errors=True)
    return {"returncode": rc, "stdout": stdout, "stderr": stderr,
            "timed_out": timed_out, "killed_for_memory": killed_memory,
            "peak_rss_mb": peak, "elapsed_s": elapsed,
            "sandboxed": use_sandbox, "infra_error": False}

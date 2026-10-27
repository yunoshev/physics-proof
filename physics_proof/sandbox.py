"""M5. Python sandbox: static review plus a Seatbelt-sandboxed runner.

Two independent layers (SPEC M5): `review` refuses dangerous code without
running it; `run_python` runs the code under macOS `sandbox-exec` with no
network, writes confined to the workspace, a clean environment and a
timeout. URLs inside strings are data and are allowed.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import sysconfig
import time
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "Problem",
    "SandboxResult",
    "review",
    "run_python",
]

#: Top-level module names the agent code may import.
_ALLOWED_IMPORTS = frozenset(
    {
        "numpy",
        "scipy",
        "PIL",
        "matplotlib",
        "blocks",
        "math",
        "cmath",
        "statistics",
        "json",
        "csv",
        "re",
        "fractions",
        "decimal",
        "random",
        "itertools",
        "functools",
        "collections",
        "dataclasses",
        "typing",
        "pathlib",
        "io",
        "textwrap",
        "string",
        "time",
        "datetime",
        "subprocess",
    }
)

#: Calls that are never allowed, even with innocent arguments.
_BANNED_CALLS = frozenset({"eval", "exec", "compile", "__import__"})

#: Module roots no attribute access may touch (import is refused already).
_BANNED_ROOTS = frozenset(
    {"os", "ctypes", "socket", "urllib", "http", "requests", "importlib"}
)

#: Binaries a sandboxed subprocess call may start (first argv element).
_SUBPROCESS_BINS = ("ffmpeg", "ffprobe")

#: URLs inside strings are data, not paths; strip them before path checks.
_URL_RE = re.compile("https?://[^ ]+")

#: Image suffixes collected from the workspace after a run.
_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})

#: stdout/stderr are truncated past this many characters, with a note.
_OUTPUT_LIMIT = 8000


@dataclass
class Problem:
    """One static-review finding: 1-based line, rule id, message."""

    line: int
    rule: str
    message: str


@dataclass
class SandboxResult:
    """Outcome of one sandboxed run."""

    ok: bool
    refused: bool
    problems: list[Problem] = field(default_factory=list)
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    seconds: float = 0.0
    images: list[Path] = field(default_factory=list)
    script: Path | None = None


class _Checker(ast.NodeVisitor):
    """Collect review problems; fail closed on anything unclear."""

    def __init__(self, problems: list[Problem], skip: set[int]) -> None:
        self.problems = problems
        self.skip = skip
        self.subprocess_names = {"subprocess"}

    def add(self, node: ast.AST, rule: str, message: str) -> None:
        self.problems.append(Problem(node.lineno, rule, message))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top == "subprocess" and alias.asname:
                self.subprocess_names.add(alias.asname)
            if top not in _ALLOWED_IMPORTS:
                self.add(node, "import-allowlist", "import of " + repr(alias.name) + " is not allowed")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        top = (node.module or "").split(".")[0]
        if node.level or top not in _ALLOWED_IMPORTS:
            name = "." * node.level + (node.module or "")
            self.add(node, "import-allowlist", "import from " + repr(name) + " is not allowed")
            return
        if top == "subprocess":
            for alias in node.names:
                if alias.name == "*":
                    self.add(node, "subprocess", "star import from subprocess is not allowed")
                else:
                    self.subprocess_names.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in _BANNED_CALLS:
            self.add(node, "banned-call", node.id + " is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        root: ast.AST = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id in _BANNED_ROOTS:
            self.add(node, "banned-module", "use of module " + repr(root.id) + " is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id == "getattr":
            self._check_getattr(node)
        elif self._is_subprocess_func(func):
            self._check_subprocess_call(node)
        self.generic_visit(node)

    def _is_subprocess_func(self, func: ast.AST) -> bool:
        if isinstance(func, ast.Attribute):
            return isinstance(func.value, ast.Name) and func.value.id in self.subprocess_names
        return isinstance(func, ast.Name) and func.id in self.subprocess_names

    def _check_getattr(self, node: ast.Call) -> None:
        if node.args:
            target = node.args[0]
            if isinstance(target, ast.Name) and (
                target.id in _BANNED_ROOTS or target.id in self.subprocess_names
            ):
                self.add(node, "banned-module", "getattr on module " + repr(target.id) + " is not allowed")
                return
        if len(node.args) < 2 or not (
            isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)
        ):
            self.add(node, "dynamic-getattr", "getattr with a non-literal name is not allowed")

    def _check_subprocess_call(self, node: ast.Call) -> None:
        cmd: ast.AST | None = node.args[0] if node.args else None
        shell: ast.AST | None = None
        for keyword in node.keywords:
            if keyword.arg == "shell":
                shell = keyword.value
            elif keyword.arg == "args" and cmd is None:
                cmd = keyword.value
        if shell is not None and not (isinstance(shell, ast.Constant) and shell.value is False):
            self.add(node, "subprocess", "subprocess with shell=True is not allowed")
            return
        if not (
            isinstance(cmd, (ast.List, ast.Tuple))
            and cmd.elts
            and isinstance(cmd.elts[0], ast.Constant)
            and cmd.elts[0].value in _SUBPROCESS_BINS
        ):
            self.add(node, "subprocess", "subprocess command must be a list starting with 'ffmpeg' or 'ffprobe'")

    def visit_Constant(self, node: ast.Constant) -> None:
        if id(node) in self.skip:
            return
        if isinstance(node.value, str):
            self._check_string(node, node.value)
        elif isinstance(node.value, bytes):
            try:
                text = node.value.decode("ascii")
            except UnicodeDecodeError:
                return
            self._check_string(node, text)
        self.generic_visit(node)

    def _check_string(self, node: ast.Constant, value: str) -> None:
        text = _URL_RE.sub("", value).strip()
        if not text or text == "/":
            return
        if text.startswith("/"):
            self.add(node, "path-outside-workspace", "absolute path " + repr(value) + " is not allowed")
        elif text.startswith("~") or any(
            part == ".." or part.startswith("~") for part in text.split("/")
        ):
            self.add(node, "path-outside-workspace", "path outside the workspace " + repr(value) + " is not allowed")


def review(code: str) -> list[Problem]:
    """Static check of agent code; returns problems (empty means allowed).

    Each problem carries the 1-based line, a rule id and a message.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [Problem(exc.lineno or 1, "syntax", "cannot parse: " + str(exc))]
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    skip.add(id(value))
    problems: list[Problem] = []
    _Checker(problems, skip).visit(tree)
    problems.sort(key=lambda p: (p.line, p.rule, p.message))
    return problems


def _repo_root() -> Path:
    """Directory of the top-level blocks.py shim (goes on sys.path)."""
    return Path(__file__).resolve().parents[1]


def _next_script_path(scripts: Path) -> Path:
    """First free workspace/scripts/NNN.py."""
    n = 1
    while (scripts / (str(n).zfill(3) + ".py")).exists():
        n += 1
    return scripts / (str(n).zfill(3) + ".py")


def _clean_env(workspace: Path) -> dict[str, str]:
    """Minimal child environment; never inherits the parent process."""
    path_parts = ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    ffmpeg = shutil.which("ffmpeg") or ""
    ffmpeg_dir = os.path.dirname(ffmpeg)
    if ffmpeg_dir and ffmpeg_dir not in path_parts:
        path_parts.append(ffmpeg_dir)
    tmpdir = workspace / "tmp"
    mpldir = workspace / ".mplconfig"
    tmpdir.mkdir(parents=True, exist_ok=True)
    mpldir.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": ":".join(path_parts),
        "HOME": str(workspace),
        "TMPDIR": str(tmpdir),
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(mpldir),
    }


def _sbpl_string(value: str) -> str:
    """Quote a path for a Seatbelt profile string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _site_dirs() -> list[Path]:
    """Site-packages dirs of this interpreter (venv packages live here)."""
    found: list[Path] = []
    for name in ("purelib", "platlib"):
        try:
            path = sysconfig.get_path(name)
        except KeyError:
            continue
        if path and Path(path).is_dir() and Path(path) not in found:
            found.append(Path(path))
    return found


def _deny_rule(operation: str, filters: list[str]) -> list[str]:
    """One ``(deny <operation> ...)`` rule; several filters are AND-ed.

    Filters inside a single Seatbelt rule are combined with OR, so more
    than one filter must be wrapped in ``(require-all ...)`` for the
    intended AND meaning. A single filter needs no wrapper.
    """
    if len(filters) > 1:
        lines = ["(deny " + operation, "  (require-all"]
        lines.extend("    " + item for item in filters)
        lines.append("  ))")
        return lines
    return ["(deny " + operation, *("  " + item for item in filters), ")"]


def _sandbox_profile(
    workspace: Path, repo_root: Path, interpreter: str, tools: list[str]
) -> str:
    """SBPL: allow by default, deny the dangerous classes with carve-outs.

    Without the leading ``(allow default)`` Seatbelt denies everything,
    including the interpreter exec itself (exit 71, Operation not
    permitted). Filters inside one rule are combined with OR, so every
    deny rule with more than one filter wraps them in ``(require-all ...)``
    for the intended AND meaning.

    Seatbelt checks both the path being executed and the resolved file,
    so the caller passes the venv interpreter path and its realpath (and
    both forms of each tool path); every one of them is carved out of the
    exec deny.
    """
    home = Path.home()
    exe = Path(interpreter).resolve()
    candidates = [
        workspace,
        repo_root,
        exe.parent.parent,
        Path(sys.base_prefix).resolve(),
        *_site_dirs(),
    ]
    seen: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.append(resolved)
    lines = ["(version 1)", "(allow default)", "(deny network*)"]
    if str(home) not in ("", "/"):
        filters = ["(subpath " + _sbpl_string(str(home)) + ")"]
        for candidate in seen:
            if candidate.is_relative_to(home) and candidate != home:
                filters.append(
                    "(require-not (subpath " + _sbpl_string(str(candidate)) + "))"
                )
        lines.extend(_deny_rule("file-read*", filters))
    lines.extend(
        _deny_rule(
            "file-write*",
            [
                "(require-not (subpath " + _sbpl_string(str(workspace.resolve())) + "))",
                "(require-not (literal " + _sbpl_string("/dev/null") + "))",
            ],
        )
    )
    literals = [interpreter, str(exe)]
    literals.extend(tools)
    lines.extend(
        _deny_rule(
            "process-exec*",
            [
                "(require-not (literal " + _sbpl_string(literal) + "))"
                for literal in dict.fromkeys(literals)
            ],
        )
    )
    return "\n".join(lines) + "\n"


def _runner_source(repo_root: Path, script: Path, site_dirs: list[Path]) -> str:
    """Bootstrap for python -I: restore the venv packages on sys.path.

    The runner launches the resolved interpreter directly, so under -I
    the venv site-packages are missing; re-add them here, with the
    blocks.py directory first so ``import blocks`` finds our shim.
    """
    lines = ["import runpy as _runpy", "import sys as _sys"]
    for entry in [*site_dirs, repo_root]:
        lines.append("_sys.path.insert(0, " + json.dumps(str(entry)) + ")")
    lines.append("_sys.argv = [" + json.dumps(str(script)) + "]")
    lines.append(
        "_runpy.run_path(" + json.dumps(str(script)) + ", run_name=" + json.dumps("__main__") + ")"
    )
    return "\n".join(lines) + "\n"


def _image_snapshot(workspace: Path) -> dict[str, tuple[int, int]]:
    """Map image path to (mtime_ns, size) for change detection."""
    found: dict[str, tuple[int, int]] = {}
    for path in sorted(workspace.rglob("*")):
        if path.suffix.lower() not in _IMAGE_SUFFIXES or not path.is_file():
            continue
        if "scripts" in path.relative_to(workspace).parts:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        found[str(path)] = (stat.st_mtime_ns, stat.st_size)
    return found


def _newest_images(workspace: Path, before: dict[str, tuple[int, int]]) -> list[Path]:
    """Up to two PNG/JPG files created or changed during the run, newest first."""
    after = _image_snapshot(workspace)
    changed = []
    for name, stamp in after.items():
        if before.get(name) != stamp:
            changed.append((stamp[0], name))
    changed.sort(key=lambda item: (-item[0], item[1]))
    return [Path(name) for _, name in changed[:2]]


def _truncate(text: str) -> str:
    """Cap output at _OUTPUT_LIMIT characters and note the cut."""
    if len(text) <= _OUTPUT_LIMIT:
        return text
    rest = len(text) - _OUTPUT_LIMIT
    return text[:_OUTPUT_LIMIT] + "\n[... truncated " + str(rest) + " more characters]"


def run_python(
    code: str, workspace: str | Path, *, timeout_s: float = 60, _skip_review: bool = False
) -> SandboxResult:
    """Run agent code in the sandbox; refuse first if review finds problems.

    The test-only _skip_review flag runs the runner layer on its own so
    each layer is tested separately.
    """
    if timeout_s <= 0:
        raise ValueError("run_python: timeout_s must be positive")
    ws = Path(workspace).resolve()
    scripts = ws / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    problems = [] if _skip_review else review(code)
    script = _next_script_path(scripts)
    script.write_text(code, encoding="utf-8")
    if problems:
        return SandboxResult(ok=False, refused=True, problems=problems, script=script)
    before = _image_snapshot(ws)
    repo_root = _repo_root()
    exe = str(Path(sys.executable).resolve())
    tool_paths = []
    for tool in ("ffmpeg", "ffprobe"):
        found = shutil.which(tool)
        if found:
            tool_paths.append(found)
            resolved = str(Path(found).resolve())
            if resolved != found:
                tool_paths.append(resolved)
    profile_path = script.with_suffix(".sb")
    profile_path.write_text(
        _sandbox_profile(ws, repo_root, sys.executable, tool_paths), encoding="utf-8"
    )
    argv = [
        "sandbox-exec",
        "-f",
        str(profile_path),
        exe,
        "-I",
        "-c",
        _runner_source(repo_root, script, _site_dirs()),
    ]
    env = _clean_env(ws)
    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(ws),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        return SandboxResult(ok=False, refused=False, exit_code=None, stderr="could not start sandbox: " + str(exc), seconds=time.monotonic() - start, script=script)
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        stdout, stderr = proc.communicate()
    seconds = time.monotonic() - start
    images = _newest_images(ws, before)
    return SandboxResult(
        ok=proc.returncode == 0,
        refused=False,
        problems=[],
        exit_code=proc.returncode,
        stdout=_truncate(stdout),
        stderr=_truncate(stderr),
        seconds=seconds,
        images=images,
        script=script,
    )

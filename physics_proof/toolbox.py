"""M14. Toolsmith: the agent builds and verifies its own measurement tools.

A tool is a small Python module plus a probe. The probe imports the
module, builds synthetic data with a known answer, checks the result
with explicit tolerances and prints PASS. Only a tool whose probe
exits 0 and prints PASS is registered; only registered tools are
importable from later ``python`` calls (they live in
``workspace/tools/registered``, which the sandbox preloads into the
child ``sys.modules`` from explicit file paths). Failed candidates
stay in ``workspace/tools`` but are
never importable. Every version is kept under ``workspace/tools``.
"""

from __future__ import annotations

import ast
import json
import keyword
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Collection

from .sandbox import SandboxResult, review

__all__ = [
    "ATTEMPTS_FILE",
    "MAX_ATTEMPTS",
    "MAX_TOOLS",
    "REGISTRY_FILE",
    "Toolbox",
    "is_valid_name",
    "module_functions",
    "module_purpose",
    "promote_tool",
    "registered_dir",
]

#: Default cap on registered tools per run (configurable per run).
MAX_TOOLS = 4
#: Default cap on make_tool attempts per name (configurable per run).
MAX_ATTEMPTS = 3

#: Layout inside the run workspace.
TOOLS_DIRNAME = "tools"
REGISTERED_DIRNAME = "registered"
VERSIONS_DIRNAME = "versions"
REGISTRY_FILE = "registry.json"
ATTEMPTS_FILE = "attempts.json"

#: A tool must be a plain snake_case module name.
_NAME_RE = re.compile(r"[a-z][a-z0-9_]*")

#: Names that would shadow the sandbox allowlist or the harness itself.
_RESERVED = frozenset(
    {
        "blocks",
        "physics_proof",
        "contrib",
        "tests",
        "numpy",
        "scipy",
        "PIL",
        "matplotlib",
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

#: How much probe output the registry keeps per tool.
_OUTPUT_LIMIT = 4000


def is_valid_name(name: Any) -> bool:
    """True for a usable snake_case tool module name."""
    return (
        isinstance(name, str)
        and _NAME_RE.fullmatch(name) is not None
        and not keyword.iskeyword(name)
        and name not in _RESERVED
    )


def registered_dir(workspace: str | Path) -> Path:
    """Directory of registered tools; the only tools dir on the path."""
    return Path(workspace) / TOOLS_DIRNAME / REGISTERED_DIRNAME


def module_purpose(code: str) -> str:
    """First line of the module docstring, or empty when there is none."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ""
    doc = ast.get_docstring(tree) or ""
    first = doc.strip().splitlines()
    return first[0].strip() if first else ""


def module_functions(code: str) -> list[str]:
    """Public function signatures, e.g. step_rate(series, fps)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    out: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        try:
            sig = node.name + "(" + ast.unparse(node.args) + ")"
        except (ValueError, SyntaxError):
            continue
        if node.returns is not None:
            try:
                sig += " -> " + ast.unparse(node.returns)
            except (ValueError, SyntaxError):
                pass
        out.append(sig)
    return out


def _pass_state(stdout: str) -> bool:
    """True when a probe output line prints PASS (prints PASS at the end)."""
    for line in stdout.splitlines():
        text = line.strip()
        if text == "PASS" or text.startswith("PASS ") or text.startswith("PASS:"):
            return True
    return False


def _truncate(text: str) -> str:
    """Cap registry output with a note about the cut."""
    if len(text) <= _OUTPUT_LIMIT:
        return text
    rest = len(text) - _OUTPUT_LIMIT
    return text[:_OUTPUT_LIMIT] + "\n[... truncated " + str(rest) + " more characters]"


#: Code runner type: plain runners take (code, workspace); runners with
#: tool support also accept an ``extra_imports`` keyword of module names
#: the static review should allow (registered tool names).
Runner = Callable[..., SandboxResult]


def _call_runner(runner: Runner, code: str, workspace: Path, extra: Collection[str]) -> SandboxResult:
    """Call a runner, passing extra_imports only when there is something.

    Plain two-argument runners (older tests) never see the keyword; only
    tool runs pass registered names, which old runners never trigger.
    """
    names = tuple(sorted(set(extra)))
    if names:
        return runner(code, workspace, extra_imports=names)
    return runner(code, workspace)


@dataclass
class Toolbox:
    """Per-run registry of agent-built tools, backed by workspace files."""

    workspace: Path
    runner: Runner
    max_tools: int = MAX_TOOLS
    max_attempts: int = MAX_ATTEMPTS

    def _dir(self) -> Path:
        """The workspace tools dir, created on first write."""
        return Path(self.workspace) / TOOLS_DIRNAME

    def _read_json(self, name: str, default: Any) -> Any:
        """Load a tools JSON file; corrupt or missing files read as default."""
        path = self._dir() / name
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def _write_json(self, name: str, value: Any) -> None:
        """Write a tools JSON file with sorted keys."""
        self._dir().mkdir(parents=True, exist_ok=True)
        path = self._dir() / name
        path.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def registry(self) -> list[dict[str, Any]]:
        """Registered tools in registration order; [] when none."""
        data = self._read_json(REGISTRY_FILE, [])
        if not isinstance(data, list):
            return []
        return [entry for entry in data if isinstance(entry, dict)]

    def attempts(self) -> dict[str, int]:
        """make_tool attempts used per name; {} when none."""
        data = self._read_json(ATTEMPTS_FILE, {})
        if not isinstance(data, dict):
            return {}
        out: dict[str, int] = {}
        for name, count in data.items():
            if isinstance(name, str) and isinstance(count, int) and count > 0:
                out[name] = count
        return out

    def registered_names(self) -> list[str]:
        """Names importable from later python calls, in order."""
        return [str(entry["name"]) for entry in self.registry() if "name" in entry]

    def count(self) -> int:
        """Number of registered tools."""
        return len(self.registry())

    def make_tool(self, name: Any, code: Any, probe: Any, *, turn: int) -> tuple[bool, str]:
        """Register a tool when its probe passes in the sandbox.

        Returns (ok, message): ok with a registered tool, or not ok with
        the refusal or the probe output for Spark. Every valid call uses
        one attempt of this name, whether it passes or not.
        """
        if not is_valid_name(name):
            return False, (
                "make_tool refused: name must be a snake_case module name "
                + "(lowercase letters, digits, underscores, not reserved), got "
                + repr(name)
            )
        if not isinstance(code, str) or not code.strip():
            return False, "make_tool refused: code must be a non-empty string."
        if not isinstance(probe, str) or not probe.strip():
            return False, "make_tool refused: probe must be a non-empty string."
        used = self.attempts()
        attempt = int(used.get(name, 0)) + 1
        if used.get(name, 0) >= self.max_attempts:
            return False, (
                "make_tool refused: already used "
                + str(used.get(name, 0)) + " of " + str(self.max_attempts)
                + " attempts for tool " + repr(name) + "."
            )
        known = self.registered_names()
        if name not in known and len(known) >= self.max_tools:
            return False, (
                "make_tool refused: already registered " + str(len(known))
                + " of " + str(self.max_tools) + " tools ("
                + ", ".join(known) + ")."
            )
        code_problems = review(code, extra_imports=known)
        probe_problems = review(probe, extra_imports=known + [name])
        if code_problems or probe_problems:
            used[name] = attempt
            self._write_json(ATTEMPTS_FILE, used)
            lines = ["make_tool refused by the static review (nothing was run):"]
            for problem in code_problems:
                lines.append(
                    "- code line " + str(problem.line) + " [" + problem.rule + "] "
                    + problem.message
                )
            for problem in probe_problems:
                lines.append(
                    "- probe line " + str(problem.line) + " [" + problem.rule + "] "
                    + problem.message
                )
            return False, "\n".join(lines)
        used[name] = attempt
        self._write_json(ATTEMPTS_FILE, used)
        self._dir().mkdir(parents=True, exist_ok=True)
        versions = self._dir() / VERSIONS_DIRNAME
        versions.mkdir(parents=True, exist_ok=True)
        module_path = self._dir() / (name + ".py")
        probe_path = self._dir() / (name + "_probe.py")
        module_path.write_text(code, encoding="utf-8")
        probe_path.write_text(probe, encoding="utf-8")
        (versions / (name + ".attempt" + str(attempt) + ".py")).write_text(
            code, encoding="utf-8"
        )
        (versions / (name + ".attempt" + str(attempt) + "_probe.py")).write_text(
            probe, encoding="utf-8"
        )
        staged = registered_dir(self.workspace)
        staged.mkdir(parents=True, exist_ok=True)
        target = staged / (name + ".py")
        backup: bytes | None = target.read_bytes() if target.exists() else None
        target.write_bytes(module_path.read_bytes())
        result = _call_runner(self.runner, probe, Path(self.workspace), known + [name])
        output = ("-- stdout --\n" + result.stdout.strip()) if result.stdout.strip() else ""
        if result.stderr.strip():
            output += ("\n" if output else "") + "-- stderr --\n" + result.stderr.strip()
        if result.refused:
            problems = "; ".join(
                "line " + str(item.line) + " [" + item.rule + "] " + item.message
                for item in result.problems
            )
            output += ("\n" if output else "") + "refused: " + problems
        passed = bool(result.ok) and result.exit_code == 0 and _pass_state(result.stdout)
        if not passed:
            if backup is None:
                try:
                    target.unlink()
                except FileNotFoundError:
                    pass
            else:
                target.write_bytes(backup)
            body = "make_tool: probe for " + repr(name) + " failed (attempt "
            body += str(attempt) + " of " + str(self.max_attempts) + ")."
            if result.exit_code is not None:
                body += " exit " + str(result.exit_code) + "."
            body += " The module stays unregistered and cannot be imported."
            if output:
                body += "\n" + _truncate(output)
            return False, body
        entry = {
            "name": name,
            "purpose": module_purpose(code),
            "functions": module_functions(code),
            "probe_source": probe,
            "probe_output": _truncate(output or "(no output)"),
            "turn": turn,
            "attempt": attempt,
        }
        entries = [item for item in self.registry() if item.get("name") != name]
        entries.append(entry)
        self._write_json(REGISTRY_FILE, entries)
        return True, (
            "make_tool: tool " + repr(name) + " registered (attempt "
            + str(attempt) + "): " + (entry["purpose"] or "no purpose line")
            + ". Later python calls can import " + name + "."
        )

    def tools_section(self) -> list[dict[str, Any]]:
        """The analysis.json tools section, filled by finish from the registry."""
        section: list[dict[str, Any]] = []
        for entry in self.registry():
            output = str(entry.get("probe_output", ""))
            summary = ""
            for line in reversed(output.splitlines()):
                if line.strip():
                    summary = line.strip()
                    break
            section.append(
                {
                    "name": entry.get("name"),
                    "purpose": entry.get("purpose", ""),
                    "functions": entry.get("functions", []),
                    "probe_summary": summary,
                    "verified": True,
                }
            )
        return section


def promote_tool(
    run_dir: str | Path, tool: str, *, repo_root: str | Path
) -> tuple[Path, Path]:
    """Promote a registered tool into the library candidate set.

    Copies the module to ``physics_proof/contrib/<tool>.py`` and turns
    its probe into ``tests/contrib/test_<tool>.py`` (a pytest test that
    runs the probe body), both with a header comment naming the run.
    Returns the two written paths.
    """
    if not is_valid_name(tool):
        raise ValueError("promote: bad tool name " + repr(tool))
    root = Path(repo_root)
    run_path = Path(run_dir)
    try:
        entries = json.loads(
            (run_path / "workspace" / TOOLS_DIRNAME / REGISTRY_FILE).read_text(
                encoding="utf-8"
            )
        )
    except (OSError, ValueError) as exc:
        raise ValueError("promote: cannot read the tool registry: " + str(exc)) from exc
    if not isinstance(entries, list):
        raise ValueError("promote: the tool registry is not a list.")
    match = next(
        (item for item in entries if isinstance(item, dict) and item.get("name") == tool),
        None,
    )
    if match is None:
        raise ValueError("promote: tool " + repr(tool) + " is not registered in this run.")
    module_path = run_path / "workspace" / TOOLS_DIRNAME / (tool + ".py")
    if not module_path.exists():
        raise ValueError("promote: module file is missing: " + str(module_path))
    module_source = module_path.read_text(encoding="utf-8")
    probe_source = match.get("probe_source")
    if not isinstance(probe_source, str) or not probe_source.strip():
        raise ValueError("promote: the registry entry has no probe source.")
    header = (
        "# Promoted from run " + run_path.name + ": tool " + tool + " ("
        + str(match.get("purpose") or "no purpose line") + ").\n"
        + "# A human must review the code and the probe before trusting it.\n"
    )
    contrib_dir = root / "physics_proof" / "contrib"
    contrib_dir.mkdir(parents=True, exist_ok=True)
    contrib_path = contrib_dir / (tool + ".py")
    text = header + "\n" + module_source
    if not text.endswith("\n"):
        text += "\n"
    contrib_path.write_text(text, encoding="utf-8")
    test_dir = root / "tests" / "contrib"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_path = test_dir / ("test_" + tool + ".py")
    test_body = (
        header
        + '"""Probe for the promoted tool: runs the registered probe body. Human review required."""\n'
        + "\n"
        + "from __future__ import annotations\n"
        + "\n"
        + "import subprocess\n"
        + "import sys\n"
        + "from pathlib import Path\n"
        + "\n"
        + "CONTRIB_DIR = Path(__file__).resolve().parents[2] / \"physics_proof\" / \"contrib\"\n"
        + "REPO_ROOT = Path(__file__).resolve().parents[2]\n"
        + "\n"
        + "PROBE_SOURCE = " + json.dumps(probe_source) + "\n"
        + "\n"
        + "\n"
        + "def test_" + tool + "_probe_passes(tmp_path):\n"
        + '    """The registered probe body exits 0 and prints PASS."""\n'
        + "    probe_file = tmp_path / " + json.dumps(tool + "_probe.py") + "\n"
        + "    code = (\n"
        + '        "import sys\\n"\n'
        + "        + \"sys.path.insert(0, \" + repr(str(CONTRIB_DIR)) + \")\\n\"\n"
        + "        + \"sys.path.insert(0, \" + repr(str(REPO_ROOT)) + \")\\n\"\n"
        + "        + PROBE_SOURCE\n"
        + "    )\n"
        + "    probe_file.write_text(code, encoding=\"utf-8\")\n"
        + "    proc = subprocess.run(\n"
        + "        [sys.executable, str(probe_file)],\n"
        + "        capture_output=True,\n"
        + "        text=True,\n"
        + "        timeout=120,\n"
        + "        cwd=str(tmp_path),\n"
        + "    )\n"
        + "    assert proc.returncode == 0, proc.stdout + proc.stderr\n"
        + '    assert "PASS" in proc.stdout\n'
    )
    test_path.write_text(test_body, encoding="utf-8")
    return contrib_path, test_path

"""The self-built-tool registry (part 10 section 3).

``workspace/selfbuilt/registry.json``, written only by our code::

    {"tools": [{"name": "sb_wall_line", "module_sha256": "...",
                "test_sha256": "...", "attempts": 2, "status": "passed",
                "purpose": "<agent one-liner>", "registered_at_turn": 17}]}

Entries carry exactly these seven keys so part 11 can check a submitted
tool name against the registry (status ``passed``, hashes match) and part
12 can list every registered tool (name, purpose, attempts).

A same-name :func:`src.selfbuilt.gate.try_register` call is a retry (or a
re-test after an edit): it is allowed and consumes an attempt. Name
collisions that are rejected outright are shadowing a helper, a stdlib
name, or a malformed ``sb_`` name — the registry rejects, never resolves.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

#: At most this many distinct self-built tools per run (part 10 §2).
MAX_TOOLS_PER_RUN = 4
#: At most this many test executions per tool; every execution counts.
MAX_ATTEMPTS_PER_TOOL = 3

#: Directory inside the run workspace holding the two files per tool.
SELFBUILT_DIR_NAME = "selfbuilt"
#: Registry filename inside that directory, written only by our code.
REGISTRY_FILENAME = "registry.json"

#: Tool-name shape: the ``sb_`` prefix is mandatory.
_NAME_RE = re.compile(r"^sb_[a-z0-9_]+$")

#: Entry keys, exactly as the spec fixes them.
_ENTRY_KEYS = ("name", "module_sha256", "test_sha256", "attempts",
               "status", "purpose", "registered_at_turn")

#: Helper-library module names a tool must not shadow (part 09 set plus the
#: promotion target package).
_HELPER_NAMES = frozenset({
    "masks_io", "tracks", "physics", "clock", "gen_docs", "helpers",
    "promoted",
})

#: Terminal states for a registry entry.
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"


def selfbuilt_dir(run_dir) -> Path:
    """Return ``<run_dir>/workspace/selfbuilt`` (not created)."""
    return Path(run_dir) / "workspace" / SELFBUILT_DIR_NAME


def registry_path(run_dir) -> Path:
    """Return the registry file path (not created)."""
    return selfbuilt_dir(run_dir) / REGISTRY_FILENAME


def module_filename(name: str) -> str:
    """Return the module filename for a tool name (``sb_x`` -> ``sb_x.py``)."""
    return f"{name}.py"


def test_filename(name: str) -> str:
    """Return the test filename (``sb_x`` -> ``test_sb_x.py``)."""
    return f"test_{name}.py"


def sha256_text(source: str) -> str:
    """Return the hex SHA-256 of a source string."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def sha256_file(path) -> str:
    """Return the hex SHA-256 of a file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _blank_registry() -> dict:
    return {"tools": []}


def load_registry(run_dir) -> dict:
    """Load the registry, or ``{"tools": []}`` when nothing registered yet.

    Raises:
        ValueError: The registry file exists but is not our JSON shape
            (``registry_corrupt``) — it is written only by our code, so a
            corrupt file is a bug, never agent content to tolerate.
    """
    path = registry_path(run_dir)
    if not path.exists():
        return _blank_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"registry_corrupt: {path}: {exc}") from exc
    if (not isinstance(data, dict) or set(data) != {"tools"}
            or not isinstance(data["tools"], list)
            or any(set(e) != set(_ENTRY_KEYS) for e in data["tools"]
                   if isinstance(e, dict)) or
            any(not isinstance(e, dict) for e in data["tools"])):
        raise ValueError(f"registry_corrupt: {path}: unexpected shape")
    return data


def save_registry(run_dir, registry: dict) -> Path:
    """Atomically write the registry (only our code writes it)."""
    path = registry_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return path


def find_tool(registry: dict, name: str):
    """Return the registry entry for ``name``, or None."""
    for entry in registry.get("tools", []):
        if entry.get("name") == name:
            return entry
    return None


def validate_tool_name(name, registry=None):
    """Check a tool name against the two-file contract (§1).

    Args:
        name: Claimed tool name (must carry the ``sb_`` prefix).
        registry: Optional registry; a name already present is a retry,
            which is allowed (it consumes an attempt at test time).

    Returns:
        ``(ok, code, detail)`` — ``ok`` True when the name is usable.
    """
    if not isinstance(name, str) or not name:
        return False, "bad_tool_name", "tool name must be a non-empty string"
    if not name.startswith("sb_"):
        return (False, "bad_tool_name",
                f"{name!r}: module filename must carry the sb_ prefix "
                f"(workspace/selfbuilt/sb_<name>.py)")
    if not _NAME_RE.match(name):
        return (False, "bad_tool_name",
                f"{name!r}: use lowercase letters, digits, underscores")
    suffix = name[len("sb_"):]
    if not suffix:
        return False, "bad_tool_name", "'sb_' alone is not a tool name"
    stdlib = sys.stdlib_module_names
    if name in stdlib or suffix in stdlib:
        return (False, "name_collision",
                f"{name!r}: shadows a stdlib module name")
    if name in _HELPER_NAMES or suffix in _HELPER_NAMES:
        return (False, "name_collision",
                f"{name!r}: shadows a helper-library module name")
    return True, "", ""


def entry_importable(run_dir, entry) -> bool:
    """True iff a ``passed`` entry's files still match the registry hashes.

    A passing tool that was later edited stops being importable until
    re-tested: any hash mismatch (or missing file) fails closed.
    """
    if entry.get("status") != STATUS_PASSED:
        return False
    directory = selfbuilt_dir(run_dir)
    module = directory / module_filename(entry["name"])
    test = directory / test_filename(entry["name"])
    try:
        if not (module.is_file() and test.is_file()):
            return False
        return (sha256_file(module) == entry["module_sha256"]
                and sha256_file(test) == entry["test_sha256"])
    except OSError:
        return False


def is_importable(run_dir, name: str) -> bool:
    """True iff ``name`` is currently importable (passed, hashes match)."""
    try:
        registry = load_registry(run_dir)
    except ValueError:
        return False
    entry = find_tool(registry, name)
    if entry is None:
        return False
    return entry_importable(run_dir, entry)


def importable_names(run_dir) -> list:
    """Names currently importable from this run's selfbuilt directory."""
    try:
        registry = load_registry(run_dir)
    except ValueError:
        return []
    return [e["name"] for e in registry.get("tools", [])
            if entry_importable(run_dir, e)]


def list_tools_for_result(run_dir) -> list:
    """Every registry entry as ``{name, purpose, attempts}``.

    The result file (part 12) lists every registered tool — whether or
    not it was used — so a judge sees exactly what the agent built.
    """
    try:
        registry = load_registry(run_dir)
    except ValueError:
        return []
    return [{"name": e["name"], "purpose": e["purpose"],
             "attempts": e["attempts"]} for e in registry.get("tools", [])]


def validate_evidence_tools(used_names, run_dir) -> list:
    """Check submitted evidence tool names against the registry (part 11).

    Args:
        used_names: Tool names the submission claims its evidence used.
        run_dir: The run whose registry binds names to hashes.

    Returns:
        A list of ``{code, field, detail}`` errors; empty means every
        named tool is registered, passed, and unmodified. Numbers from an
        unregistered or failed tool are invalid by construction: the code
        that produced them could not have imported it.
    """
    try:
        registry = load_registry(run_dir)
    except ValueError as exc:
        return [{"code": "selfbuilt_registry_unreadable",
                 "field": "evidence.selfbuilt_tools",
                 "detail": str(exc)}]
    errors = []
    for name in (used_names or []):
        entry = find_tool(registry, name)
        if entry is None:
            errors.append({
                "code": "unregistered_selfbuilt_tool",
                "field": "evidence.selfbuilt_tools",
                "detail": f"{name!r} is not in the run registry",
            })
        elif entry.get("status") != STATUS_PASSED:
            errors.append({
                "code": "unregistered_selfbuilt_tool",
                "field": "evidence.selfbuilt_tools",
                "detail": f"{name!r} never passed its synthetic test",
            })
        elif not entry_importable(run_dir, entry):
            errors.append({
                "code": "unregistered_selfbuilt_tool",
                "field": "evidence.selfbuilt_tools",
                "detail": f"{name!r} was modified after registration",
            })
    return errors

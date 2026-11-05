# generated from brief/07 · part 07 owns this file
"""Shared path, naming and timing helpers for the tool layer (part 07).

All tool paths are run-relative and start with ``input/``,
``workspace/`` or ``artifacts`` (§10, §1 rule 4). Absolute paths and
``..`` are rejected. Artifact files use deterministic names
(``t<turn>_<tool>_<n>.<ext>``).
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from src import config as _config

__all__ = [
    "ALLOWED_PREFIXES",
    "reject_path",
    "check_run_path",
    "run_path",
    "artifact_name",
    "next_artifact",
    "read_timing",
    "append_produced",
    "produced_log_path",
    "read_produced",
]

#: Run-relative prefixes a tool may touch (§10: never ``logs/``).
ALLOWED_PREFIXES = ("input/", "workspace/", "artifacts/")


def reject_path(rel) -> str:
    """Why ``rel`` is unusable (``""`` when it is a clean run path)."""
    if not isinstance(rel, str) or not rel:
        return "path must be a non-empty string"
    if Path(rel).is_absolute() or ".." in PurePosixPath(rel).parts:
        return f"path escapes the run: {rel!r}"
    if not rel.startswith(ALLOWED_PREFIXES):
        return (f"path must start with input/, workspace/ or artifacts/: "
                f"{rel!r}")
    return ""


def check_run_path(rel) -> str | None:
    """The rejection reason for ``rel``, or ``None`` when clean."""
    reason = reject_path(rel)
    return reason or None


def run_path(run_dir, rel: str) -> Path:
    """Resolve a validated run-relative path inside the run directory."""
    return Path(str(run_dir)) / rel


def artifact_name(turn: int, tool: str, n: int, ext: str) -> str:
    """Deterministic artifact name (``t<turn>_<tool>_<n>.<ext>``)."""
    suffix = ext if ext.startswith(".") else f".{ext}"
    return f"artifacts/t{int(turn)}_{tool}_{int(n)}{suffix}"


def next_artifact(run_dir, turn: int, tool: str, ext: str,
                  start: int = 0) -> str:
    """First unused artifact name for this turn/tool/extension."""
    n = int(start)
    while True:
        name = artifact_name(turn, tool, n, ext)
        if not (Path(str(run_dir)) / name).exists():
            return name
        n += 1


def read_timing(run_dir) -> dict:
    """Load ``input/timing.json`` (raises ``ValueError`` when unusable)."""
    path = Path(str(run_dir)) / str(_config.INPUT_DIR_NAME) / "timing.json"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"unreadable timing.json: {exc}") from exc
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"invalid timing.json: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("timing.json must hold an object")
    return data


def produced_log_path(run_dir) -> Path:
    """Operator-side produced-files log (never agent-visible)."""
    return (Path(str(run_dir)) / str(_config.WORKSPACE_DIR_NAME)
            / "produced_files.json")


def append_produced(run_dir, rels) -> None:
    """Record run-relative files this run created (best effort)."""
    try:
        log = produced_log_path(run_dir)
        known = []
        if log.is_file():
            try:
                known = json.loads(log.read_text(encoding="utf-8"))
            except ValueError:
                known = []
        seen = set(known) if isinstance(known, list) else set()
        for rel in rels:
            seen.add(str(rel))
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(json.dumps(sorted(seen), indent=2) + "\n",
                       encoding="utf-8")
    except OSError:
        pass


def read_produced(run_dir) -> list:
    """Run-relative files recorded as created in this run."""
    try:
        text = produced_log_path(run_dir).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, ValueError):
        return []
    return [str(v) for v in data] if isinstance(data, list) else []

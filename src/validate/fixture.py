# generated from brief/11 · part 11 owns this file
"""Real-run fixture: ``fixtures/run-7/`` from ``fixtures/source/run-7/``.

Assembled by the same code that assembles live runs
(``collect`` on a temporary copy, then assembly from
``artifacts/t34_evidence.json``), plus copies of every artifact the
result cites. Because that evidence fails the new scale rules, the
fixture is built by assembly without the rejecting checks, and its
verdict comes from the verdict rules (expected: undetermined, clock
cannot separate). The copy is closed (brief §11): every path inside a
copied JSON or JSONL file is copied too, transitively, with
run-relative paths.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

__all__ = [
    "FIXTURE_EVIDENCE",
    "SOURCE_DIR",
    "TARGET_DIR",
    "build_fixture",
    "collect",
]

REPO = Path(__file__).resolve().parent.parent.parent
SOURCE_DIR = REPO / "fixtures" / "source" / "run-7"
TARGET_DIR = REPO / "fixtures" / "run-7"
FIXTURE_EVIDENCE = "artifacts/t34_evidence.json"
_SUFFIXES = (".png", ".jpg", ".jpeg", ".npz", ".json", ".jsonl", ".mp4")


def collect(run_dir) -> dict:
    """Minimal run context over a directory (mirrors part 07's)."""
    base = Path(str(run_dir))
    try:
        timing = json.loads(
            (base / "input" / "timing.json").read_text(encoding="utf-8"))
        if not isinstance(timing, dict):
            timing = {}
    except (OSError, ValueError):
        timing = {}
    artifacts = sorted(
        str(p.relative_to(base)) for p in (base / "artifacts").rglob("*")
        if p.is_file()) if (base / "artifacts").is_dir() else []
    produced: list = []
    produced_log = base / "workspace" / "produced_files.json"
    try:
        produced = json.loads(produced_log.read_text(encoding="utf-8"))
        if not isinstance(produced, list):
            produced = []
    except (OSError, ValueError):
        produced = []
    return {"run_dir": str(base), "run_id": base.name, "timing": timing,
            "artifacts": artifacts, "produced_files": [str(p) for p in
                                                       produced]}


def _file_strings(node, found: list):
    if isinstance(node, dict):
        for value in node.values():
            _file_strings(value, found)
    elif isinstance(node, list):
        for value in node:
            _file_strings(value, found)
    elif (isinstance(node, str) and "://" not in node
            and node.lower().endswith(_SUFFIXES)):
        found.append(node)


def _copy_closed(source: Path, target: Path, cited):
    """Copy cited paths transitively; fail on an absent file."""
    target.mkdir(parents=True, exist_ok=True)
    seen = set()
    queue = list(cited)
    while queue:
        rel = queue.pop(0)
        if not isinstance(rel, str) or not rel or rel in seen:
            continue
        seen.add(rel)
        origin = source / rel
        dest = target / rel
        if not origin.is_file():
            if dest.is_file():
                # Already placed (result.json/summary.json): scan it
                # for transitive references without recopying.
                origin = dest
            else:
                raise FileNotFoundError(
                    f"fixture source is missing the cited file: {rel}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, dest)
        if origin.suffix in (".json", ".jsonl"):
            try:
                if origin.suffix == ".jsonl":
                    nodes = [json.loads(line) for line in
                             origin.read_text(
                                 encoding="utf-8").splitlines()
                             if line.strip()]
                else:
                    nodes = [json.loads(origin.read_text(
                        encoding="utf-8"))]
            except ValueError:
                continue
            found: list = []
            for node in nodes:
                _file_strings(node, found)
            queue.extend(found)


def build_fixture(out_dir: Path | None = None) -> Path:
    """Rebuild the run-7 fixture from the owner source directory.

    Builds into the directory given by ``out_dir``; the default stays
    ``fixtures/run-7/`` for the one deliberate rebuild part 11 does
    while it is generated (brief §22). Tests always pass an explicit
    directory under ``tmp_path`` and never write under ``fixtures/``.
    """
    from src.contract import CONTRACT_VERSION, validate_result, validate_summary

    from .validate import assemble_result, run_checks

    dest = Path(out_dir) if out_dir is not None else TARGET_DIR
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "run-7"
        shutil.copytree(str(SOURCE_DIR), str(work),
                        ignore=shutil.ignore_patterns("logs"))
        ctx = collect(work)
        evidence = json.loads(
            (work / FIXTURE_EVIDENCE).read_text(encoding="utf-8"))
        try:
            _errors, computed = run_checks(evidence, {**ctx,
                                                     "run_dir": str(work)},
                                           dry_run=True)
        except (TypeError, ValueError, AttributeError, KeyError,
                ZeroDivisionError, ArithmeticError):
            import traceback

            raise RuntimeError("".join(
                traceback.format_exc(limit=5)))
        result = assemble_result(evidence, {**ctx, "run_dir": str(work)},
                                 computed)
        # The fixture stays part 12's previous-version sample
        # (test_previous_version_result_still_loads pins it at
        # CONTRACT_VERSION - 1). Live results stamp CONTRACT_VERSION;
        # this archival rebuild keeps the previous stamp with the new
        # fields present.
        result["contract_version"] = CONTRACT_VERSION - 1
        problems = validate_result(result)
        if problems:
            raise RuntimeError(
                "assembled fixture does not validate: "
                + "; ".join(problems[:5]))
        summary = {
            "contract_version": CONTRACT_VERSION - 1,
            "run_id": "run-7",
            "cost_usd": _source_cost(work),
            "turns": _source_turns(work),
            "model": "muse-spark-1.3-contributor",
            "sam_frames_billed": 0,
            "searches": 0,
            "mask_checks": 1,
            "wall_time_s": _source_wall(work),
            "budget_outcome": "completed",
            "result_path": "result.json",
        }
        problems = validate_summary(summary)
        if problems:
            raise RuntimeError(
                "assembled fixture summary does not validate: "
                + "; ".join(problems[:5]))
        if dest.exists():
            shutil.rmtree(str(dest))
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        (dest / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        (dest / "input").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(SOURCE_DIR / "input" / "timing.json"),
                        str(dest / "input" / "timing.json"))
        found: list = []
        _file_strings(result, found)
        _file_strings(summary, found)
        _copy_closed(SOURCE_DIR, dest, found)
    return dest


def _source_cost(work: Path) -> dict:
    try:
        summary = json.loads(
            (work / "summary.json").read_text(encoding="utf-8"))
        cost = summary.get("cost_usd", {})
        if isinstance(cost, dict):
            return {"total": float(cost.get("total", 0.0) or 0.0),
                    "spark_input": float(cost.get("spark_input", 0.0)
                                         or 0.0),
                    "spark_cached": float(cost.get("spark_cached", 0.0)
                                          or 0.0),
                    "spark_output": float(cost.get("spark_output", 0.0)
                                          or 0.0),
                    "sam": float(cost.get("sam", 0.0) or 0.0),
                    "search": float(cost.get("search", 0.0) or 0.0)}
    except (OSError, ValueError, TypeError):
        pass
    return {"total": 0.0, "spark_input": 0.0, "spark_cached": 0.0,
            "spark_output": 0.0, "sam": 0.0, "search": 0.0}


def _source_turns(work: Path) -> int:
    try:
        summary = json.loads(
            (work / "summary.json").read_text(encoding="utf-8"))
        return int(summary.get("turns", 0) or 0)
    except (OSError, ValueError, TypeError):
        return 0


def _source_wall(work: Path) -> float:
    try:
        summary = json.loads(
            (work / "summary.json").read_text(encoding="utf-8"))
        return float(summary.get("wall_time_s", 0.0) or 0.0)
    except (OSError, ValueError, TypeError):
        return 0.0

# generated from brief/15 · part 15 owns this file
"""Acceptance harness: implements part-03 §§3–5 (owned by part 15).

The acceptance constants below live ONLY here. They must never be
imported by, embedded in, or reachable from the analysis runtime or the
agent's prompt (part 03 §5). The prompt-leak test (§4) and the
structural separation check below enforce that boundary; a leak failure
fails the whole suite even if every verdict is right.

Offline: every check here is a pure function of stubbed inputs, so the
tests in this directory run with no model calls, no network, and no
money. The live path (`run_full_acceptance`, behind PHYSICS_PROOF_LIVE=1
via `dev_loop --acceptance`) runs 3 fresh analyses per clip through the
normal one-command entrypoint.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


# --- Harness-only constants (part 03 §4; never leave this module) --------

#: Verdict/tolerance expectations per clip slug.
EXPECTED = {
    "A": {
        "verdict_world": "Moon",
        "g_expected": 1.62,
        "sigma_cap": 0.35,
    },
    "B": {
        "retime_factor": 1.5,
        "factor_tolerance": 0.25,
    },
    "C": {
        "wall_sigma_threshold": 5.0,
        "earth_g": 9.81,
    },
}

RUNS_PER_CLIP = 3
PASSES_NEEDED = 2
HARD_COST_CAP_USD = 2.0
HARD_WALL_TIME_S = 30 * 60

#: Clip identities: forbidden in everything the system/operator sends.
IDENTITY_STRINGS = [
    "apollo",
    "alsj",
    "a16salute",
    "a16salute.mpg",
    "john young",
    "charles duke",
    "charlie duke",
    "wall run",
    "moon landing hoax",
    "lunar surface journal",
    "jump salute",
]

#: Tolerance/answer strings as expectations. Generic physics (Earth 9.81,
#: Moon 1.62, Mars 3.71 — the candidate world table every clip may use)
#: is NOT a leak; only per-clip expectations are. Distinctive forms are
#: listed so ordinary numbers (frame counts, timestamps) never match.
EXPECTATION_STRINGS = [
    "0.35",
    "±0.25",
    "+/-0.25",
    "5σ",
    "5-sigma",
    "5 sigma",
    "2-of-3",
    "2 of 3",
    "expected verdict",
    "expected moon",
    "must be moon",
    "should be moon",
    "expected retiming",
    "expected impossible",
    "must be impossible",
]


def _norm(text: str) -> str:
    return text.casefold()


def _contains(haystack: str, needle: str) -> bool:
    return _norm(needle) in _norm(haystack)


# --- Prompt-leak test (part 03 §5 + 2026-10-28 addendum) -------------------

#: What the system and the operator put in front of the agent: the fixed
#: prompt, tool descriptions, helper docs, ingest metadata, the
#: operator's words, and the harness. Identities AND expectations fail.
SYSTEM_FORBIDDEN = IDENTITY_STRINGS + EXPECTATION_STRINGS

#: The agent's own turn texts and its own search results: scanned only
#: for acceptance constants and expected verdicts, never for identities —
#: the agent may name what it identifies in the frames (part 01).
AGENT_FORBIDDEN = EXPECTATION_STRINGS


def check_no_leak(system_texts, agent_texts, search_texts=()):
    """Scan captured Spark-bound traffic; return a list of findings.

    Each finding names the bucket and the forbidden string. Empty means
    the run passes the leak test. Matching is case-insensitive.
    """
    findings: list[str] = []
    for text in system_texts:
        for forbidden in SYSTEM_FORBIDDEN:
            if _contains(str(text), forbidden):
                findings.append(f"system text contains {forbidden!r}")
    for text in agent_texts:
        for forbidden in AGENT_FORBIDDEN:
            if _contains(str(text), forbidden):
                findings.append(f"agent text contains {forbidden!r}")
    for text in search_texts:
        for forbidden in AGENT_FORBIDDEN:
            if _contains(str(text), forbidden):
                findings.append(f"search result contains {forbidden!r}")
    return sorted(set(findings))


def collect_run_texts(run_dir):
    """Bucket everything sent to Spark by a run into system/agent/search.

    Reads ``logs/`` traffic records of the form
    ``{"origin": "system" | "agent_turn" | "search_result", "text": ...}``
    (one JSON object per line). Lines without an origin marker are
    conservatively treated as system text. Returns
    ``(system, agent, search)`` text lists.
    """
    run_dir = Path(run_dir)
    system: list[str] = []
    agent: list[str] = []
    search: list[str] = []
    logs_dir = run_dir / "logs"
    if not logs_dir.is_dir():
        return system, agent, search
    for path in sorted(logs_dir.iterdir()):
        if not path.is_file() or path.suffix not in (".json", ".jsonl"):
            continue
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                system.append(raw)
                continue
            if isinstance(record, dict) and "text" in record:
                origin = str(record.get("origin", "system"))
                text = str(record.get("text", ""))
            else:
                origin, text = "system", raw
            if origin == "agent_turn":
                agent.append(text)
            elif origin == "search_result":
                search.append(text)
            else:
                system.append(text)
    return system, agent, search


#: Import/read patterns that would couple the runtime to the test
#: side: importing the harness or the clip-preparation module, reading
#: the harness files, or reading the wall-clip env var the harness owns.
#: Plain prose mentions (docstrings) and the blindness-pattern
#: allowlist (``src/config.py`` BLINDNESS_PATTERNS, required by part 04
#: §7) are not imports or reads and never match these patterns.
SEPARATION_PATTERNS = [
    r"(from|import)\s+[\w\.]*\b(tests|make_clips|acceptance|harness)\b",
    r"open\s*\([^)]*(tests/acceptance|tests/dev_loop|make_clips|harness\.py)",
    r"tests/acceptance",
    r"tests/dev_loop",
    r"(from|import)\s+make_clips",
    r"\bWALLRUN_CLIP\b",
    r"\brun_full_acceptance\b",
    r"\bCLIP_CHECKERS\b",
]

_SEPARATION_RES = [re.compile(pattern) for pattern in SEPARATION_PATTERNS]


def check_runtime_separation(repo_root):
    """Structural guarantee behind the leak scan (part 03 §5).

    The analysis runtime must not import or read the test harness, this
    module's constants, or the clip-preparation ground truth. Scans the
    runtime text (``src/``, ``prompts/``, ``player/``) for references to
    those holders. ``tools/dev_loop`` is the regeneration driver, not
    the runtime, so its (legitimate) harness reference is out of scope.
    Returns a list of findings; empty passes.
    """
    repo_root = Path(repo_root)
    findings: list[str] = []
    for scan_dir in ("src", "prompts", "player"):
        base = repo_root / scan_dir
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix != ".py":
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(lines, 1):
                for pattern in _SEPARATION_RES:
                    if pattern.search(line):
                        findings.append(
                            f"{path.relative_to(repo_root)}:{number}: "
                            f"{line.strip()[:100]}"
                        )
    return sorted(set(findings))


# --- Per-run evaluation (harness-only constants) ---------------------------

def _verdict(result):
    verdict = result.get("verdict") or {}
    return verdict if isinstance(verdict, dict) else {}


def check_clip_a(result):
    """Part 03 §4.1: Moon verdict, |g − 1.62| ≤ 2σ and σ ≤ 0.35."""
    exp = EXPECTED["A"]
    verdict = _verdict(result)
    problems: list[str] = []
    if verdict.get("world") != exp["verdict_world"]:
        problems.append(f"verdict world is {verdict.get('world')!r}, want Moon")
    g = verdict.get("g_measured")
    sigma = verdict.get("sigma_g")
    if g is None or sigma is None:
        problems.append("verdict carries no g_measured/sigma_g")
        return problems
    if not sigma <= exp["sigma_cap"]:
        problems.append(f"σ {sigma} exceeds cap {exp['sigma_cap']}")
    if not abs(g - exp["g_expected"]) <= 2 * sigma:
        problems.append(f"|g − 1.62| = {abs(g - exp['g_expected'])} > 2σ")
    return problems


def check_clip_b(result):
    """Part 03 §4.2: no scene-allowed world fits native; retimed 1.5±0.25."""
    exp = EXPECTED["B"]
    verdict = _verdict(result)
    problems: list[str] = []
    worlds = result.get("worlds") or {}
    candidates = worlds.get("candidates") or []
    native = [c for c in candidates if c.get("fits_native")]
    if native:
        names = [c.get("world") for c in native]
        problems.append(f"a world fits at native speed: {names}")
    factor = verdict.get("factor")
    if factor is None:
        problems.append("verdict carries no retiming factor")
        return problems
    if verdict.get("world") is None:
        problems.append("retimed verdict names no world")
    if not abs(factor - exp["retime_factor"]) <= exp["factor_tolerance"]:
        problems.append(
            f"factor {factor} outside 1.5 ± 0.25 "
            f"({exp['retime_factor']} ± {exp['factor_tolerance']})"
        )
    return problems


def _clock_reads_normal(result):
    """The independent clock reads normal (s_clock consistent with 1)."""
    clock = result.get("clock")
    note = str(result.get("clock_note") or "")
    if isinstance(clock, dict):
        for key in ("verdict", "status", "reading"):
            value = str(clock.get(key) or "").casefold()
            if value in ("normal", "consistent", "consistent with 1"):
                return True
        if clock.get("consistent_with_unity") is True:
            return True
        s_clock = clock.get("s_clock")
        s_sigma = clock.get("sigma_s") or clock.get("sigma")
        if s_clock is not None and s_sigma:
            try:
                return abs(float(s_clock) - 1.0) <= 2 * float(s_sigma)
            except (TypeError, ValueError):
                pass
    return "normal" in note.casefold()


def _wall_segment_sigma(result):
    """Largest |g − Earth| / σ over wall-marked segments, or None."""
    exp = EXPECTED["C"]
    segments = result.get("segments")
    if not isinstance(segments, list):
        return None
    best = None
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        marker = (
            str(segment.get("id") or "")
            + " " + str(segment.get("kind") or "")
            + " " + str(segment.get("type") or "")
        ).casefold()
        if "wall" not in marker:
            continue
        g = segment.get("g_measured", segment.get("g"))
        sigma = segment.get("sigma_g", segment.get("sigma"))
        if g is None or not sigma:
            continue
        try:
            distance = abs(float(g) - exp["earth_g"]) / float(sigma)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        best = distance if best is None else max(best, distance)
    return best


def check_clip_c(result):
    """Part 03 §4.3: impossible; wall >5σ from Earth g; clock normal."""
    exp = EXPECTED["C"]
    verdict = _verdict(result)
    problems: list[str] = []
    kind = str(verdict.get("kind") or "")
    reason = str(verdict.get("reason") or "")
    if kind != "impossible" and "impossible" not in reason.casefold():
        problems.append(f"verdict is not impossible: kind={kind!r}")
    distance = _wall_segment_sigma(result)
    if distance is None:
        problems.append("no wall segment with g ± σ found")
    elif not distance > exp["wall_sigma_threshold"]:
        problems.append(
            f"wall segment is {distance:.2f}σ from Earth g, need >5σ"
        )
    if not _clock_reads_normal(result):
        problems.append("independent clock does not read normal")
    return problems


CLIP_CHECKERS = {"A": check_clip_a, "B": check_clip_b, "C": check_clip_c}


def check_universal(result, summary):
    """Part 03 §4.4: cost, time, mask check, valid file (per run)."""
    problems: list[str] = []
    if not isinstance(summary, dict):
        return ["summary.json is not an object"]
    cost = summary.get("cost_usd") or {}
    total = cost.get("total") if isinstance(cost, dict) else None
    if total is None:
        problems.append("summary carries no cost total")
    elif not total < HARD_COST_CAP_USD:
        problems.append(f"cost ${total} reaches the $2 hard cap")
    wall = summary.get("wall_time_s")
    if wall is None:
        problems.append("summary carries no wall_time_s")
    elif not wall < HARD_WALL_TIME_S:
        problems.append(f"wall time {wall}s reaches the 30 min hard cap")
    mask_checks = summary.get("mask_checks", 0) or 0
    steps = result.get("calculation_steps") or []
    recorded = any(
        isinstance(step, dict) and step.get("id") == "mask_check"
        for step in steps
    )
    if not (mask_checks >= 1 or recorded):
        problems.append("no blind mask check recorded")
    return problems


def ab_ratio(g_a, g_b):
    """A/B acceleration cross-check for the report only (≈1.5, §4 note).

    Never fed back into a run, never changes a verdict, and never
    written to a per-clip player page (whose result file cannot contain
    another clip's numbers, part 12 §1).
    """
    if not g_a:
        return None
    return g_b / g_a


# --- Orchestration (live path only) ----------------------------------------

def _ensure_clips(repo_root):
    """Resolve clip A/B paths, generating them if needed; C by env path."""
    repo_root = Path(repo_root)
    clips_dir = repo_root / "clips"
    path_a = Path(os.environ.get("CLIP_A", clips_dir / "clip_a.mp4"))
    path_b = Path(os.environ.get("CLIP_B", clips_dir / "clip_b.mp4"))
    missing = [p for p in (path_a, path_b) if not p.is_file()]
    if missing:
        script = repo_root / "scripts" / "make_clips.py"
        proc = subprocess.run(
            [sys.executable or "python3", str(script),
             "--out-dir", str(clips_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=repo_root,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"make_clips failed:\n{proc.stdout[-2000:]}")
    wall = os.environ.get("WALLRUN_CLIP", "")
    clips = {"A": path_a, "B": path_b}
    if wall:
        clips["C"] = Path(wall)
    return clips


def _run_once(repo_root, clip_path):
    """One fresh analysis through the normal one-command entrypoint."""
    sys.path.insert(0, str(Path(repo_root)))
    try:
        from src import cli  # noqa: WPS433 (live path only)
    finally:
        sys.path.pop(0)
    started = time.time()
    outcome = cli.run_analysis(str(clip_path))
    run_dir = Path(outcome["run_dir"])
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    summary = json.loads(
        (run_dir / "summary.json").read_text(encoding="utf-8")
    )
    summary.setdefault("wall_time_s", time.time() - started)
    return run_dir, result, summary


def _result_g(result):
    verdict = _verdict(result)
    g = verdict.get("g_measured")
    try:
        return float(g) if g is not None else None
    except (TypeError, ValueError):
        return None


def run_full_acceptance(repo_root):
    """Run the part-03 protocol: 3 fresh runs per clip, 2-of-3, universals.

    Live only (called behind PHYSICS_PROOF_LIVE=1). Returns
    ``(exit_code, report_text, summary_line)``.
    """
    repo_root = Path(repo_root)
    sys.path.insert(0, str(repo_root))
    try:
        from src.contract import validate_result  # noqa: WPS433
    finally:
        sys.path.pop(0)
    clips = _ensure_clips(repo_root)
    lines: list[str] = []
    failures: list[str] = []
    g_values: dict[str, list] = {}
    skipped: list[str] = []
    for slug in ("A", "B", "C"):
        if slug not in clips:
            skipped.append(slug)
            lines.append(f"clip {slug}: SKIPPED (WALLRUN_CLIP unset)")
            continue
        checker = CLIP_CHECKERS[slug]
        passed_runs = 0
        g_values[slug] = []
        for attempt in range(1, RUNS_PER_CLIP + 1):
            run_dir, result, summary = _run_once(repo_root, clips[slug])
            run_problems = list(validate_result(result))
            run_problems += check_universal(result, summary)
            run_problems += checker(result)
            system, agent, search = collect_run_texts(run_dir)
            run_problems += check_no_leak(system, agent, search)
            g_values[slug].append(_result_g(result))
            if run_problems:
                lines.append(f"clip {slug} run {attempt}: FAIL")
                failures.extend(
                    f"clip {slug} run {attempt}: {problem}"
                    for problem in run_problems
                )
            else:
                passed_runs += 1
                lines.append(f"clip {slug} run {attempt}: pass")
        if passed_runs >= PASSES_NEEDED:
            lines.append(f"clip {slug}: PASS ({passed_runs}/3 runs)")
        else:
            lines.append(f"clip {slug}: FAIL ({passed_runs}/3 runs)")
            failures.append(f"clip {slug}: only {passed_runs}/3 runs passed")
    leak_structural = check_runtime_separation(repo_root)
    failures.extend(leak_structural)
    if "A" in g_values and "B" in g_values:
        a_vals = [g for g in g_values["A"] if g]
        b_vals = [g for g in g_values["B"] if g]
        if a_vals and b_vals:
            ratio = ab_ratio(sum(a_vals) / len(a_vals),
                             sum(b_vals) / len(b_vals))
            lines.append(
                f"cross-check (report only, never on a page): "
                f"A/B acceleration ratio ≈ {ratio:.2f} (expected ≈1.5)"
            )
    if skipped:
        lines.append(f"skipped clips: {', '.join(skipped)}")
    report = "\n".join(lines)
    summary_line = (
        f"{RUNS_PER_CLIP} runs/clip, 2-of-3, "
        f"{'FAIL: ' + '; '.join(failures) if failures else 'all clips pass'}"
    )
    return (1 if failures else 0, report, summary_line)

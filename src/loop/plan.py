# generated from brief/06 · part 06 owns this file
"""Placeholder refusal and plan progress (part 06 addenda 2026-10-31).

Hand run 7 dry-ran a placeholder (empty ``references`` and
``range_checks``, a dummy scale) and then never wrote a measurement
into ``workspace/evidence.json``; at turn 70 the loop submitted the
placeholder. Wall run 12 did the same twice.

- The loop refuses a placeholder dry run without calling the
  validator and without counting it as a dry run. A placeholder has
  no reference with an ``extent_px``, no range check with an extent,
  and no segment with frames.
- Every turn's status line shows the plan's progress: one entry per
  Wonder check (its ``kind`` and a few words) plus whether
  ``workspace/evidence.json`` holds it now. The loop reads the file
  each turn and never edits it.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    "DECIDED_DECISIONS",
    "MEASURED_DECISION",
    "PLACEHOLDER_REFUSAL",
    "evidence_has_measurement",
    "plan_checks",
    "plan_progress_line",
    "resolve_submit_evidence",
]

#: The refusal text a placeholder dry run gets instead of a validator
#: verdict (hand run 7 / wall run 12 addendum): no validator call, no
#: dry-run count, and the run goes on.
PLACEHOLDER_REFUSAL = (
    "This evidence has no measurement yet. Measure one check of the "
    "plan with helpers.ranges or a segment fit, write it into "
    "workspace/evidence.json, then dry-run."
)


def _items(value) -> list:
    """List entries of ``value`` (anything else counts as empty)."""
    return list(value) if isinstance(value, (list, tuple)) else []


def evidence_has_measurement(evidence) -> bool:
    """Whether ``evidence`` holds at least one real measurement.

    A reference counts once it carries an ``extent_px``; a range
    check counts once it carries ``extents``; a segment counts once
    it carries ``frames``. Anything else — including a placeholder
    with empty ``references`` and ``range_checks`` — has none.
    """
    if not isinstance(evidence, dict):
        return False
    for reference in _items(evidence.get("references")):
        if isinstance(reference, dict) and reference.get("extent_px"):
            return True
    for check in _items(evidence.get("range_checks")):
        if isinstance(check, dict) and check.get("extents"):
            return True
    for segment in _items(evidence.get("segments")):
        if isinstance(segment, dict) and segment.get("frames"):
            return True
    return False


def resolve_submit_evidence(run_dir, arguments):
    """The submit call's evidence as a dict, or ``None``.

    Mirrors the submit tool's own loading (inline object, JSON
    string, or ``evidence_path`` under the run directory) so the
    loop can spot a placeholder before dispatching. ``None`` means
    the evidence cannot be loaded into a dict here — the submit
    tool's own argument errors still handle that path.
    """
    if not isinstance(arguments, dict):
        return None
    inline = arguments.get("evidence")
    if isinstance(inline, dict):
        return inline
    if isinstance(inline, str):
        try:
            parsed = json.loads(inline)
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None
    path = arguments.get("evidence_path")
    if isinstance(path, str) and path:
        try:
            parsed = json.loads(
                (Path(str(run_dir)) / path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def plan_checks(wonder) -> list:
    """The Wonder plan's checks (``[]`` with no plan)."""
    if not isinstance(wonder, dict):
        return []
    checks = wonder.get("checks")
    if not isinstance(checks, list):
        return []
    return [check for check in checks if isinstance(check, dict)]


#: Candidate decisions the overview may carry (part 12 §24):
#: ``measured`` names its segment, the others carry a reason.
MEASURED_DECISION = "measured"
DECIDED_DECISIONS = ("measured", "not_a_flight", "not_measurable")


def _overview_complete(evidence: dict) -> bool:
    """Whether the motion survey is decided and the measured fly.

    A motion check counts as done only when ``first_look.overview``
    gives every candidate a decision and every ``measured`` candidate
    has a segment with frames (part 06 addendum 2026-11-01, Moon and
    sped-up Moon runs). The file is read, never edited.
    """
    if not isinstance(evidence, dict):
        return False
    first = evidence.get("first_look")
    overview = first.get("overview") if isinstance(first, dict) else None
    if not isinstance(overview, dict):
        return False
    candidates = overview.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return False
    by_id = {}
    for segment in _items(evidence.get("segments")):
        if isinstance(segment, dict) and segment.get("id") is not None:
            by_id[segment.get("id")] = segment
    for candidate in candidates:
        if not isinstance(candidate, dict):
            return False
        decision = candidate.get("decision")
        if decision not in DECIDED_DECISIONS:
            return False
        if decision == MEASURED_DECISION:
            segment_id = candidate.get("segment_id")
            if (not isinstance(segment_id, str) or not segment_id
                    or candidate.get("reason") is not None):
                return False
            segment = by_id.get(segment_id)
            if not isinstance(segment, dict) or not segment.get("frames"):
                return False
        else:
            reason = candidate.get("reason")
            if (not isinstance(reason, str) or not reason.strip()
                    or candidate.get("segment_id") is not None):
                return False
    return True


def _check_present(kind: str, evidence: dict) -> bool:
    """Whether ``evidence.json`` holds this check's kind of result.

    A motion (``gravity``) check counts only once the overview is
    decided with every measured candidate flying as a segment with
    frames; a range check once a range check with extents exists,
    and a clock check once a clock exists — matching the initial
    task's evidence mapping.
    """
    if not isinstance(evidence, dict):
        return False
    if kind in ("gravity", "motion"):
        return _overview_complete(evidence)
    if kind == "range":
        return any(isinstance(check, dict) and check.get("extents")
                   for check in _items(evidence.get("range_checks")))
    if kind == "clock":
        clock = evidence.get("clock")
        return isinstance(clock, dict) and bool(clock)
    return False


def _short_words(what) -> str:
    """The check's subject in a few words, on one line."""
    return " ".join(str(what or "").split())


def plan_progress_line(wonder, run_dir) -> str | None:
    """The plan's progress as one status line (``None`` with no plan).

    One entry per Wonder check — ``N kind: words — in/not in
    evidence.json`` — read from ``workspace/evidence.json`` now and
    never edited. The caller appends this after the budget line, so
    every turn's status shows what the plan still needs.
    """
    checks = plan_checks(wonder)
    if not checks:
        return None
    try:
        evidence = json.loads(
            (Path(str(run_dir)) / "workspace" / "evidence.json")
            .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        evidence = {}
    if not isinstance(evidence, dict):
        evidence = {}
    entries = []
    for index, check in enumerate(checks, start=1):
        kind = str(check.get("kind") or "").strip()
        words = _short_words(check.get("what"))
        state = ("in evidence.json" if _check_present(kind, evidence)
                 else "not in evidence.json")
        entries.append(f"{index} {kind}: {words} \u2014 {state}")
    return "plan: " + "; ".join(entries)

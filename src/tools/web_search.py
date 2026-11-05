# generated from brief/07 · part 07 owns this file
"""``web_search`` — size lookup behind the blindness filter
(part 07 §§5, 17).

The only web access, behind two in-code gates:

1. **Pattern screen:** reject queries carrying the run's anonymous
   filename, hashes, or answer-seeking forms. The screen blocks the
   answer, not the identity: queries may name what the agent
   identified in the frames (places, missions, people, models, eras)
   to look up facts about those things (heights, dimensions,
   equipment sizes, standard rates). Rejected are queries that look
   for the clip or its answer — the clip itself, an analysis of it,
   "real or fake", "hoax", "faked", or a measured gravity, jump
   height or hang time of the event. Generic in structure: it blocks
   answer-seeking, never physics, places, missions or people.
2. **Context-free classifier:** a separate call seeing only the
   query text, answering whether it tries to find a specific video,
   an analysis of it, or the answer to whether its motion is real or
   what gravity it shows, rather than facts about objects, people or
   places. Reject on yes/uncertain.

Allowed queries return the sourced facts — every item with its
text, source URL and verbatim quote — so ``references[].sources``
can quote them. All queries and filter decisions are logged for the
prompt-leak audit.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src import config as _config

from .common import append_produced, next_artifact, run_path
from .result import err_result, ok_result

__all__ = [
    "web_search",
    "pattern_hit",
    "run_tokens",
    "search_log_path",
    "ANSWER_SEEKING_PATTERNS",
    "CLASSIFIER_QUESTION",
]

#: Answer-seeking forms blocked by the pattern screen (part 07 §17).
#: Generic in structure: they name the clip/source or seek its
#: answer, never physics, places, missions or people. Names of
#: missions, places and people are deliberately NOT here.
ANSWER_SEEKING_PATTERNS = (
    "hoax",
    "fake",
    "faked",
    "real or fake",
    "debunk",
    "gravity in the video",
    "slowed down footage",
)

#: The classifier question (part 07 §17). The injected classifier
#: callable carries this wording to the model and answers exactly
#: "yes", "no" or "uncertain"; the tool only sees the verdict back.
CLASSIFIER_QUESTION = (
    "Is this query trying to find a specific video, an analysis of "
    "it, or the answer to whether its motion is real or what gravity "
    "it shows, rather than facts about objects, people or places "
    "(sizes, dimensions, rates)?")

#: A measured gravity of the event in the clip (part 07 §17).
_GRAVITY_MEASURED_RE = re.compile(
    r"gravity\s+(measured|measurement|of\s+the\s+(jump|event|video|clip)|"
    r"in\s+the\s+(video|clip)|value|estimate)")

#: A jump height or hang time of the event in the clip (part 07 §17).
_JUMP_SIZED_RE = re.compile(
    r"(jump\s+height|hang\s*time|air\s*time|how\s+(high|long)\b.{0,20}jump|"
    r"jump.{0,20}how\s+(high|long))")

#: Looking for the clip itself (part 07 §17).
_CLIP_HUNT_RE = re.compile(
    r"(video\s+of\s+.{0,40}(jump|salute|landing)|viral\s+.{0,20}(video|clip)|"
    r"footage\s+of\s+.{0,40}(jump|salute)|"
    r"analysis\s+of\s+.{0,20}(video|clip|footage))")

#: Hex runs that look like content hashes, never like physics.
_HASH_RE = re.compile(r"\b[0-9a-f]{8,}\b")


def search_log_path(run_dir) -> Path:
    """Operator-side query/decision log (prompt-leak audit input)."""
    return Path(str(run_dir)) / str(_config.LOGS_DIR_NAME) / "search.jsonl"


def run_tokens(run_dir) -> list:
    """Identifying tokens of this run: clip stem and run-dir name.

    Public so sibling tools (``check_line``) can apply the same
    pattern screen; the blindness filter is one filter everywhere.
    """
    tokens: list = []
    try:
        names = [p.name for p in
                 (Path(str(run_dir)) / str(_config.INPUT_DIR_NAME)
                  ).iterdir() if p.is_file()]
    except OSError:
        names = []
    for name in names:
        stem = Path(name).stem.lower()
        if len(stem) >= 4:
            tokens.append(stem)
    base = Path(str(run_dir)).name.lower()
    if len(base) >= 4:
        tokens.append(base)
    return tokens


def _run_tokens(run_dir) -> list:
    """Private alias of :func:`run_tokens` (kept for callers)."""
    return run_tokens(run_dir)


def pattern_hit(query: str, extra_tokens=()) -> str:
    """The answer-seeking pattern ``query`` trips, or ``""`` when clean.

    Generic in structure (part 07 §17): it blocks the answer, not
    the identity — the run's own file names and hashes plus
    answer-seeking forms (hoax/fake claims, real-or-fake questions,
    debunking, measured gravity / jump height / hang time of the
    event, hunting the clip itself). Names of places, missions and
    people pass: they look up facts about those things. Never
    physics.
    """
    lowered = str(query).lower()
    for pattern in ANSWER_SEEKING_PATTERNS:
        if pattern in lowered:
            return str(pattern)
    if _GRAVITY_MEASURED_RE.search(lowered):
        return "measured-gravity-of-the-event"
    if _JUMP_SIZED_RE.search(lowered):
        return "jump-height-or-hang-time-of-the-event"
    if _CLIP_HUNT_RE.search(lowered):
        return "looking-for-the-clip-itself"
    for token in list(extra_tokens or []):
        if str(token).lower() in lowered:
            return f"run-token:{token}"
    match = _HASH_RE.search(lowered)
    if match:
        return f"hash-like:{match.group(0)}"
    return ""


def _log_decision(run_dir, record: dict) -> None:
    try:
        path = search_log_path(run_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
    except OSError:
        pass


def _refuse(run_dir, turn, query, code, detail, decision) -> dict:
    _log_decision(run_dir, {"turn": int(turn), "query": str(query),
                            "allowed": False, **decision})
    return err_result(code, detail,
                      metrics={"query": str(query), "allowed": False,
                               **decision})


def web_search(run_dir, turn, query=None, *, search_client=None,
               classifier=None, ledger=None) -> dict:
    """Run one generic-fact lookup; refusals name the tripped gate."""
    if not isinstance(query, str) or not query.strip():
        return err_result("bad_query", "query must be a non-empty string",
                          metrics={"query": query, "allowed": False})
    text = query.strip()
    hit = pattern_hit(text, _run_tokens(run_dir))
    if hit:
        return _refuse(
            run_dir, turn, text, "query_rejected",
            f"pattern screen: query seeks the clip or its answer ({hit}); "
            "rephrase generically (sizes, dimensions or rates of named "
            "things — never the clip, an analysis of it, or its answer)",
            {"stage": "pattern_screen", "pattern": hit})
    if classifier is None:
        return _refuse(
            run_dir, turn, text, "classifier_unavailable",
            "no blindness classifier is wired; the query cannot be "
            "cleared, so it is refused (fail closed)",
            {"stage": "classifier", "verdict": "unavailable"})
    try:
        verdict = classifier(text)
    except Exception as exc:  # noqa: BLE001 — doubt fails closed
        return _refuse(
            run_dir, turn, text, "classifier_failed",
            f"blindness classifier failed ({type(exc).__name__}); "
            "the query is refused (fail closed)",
            {"stage": "classifier", "verdict": "error"})
    word = re.sub(r"[^a-z]", "", str(verdict or "").lower())
    if word != "no":
        return _refuse(
            run_dir, turn, text, "query_rejected",
            f"context-free classifier verdict {word or 'empty'!r}: the "
            "query looks like it finds a specific video, an analysis of "
            "it, or the answer to whether its motion is real or what "
            "gravity it shows; rephrase generically",
            {"stage": "classifier", "verdict": word or str(verdict)})
    if search_client is None:
        return _refuse(
            run_dir, turn, text, "search_unavailable",
            "no web-search backend is wired for this run",
            {"stage": "search", "verdict": "no"})
    try:
        data = search_client(text)
    except Exception as exc:  # noqa: BLE001 — search death is a tool error
        _log_decision(run_dir, {"turn": int(turn), "query": text,
                                "allowed": True, "stage": "search",
                                "verdict": "no",
                                "error": f"{type(exc).__name__}: {exc}"})
        return err_result("search_failed",
                          f"{type(exc).__name__}: {exc}",
                          metrics={"query": text, "allowed": True,
                                   "stage": "search"})
    items = []
    if isinstance(data, dict):
        raw = data.get("facts", data.get("answer", []))
        if isinstance(raw, list):
            items = raw
    facts = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        facts.append({
            "text": str(entry.get("text", "")),
            "url": str(entry.get("source_url", "")
                       or entry.get("url", "")),
            "quote": str(entry.get("quote", "")),
        })
    if ledger is not None:
        try:
            ledger.debit_search(int(turn))
        except (TypeError, ValueError):
            pass
    facts_rel = next_artifact(run_dir, turn, "web_search", ".json")
    facts_path = run_path(run_dir, facts_rel)
    facts_path.parent.mkdir(parents=True, exist_ok=True)
    facts_path.write_text(
        json.dumps({"query": text, "facts": facts}, indent=2) + "\n",
        encoding="utf-8")
    append_produced(run_dir, [facts_rel])
    _log_decision(run_dir, {"turn": int(turn), "query": text,
                            "allowed": True, "stage": "search",
                            "verdict": "no", "fact_count": len(facts)})
    head = "; ".join(f["text"][:120] for f in facts[:3])
    return ok_result(
        f"{len(facts)} sourced fact(s) for {text!r}"
        + (f": {head}" if head else ""),
        files=[facts_rel],
        metrics={"query": text, "allowed": True,
                 "classifier_verdict": "no",
                 "facts": facts,
                 "fact_count": len(facts),
                 "facts_artifact": facts_rel})

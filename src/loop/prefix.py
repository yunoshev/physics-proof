# generated from brief/06 · part 06 owns this file
"""Stable prompt prefix: system prompt, tool schemas, rules, helper docs.

Everything here is assembled once per run and never changes mid-run, so
the API's prompt caching works (part 06 §1). :func:`build_prefix` reads
``prompts/measuring_rules.md`` and ``src/helpers/HELPERS_DOCS.md`` from
disk and concatenates them deterministically; two calls in one run return
byte-identical text.

The loop never hints at a preferred tool sequence beyond the tool
descriptions and the measuring rules. The prompt plans the finish instead
(part 06 addendum 2026-10-28, sixth live run): dry-run by half the turns,
re-dry-run after each fix, real submit after a clean dry run.
"""

from __future__ import annotations

from pathlib import Path

from src.tools.schemas import TOOL_SCHEMAS

__all__ = [
    "TOOL_SCHEMAS",
    "SYSTEM_PROMPT",
    "INITIAL_TASK",
    "HELPER_HEADING",
    "EXAMPLE_HEADING",
    "OWN_CLIP_LINE",
    "build_prefix",
    "helper_module_names",
    "initial_task",
    "system_prompt",
]


#: Heading under which the helper docs are appended verbatim
#: (part 06 addendum 2026-10-28, Moon run 12 / wall run 3).
HELPER_HEADING = (
    "HELPER LIBRARY (import as helpers.<module> inside run_python):"
)

#: Heading for the two shape-only evidence examples (part 06 addendum
#: 2026-10-30, wall run 7): the Moon example (a gravity segment) and
#: the still-range fixture's evidence (range checks only, no segment).
EXAMPLE_HEADING = "EVIDENCE EXAMPLES (shape only — never copy values):"

#: The line every prefix carries after the examples: names, values and
#: sources must come from the agent's own clip and searches. Part 11
#: rejects an evidence that still carries an example's reference name
#: or value as ``EXAMPLE_VALUE_COPIED``.
OWN_CLIP_LINE = (
    "Every name, value and source in your evidence comes from your own "
    "clip and your own searches; an evidence that still carries an "
    "example's reference name or value is rejected."
)

#: The two example evidences, read verbatim from disk (part 12 §§14,
#: 22): the Moon example shipped with the evidence schema, and the
#: still-range fixture's evidence.
MOON_EXAMPLE_REL = "src/contract/evidence.example.json"
STILL_EXAMPLE_REL = "fixtures/still-range/evidence.json"

#: Evidence field each check kind maps to (part 06 addendum
#: 2026-10-30, wall run 7): gravity → a segment, range → one
#: ``range_checks`` item, clock → ``clock``.
KIND_EVIDENCE_FIELD = {
    "gravity": "segments",
    "range": "range_checks",
    "clock": "clock",
}

#: When to survey the trajectories first (part 06 addendum 2026-11-01,
#: part 08 R-M6, R-M7, R-S11, R-S12): one short paragraph. Segmenting
#: the moving body and running the overview is method, not a tool
#: order — the paragraph names the rules that already require it.
MOTION_PARAGRAPH = (
    "MOTION SURVEY (R-M6, R-M7, R-S11, R-S12): before measuring a "
    "motion check, segment the moving body over the whole clip in one "
    "call, run motion_overview on it, look at the chart and strips, "
    "decide every candidate, measure the free flights (one first, the "
    "others as confirmations), measure references close before the "
    "first flight on short segments."
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def system_prompt() -> str:
    """The stable system prompt (no tool order, no budget watching)."""
    return "\n".join([
        "You are analysing an anonymised video clip to test whether its",
        "motion obeys physics. You work turn by turn: look at frames,",
        "segment objects, measure with sandboxed Python, check masks, look",
        "up generic facts, and hand in structured evidence with submit.",
        "",
        "What you decide is up to you — which frames to view, what to",
        "segment, what to measure, in which order. The tool descriptions",
        "and the measuring rules below are the only guidance on method.",
        "",
        "The verdict is not yours to write. You submit structured evidence",
        "(measurements, segments, references, world exclusions, clock",
        "readings, provenance pointers) and deterministic code computes the",
        "verdict and the display sentence from it. Never phrase anything to",
        "match an expected sentence: no check compares your prose to a",
        "required string. Rejections come back as structured error codes",
        "with field names; fix the named fields.",
        "",
        "Plan the finish from the start. As soon as you have a track and a",
        "scale, write your evidence file and run submit with dry_run (aim",
        "for half the turns). Dry-run again after each fix, and make the",
        "real submit after a clean dry run. Submit with evidence_path",
        "(part 07): write workspace/evidence.json with run_python and pass",
        "its path, so the measured arrays are handed in byte for byte.",
        "",
        "Budget numbers you see are informational copies of the run",
        "ledger. When a notice asks you to finish and submit, do that.",
    ]) + "\n"


#: The stable system prompt, built once at import.
SYSTEM_PROMPT = system_prompt()


def _tool_lines() -> list:
    lines = ["TOOLS (call exactly one per tool call):"]
    for entry in TOOL_SCHEMAS:
        lines.append(f"## {entry['name']}")
        lines.append(str(entry.get("description", "")).strip())
        params = entry.get("parameters", {}) or {}
        props = params.get("properties", {}) or {}
        required = set(params.get("required", []) or [])
        for name, spec in props.items():
            kind = spec.get("type", "object")
            if isinstance(kind, list):
                kind = "/".join(str(k) for k in kind)
            flag = "required" if name in required else "optional"
            desc = str(spec.get("description", "") or "").strip()
            line = f"- `{name}` ({kind}, {flag})"
            if desc:
                line += f": {desc}"
            lines.append(line)
    return lines


def initial_task(wonder: dict | None = None,
                 card: dict | None = None) -> str:
    """The first user message: what to do, where things live.

    With a Wonder plan, the task quotes ``wonder.json`` verbatim and
    names it the plan (part 06 addendum 2026-10-29): the agent
    measures its checks, and ``first_look.question`` is Wonder's
    question. Without a plan the task is the same minus the plan
    block. With a clip card (part 06 addendum 2026-11-04), the task
    quotes each object with its masks artifact and object id, each
    candidate flight, the contacts, and the camera's movement. Either
    way the text is fixed for the run.
    """
    import json as _json

    from src.loop.card import card_task_lines  # noqa: PLC0415 — quote

    lines = [
        "Analyse the clip in input/ (video plus input/timing.json with",
        "measured frame timestamps). The helper library is documented",
        "above; do not read its source — import it inside run_python as",
        "`from helpers import masks_io` (also tracks, physics, clock).",
        "Write scratch files under workspace/; every tool names the files",
        "it produced under artifacts/. When you have measured the plan's",
        "checks, write workspace/evidence.json and submit it with dry_run,",
        "aiming for half the turns; dry-run again after each fix, then",
        "submit for real with evidence_path after a clean dry run.",
        "Dry-run early: submit a first evidence with dry_run",
        "by one third of the budget, even incomplete; its errors and push",
        "codes tell you what is still missing, and you need the remaining",
        "time to add it.",
        "Build every range check with the library: load the measured",
        "thing's mask, take each extent with `ranges.mask_extent`, the",
        "value and σ with `ranges.range_value`, and print the whole item",
        "with `ranges.print_check` in one run_python. That run_python is",
        "the check's `measurement_artifact`. Copy the printed item into",
        "the evidence unchanged, then add `range` from your search.",
        "Build `clock` with `clock.clock_evidence` and copy it unchanged.",
        "A range bound's `quote` is copied character for character from",
        "the `web_search` fact that gave it.",
        "Never dry-run a placeholder; dry-run what you have measured, even if it is only one check.",
        "From your first measured check on, keep workspace/evidence.json current after every measurement; the loop submits that file when time runs out.",
        "Before a range check goes into a dry run, check its lines with check_line(frame, lines) on the frame you measured; re-measure any line the second look does not confirm.",
    ]
    if isinstance(wonder, dict) and wonder:
        question = str(wonder.get("question", "") or "").strip()
        lines += [
            "",
            "This is your plan. Measure these checks; you may change a",
            "check, but say why in first_look.summary.",
        ]
        if question:
            lines.append(f"first_look.question: {question}")
        for check in (wonder.get("checks") or []):
            if not isinstance(check, dict):
                continue
            what = str(check.get("what", "") or "").strip()
            kind = str(check.get("kind", "") or "").strip()
            field = KIND_EVIDENCE_FIELD.get(kind, "evidence")
            if what and kind:
                lines.append(
                    f'- "{what}" (kind {kind}) becomes evidence `{field}`.')
            elif what:
                lines.append(f'- "{what}" becomes evidence `{field}`.')
        lines += [
            "Evidence mapping: every `gravity` check becomes a segment;",
            "every `range` check becomes one `range_checks` item with its",
            "value, sigma, extents and a sourced range; a `clock` check",
            "becomes `clock`; an evidence that has range checks and no",
            "segment is valid.",
            "Plan (artifacts/wonder.json):",
            _json.dumps(wonder, indent=2, sort_keys=True,
                        ensure_ascii=True),
        ]
    lines += card_task_lines(card)
    return "\n".join(lines) + "\n"


#: The first user message, fixed for the run.
INITIAL_TASK = initial_task()


def helper_module_names(helpers_docs: str | None = None) -> tuple:
    """Public helper module names: the ``## `` headings of the docs."""
    text = helpers_docs
    if text is None:
        text = _read_text(_repo_root() / "src" / "helpers"
                          / "HELPERS_DOCS.md")
    names: list = []
    for line in text.splitlines():
        if line.startswith("## "):
            name = line[3:].strip().split()[0]
            if name and name not in names:
                names.append(name)
    return tuple(names)


def _example_block(label: str, rel: str) -> str:
    """One labelled verbatim example (shape only, never values)."""
    text = _read_text(_repo_root() / rel).strip()
    if not text:
        return ""
    return f"{label}\n```json\n{text}\n```\n"


def build_prefix(measuring_rules: str | None = None,
                 helpers_docs: str | None = None) -> str:
    """Assemble the stable prefix (byte-identical across turns)."""
    root = _repo_root()
    rules = (measuring_rules if measuring_rules is not None
             else _read_text(root / "prompts" / "measuring_rules.md"))
    docs = (helpers_docs if helpers_docs is not None
            else _read_text(root / "src" / "helpers" / "HELPERS_DOCS.md"))
    parts = [SYSTEM_PROMPT]
    parts.append("\n".join(_tool_lines()) + "\n")
    if rules.strip():
        parts.append("MEASURING RULES (code checks are authoritative):\n"
                     + rules.strip() + "\n")
    parts.append(MOTION_PARAGRAPH + "\n")
    if docs.strip():
        parts.append(HELPER_HEADING + "\n" + docs.strip() + "\n")
    moon = _example_block(
        "Example A (shape only — a gravity segment):", MOON_EXAMPLE_REL)
    still = _example_block(
        "Example B (shape only — range checks only, no segment):",
        STILL_EXAMPLE_REL)
    examples = "\n".join(block for block in
                         (EXAMPLE_HEADING, moon.strip(), still.strip(),
                          OWN_CLIP_LINE) if block)
    if examples.strip():
        parts.append(examples + "\n")
    return "\n".join(part.strip() for part in parts if part.strip()) + "\n"

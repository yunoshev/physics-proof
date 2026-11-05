# generated from brief/06 · part 06 owns this file
"""Describe, then Wonder, then measure (part 06 addendum 2026-10-29).

Before turn 1, one Spark call describes the clip and a second one asks
what in it is worth proving and how. The measuring loop then starts
from that plan as its initial task.

- Describe input: contact sheets of the whole clip at a spacing of at
  most half a second, built by the same code the loop runs for
  ``view_frames`` (part 07), plus the clip facts (duration, fps, size).
  Output JSON goes to ``artifacts/describe.json``.
- Wonder input: Describe's JSON and the same sheets. Output JSON goes
  to ``artifacts/wonder.json``.
- Both calls ride the run's ledger (dollar and wall-clock budgets, not
  turns). A call that fails or returns invalid JSON is retried once; a
  second failure skips the plan and the loop starts as before, with the
  reason recorded under ``logs/``.
- Blindness: both calls see only frames and clip facts, never the file
  name; the request carries no run identity either.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from src import config as _config
from src.accounting import classify_terminal
from src.loop.dispatch import validate_args
from src.loop.render import image_files

__all__ = [
    "CHECK_KINDS",
    "CHECK_REQUIRED",
    "DESCRIBE_FILENAME",
    "DESCRIBE_REQUIRED",
    "DONATED_AGENT_TURN",
    "WONDER_FILENAME",
    "WONDER_REQUIRED",
    "_PREPLAN_SYSTEM",
    "clip_facts",
    "describe_prompt",
    "extract_json",
    "run_preplan",
    "sheet_indices",
    "validate_describe",
    "validate_wonder",
    "wonder_prompt",
]

#: Artifact names for the two pre-loop calls (part 06 addendum).
DESCRIBE_FILENAME = "artifacts/describe.json"
WONDER_FILENAME = "artifacts/wonder.json"

#: Required top-level keys of each call's JSON answer.
DESCRIBE_REQUIRED = ("what_happens", "scene", "things", "on_screen_text")
WONDER_REQUIRED = ("claim", "question", "world", "checks",
                   "realistic_if", "not_realistic_if")

#: Check objects name what to look up in generic terms only.
CHECK_REQUIRED = ("what", "why", "how", "compare_with", "kind")

#: The three kinds of check the loop can measure (part 06 addendum
#: 2026-10-30, wall run 7): a gravity check becomes a segment, a
#: range check becomes a ``range_checks`` item, a clock check becomes
#: ``clock``.
CHECK_KINDS = ("gravity", "range", "clock")

#: Sheet spacing: the whole clip at no more than this many seconds
#: between sampled frames.
SHEET_SPACING_S = 0.5


def sheet_indices(frame_count: int, fps: float) -> list:
    """Frame indices covering the whole clip at ≤ 0.5 s spacing."""
    try:
        count = int(frame_count)
    except (TypeError, ValueError):
        return []
    if count <= 0:
        return []
    try:
        rate = float(fps)
    except (TypeError, ValueError):
        rate = 0.0
    step = 1
    if rate > 0:
        step = max(1, int(math.floor(SHEET_SPACING_S * rate)))
    indices = list(range(0, count, step))
    if indices and indices[-1] != count - 1:
        indices.append(count - 1)
    return indices


def clip_facts(run_dir) -> dict:
    """Numbers only: duration, fps, frame count, file size.

    Never the file name (blindness): the request carries these four
    numbers and the sheet images, nothing else.
    """
    from src.tools.timing import find_clip, load_timing  # noqa: PLC0415
    facts = load_timing(run_dir)
    stamps = facts["timestamps"]
    rate = float(facts["measured_fps"])
    count = int(facts["frame_count"])
    if len(stamps) >= 2:
        duration = float(stamps[-1]) - float(stamps[0])
    elif rate > 0:
        duration = count / rate
    else:
        raise ValueError("timing report gives no usable duration")
    clip = find_clip(run_dir)
    size = int(clip.stat().st_size)
    if size <= 0:
        raise ValueError("clip file is empty")
    return {"duration_s": float(duration), "fps": float(rate),
            "frame_count": count, "bytes": size}


def describe_prompt(facts: dict) -> str:
    """The Describe instruction: JSON only, fixed keys, no guessing."""
    return "\n".join([
        "You are given contact sheets covering a whole anonymised video",
        "clip (frames in time order, with per-frame times) plus measured",
        "clip facts. Describe only what is visible in the frames.",
        "Reply with ONLY a JSON object with exactly these keys:",
        '- "what_happens": an array of 3 to 6 strings, in time order,',
        "  each naming the clip time in seconds it describes;",
        '- "scene": where the scene is and which world the frames show,',
        "  naming the frame that shows it;",
        '- "things": the people, animals and objects visible, with what',
        "  can be identified about them (model, event, place);",
        '- "moving_things": an array of up to 4 short noun phrases, each',
        "  a thing that moves in the clip (a person, an animal, a",
        "  vehicle, a ball) that the masks step can segment, the most",
        "  important first;",
        '- "on_screen_text": any text visible in the frames, verbatim,',
        "  or an empty string when there is none.",
        "Name only what the frames show; never name the clip, its source",
        "file, or any suspected answer.",
        "Clip facts: "
        f"duration_s={float(facts['duration_s']):.3f}, "
        f"fps={float(facts['fps']):.3f}, "
        f"frame_count={int(facts['frame_count'])}, "
        f"bytes={int(facts['bytes'])}.",
    ]) + "\n"


def wonder_prompt(describe: dict, card: dict | None = None) -> str:
    """The Wonder instruction: a measurable plan, JSON only.

    With a clip card, its JSON follows the description and a check
    whose ``how`` relies on a contact names a contact range the card
    lists.
    """
    lines = [
        "You are given the same contact sheets plus a JSON description",
        "of what an anonymised video clip shows (below). Ask what in it",
        "is worth proving and how. Reply with ONLY a JSON object with",
        "exactly these keys:",
        '- "claim": what the clip shows or says that a viewer might doubt;',
        '- "question": the viewer\'s question, in plain words;',
        '- "world": the scene\'s world;',
        '- "checks": an array of one to three objects, each with "kind"',
        '  (one of "gravity", "range" or "clock", naming which of the',
        '  three checks below this item is), "what" (the quantity to',
        '  measure), "why" (how it answers the question), "how" (what to',
        "  measure in which frames, against which object of known size)",
        '  and "compare_with" (the real-world value or range to look up:',
        "  the world's gravity, records, body norms, a product's",
        "  published size);",
        '  A "gravity" check measures a body moving with nothing holding',
        "  it up, which must accelerate downward at the world's g.",
        '  A "range" check compares a measured size, ratio, speed, height',
        "  or duration with a sourced real-world range.",
        '  A "clock" check reads a periodic motion with a known natural',
        "  rate to show whether the clip plays at real speed.",
        "  Include at least one check of the kind that would settle the",
        "  question;",
        '- "realistic_if" and "not_realistic_if": one sentence each.',
        "Name only generic lookup targets (a gravity value, body norms, a",
        "published size); never name the clip, its source, or any",
        "suspected answer.",
        "Description:",
        json.dumps(describe, indent=2, sort_keys=True, ensure_ascii=True),
    ]
    if isinstance(card, dict) and card.get("objects"):
        lines += [
            "Clip card (masks already measured from the clip; reuse the",
            "artifacts it names instead of re-segmenting these objects):",
            json.dumps(card, indent=2, sort_keys=True, ensure_ascii=True,
                       default=str),
            "A check whose `how` relies on a contact names a contact",
            "range the card lists.",
        ]
    return "\n".join(lines) + "\n"


def extract_json(text: str, required) -> dict | None:
    """First JSON object in ``text`` holding every required key."""
    if not isinstance(text, str) or not text.strip():
        return None
    decoder = json.JSONDecoder()
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and all(k in parsed for k in required):
        return parsed
    for match in re.finditer(r"\{", text):
        try:
            parsed, _ = decoder.raw_decode(text[match.start():])
        except ValueError:
            continue
        if isinstance(parsed, dict) and all(k in parsed
                                            for k in required):
            return parsed
    return None


def validate_describe(obj) -> bool:
    """Shape check for a Describe answer (keys present, usable)."""
    if not isinstance(obj, dict):
        return False
    if any(key not in obj for key in DESCRIBE_REQUIRED):
        return False
    happenings = obj.get("what_happens")
    if isinstance(happenings, str):
        happenings = [happenings]
    if (not isinstance(happenings, list) or not happenings
            or not all(isinstance(item, str) and item.strip()
                       for item in happenings)):
        return False
    return True


def validate_wonder(obj) -> bool:
    """Shape check for a Wonder answer (keys plus 1–3 full checks)."""
    if not isinstance(obj, dict):
        return False
    if any(key not in obj for key in WONDER_REQUIRED):
        return False
    if (not isinstance(obj.get("question"), str)
            or not obj["question"].strip()):
        return False
    checks = obj.get("checks")
    if (not isinstance(checks, list) or not 1 <= len(checks) <= 3):
        return False
    for check in checks:
        if not isinstance(check, dict):
            return False
        if any(key not in check for key in CHECK_REQUIRED):
            return False
        if (not isinstance(check.get("what"), str)
                or not check["what"].strip()):
            return False
        if str(check.get("kind")) not in CHECK_KINDS:
            return False
    return True


#: System line for both pre-loop calls. It carries no run identity,
#: no file name and no clip identity (blindness): the model sees only
#: frames and clip facts. A system message keeps the prompt stable and
#: puts the request's instructions where the agent client expects them.
_PREPLAN_SYSTEM = ("You describe anonymised footage and ask what in it "
                   "is worth proving. Reply with JSON only.")

#: Marker for a pre-loop reply that arrived shaped like an agent turn
#: (it carries tool calls). Older harnesses serve agent turns first;
#: the loop donates that reply to turn 1 instead of discarding it, so
#: the shared queue stays aligned. See :func:`run_preplan`.
DONATED_AGENT_TURN = "donated-agent-turn"


def _spark_request(text: str, sheets: list) -> dict:
    """One context-free agent-shaped request: text plus sheet images."""
    content: list = [{"type": "text", "text": str(text)}]
    for rel in sheets or []:
        content.append({"type": "image", "artifact": str(rel)})
    return {"model": str(_config.SPARK_MODEL),
            "messages": [{"role": "system",
                          "content": [{"type": "text",
                                       "text": _PREPLAN_SYSTEM}]},
                         {"role": "user", "content": content}],
            "max_output_tokens": int(_config.MAX_OUTPUT_TOKENS),
            "reasoning_effort": str(_config.SPARK_REASONING_EFFORT)}


def _donated_response(response) -> dict | None:
    """The agent-turn reply to donate to turn 1 (or ``None``).

    A pre-loop reply carrying tool calls was never a plan answer: these
    calls run with no tools by construction. Rather than discard it and
    misalign a shared queue behind it, the loop reuses it as turn 1.
    """
    if not isinstance(response, dict):
        return None
    calls = response.get("tool_calls")
    if isinstance(calls, list) and calls:
        return response
    return None


def _request_hash(request: dict) -> str:
    try:
        canonical = json.dumps(request, sort_keys=True, ensure_ascii=True,
                               default=str)
    except (TypeError, ValueError):
        canonical = str(request)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _loop_log_path(run_dir) -> Path:
    return (Path(str(run_dir)) / str(_config.LOGS_DIR_NAME)
            / "loop.jsonl")


def _log_attempt(run_dir, phase: str, attempt: int, request: dict,
                 terminal, ok: bool, error: str, ledger) -> None:
    """One replayable ``logs/`` entry per pre-loop attempt (turn 0)."""
    try:
        record = ledger.ledger_record()
    except (TypeError, ValueError, AttributeError):
        record = {}
    try:
        preplan_effort = str(request.get("reasoning_effort")
                             or _config.SPARK_REASONING_EFFORT)
    except (TypeError, ValueError, AttributeError):
        preplan_effort = str(_config.SPARK_REASONING_EFFORT)
    entry = {"turn": 0, "phase": str(phase), "attempt": int(attempt),
             "prompt_hash": _request_hash(request),
             "spark_terminal": terminal,
             "reasoning_effort": preplan_effort, "tool_calls": [],
             "ok": bool(ok), "error": str(error or ""),
             "ledger": record}
    try:
        path = _loop_log_path(run_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True,
                                    default=str) + "\n")
    except OSError:
        pass


def _write_skipped(run_dir, reason: str, phase: str = "") -> None:
    """Record why the run starts without a plan (operator-only)."""
    try:
        path = (Path(str(run_dir)) / str(_config.LOGS_DIR_NAME)
                / "preplan.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"status": "skipped",
                                    "phase": str(phase or "describe"),
                                    "reason": str(reason),
                                    "describe_artifact": DESCRIBE_FILENAME,
                                    "wonder_artifact": WONDER_FILENAME},
                                   indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    except OSError:
        pass


def _attempt_call(phase: str, text: str, sheets: list, required,
                is_valid, run_dir, spark_client, ledger, attempt: int):
    """One attempt of one pre-loop call.

    Returns ``(obj, "", None)`` on a valid plan answer, ``(None, why,
    None)`` on a retryable failure, and ``(None, DONATED_AGENT_TURN,
    response)`` when the reply arrived shaped like an agent turn (it
    carries tool calls): these calls run with no tools by construction,
    so the reply is donated to turn 1 instead of being discarded.
    Every attempt is debited to the ledger with turn 0 — dollar and
    wall-clock budgets, never turns.
    """
    request = _spark_request(text, sheets)
    response = None
    try:
        response = spark_client(request)
    except Exception as exc:  # noqa: BLE001 — any failure retries once
        _log_attempt(run_dir, phase, attempt, request, None, False,
                     f"{type(exc).__name__}: {exc}", ledger)
        return None, f"spark call failed: {type(exc).__name__}", None
    terminal = response.get("terminal") if isinstance(response, dict) \
        else None
    usage = response.get("usage") if isinstance(response, dict) else None
    try:
        ledger.debit_terminal_event(0, {"type": terminal, "usage": usage})
    except (TypeError, ValueError, AttributeError):
        pass
    donated = _donated_response(response)
    if donated is not None:
        _log_attempt(run_dir, phase, attempt, request, terminal, False,
                     "served an agent turn; donated to turn 1", ledger)
        return None, DONATED_AGENT_TURN, donated
    kind = classify_terminal(terminal)
    answer = ""
    if isinstance(response, dict):
        answer = response.get("text", "") or ""
    if kind == "completed" and isinstance(answer, str) and answer.strip():
        obj = extract_json(answer, required)
        if obj is not None and is_valid(obj):
            _log_attempt(run_dir, phase, attempt, request, terminal, True,
                         "", ledger)
            return obj, "", None
        _log_attempt(run_dir, phase, attempt, request, terminal, False,
                     "invalid JSON", ledger)
        return None, "invalid JSON", None
    detail = ""
    if isinstance(response, dict) and response.get("error"):
        detail = f": {str(response['error'])[:200]}"
    _log_attempt(run_dir, phase, attempt, request, terminal, False,
                 f"spark terminal {terminal!r}{detail}", ledger)
    return None, f"spark terminal {terminal!r}{detail}", None


def _call_with_retry(phase: str, text: str, sheets: list, required,
                     is_valid, run_dir, spark_client, ledger):
    """One pre-loop call with exactly one retry (two attempts total).

    Returns ``(obj, "", None)`` on success, ``(None, why, None)`` after
    two failures, or ``(None, DONATED_AGENT_TURN, response)`` at once
    when the reply arrived shaped like an agent turn (no retry: a
    second attempt would only consume the turn behind it).
    """
    why = ""
    for attempt in (1, 2):
        obj, why, donated = _attempt_call(
            phase, text, sheets, required, is_valid, run_dir,
            spark_client, ledger, attempt)
        if donated is not None:
            return None, why, donated
        if obj is not None:
            return obj, "", None
    return None, why, None


def run_preplan(run_dir, run_id, spark_client, ledger,
                elapsed_s: float = 0.0, sam_client=None,
                segment_cache=None) -> tuple:
    """Describe, then the clip card, then Wonder, before turn 1.

    Returns ``(wonder_or_None, donated_or_None, card_or_None)``.
    ``wonder`` is the plan for the initial task (or ``None`` when the
    loop starts as before); ``card`` is the clip card quoted beside it
    (or ``None`` when there is nothing to quote). ``donated`` is an
    agent-turn-shaped reply served to a pre-loop call (it carries tool
    calls): the caller reuses it as turn 1 instead of spending another
    call, so a shared queue behind it stays aligned.

    Sheets come from the same ``view_frames`` code the loop runs, and
    only proceed when the call succeeds with sheet image files that
    exist on disk. Each call is retried once; a second failure skips
    the plan and the loop starts as before. The card step runs no
    Spark call: it segments Describe's moving things over the whole
    clip and measures contacts and the camera from masks.
    """
    if not callable(spark_client):
        return None, None, None
    try:
        spent = float(ledger.total_cost_usd)
    except (TypeError, ValueError, AttributeError):
        spent = 0.0
    try:
        capped = (spent >= float(_config.HARD_CAP_COST_USD)
                  or float(elapsed_s) >= float(_config.HARD_CAP_WALL_S))
    except (TypeError, ValueError):
        capped = False
    if capped:
        _write_skipped(run_dir, "budget already exhausted", "describe")
        return None, None, None
    try:
        facts = clip_facts(run_dir)
    except Exception as exc:  # noqa: BLE001 — no facts, no plan
        _write_skipped(run_dir, f"no clip facts: {type(exc).__name__}",
                       "describe")
        return None, None, None
    indices = sheet_indices(facts["frame_count"], facts["fps"])
    if not indices:
        _write_skipped(run_dir, "no sheet frames", "describe")
        return None, None, None
    expected = None
    try:
        from src.tools.schemas import (  # noqa: PLC0415 — single source
            EXPECTED_PARAMS,
        )
        expected = EXPECTED_PARAMS.get("view_frames")
    except Exception:  # noqa: BLE001 — fall back to validating anyway
        expected = None
    arguments = {key: None for key in (expected or ())}
    arguments["frame_indices"] = list(indices)
    clean, fault = validate_args("view_frames", arguments)
    if fault is not None:
        _write_skipped(run_dir, "sheet arguments rejected", "describe")
        return None, None, None
    try:
        from src.tools.view_frames import (  # noqa: PLC0415 — same code
            view_frames,
        )
        result = view_frames(run_dir, 0, **clean)
    except Exception as exc:  # noqa: BLE001 — sheets failed, skip plan
        _write_skipped(run_dir,
                       f"sheets failed: {type(exc).__name__}", "describe")
        return None, None, None
    if not isinstance(result, dict) or not result.get("ok"):
        _write_skipped(run_dir, "sheets failed", "describe")
        return None, None, None
    base = Path(str(run_dir))
    sheets = [name for name in image_files(result.get("files"))
              if (base / str(name)).is_file()]
    if not sheets:
        _write_skipped(run_dir, "no sheet images", "describe")
        return None, None, None
    describe, why, donated = _call_with_retry(
        "describe", describe_prompt(facts), sheets, DESCRIBE_REQUIRED,
        validate_describe, run_dir, spark_client, ledger)
    if donated is not None:
        _write_skipped(run_dir,
                       f"describe served an agent turn: {why}", "describe")
        return None, donated, None
    if describe is None:
        _write_skipped(run_dir, f"describe failed twice: {why}",
                       "describe")
        return None, None, None
    try:
        (base / DESCRIBE_FILENAME).write_text(
            json.dumps(describe, indent=2, sort_keys=True,
                       ensure_ascii=True) + "\n", encoding="utf-8")
    except OSError as exc:
        _write_skipped(run_dir, f"describe artifact failed: {exc}",
                       "describe")
        return None, None, None
    from src.loop.card import run_card  # noqa: PLC0415 — card step
    card = run_card(str(run_dir), describe, sam_client=sam_client,
                    ledger=ledger,
                    segment_cache=(segment_cache
                                   if isinstance(segment_cache, dict)
                                   else {}))
    charts: list = []
    if isinstance(card, dict):
        for entry in card.get("objects") or []:
            rel = entry.get("chart_artifact") if isinstance(entry, dict) \
                else None
            if isinstance(rel, str) and rel and (
                    base / rel).is_file() and rel not in charts:
                charts.append(rel)
    wonder, why, donated = _call_with_retry(
        "wonder", wonder_prompt(describe, card), sheets + charts,
        WONDER_REQUIRED, validate_wonder, run_dir, spark_client, ledger)
    if donated is not None:
        _write_skipped(run_dir,
                       f"wonder served an agent turn: {why}", "wonder")
        return None, donated, card
    if wonder is None:
        _write_skipped(run_dir, f"wonder failed twice: {why}", "wonder")
        return None, None, card
    try:
        (base / WONDER_FILENAME).write_text(
            json.dumps(wonder, indent=2, sort_keys=True,
                       ensure_ascii=True) + "\n", encoding="utf-8")
    except OSError as exc:
        _write_skipped(run_dir, f"wonder artifact failed: {exc}", "wonder")
        return None, None, card
    return wonder, None, card

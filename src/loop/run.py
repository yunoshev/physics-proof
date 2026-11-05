# generated from brief/06 · part 06 owns this file
"""The Spark agent loop: one Spark call plus tool dispatch per turn.

A turn is one agent call followed by zero or more tool calls, executed
by our code, whose results are appended for the next turn. The loop runs
until submit is accepted, a budget is exhausted, or an unrecoverable
error lands in the synthesis path (part 06 §§1, 5, 6).

Budgets live in the frame, not the prompt: the ledger
(:mod:`src.accounting`) counts turns, wall seconds, tokens, SAM frames,
searches, mask checks, execs and dollars, and this module enforces the
caps from :mod:`src.config`. The agent only ever sees informational
copies (the budget line) and steering notices.

Injection interface (part 04 §6)::

    run_loop(run_dir, run_id,
             spark_client=..., blind_spark_client=..., classifier=...,
             sam_client=..., search_client=..., validator=...,
             ledger=..., sleep=..., clock=...)

``spark_client`` is ``(request) -> response`` with ``request``
``{"model", "messages", "max_output_tokens"}`` (the
:class:`src.loop.history.History` snapshot) and ``response``
``{"terminal", "text", "tool_calls", "usage"}``. Every other callable
goes straight to the part-07 tool that owns it. ``clock`` is a
seconds-returning callable (tests inject a fake clock); ``sleep`` is
the backoff sleeper.
"""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from src import config as _config
from src.accounting import Ledger, backoff_delay_s, should_retry_network

from src.loop.budgets import (
    EXPLORATION_TOOLS,
    FINISHING_TURNS,
    MAX_EFFORT_FIRST_TURNS,
    ROUTINE_EFFORT,
    dollars_spent,
    exploration_closed,
    finishing_notice,
    first_over,
    halfway_notice,
    run_ratios,
    turns_left,
    wall_left_s,
)
from src.loop.dispatch import (
    EXPECTED_PARAMS,
    TRANSIENT_EXCEPTIONS,
    CatastrophicToolError,
    validate_args,
)
from src.loop.history import History
from src.loop.plan import (
    PLACEHOLDER_REFUSAL,
    evidence_has_measurement,
    plan_progress_line,
    resolve_submit_evidence,
)
from src.loop.prefix import build_prefix, initial_task
from src.loop.preplan import run_preplan
from src.loop.render import image_files, render_tool_result

__all__ = [
    "EXPLORATION_CLOSED_LINE",
    "FINISHING_CLOSED_LINE",
    "IMAGE_REFUSED_PLACEHOLDER",
    "MAX_EFFORT_FIRST_TURNS",
    "MAX_SUBMIT_ATTEMPTS",
    "REPEAT_CLOSED_LINE",
    "REPEAT_NOTICE",
    "ROUTINE_EFFORT",
    "SPARK_REFUSED_REASON",
    "budget_line",
    "reasoning_effort_for_turn",
    "run_loop",
]

#: Real (non-dry-run) submit rejections before the run ends as
#: undetermined with the last error list recorded (part 06 §2).
MAX_SUBMIT_ATTEMPTS = 3

#: Consecutive identical failures before the notice rides along.
REPEAT_NOTICE_AFTER = 3
#: Consecutive identical failures before the tool is closed for the run.
REPEAT_CLOSE_AFTER = 5

#: Steering notice appended to a repeatedly failing tool's result.
REPEAT_NOTICE = (
    "notice: this tool keeps failing in this run; stop calling it, "
    "and use the other tools or submit with what you have "
    "(an undetermined answer is acceptable)"
)

REPEAT_CLOSED_LINE = (
    "closed for this run after repeated failures: use the other tools "
    "or submit with what you have (an undetermined answer is acceptable)"
)

#: Exploration closing answer (part 06 addendum 2026-10-28, run 12/3).
EXPLORATION_CLOSED_LINE = (
    "closed until your first dry run: write workspace/evidence.json "
    "and submit it with dry_run"
)

#: Finishing-phase answer (part 06 addendum 2026-10-29, run 13/4).
FINISHING_CLOSED_LINE = (
    "finishing phase: fix the errors of your last dry run with "
    "run_python and submit; dry-run first if you have not"
)

#: Push codes count as clean at the cap (part 11 §16, part 06 addendum
#: 2026-10-28, run 10 / wall run).
try:
    from src.validate import PUSH_CODES as _PUSH_CODES
except Exception:  # noqa: BLE001 — pinned fallback, never fatal
    _PUSH_CODES = ("SECOND_REFERENCE_REQUIRED", "CLOCK_REQUIRED",
                   "MOTIONS_SCAN_MISSING")

#: A real submit carrying only push codes is held back while every
#: run-level budget is under this fraction used (part 06 addendum
#: 2026-11-02: no early real submit while pushes remain). From half
#: of any run-level budget the submit is accepted as before.
EARLY_SUBMIT_RATIO = 0.5

#: Text replacing image blocks when the model service refused the
#: request with images (part 06 addendum 2026-11-03, sped-up run
#: 20261102T222230Z).
IMAGE_REFUSED_PLACEHOLDER = (
    "(image omitted: the model service refused the request with this "
    "image)"
)

#: Synthesis reason when the agent call fails three times in a row
#: (part 06 addendum 2026-11-03, part 14 §5).
SPARK_REFUSED_REASON = "the model service refused the request"

#: Consecutive ``response.failed`` agent calls before the next request
#: goes out with the newest turn's images replaced by
#: :data:`IMAGE_REFUSED_PLACEHOLDER`.
FAILED_STRIP_AFTER = 2

#: Consecutive ``response.failed`` agent calls before the run ends
#: through synthesis.
MAX_CONSECUTIVE_FAILED = 3

#: The API's error payload is logged cut to this many characters.
SPARK_ERROR_CAP = 2000


def budget_line(turn: int, ledger, elapsed_s: float,
                last_dry: dict | None = None) -> str:
    """The informational budget line ending every tool result (§5)."""
    try:
        max_turns = int(_config.MAX_TURNS)
    except (TypeError, ValueError):
        max_turns = 90
    left = turns_left(ledger)
    mins = wall_left_s(elapsed_s) / 60.0
    spent = dollars_spent(ledger)
    try:
        cap = float(_config.HARD_CAP_COST_USD)
    except (TypeError, ValueError):
        cap = 2.00
    try:
        sam = int(ledger.sam_frames_billed)
    except (TypeError, ValueError, AttributeError):
        sam = 0
    try:
        max_sam = int(_config.MAX_SAM_FRAMES)
    except (TypeError, ValueError):
        max_sam = 1500
    try:
        searches = int(ledger.searches)
    except (TypeError, ValueError, AttributeError):
        searches = 0
    try:
        max_searches = int(_config.MAX_SEARCHES)
    except (TypeError, ValueError):
        max_searches = 6
    try:
        masks = int(ledger.mask_checks)
    except (TypeError, ValueError, AttributeError):
        masks = 0
    try:
        max_masks = int(_config.MAX_MASK_CHECKS)
    except (TypeError, ValueError):
        max_masks = 4
    line = (f"turn {int(turn)}/{max_turns} · {left} turns left · "
            f"{mins:.1f} min left · ${spent:.3f} of ${cap:.2f} · "
            f"SAM {sam}/{max_sam} frames · searches "
            f"{searches}/{max_searches} · mask checks {masks}/{max_masks}")
    if isinstance(last_dry, dict) and last_dry.get("turn"):
        errors = last_dry.get("errors") or []
        if last_dry.get("clean"):
            line += f" · last dry run: clean (turn {last_dry['turn']})"
        else:
            line += (f" · last dry run: {len(errors)} errors "
                     f"(turn {last_dry['turn']})")
    return line


def reasoning_effort_for_turn(turn: int, state: _State) -> str:
    """The ``reasoning_effort`` for this turn's agent request (§ 2026-11-04).

    ``SPARK_REASONING_EFFORT`` (part 04's ``"max"``) on the first
    :data:`MAX_EFFORT_FIRST_TURNS` turns; on a turn whose new input
    holds a ``submit`` result (a dry run's errors, a refusal or an
    early hold); and on a turn whose new input holds a loop notice
    (half-way, 80 %, exploration closed, finishing, a closed tool).
    :data:`ROUTINE_EFFORT` on every other turn.
    """
    try:
        first_turns = int(MAX_EFFORT_FIRST_TURNS)
    except (TypeError, ValueError):
        first_turns = 20
    try:
        current = int(turn)
    except (TypeError, ValueError):
        current = first_turns + 1
    if current <= first_turns:
        return str(_config.SPARK_REASONING_EFFORT)
    try:
        if bool(getattr(state, "submit_pending", False)):
            return str(_config.SPARK_REASONING_EFFORT)
    except (TypeError, ValueError, AttributeError):
        pass
    try:
        if bool(getattr(state, "notice_pending", False)):
            return str(_config.SPARK_REASONING_EFFORT)
    except (TypeError, ValueError, AttributeError):
        pass
    return str(ROUTINE_EFFORT)


def _status_suffix(turn: int, ledger, elapsed_s: float, state: _State,
                   run_dir) -> str:
    """Every turn's status: the budget line plus the plan's progress.

    The plan line follows the budget line only when the run has a
    Wonder plan; otherwise the status is the budget line alone. The
    evidence file is re-read for every tool result and never edited
    (part 06 addendum 2026-10-31, hand run 7 / wall run 12).
    """
    suffix = budget_line(turn, ledger, elapsed_s, state.last_dry)
    plan = plan_progress_line(state.wonder, run_dir)
    if plan:
        suffix += "\n" + plan
    return suffix


class _State:
    """Mutable per-run loop state (never shared across runs, §6)."""

    def __init__(self) -> None:
        self.has_submitted = False
        self.wonder: dict | None = None
        self.card: dict | None = None
        self.closed_sent: set = set()
        self.real_attempts = 0
        self.last_errors: list = []
        self.last_dry: dict | None = None
        self.halfway_budget: str | None = None
        self.finishing = False
        self.finishing_budget = ""
        self.finishing_start: int | None = None
        self.repeat_closed: set = set()
        self.fail_streak: dict = {}
        self.identical: list = []
        self.notices: list = []
        self.seg_cache: dict = {}
        self.catastrophic = None
        self.failed_streak: int = 0
        self.last_spark_error: str = ""
        self.last_spark_code: str = ""
        self.newest_tool_span = None
        self.submit_pending = False
        self.notice_pending = False


def _ensure_layout(run_dir) -> None:
    base = Path(str(run_dir))
    for name in (_config.INPUT_DIR_NAME, _config.WORKSPACE_DIR_NAME,
                 _config.ARTIFACTS_DIR_NAME, _config.LOGS_DIR_NAME):
        try:
            (base / str(name)).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass


def _append_log(run_dir, entry: dict) -> None:
    try:
        path = (Path(str(run_dir)) / str(_config.LOGS_DIR_NAME)
                / "loop.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True,
                                    default=str) + "\n")
    except OSError:
        pass


def _per_tool_closure(tool: str, ledger) -> str | None:
    """One-line closing for an exhausted or nearly spent tool budget."""
    try:
        warn = float(_config.WARN_RATIO)
    except (TypeError, ValueError):
        warn = 0.80
    try:
        dollars_ratio = (dollars_spent(ledger)
                         / float(_config.HARD_CAP_COST_USD))
    except (TypeError, ValueError, ZeroDivisionError):
        dollars_ratio = 0.0

    def _line(budget: str, used, cap: int, spent_word: str) -> str:
        return (f"{tool} is closed for this run: the {budget} budget is "
                f"{spent_word} ({used} of {cap} used); use the other "
                "tools or submit with what you have")

    if tool == "segment":
        try:
            billed = int(ledger.sam_frames_billed)
        except (TypeError, ValueError, AttributeError):
            billed = 0
        try:
            cap = int(_config.MAX_SAM_FRAMES)
        except (TypeError, ValueError):
            cap = 1500
        if billed >= cap:
            return _line("SAM", billed, cap, "spent")
        if cap > 0 and (billed / cap >= warn or dollars_ratio >= warn):
            return _line("SAM", billed, cap, "nearly spent")
    elif tool == "check_mask":
        try:
            used = int(ledger.mask_checks)
        except (TypeError, ValueError, AttributeError):
            used = 0
        try:
            cap = int(_config.MAX_MASK_CHECKS)
        except (TypeError, ValueError):
            cap = 4
        if used >= cap:
            return _line("mask-check", used, cap, "spent")
        if cap > 0 and (used / cap >= warn or dollars_ratio >= warn):
            return _line("mask-check", used, cap, "nearly spent")
    elif tool == "web_search":
        try:
            used = int(ledger.searches)
        except (TypeError, ValueError, AttributeError):
            used = 0
        try:
            cap = int(_config.MAX_SEARCHES)
        except (TypeError, ValueError):
            cap = 6
        if used >= cap:
            return _line("search", used, cap, "spent")
        if cap > 0 and (used / cap >= warn or dollars_ratio >= warn):
            return _line("search", used, cap, "nearly spent")
    return None


def _tool_closed(tool: str, state: _State, ledger, turn: int,
                 elapsed_s: float = 0.0) -> str | None:
    """Why ``tool`` must not run now (``None`` when it may run).

    Exploration closes once the first run-level budget reaches one
    third with no submit yet (part 06 addendum 2026-10-29, Moon run
    15); the first submit reopens it. The finishing phase (80 %) closes
    the same tools for the rest of the run.
    """
    if tool in state.repeat_closed:
        return f"{tool} is {REPEAT_CLOSED_LINE}"
    if state.finishing and tool in EXPLORATION_TOOLS:
        return FINISHING_CLOSED_LINE
    if tool in EXPLORATION_TOOLS and exploration_closed(
            turn, elapsed_s, dollars_spent(ledger),
            state.has_submitted):
        return EXPLORATION_CLOSED_LINE
    return _per_tool_closure(tool, ledger)


def _dry_clean(errors) -> bool:
    """A dry run counts as clean with no errors or only push codes."""
    items = [e for e in (errors or []) if isinstance(e, dict)]
    if not items:
        return True
    push = set(_PUSH_CODES or ())
    return bool(push) and all(str(e.get("code")) in push for e in items)


def _is_push_error(error) -> bool:
    """Whether one validator error item is a push code, not a hard error.

    A push-code item carries ``"push": True`` (part 11 §§25–26); a
    tightened refusal carries ``"push": False`` and stays a hard error
    even though its code is a push code (part 11 §44).
    """
    if not isinstance(error, dict):
        return False
    if error.get("push") is False:
        return False
    if error.get("push") is True:
        return True
    return str(error.get("code", "") or "") in set(_PUSH_CODES or ())


def _run_budgets_under_half(turns_used: int, elapsed_s: float,
                            dollars: float) -> bool:
    """Whether every run-level budget is under half used (§ 2026-11-02).

    Turns, wall time and dollars must all be under
    :data:`EARLY_SUBMIT_RATIO`; from half of any one of them an early
    real submit with pushes is accepted as before.
    """
    ratios = run_ratios(turns_used, elapsed_s, dollars)
    for key in ("turns", "wall", "dollars"):
        try:
            if float(ratios.get(key, 0.0)) >= EARLY_SUBMIT_RATIO:
                return False
        except (TypeError, ValueError):
            continue
    return True


def _early_holdback_line(turn: int, elapsed_s: float) -> str:
    """First line of a held-back early submit's dry-run reply."""
    try:
        max_turns = int(_config.MAX_TURNS)
    except (TypeError, ValueError):
        max_turns = 90
    try:
        cap_min = int(float(_config.HARD_CAP_WALL_S) // 60)
    except (TypeError, ValueError):
        cap_min = 30
    try:
        used_min = int(float(elapsed_s) // 60)
    except (TypeError, ValueError):
        used_min = 0
    return (f"Time remains ({int(turn)} of {max_turns} turns, "
            f"{used_min} of {cap_min} min used): the pushes below can "
            "still change the result. Work on them, then submit again.")


def _bump_dry_run_count(run_dir) -> int:
    """Count a held-back submit against the dry-run budget.

    The held-back call went through the submit tool as a real submit,
    so the tool's own dry-run counter did not move; the loop moves it
    here so the hold-back counts as the dry run the reply claims it
    is. Same file and shape the submit tool reads.
    """
    try:
        path = (Path(str(run_dir)) / str(_config.LOGS_DIR_NAME)
                / "dry_runs.json")
    except (TypeError, ValueError):
        return 0
    count = 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            count = max(0, int(raw.get("dry_runs", 0)))
    except (OSError, ValueError, TypeError):
        count = 0
    count += 1
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"dry_runs": count}) + "\n",
                        encoding="utf-8")
    except OSError:
        pass
    return count


def _maybe_hold_early_submit(result: dict, clean: dict, state: _State,
                             turn: int, run_dir, ledger,
                             elapsed_s: float):
    """Hold back an early real submit rejected with only push codes.

    Returns the rewritten dry-run reply (and records it as a dry run)
    when a real submit was rejected with push codes and no hard errors
    while every run-level budget is under half used; otherwise ``None``
    and the submit follows the normal accepted/rejected path (part 06
    addendum 2026-11-02). A held-back submit never consumes a real
    attempt.
    """
    if not isinstance(result, dict) or not isinstance(clean, dict):
        return None
    if bool(clean.get("dry_run", False)):
        return None
    metrics = result.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    # Only a rejected submit can carry pushes: the submit tool reports
    # an acceptance with an empty error list, so there is nothing to
    # hold back on (and its result is already written).
    if bool(metrics.get("accepted", bool(result.get("ok", False)))):
        return None
    errors = [e for e in (metrics.get("errors") or [])
              if isinstance(e, dict)]
    pushes = [e for e in errors if _is_push_error(e)]
    hard = [e for e in errors if not _is_push_error(e)]
    if not pushes or hard:
        return None
    try:
        turns_used = int(ledger.turns)
    except (TypeError, ValueError, AttributeError):
        turns_used = int(turn)
    if not _run_budgets_under_half(turns_used, elapsed_s,
                                   dollars_spent(ledger)):
        return None
    state.last_dry = {"turn": int(turn), "errors": list(errors),
                      "clean": True,
                      "evidence": _retain_evidence(run_dir, clean)}
    _bump_dry_run_count(run_dir)
    lines = [_early_holdback_line(turn, elapsed_s)]
    for error in pushes:
        lines.append(f"{error.get('code', 'error')} "
                     f"{error.get('field', '?')}: "
                     f"{error.get('detail', '')}")
    held_metrics = dict(metrics)
    held_metrics["dry_run"] = True
    held_metrics["held_back_early_submit"] = True
    held = dict(result)
    held["summary"] = "\n".join(lines)
    held["metrics"] = held_metrics
    # The render head quotes the error detail, so point it at the new
    # first line: the agent must not see the stale real-submit framing.
    held["error"] = {"code": "submit_rejected", "detail": lines[0]}
    return held


def _extra_dry_pushes(run_dir, clean: dict, clients: dict) -> list | None:
    """Push-only errors from validating the same evidence as a dry run.

    Part 06 addendum 2026-11-02 (second): a real submit never returns
    push codes (part 11 turns them into an undetermined verdict), so the
    loop cannot see pushes in the real reply. Before accepting an early
    real submit it validates the same evidence as a dry run and holds
    the submit back when that dry run gives push codes and no errors.
    Returns the push list when the dry run is pushes-only, else
    ``None`` (clean, hard errors, unusable evidence or a validator
    fault all let the real submit go on as usual). Never writes files
    and never touches the dry-run counter; only a hold counts as a dry
    run.
    """
    if not isinstance(clean, dict):
        return None
    evidence = _retain_evidence(run_dir, clean)
    if not isinstance(evidence, dict):
        return None
    try:
        from src.tools.submit import (
            _call_validator as _call_v,
        )
        from src.tools.submit import (
            _default_validator as _default_v,
        )
        from src.tools.submit import (
            collect_run_context as _collect_ctx,
        )
    except Exception:  # noqa: BLE001 — fall through to the real submit
        return None
    check = None
    try:
        check = clients.get("validator") if isinstance(clients, dict) else None
    except (AttributeError, TypeError):
        check = None
    if check is None:
        check = _default_v
    try:
        run_context = _collect_ctx(run_dir)
    except Exception:  # noqa: BLE001 — context never blocks the probe
        run_context = {"run_dir": str(run_dir)}
    try:
        report = _call_v(check, copy.deepcopy(evidence), run_context,
                         dry_run=True)
    except Exception:  # noqa: BLE001 — a fault lets the real submit run
        return None
    if not isinstance(report, dict):
        return None
    if bool(report.get("accepted")):
        return None
    errors = [e for e in (report.get("errors") or [])
              if isinstance(e, dict)]
    if not errors:
        return None
    pushes = [e for e in errors if _is_push_error(e)]
    hard = [e for e in errors if not _is_push_error(e)]
    if pushes and not hard:
        return pushes
    return None


def _held_from_dry_pushes(pushes: list, clean: dict, state: _State,
                           turn: int, run_dir, ledger,
                           elapsed_s: float) -> dict:
    """Held-back reply built from the extra dry run's push list."""
    evidence = _retain_evidence(run_dir, clean)
    state.last_dry = {"turn": int(turn), "errors": list(pushes),
                      "clean": True, "evidence": evidence}
    _bump_dry_run_count(run_dir)
    lines = [_early_holdback_line(turn, elapsed_s)]
    for error in pushes:
        lines.append(f"{error.get('code', 'error')} "
                     f"{error.get('field', '?')}: "
                     f"{error.get('detail', '')}")
    return {
        "ok": False,
        "summary": "\n".join(lines),
        "files": [],
        "metrics": {"accepted": False, "errors": list(pushes),
                    "dry_run": True, "held_back_early_submit": True},
        "error": {"code": "submit_rejected", "detail": lines[0]},
    }


def _refuse_placeholder(run_dir, name: str, clean: dict) -> bool:
    """Whether this dry-run submit is a placeholder to refuse.

    Only dry runs are refused: without calling the validator and
    without counting as a dry run, the run goes on (part 06 addendum
    2026-10-31, hand run 7 / wall run 12). An evidence that cannot be
    loaded into a dict here is not a placeholder — the submit tool's
    own argument errors still handle that path.
    """
    if name != "submit" or not bool(clean.get("dry_run")):
        return False
    loaded = resolve_submit_evidence(run_dir, clean)
    return loaded is not None and not evidence_has_measurement(loaded)


def _identical_key(tool: str, arguments: dict) -> tuple:
    """Canonical identity of one call for identical-call flagging."""
    try:
        canonical = json.dumps(arguments, sort_keys=True,
                               ensure_ascii=True, default=str)
    except (TypeError, ValueError):
        canonical = str(arguments)
    return (str(tool), canonical)


def _track_failure(state: _State, tool: str, result: dict):
    """Update the consecutive-identical-failure streak (non-submit).

    A failure counts only when code **and** detail match the tool's
    previous failure (addendum 2026-10-28, fifth live run). Returns
    the streak length, or ``None`` when the result is not a failure.
    """
    key = _failure_key(result)
    if key is None:
        state.fail_streak.pop(str(tool), None)
        return None
    prev = state.fail_streak.get(str(tool))
    streak = prev["count"] + 1 if prev and prev["key"] == key else 1
    state.fail_streak[str(tool)] = {"key": key, "count": streak}
    return streak


def _handle_submit(result: dict, clean: dict, state: _State, turn: int,
                   run_dir) -> tuple:
    """Book-keep one submit result.

    Returns ``("accepted", (result_path, result))``,
    ``("spent", errors)`` after the last real attempt, or
    ``("continue", None)``. Dry runs never consume an attempt but are
    recorded (with retained evidence) for the budget-line suffix and
    the at-cap last resort.
    """
    metrics = result.get("metrics") if isinstance(result, dict) else None
    metrics = metrics if isinstance(metrics, dict) else {}
    dry = bool(metrics.get("dry_run", bool(clean.get("dry_run", False))))
    accepted = bool(metrics.get("accepted", bool(result.get("ok", False))))
    errors = metrics.get("errors") or []
    errors = [e for e in errors if isinstance(e, dict)]
    if dry:
        state.last_dry = {"turn": int(turn), "errors": list(errors),
                          "clean": bool(accepted or _dry_clean(errors)),
                          "evidence": _retain_evidence(run_dir, clean)}
        return ("continue", None)
    state.real_attempts = int(state.real_attempts) + 1
    if accepted:
        return ("accepted", (metrics.get("result_path"),
                             metrics.get("result")))
    state.last_errors = list(errors)
    if int(state.real_attempts) >= MAX_SUBMIT_ATTEMPTS:
        return ("spent", list(errors))
    return ("continue", None)


def _retain_evidence(run_dir, arguments):
    """Deep copy of dry-run evidence for a last-resort cap submit."""
    if not isinstance(arguments, dict):
        return None
    if isinstance(arguments.get("evidence"), dict):
        return copy.deepcopy(arguments["evidence"])
    if isinstance(arguments.get("evidence"), str):
        try:
            parsed = json.loads(arguments["evidence"])
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


def _invoke(tool: str, arguments: dict, run_dir, turn: int,
            clients: dict, ledger) -> dict:
    """Call one part-07 tool with its injected clients (may raise)."""
    if tool == "view_frames":
        from src.tools.view_frames import view_frames
        return view_frames(run_dir, turn, **arguments)
    if tool == "segment":
        from src.tools.segment import segment
        return segment(run_dir, turn, **arguments,
                       sam_client=clients.get("sam_client"),
                       ledger=ledger,
                       cache=clients.get("segment_cache"))
    if tool == "check_mask":
        from src.tools.check_mask import check_mask
        return check_mask(run_dir, turn, **arguments,
                          spark_client=clients.get("blind_spark_client"),
                          ledger=ledger)
    if tool == "check_line":
        from src.tools.check_line import check_line
        return check_line(run_dir, turn, **arguments,
                          spark_client=clients.get("blind_spark_client"),
                          classifier=clients.get("classifier"),
                          ledger=ledger)
    if tool == "web_search":
        from src.tools.web_search import web_search
        return web_search(run_dir, turn, **arguments,
                          search_client=clients.get("search_client"),
                          classifier=clients.get("classifier"),
                          ledger=ledger)
    if tool == "run_python":
        from src.tools.run_python import run_python
        return run_python(run_dir, turn, **arguments, ledger=ledger)
    if tool == "motion_overview":
        from src.tools.motion_overview import motion_overview
        return motion_overview(run_dir, turn, **arguments)
    if tool == "submit":
        from src.tools.submit import submit
        return submit(run_dir, turn,
                      evidence=arguments.get("evidence"),
                      evidence_path=arguments.get("evidence_path"),
                      dry_run=bool(arguments.get("dry_run", False)),
                      validator=clients.get("validator"))
    raise AssertionError(f"validated tool has no handler: {tool!r}")


def _failure_key(result: dict) -> tuple | None:
    """``(code, detail)`` of a failed result (``None`` when ok)."""
    if not isinstance(result, dict) or result.get("ok"):
        return None
    error = result.get("error") or {}
    if not isinstance(error, dict):
        return None
    return (str(error.get("code", "")), str(error.get("detail", "")))


def _spark_error(response) -> str:
    """The API's error payload for the operator log row.

    The terminal event carries the ``error`` object (or the HTTP
    status and body, depending on the client); only that value is
    logged — never a header or a key — cut to :data:`SPARK_ERROR_CAP`
    characters (part 06 addendum 2026-11-03).
    """
    error = response.get("error") if isinstance(response, dict) else None
    if isinstance(error, dict):
        try:
            text = json.dumps(error, ensure_ascii=True, default=str)
        except (TypeError, ValueError):
            text = str(error)
    elif error is None:
        terminal = (response.get("terminal")
                    if isinstance(response, dict) else "")
        text = str(terminal or "response.failed")
    else:
        text = str(error)
    return text[:SPARK_ERROR_CAP]


def _spark_error_code(response, spark_error: str) -> str:
    """The short code of the last failure for the synthesis detail."""
    error = response.get("error") if isinstance(response, dict) else None
    if isinstance(error, dict) and error.get("code"):
        return str(error.get("code"))[:200]
    return spark_error


def _strip_newest_images(request: dict, span) -> bool:
    """Replace the newest turn's image blocks with placeholder text.

    ``span`` is the ``(start, end)`` slice of ``request["messages"]``
    holding the most recent turn's tool outputs. Every ``image`` block
    there becomes :data:`IMAGE_REFUSED_PLACEHOLDER` text; older turns
    and non-image content are untouched. Returns whether any block
    was replaced (part 06 addendum 2026-11-03).
    """
    if span is None:
        return False
    try:
        start, end = span
    except (TypeError, ValueError):
        return False
    messages = request.get("messages") if isinstance(request, dict) else None
    if not isinstance(messages, list):
        return False
    stripped = False
    for message in messages[int(start):int(end)]:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "tool":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for index, block in enumerate(content):
            if (isinstance(block, dict)
                    and block.get("type") == "image"):
                content[index] = {"type": "text",
                                  "text": IMAGE_REFUSED_PLACEHOLDER}
                stripped = True
    return stripped


def _identical_turn(state: _State, tool: str, arguments: dict) -> tuple:
    """``(first_turn, count)`` of identical earlier calls in this run."""
    try:
        canonical = json.dumps(arguments, sort_keys=True,
                               ensure_ascii=True, default=str)
    except (TypeError, ValueError):
        canonical = str(arguments)
    key = (str(tool), canonical)
    prior = [turn for key_, turn in state.identical if key_ == key]
    return (prior[0] if prior else None, len(prior))


def _write_completed_summary(run_dir, ledger, result_path: str) -> str:
    """Write the ``completed`` summary; the loop's submitted path."""
    try:
        summary = ledger.write_summary(result_path, "completed",
                                       run_dir=str(run_dir))
        path = Path(str(run_dir)) / str(_config.SUMMARY_FILENAME)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True)
                        + "\n", encoding="utf-8")
        return str(path)
    except Exception:  # noqa: BLE001 — files, not traces
        from src.loop.synthesis import (  # noqa: PLC0415
            _safe_write_summary,
        )
        return _safe_write_summary(ledger, str(run_dir), result_path,
                                   "completed")


def _synthesise(run_dir, run_id: str, ledger, reason: str, detail: str = "",
                errors=None) -> dict:
    """Every unsubmitted ending funnels through the loop's synthesis."""
    from src.loop.synthesis import (  # noqa: PLC0415 — single writer
        synthesize_undetermined as _syn,
    )
    return _syn(str(run_dir), str(run_id), str(reason),
                detail=str(detail or ""), ledger=ledger, errors=errors)


def _note_cap_provenance(run_dir, report: dict) -> None:
    """Record the at-cap clean-dry-run submit in result provenance."""
    try:
        metrics = report.get("metrics") or {}
        result_path = metrics.get("result_path")
        if not result_path:
            return
        result = json.loads(Path(str(result_path)).read_text(
            encoding="utf-8"))
        provenance = result.get("provenance")
        if not isinstance(provenance, dict):
            return
        artifacts = provenance.get("artifacts")
        if not isinstance(artifacts, list):
            return
        note_path = (metrics.get("errors_artifact")
                     or metrics.get("evidence_artifact")
                     or "logs/loop.jsonl")
        artifacts.append({
            "name": ("submitted at the budget limit from the last "
                     "clean dry run"),
            "produced_by": "submit",
            "path": str(note_path),
        })
        from src.contract import validate_result  # noqa: PLC0415
        if validate_result(result) != []:
            return
        Path(str(result_path)).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    except (OSError, ValueError, TypeError):
        pass


def _call_spark(spark_client, request, turn: int, ledger, sleep) -> dict:
    """One agent call with transport retries (never for other classes)."""
    from src.accounting import NetworkError, classify_terminal
    attempt = 0
    while True:
        attempt += 1
        try:
            response = spark_client(request)
        except TRANSIENT_EXCEPTIONS as exc:
            ledger.record_attempt(turn, "spark",
                                  detail=f"{type(exc).__name__}: {exc}",
                                  attempt=attempt)
            if not should_retry_network(attempt):
                raise
            sleep(backoff_delay_s(attempt))
            continue
        if not isinstance(response, dict):
            ledger.record_attempt(turn, "spark",
                                  detail="spark returned no structured "
                                  "response",
                                  attempt=attempt)
            if not should_retry_network(attempt):
                raise NetworkError("spark returned no structured "
                                   "response")
            sleep(backoff_delay_s(attempt))
            continue
        if classify_terminal(response.get("terminal")) == "network":
            ledger.record_attempt(turn, "spark",
                                  detail="no terminal event",
                                  attempt=attempt)
            if not should_retry_network(attempt):
                raise NetworkError("spark response had no terminal "
                                   "event")
            sleep(backoff_delay_s(attempt))
            continue
        return response


def run_loop(run_dir, run_id=None, *, spark_client=None,
             blind_spark_client=None, classifier=None, sam_client=None,
             search_client=None, validator=None, ledger=None, sleep=None,
             clock=None) -> dict:
    """Run the agent loop to submit, budget exhaustion or synthesis.

    A ``response.failed`` agent call is logged with its API error
    payload (``spark_error``) and the agent may adapt; after two in a
    row the next request goes out with the newest turn's images
    replaced by placeholder text, and a third ends the run through
    synthesis with ``the model service refused the request`` (part 06
    addendum 2026-11-03, part 14 §§4–5).
    """
    from src.accounting import NetworkError, classify_terminal
    _ensure_layout(run_dir)
    rid = str(run_id) if run_id is not None else Path(str(run_dir)).name
    if ledger is None:
        ledger = Ledger(run_id=rid or "run", run_dir=str(run_dir))
    sleep_fn = sleep if callable(sleep) else time.sleep
    clock_fn = clock if callable(clock) else time.time
    try:
        t0 = float(clock_fn())
    except (TypeError, ValueError):
        t0 = time.time()
        clock_fn = time.time
    try:
        max_turns = int(_config.MAX_TURNS)
    except (TypeError, ValueError):
        max_turns = 90
    try:
        hard_wall = float(_config.HARD_CAP_WALL_S)
    except (TypeError, ValueError):
        hard_wall = 2700.0
    try:
        hard_cap = float(_config.HARD_CAP_COST_USD)
    except (TypeError, ValueError):
        hard_cap = 2.00
    try:
        warn_ratio = float(_config.WARN_RATIO)
    except (TypeError, ValueError):
        warn_ratio = 0.80

    prefix = build_prefix()
    try:
        (Path(str(run_dir)) / str(_config.LOGS_DIR_NAME)
         / "prefix.txt").write_text(prefix, encoding="utf-8")
    except OSError:
        pass
    def _elapsed() -> float:
        try:
            return max(0.0, float(clock_fn()) - t0)
        except (TypeError, ValueError):
            return 0.0

    # Describe, then the clip card, then Wonder, then measure (part 06
    # addendum 2026-10-29 and the 2026-11-04 card addendum): the plan
    # calls run before turn 1 and never consume a turn. A donated
    # reply (an agent-turn-shaped answer served to a pre-loop call) is
    # reused as turn 1 without spending another call, so a shared
    # queue behind it stays aligned.
    state = _State()
    clients = {"blind_spark_client": blind_spark_client,
               "classifier": classifier,
               "sam_client": sam_client,
               "search_client": search_client,
               "validator": validator,
               "segment_cache": state.seg_cache}
    wonder, donated, card = run_preplan(
        str(run_dir), rid, spark_client, ledger, _elapsed(),
        sam_client=clients.get("sam_client"),
        segment_cache=clients.get("segment_cache"))
    pending_donated = donated if isinstance(donated, dict) else None
    history = History()
    history.append_system(prefix)
    history.append_user(initial_task(
        wonder, card if isinstance(card, dict) else None))
    state.wonder = wonder if isinstance(wonder, dict) else None
    state.card = card if isinstance(card, dict) else None

    def _cap_stop(detail: str) -> dict:
        last = state.last_dry
        if (isinstance(last, dict) and last.get("clean")
                and isinstance(last.get("evidence"), dict)):
            try:
                from src.tools.submit import submit as _submit
                res = _submit(str(run_dir), int(ledger.turns) or 1,
                              evidence=copy.deepcopy(last["evidence"]),
                              dry_run=False, validator=validator)
            except Exception:  # noqa: BLE001 — fall through to budget
                res = None
            if isinstance(res, dict):
                metrics = res.get("metrics") or {}
                if bool(metrics.get("accepted", res.get("ok"))):
                    result_path = metrics.get("result_path")
                    result = metrics.get("result")
                    if not result_path and isinstance(result, dict):
                        try:
                            from src.validate.synthesis import write_result
                            result_path = write_result(str(run_dir),
                                                       result)
                        except OSError:
                            result_path = None
                    if result_path:
                        _note_cap_provenance(str(run_dir), res)
                        summary_path = _write_completed_summary(
                            str(run_dir), ledger, result_path)
                        return {"status": "submitted",
                                "reason": ("budget limit reached; "
                                           "submitted from the last clean "
                                           "dry run"),
                                "turns": int(ledger.turns or 0),
                                "result_path": result_path,
                                "summary_path": summary_path}
        return _synthesise(str(run_dir), rid, ledger, "budget",
                           detail=detail)

    def _submitted(result_path: str | None, result) -> dict:
        if not result_path and isinstance(result, dict):
            try:
                from src.validate.synthesis import write_result
                result_path = write_result(str(run_dir), result)
            except OSError:
                result_path = str(Path(str(run_dir)) / "result.json")
        summary_path = _write_completed_summary(
            str(run_dir), ledger, result_path or "result.json")
        return {"status": "submitted", "reason": "",
                "turns": int(ledger.turns or 0),
                "result_path": result_path or "result.json",
                "summary_path": summary_path}

    def _finish_submit() -> dict:
        """The loop finishes the run (part 06 addendum 2026-10-30).

        After the fourth finishing turn (or a spent run-level budget,
        via :func:`_cap_stop`), the loop submits
        ``workspace/evidence.json`` itself, for real, when the file
        exists and parses. The validator's answer decides: accepted
        ends submitted; rejected ends through part 11's synthesis with
        kind ``not finished``. With no evidence file at all the run
        ends ``undetermined: budget`` like any other budget stop.
        """
        rel = "workspace/evidence.json"
        try:
            raw = (Path(str(run_dir)) / rel).read_text(encoding="utf-8")
        except OSError:
            return _synthesise(
                str(run_dir), rid, ledger, "budget",
                detail="finishing phase ended with no evidence file")
        try:
            parsed = json.loads(raw)
        except ValueError:
            return _synthesise(
                str(run_dir), rid, ledger, "budget",
                detail="finishing phase ended with no evidence file")
        if not isinstance(parsed, dict):
            return _synthesise(
                str(run_dir), rid, ledger, "budget",
                detail="finishing phase ended with no evidence file")
        try:
            from src.tools.submit import submit as _submit
            res = _submit(str(run_dir), int(ledger.turns) or 1,
                          evidence_path=rel, dry_run=False,
                          validator=validator)
        except Exception:  # noqa: BLE001 — fall through to budget
            res = None
        if isinstance(res, dict):
            metrics = res.get("metrics") or {}
            if bool(metrics.get("accepted", res.get("ok"))):
                return _submitted(metrics.get("result_path"),
                                  metrics.get("result"))
            errors = [e for e in (metrics.get("errors") or [])
                      if isinstance(e, dict)]
            if errors:
                _append_log(str(run_dir),
                            {"turn": int(ledger.turns or 0),
                             "prompt_hash": "loop-submit",
                             "spark_terminal": "loop-submit",
                             "reasoning_effort": str(
                                 _config.SPARK_REASONING_EFFORT),
                             "tool_calls": [{"name": "submit",
                                             "submit_kind": "loop"}],
                             "ledger": ledger.ledger_record()})
                return _synthesise(str(run_dir), rid, ledger,
                                   "not finished",
                                   detail=("loop submit rejected at the "
                                           "finishing limit"),
                                   errors=errors)
        return _synthesise(
            str(run_dir), rid, ledger, "budget",
            detail="finishing phase ended with no evidence file")

    if spark_client is None or not callable(spark_client):
        return _synthesise(str(run_dir), rid, ledger,
                           "no model configured")

    while int(getattr(ledger, "turns", 0) or 0) < max_turns:
        turn = int(ledger.count_turn())
        elapsed = _elapsed()
        spent = dollars_spent(ledger)
        ratios = run_ratios(int(ledger.turns), elapsed, spent)
        if elapsed >= hard_wall:
            return _cap_stop(f"wall_time ≥ {int(hard_wall)}")
        if spent >= hard_cap:
            return _cap_stop(f"cost ≥ {hard_cap:.2f}")
        if (state.halfway_budget is None and not state.has_submitted):
            over = first_over(ratios, 0.5)
            if over is not None:
                state.halfway_budget = over
                notice = halfway_notice(over)
                history.append_user(f"system notice: {notice}")
                state.notices.append({"turn": turn, "kind": "halfway",
                                      "budget": over, "text": notice})
                state.notice_pending = True
        if not state.finishing:
            over80 = first_over(ratios, warn_ratio)
            if over80 is not None:
                state.finishing = True
                state.finishing_budget = over80
                state.finishing_start = turn
                notice = finishing_notice(over80, state.last_dry)
                history.append_user(f"system notice: {notice}")
                state.notices.append({"turn": turn, "kind": "finishing",
                                      "budget": over80, "text": notice})
                state.notice_pending = True
        elif (state.finishing_start is not None
                and turn - int(state.finishing_start) >= FINISHING_TURNS):
            return _finish_submit()
        if not state.finishing and not exploration_closed(
                turn, elapsed, spent, state.has_submitted):
            for tool_name in ("segment", "check_mask", "web_search"):
                # A closing line for a tool is sent once (part 06
                # addendum 2026-11-04, street-jump run 83): repeats of
                # the same line used to count as a loop notice every
                # turn, pinning every turn to max effort.
                if tool_name in state.closed_sent:
                    continue
                line = _per_tool_closure(tool_name, ledger)
                if line is not None:
                    history.append_user(f"system notice: {line}")
                    state.notices.append({"turn": turn,
                                          "kind": "per_tool_budget",
                                          "budget": tool_name,
                                          "text": line})
                    state.closed_sent.add(tool_name)
                    state.notice_pending = True
        prompt_hash = history.prompt_hash()
        # Part 06 addendum 2026-11-04: every agent request names its
        # reasoning effort — max where judgment is made, high for
        # routine turns. The flags are one-shot: they describe the new
        # input of this request and are consumed here, so the next
        # routine turn drops back to routine effort.
        effort = reasoning_effort_for_turn(turn, state)
        state.submit_pending = False
        state.notice_pending = False
        donated_response = None
        if pending_donated is not None:
            donated_response, pending_donated = pending_donated, None
        stripped_images = False
        if donated_response is not None:
            # Reused pre-loop reply: its usage was already debited to
            # turn 0, so it must not be debited again here.
            response = donated_response
        else:
            request = history.snapshot()
            # Part 06 §3: thinking counts toward the output limit, so
            # every agent call carries the named config value (never a
            # literal).
            request["max_output_tokens"] = int(_config.MAX_OUTPUT_TOKENS)
            # Part 06 addendum 2026-11-04: the request names its
            # reasoning effort (part 04 sends it to Spark).
            request["reasoning_effort"] = effort
            if state.failed_streak >= FAILED_STRIP_AFTER:
                # Two consecutive failures: retry once without the
                # newest turn's images (part 06 addendum 2026-11-03).
                stripped_images = _strip_newest_images(
                    request, state.newest_tool_span)
            try:
                response = _call_spark(spark_client, request, turn,
                                       ledger, sleep_fn)
            except TRANSIENT_EXCEPTIONS as exc:
                _append_log(str(run_dir),
                            {"turn": turn, "prompt_hash": prompt_hash,
                             "spark_terminal": "transport_exhausted",
                             "reasoning_effort": effort,
                             "error": f"{type(exc).__name__}: {exc}",
                             "ledger": ledger.ledger_record()})
                return _synthesise(str(run_dir), rid, ledger,
                                   "agent call failed",
                                   detail=f"{type(exc).__name__}")
        terminal = response.get("terminal")
        kind = classify_terminal(terminal)
        usage = response.get("usage") if isinstance(response, dict) else None
        if donated_response is None:
            try:
                ledger.debit_terminal_event(turn, {"type": terminal,
                                                   "usage": usage})
            except (TypeError, ValueError, AttributeError):
                pass
        if kind == "incomplete":
            notice = ("your last reply was cut off at the output limit "
                      "(incomplete): continue concisely from your last "
                      "tool state, or submit with what you have.")
            history.append_user(f"system notice: {notice}")
            _append_log(str(run_dir),
                        {"turn": turn, "prompt_hash": prompt_hash,
                         "spark_terminal": terminal,
                         "reasoning_effort": effort,
                         "incomplete_reason": response.get(
                             "incomplete_reason", ""),
                         "tool_calls": [],
                         "ledger": ledger.ledger_record()})
            continue
        if kind == "failed":
            spark_error = _spark_error(response)
            state.failed_streak = int(state.failed_streak) + 1
            state.last_spark_error = spark_error
            state.last_spark_code = _spark_error_code(response,
                                                      spark_error)
            row = {"turn": turn, "prompt_hash": prompt_hash,
                   "spark_terminal": terminal,
                   "reasoning_effort": effort,
                   "spark_error": spark_error,
                   "tool_calls": [],
                   "ledger": ledger.ledger_record()}
            if stripped_images:
                row["request_images_stripped"] = True
            if state.failed_streak >= MAX_CONSECUTIVE_FAILED:
                _append_log(str(run_dir), row)
                return _synthesise(
                    str(run_dir), rid, ledger, SPARK_REFUSED_REASON,
                    detail=state.last_spark_code)
            error = str(response.get("error", "") or terminal or kind)
            notice = (f"agent call failed ({error}); continue: call "
                      "exactly one tool next, or submit.")
            history.append_user(f"system notice: {notice}")
            _append_log(str(run_dir), row)
            continue
        if kind == "network":
            error = str(response.get("error", "") or terminal or kind)
            notice = (f"agent call failed ({error}); continue: call "
                      "exactly one tool next, or submit.")
            history.append_user(f"system notice: {notice}")
            _append_log(str(run_dir),
                        {"turn": turn, "prompt_hash": prompt_hash,
                         "spark_terminal": terminal,
                         "reasoning_effort": effort,
                         "tool_calls": [],
                         "ledger": ledger.ledger_record()})
            continue
        # The model answered: consecutive failures reset.
        state.failed_streak = 0
        state.last_spark_error = ""
        state.last_spark_code = ""
        text = response.get("text", "") or ""
        calls = response.get("tool_calls", "") or []
        calls = calls if isinstance(calls, list) else []
        history.append_assistant(text, [c for c in calls
                                        if isinstance(c, dict)])
        if not calls:
            nudge = ("no tool call was made: call exactly one tool "
                     "next, or submit.")
            history.append_user(f"system notice: {nudge}")
            _append_log(str(run_dir),
                        {"turn": turn, "prompt_hash": prompt_hash,
                         "spark_terminal": terminal,
                         "reasoning_effort": effort,
                         "tool_calls": [],
                         "ledger": ledger.ledger_record()})
            continue
        turn_records: list = []
        span_start = len(history.messages)
        for index, call in enumerate(calls):
            if not isinstance(call, dict):
                continue
            name = str(call.get("name", "") or "")
            call_id = str(call.get("call_id", "")
                          or f"call_t{turn}_{index}")
            arguments = call.get("arguments", {})
            record: dict = {"name": name, "call_id": call_id,
                            "arguments": arguments}
            closed = (_tool_closed(name, state, ledger, turn,
                                     _elapsed())
                      if name else "empty tool name: call exactly one "
                      "listed tool")
            if closed is not None:
                full = (closed + "\n"
                        + _status_suffix(turn, ledger, _elapsed(),
                                         state, str(run_dir)))
                history.append_tool(call_id, name or "unknown", full,
                                    [])
                record["closed"] = closed
                record["rendered"] = full
                turn_records.append(record)
                # A closed tool is a loop notice the first time it is
                # sent (part 06 addendum 2026-11-04): only the first
                # send counts for the reasoning effort, so the next
                # turn answers it with max effort and later turns drop
                # back to routine effort.
                if name and name not in state.closed_sent:
                    state.closed_sent.add(name)
                    state.notice_pending = True
                elif not name:
                    state.notice_pending = True
                continue
            clean, fault = validate_args(name, arguments)
            if fault is not None:
                body = render_tool_result(name, fault)
                full = (body + "\n"
                        + _status_suffix(turn, ledger, _elapsed(),
                                         state, str(run_dir)))
                history.append_tool(call_id, name, full, [])
                record["fault"] = fault
                record["rendered"] = full
                turn_records.append(record)
                _track_failure(state, name, fault)
                continue
            first_turn, prior = _identical_turn(state, name, clean)
            state.identical.append(
                (_identical_key(name, clean), turn))
            refused = _refuse_placeholder(str(run_dir), name, clean)
            if name == "submit" and not refused:
                state.has_submitted = True
            preheld = None
            if (name == "submit" and not refused
                    and not bool(clean.get("dry_run", False))):
                try:
                    _turns_used = int(ledger.turns)
                except (TypeError, ValueError, AttributeError):
                    _turns_used = int(turn)
                try:
                    _early = _run_budgets_under_half(
                        _turns_used, _elapsed(), dollars_spent(ledger))
                except (TypeError, ValueError, AttributeError):
                    _early = False
                if _early:
                    _pushes = _extra_dry_pushes(str(run_dir), clean,
                                                clients)
                    if _pushes is not None:
                        preheld = _held_from_dry_pushes(
                            _pushes, clean, state, turn, str(run_dir),
                            ledger, _elapsed())
            try:
                if preheld is not None:
                    result = preheld
                elif refused:
                    result = {"ok": False, "summary": PLACEHOLDER_REFUSAL,
                              "files": [], "metrics": {"dry_run": True,
                                                       "refused":
                                                       "placeholder"},
                              "error": {"code": "placeholder",
                                        "detail": PLACEHOLDER_REFUSAL}}
                else:
                    result = _invoke(name, clean, str(run_dir), turn,
                                     clients, ledger)
            except TypeError as exc:
                from src.tools.result import err_result
                result = err_result(
                    "bad_arguments",
                    f"{name}: argument error ({exc}); expected "
                    "parameters "
                    + ", ".join(EXPECTED_PARAMS.get(name, ())),
                    metrics={"tool": name})
            except Exception as exc:  # noqa: BLE001 — our bug
                state.catastrophic = CatastrophicToolError(name, exc)
                break
            if not isinstance(result, dict):
                result = {"ok": False, "summary": str(result),
                          "files": [], "metrics": {},
                          "error": {"code": "tool_malformed",
                                    "detail": "tool returned no "
                                    "structured result"}}
            if refused:
                record["refused"] = "placeholder"
            if name == "submit" and not refused:
                if preheld is not None:
                    record["submit_kind"] = "held_back"
                    kind = "held_back"
                else:
                    held = _maybe_hold_early_submit(
                        result, clean, state, turn, str(run_dir), ledger,
                        _elapsed())
                    if held is not None:
                        result = held
                        record["submit_kind"] = "held_back"
                        kind = "held_back"
                    else:
                        kind, payload = _handle_submit(
                            result, clean, state, turn, str(run_dir))
                        record["submit_kind"] = kind
                if kind == "accepted":
                    result_path, res = payload
                    _append_log(str(run_dir),
                                {"turn": turn,
                                 "prompt_hash": prompt_hash,
                                 "spark_terminal": terminal,
                                 "reasoning_effort": effort,
                                 "tool_calls": turn_records + [record],
                                 "ledger": ledger.ledger_record()})
                    return _submitted(result_path, res)
                if kind == "spent":
                    _append_log(str(run_dir),
                                {"turn": turn,
                                 "prompt_hash": prompt_hash,
                                 "spark_terminal": terminal,
                                 "reasoning_effort": effort,
                                 "tool_calls": turn_records + [record],
                                 "ledger": ledger.ledger_record()})
                    return _synthesise(
                        str(run_dir), rid, ledger,
                        "submit attempts",
                        detail=(f"{MAX_SUBMIT_ATTEMPTS} rejected submits"),
                        errors=payload)
            if name == "submit":
                # The next turn answers this submit result — a dry
                # run's errors, a refusal or an early hold — with max
                # effort (part 06 addendum 2026-11-04).
                state.submit_pending = True
            prefix_text = ""
            if first_turn is not None:
                prefix_text = f"same call as turn {first_turn}\n"
            body = render_tool_result(name, result)
            notice_text = ""
            if name != "submit":
                key = _failure_key(result)
                streak = _track_failure(state, name, result)
                if key is not None and streak is not None \
                        and streak >= REPEAT_NOTICE_AFTER:
                    notice_text = REPEAT_NOTICE
                    if streak >= REPEAT_CLOSE_AFTER:
                        state.repeat_closed.add(name)
                        notice_text += f"; {name} is now closed for " \
                            "this run"
            if prior + 1 >= 3 and REPEAT_NOTICE not in notice_text:
                notice_text = (notice_text + " " + REPEAT_NOTICE).strip()
            full = prefix_text + body
            if notice_text:
                full += "\n" + notice_text
            full += ("\n" + _status_suffix(turn, ledger, _elapsed(),
                                              state, str(run_dir)))
            history.append_tool(call_id, name, full,
                                image_files(result.get("files")))
            record["rendered"] = full
            record["ok"] = bool(result.get("ok"))
            turn_records.append(record)
        if len(history.messages) > span_start:
            state.newest_tool_span = (span_start, len(history.messages))
        if state.catastrophic is not None:
            exc = state.catastrophic
            from src.loop.synthesis import log_fault  # noqa: PLC0415
            fault_path = log_fault(str(run_dir), "tool_fault.txt",
                                   exc.exc)
            _append_log(str(run_dir),
                        {"turn": turn, "prompt_hash": prompt_hash,
                         "spark_terminal": terminal,
                         "reasoning_effort": effort,
                         "tool_calls": turn_records,
                         "catastrophic_tool": exc.tool,
                         "error": str(exc),
                         "fault": fault_path,
                         "ledger": ledger.ledger_record()})
            return _synthesise(str(run_dir), rid, ledger, "tool failed",
                               detail=str(exc.tool))
        _append_log(str(run_dir),
                    {"turn": turn, "prompt_hash": prompt_hash,
                     "spark_terminal": terminal,
                     "reasoning_effort": effort,
                     "tool_calls": turn_records,
                     "ledger": ledger.ledger_record()})
    return _cap_stop(f"turns ≥ {max_turns}")




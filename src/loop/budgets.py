# generated from brief/06 · part 06 owns this file
"""Budget arithmetic and notice texts (part 06 §5 and the live-run
addenda). Run-level budgets — turns, wall time, dollars — end the run;
per-tool budgets — SAM frames, web searches, blind mask checks, dry
runs — close only their own tool with a one-line notice, and the run
goes on (addendum 2026-10-28, fifth live run).

Thresholds and caps are read from :mod:`src.config` at call time, so a
config change moves the loop with it.
"""

from __future__ import annotations

from src import config as _config

__all__ = [
    "EXPLORATION_CLOSE_RATIO",
    "EXPLORATION_TOOLS",
    "FINISHING_TURNS",
    "MAX_EFFORT_FIRST_TURNS",
    "ROUTINE_EFFORT",
    "dollars_spent",
    "exploration_closed",
    "finishing_notice",
    "first_over",
    "halfway_notice",
    "run_ratios",
    "turns_left",
    "wall_left_s",
]

#: Tools closed by the exploration and finishing closings; ``run_python``
#: and ``submit`` stay open under both.
EXPLORATION_TOOLS = ("segment", "view_frames", "web_search", "check_mask")

#: Exploration closes when the first run-level budget (turns, wall time
#: or dollars) reaches this fraction with no ``submit`` call yet in the
#: run (part 06 addendum 2026-10-29, Moon run 15: one third, replacing
#: "three turns after the half-way notice").
EXPLORATION_CLOSE_RATIO = 1.0 / 3.0

#: Turns the agent gets in the finishing phase before the loop submits
#: the evidence file itself (part 06 addendum 2026-10-30, wall run 7).
FINISHING_TURNS = 4

#: First turns that always ask for the strongest reasoning (part 06
#: addendum 2026-11-04, street-jump run 82): judgment is made in the
#: first look, while most later turns only answer a routine tool
#: result. The first ``MAX_EFFORT_FIRST_TURNS`` turns carry
#: ``SPARK_REASONING_EFFORT`` (part 04's ``"max"``).
MAX_EFFORT_FIRST_TURNS = 20

#: Reasoning effort on every other turn: a routine tool result needs
#: no max-effort judgment (part 06 addendum 2026-11-04,
#: street-jump run 82).
ROUTINE_EFFORT = "high"

_HALFWAY_NOTICES = {
    "turns": ("Half the turns are used and nothing has been submitted: "
              "write workspace/evidence.json and submit it with dry_run "
              "now."),
    "wall": ("Half the time is used and nothing has been submitted: "
             "write workspace/evidence.json and submit it with dry_run "
             "now."),
    "dollars": ("Half the budget is used and nothing has been submitted: "
                "write workspace/evidence.json and submit it with "
                "dry_run now."),
}


def dollars_spent(ledger) -> float:
    """Exact debited dollars (excludes unknown-cost calls)."""
    try:
        return float(ledger.total_cost_usd)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def turns_left(ledger) -> int:
    """Whole turns remaining under the turn cap."""
    try:
        used = int(ledger.turns)
    except (TypeError, ValueError, AttributeError):
        used = 0
    return max(0, int(_config.MAX_TURNS) - used)


def wall_left_s(elapsed_s: float) -> float:
    """Wall seconds remaining under the wall cap."""
    try:
        left = float(_config.HARD_CAP_WALL_S) - float(elapsed_s)
    except (TypeError, ValueError):
        left = 0.0
    return max(0.0, left)


def run_ratios(turns_used: int, elapsed_s: float, dollars: float) -> dict:
    """Fraction of each run-level budget consumed (turns/wall/dollars)."""
    caps = {
        "turns": float(int(_config.MAX_TURNS)),
        "wall": float(_config.HARD_CAP_WALL_S),
        "dollars": float(_config.HARD_CAP_COST_USD),
    }
    used = {
        "turns": float(turns_used or 0),
        "wall": float(elapsed_s or 0.0),
        "dollars": float(dollars or 0.0),
    }
    ratios = {}
    for key in ("turns", "wall", "dollars"):
        cap = caps[key]
        ratios[key] = (used[key] / cap) if cap > 0 else 1.0
    return ratios


def first_over(ratios: dict, threshold: float) -> str | None:
    """The most-consumed run-level budget at or past ``threshold``."""
    best: str | None = None
    best_ratio = float(threshold)
    for key in ("turns", "wall", "dollars"):
        try:
            ratio = float((ratios or {}).get(key, 0.0))
        except (TypeError, ValueError):
            continue
        if ratio >= best_ratio or (best is None and ratio >= best_ratio):
            if ratio > best_ratio or best is None:
                best, best_ratio = key, ratio
    return best


def halfway_notice(budget: str) -> str:
    """The one half-way notice, naming the budget that crossed first."""
    return _HALFWAY_NOTICES.get(str(budget),
                                _HALFWAY_NOTICES["turns"])


def _plain_detail(detail: str) -> str:
    """First sentence of an error detail, in plain words (§23)."""
    text = str(detail or "").strip()
    if not text:
        return ""
    cut = len(text)
    for mark in (". ", "; ", ": "):
        pos = text.find(mark)
        if 0 < pos < cut:
            cut = pos
    return text[:cut][:160].rstrip(" .;:,") or text[:160]


def finishing_notice(budget: str, last_dry=None) -> str:
    """The finishing-phase notice (part 06 addendum 2026-10-30).

    At the first finishing turn the notice lists the last dry run's
    errors in plain words; with no dry run yet it says to write the
    evidence file now. ``last_dry`` is the loop's ``{"turn",
    "errors", "clean"}`` record (or ``None``).
    """
    head = (f"finishing phase ({str(budget)} nearly exhausted): you have "
            f"at most {int(FINISHING_TURNS)} more turns. Fix the errors "
            "of your last dry run with run_python and submit; dry-run "
            "first if you have not.")
    if not isinstance(last_dry, dict) or not last_dry.get("turn"):
        return (f"finishing phase ({str(budget)} nearly exhausted): you "
                f"have at most {int(FINISHING_TURNS)} more turns. Write "
                "workspace/evidence.json now and submit it with dry_run.")
    turn = last_dry.get("turn")
    errors = last_dry.get("errors") or []
    if last_dry.get("clean"):
        return (head + f" Your last dry run (turn {turn}) was clean: "
                "submit for real now.")
    words = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        plain = _plain_detail(error.get("detail", ""))
        code = str(error.get("code", "error") or "error")
        field = str(error.get("field", "?") or "?")
        words.append(f"{code} {field}: {plain}".rstrip())
    if words:
        return (head + f" Last dry run (turn {turn}) errors: "
                + "; ".join(words[:4]))
    return head + f" Your last dry run was turn {turn}."


def exploration_closed(turn: int, elapsed_s: float, dollars: float,
                       has_submitted: bool) -> bool:
    """Whether exploration tools are closed before the first submit.

    True once the first run-level budget (turns, wall time or dollars)
    reaches :data:`EXPLORATION_CLOSE_RATIO` with no ``submit`` call yet
    (part 06 addendum 2026-10-29, Moon run 15). The first submit —
    dry or real — reopens them, so the check is live, not latched.
    """
    if has_submitted:
        return False
    try:
        used_turn = int(turn)
    except (TypeError, ValueError):
        used_turn = 0
    try:
        spent = float(dollars)
    except (TypeError, ValueError):
        spent = 0.0
    try:
        elapsed = float(elapsed_s)
    except (TypeError, ValueError):
        elapsed = 0.0
    ratios = run_ratios(used_turn, elapsed, spent)
    return first_over(ratios, EXPLORATION_CLOSE_RATIO) is not None

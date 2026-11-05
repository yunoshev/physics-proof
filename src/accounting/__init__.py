# generated from brief/14 · part 14 owns this file
"""Cost, runtime and failure accounting (brief part 14).

One ledger per run, owned by the loop (part 06), written by every
model/tool call through this module. Prices live in
:mod:`src.config` — the only place they live; the ledger stamps the
price-table version into the run log so old runs stay interpretable.

Counting rule (§2): cost is counted from the usage in the terminal
event only. The usage fields are subsets, not addends: ``cached`` is
part of ``input`` and ``reasoning`` is part of ``output``, so a call
costs exactly ``(input − cached) × input-price + cached ×
cached-price + output × output-price`` (per 1M). Reasoning tokens are
recorded for diagnostics and already paid for inside ``output``.

Retries (§4) are three error classes, never confused: network /
transport (no terminal event — retry with backoff, max 3 attempts),
``response.incomplete`` (never retried as network), and
``response.failed`` (no blind retry of an identical request).
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

from src import config as _config

__all__ = [
    "FailedCallError",
    "Ledger",
    "NetworkError",
    "backoff_delay_s",
    "classify_terminal",
    "price_call",
    "should_retry_network",
]

#: Terminal kinds the ledger recognises (skill: meta-api).
TERMINAL_COMPLETED = "response.completed"
TERMINAL_INCOMPLETE = "response.incomplete"
TERMINAL_FAILED = "response.failed"

#: Budget outcomes written into ``summary.json`` (part 12 §12).
OUTCOME_COMPLETED = "completed"
OUTCOME_BUDGET = "budget_undetermined"


class NetworkError(ConnectionError):
    """A transport death: no terminal event, connection error, 5xx.

    A subclass of :class:`ConnectionError` so the loop's
    ``TRANSIENT_EXCEPTIONS`` (part 06) retries it with backoff — never
    confused with the other two classes.
    """


class FailedCallError(Exception):
    """A ``response.failed`` terminal or a non-retryable 4xx.

    Never retried as network: it is not an ``OSError`` (part 06's
    transient set), so the loop surfaces it as a structured
    tool/agent error instead of retrying an identical request.
    """


def price_call(input_tokens, cached_tokens, output_tokens,
               model=None) -> float:
    """One Spark call's price in USD (subset formula, never a sum).

    ``cached`` is the cached part of ``input`` (priced at the cached
    rate, the rest at the input rate); reasoning is already inside
    ``output`` and takes no separate argument — adding it again
    double-counts. Reads the price table from :mod:`src.config`.
    """
    try:
        total_in = max(0, int(input_tokens))
    except (TypeError, ValueError):
        total_in = 0
    try:
        cached = max(0, int(cached_tokens))
    except (TypeError, ValueError):
        cached = 0
    try:
        output = max(0, int(output_tokens))
    except (TypeError, ValueError):
        output = 0
    cached = min(cached, total_in)
    uncached = total_in - cached
    if model == _config.SPARK_STANDARD_MODEL:
        price_in = float(_config.PRICE_SPARK_STANDARD_INPUT_PER_1M)
        price_cached = float(
            _config.PRICE_SPARK_STANDARD_CACHED_PER_1M)
        price_out = float(_config.PRICE_SPARK_STANDARD_OUTPUT_PER_1M)
    else:
        price_in = float(_config.PRICE_SPARK_INPUT_PER_1M)
        price_cached = float(_config.PRICE_SPARK_CACHED_PER_1M)
        price_out = float(_config.PRICE_SPARK_OUTPUT_PER_1M)
    return (uncached * price_in + cached * price_cached
            + output * price_out) / 1_000_000


def classify_terminal(terminal) -> str:
    """One of ``completed`` / ``incomplete`` / ``failed`` / ``network``.

    ``response.incomplete`` is its own class — never network.
    Anything without a terminal event (``None``, ``""``, unknown) is
    the network class: no trustworthy usage exists for it.
    """
    if terminal == TERMINAL_COMPLETED:
        return "completed"
    if terminal == TERMINAL_INCOMPLETE:
        return "incomplete"
    if terminal == TERMINAL_FAILED:
        return "failed"
    return "network"


def should_retry_network(attempts: int) -> bool:
    """Whether a transport death gets another attempt (config: max 3)."""
    try:
        made = int(attempts)
    except (TypeError, ValueError):
        return False
    return made < int(_config.RETRY_MAX_ATTEMPTS)


def backoff_delay_s(attempt: int) -> float:
    """Backoff before the next attempt: base 2 s, doubling, + jitter."""
    try:
        step = max(1, int(attempt))
    except (TypeError, ValueError):
        step = 1
    base = float(_config.RETRY_BASE_DELAY_S)
    mult = float(_config.RETRY_BACKOFF_MULT)
    return base * (mult ** (step - 1)) + random.uniform(0.0, 1.0)


def _clean_usage(usage) -> dict | None:
    """Four non-negative usage ints with subsets clamped, or None."""
    if not isinstance(usage, dict):
        return None
    try:
        total_in = int(usage.get("input_tokens", 0))
        output = int(usage.get("output_tokens", 0))
        cached = int(usage.get("cached_tokens", 0))
        reasoning = int(usage.get("reasoning_tokens", 0))
    except (TypeError, ValueError):
        return None
    if min(total_in, output, cached, reasoning) < 0:
        return None
    cached = min(cached, total_in)
    reasoning = min(reasoning, output)
    return {"input_tokens": total_in, "cached_tokens": cached,
            "output_tokens": output, "reasoning_tokens": reasoning}


class Ledger:
    """One run's cost/runtime ledger (brief part 14 §2).

    ``turns`` counts loop turns (``count_turn`` hands out 1-based turn
    numbers); token and dollar accumulators grow only from terminal
    events, never from streaming deltas. ``estimated`` flips the first
    time a call ends without trustworthy usage — estimates never
    silently pass as exact.
    """

    def __init__(self, run_id="run", run_dir=None):
        try:
            rid = str(run_id) if run_id else "run"
        except (TypeError, ValueError):
            rid = "run"
        self.run_id = Path(rid).name or "run"
        self._run_dir = (str(run_dir) if run_dir else None)
        self._t0 = time.time()
        self.turns = 0
        self.spark_input_tokens = 0
        self.spark_cached_tokens = 0
        self.spark_output_tokens = 0
        self.spark_reasoning_tokens = 0
        self.cost_spark_input = 0.0
        self.cost_spark_cached = 0.0
        self.cost_spark_output = 0.0
        self.cost_sam = 0.0
        self.cost_search = 0.0
        self.sam_frames_billed = 0
        self.searches = 0
        self.mask_checks = 0
        self.execs = 0
        self.estimated = False
        self.cost_unknown_count = 0
        self.attempt_count = 0
        self.entries: list = []

    @property
    def total_cost_usd(self) -> float:
        """Exact debited dollars (excludes unknown-cost calls)."""
        return (self.cost_spark_input + self.cost_spark_cached
                + self.cost_spark_output + self.cost_sam
                + self.cost_search)

    def count_turn(self) -> int:
        """Start a turn: increment the counter, return the 1-based turn."""
        self.turns = int(self.turns) + 1
        return int(self.turns)

    def elapsed_s(self) -> float:
        """Wall seconds since the ledger was created."""
        return max(0.0, time.time() - self._t0)

    def _spark_cost_parts(self, usage: dict, model=None):
        """``(input, cached, output)`` dollar parts for one usage."""
        uncached = usage["input_tokens"] - usage["cached_tokens"]
        if model == _config.SPARK_STANDARD_MODEL:
            price_in = float(_config.PRICE_SPARK_STANDARD_INPUT_PER_1M)
            price_cached = float(
                _config.PRICE_SPARK_STANDARD_CACHED_PER_1M)
            price_out = float(
                _config.PRICE_SPARK_STANDARD_OUTPUT_PER_1M)
            name = str(_config.SPARK_STANDARD_MODEL)
        else:
            price_in = float(_config.PRICE_SPARK_INPUT_PER_1M)
            price_cached = float(_config.PRICE_SPARK_CACHED_PER_1M)
            price_out = float(_config.PRICE_SPARK_OUTPUT_PER_1M)
            name = str(_config.SPARK_MODEL)
        return ((uncached * price_in / 1_000_000,
                 usage["cached_tokens"] * price_cached / 1_000_000,
                 usage["output_tokens"] * price_out / 1_000_000), name)

    def _debit_spark_usage(self, turn, usage: dict, kind: str,
                           model=None, artifact=None) -> float:
        """Add one terminal usage to the Spark accumulators."""
        (part_in, part_cached, part_out), name = \
            self._spark_cost_parts(usage, model)
        self.spark_input_tokens += (usage["input_tokens"]
                                    - usage["cached_tokens"])
        self.spark_cached_tokens += usage["cached_tokens"]
        self.spark_output_tokens += usage["output_tokens"]
        self.spark_reasoning_tokens += usage["reasoning_tokens"]
        self.cost_spark_input += part_in
        self.cost_spark_cached += part_cached
        self.cost_spark_output += part_out
        cost = part_in + part_cached + part_out
        self.entries.append({
            "turn": int(turn), "kind": str(kind),
            "model": name, "usage": dict(usage),
            "cost_usd": cost, "artifact": artifact,
        })
        return cost

    def debit_terminal_event(self, turn, event) -> float:
        """Count one agent call from its terminal event (never deltas).

        ``event`` is ``{"type": terminal, "usage": {...}}``. Completed
        and incomplete terminals with usage are priced by the subset
        formula; failed terminals — or any event without trustworthy
        usage — record ``cost_unknown`` and mark the run estimated.
        """
        terminal = None
        usage = None
        model = None
        if isinstance(event, dict):
            terminal = event.get("type")
            usage = event.get("usage")
            model = event.get("model")
            if usage is None and "input_tokens" in event:
                terminal = terminal or TERMINAL_COMPLETED
                usage = event
        kind = classify_terminal(terminal)
        clean = _clean_usage(usage)
        if kind in ("completed", "incomplete") and clean is not None:
            return self._debit_spark_usage(turn, clean, "spark",
                                           model=model)
        detail = str(terminal or "no terminal event")
        estimate = clean["input_tokens"] if clean is not None else 0
        return self.record_cost_unknown(turn, kind="spark",
                                       detail=detail,
                                       input_estimate=estimate)

    def record_mask_check(self, turn, usage=None, artifact=None) -> float:
        """Count one blind mask check: a contributor Spark call (§2).

        Its token cost folds into the Spark buckets (the summary has
        no mask-check cost bucket); the check itself increments
        ``mask_checks``. Without usage the check still counts, but the
        run is marked estimated.
        """
        self.mask_checks = int(self.mask_checks) + 1
        clean = _clean_usage(usage)
        if clean is None:
            self.record_cost_unknown(turn, kind="mask_check",
                                     detail="blind check without usage",
                                     input_estimate=0)
            return 0.0
        return self._debit_spark_usage(turn, clean, "mask_check",
                                       artifact=artifact)

    def debit_sam(self, turn, frames_requested: int) -> int:
        """Bill one SAM call: ``max(50, frames)`` at call time (§2).

        Returns the billed frame count. Retries never double-bill:
        only executed calls reach this method — attempts are logged
        separately via :meth:`record_attempt`.
        """
        try:
            requested = int(frames_requested)
        except (TypeError, ValueError):
            requested = 0
        billed = max(int(_config.SAM_MIN_BILLED_FRAMES),
                     max(0, requested))
        cost = (billed * float(_config.PRICE_SAM_PER_1000_FRAMES)
                / 1000.0)
        self.sam_frames_billed = int(self.sam_frames_billed) + billed
        self.cost_sam += cost
        self.entries.append({
            "turn": int(turn), "kind": "sam",
            "model": str(_config.SAM_MODEL),
            "usage": {"frames_requested": max(0, requested),
                      "frames_billed": billed},
            "cost_usd": cost, "artifact": None,
        })
        return billed

    def debit_search(self, turn) -> float:
        """Bill one web search at call time; return its dollar cost."""
        cost = float(_config.PRICE_SEARCH_PER_CALL)
        self.searches = int(self.searches) + 1
        self.cost_search += cost
        self.entries.append({
            "turn": int(turn), "kind": "search", "model": "web_search",
            "usage": {"calls": 1}, "cost_usd": cost, "artifact": None,
        })
        return cost

    def record_exec(self, turn, artifact=None) -> int:
        """Count one sandboxed execution (no dollar cost); return total."""
        self.execs = int(self.execs) + 1
        self.entries.append({
            "turn": int(turn), "kind": "exec", "model": "sandbox",
            "usage": {}, "cost_usd": 0.0, "artifact": artifact,
        })
        return int(self.execs)

    def record_attempt(self, turn, kind, detail="", attempt=None) -> int:
        """Log one retry attempt separately: attempts never bill (§4).

        Returns the run's attempt count. Because attempts are entries
        of their own, double-billing would be visible in the log.
        """
        self.attempt_count = int(self.attempt_count) + 1
        try:
            number = int(attempt) if attempt is not None else \
                int(self.attempt_count)
        except (TypeError, ValueError):
            number = int(self.attempt_count)
        self.entries.append({
            "turn": int(turn), "kind": str(kind or "spark"),
            "model": None, "usage": {}, "cost_usd": 0.0,
            "artifact": None, "attempt": number, "billed": False,
            "detail": str(detail or ""),
        })
        return int(self.attempt_count)

    def record_cost_unknown(self, turn, kind="spark", detail="",
                            input_estimate=0) -> float:
        """Mark one call as unpriceable: no usage, estimate only (§2).

        The run's total is marked estimated from here on. Returns 0.0
        (nothing exact is added to the total).
        """
        try:
            estimate = max(0, int(input_estimate))
        except (TypeError, ValueError):
            estimate = 0
        self.estimated = True
        self.cost_unknown_count = int(self.cost_unknown_count) + 1
        self.entries.append({
            "turn": int(turn), "kind": str(kind or "spark"),
            "model": None,
            "usage": {"input_tokens_estimate": estimate},
            "cost_usd": 0.0, "artifact": None,
            "cost_unknown": True, "detail": str(detail or ""),
        })
        return 0.0

    def ledger_record(self) -> dict:
        """JSON-serialisable snapshot for the per-turn operator log."""
        return {
            "run_id": self.run_id,
            "price_table_version": int(_config.PRICE_TABLE_VERSION),
            "model": str(_config.SPARK_MODEL),
            "totals": {
                "turns": int(self.turns),
                "wall_time_s": float(self.elapsed_s()),
                "cost_usd": float(self.total_cost_usd),
                "cost_spark_input": float(self.cost_spark_input),
                "cost_spark_cached": float(self.cost_spark_cached),
                "cost_spark_output": float(self.cost_spark_output),
                "cost_sam": float(self.cost_sam),
                "cost_search": float(self.cost_search),
                "spark_input_tokens": int(self.spark_input_tokens),
                "spark_cached_tokens": int(self.spark_cached_tokens),
                "spark_output_tokens": int(self.spark_output_tokens),
                "spark_reasoning_tokens": int(
                    self.spark_reasoning_tokens),
                "sam_frames_billed": int(self.sam_frames_billed),
                "searches": int(self.searches),
                "mask_checks": int(self.mask_checks),
                "execs": int(self.execs),
                "estimated": bool(self.estimated),
                "cost_unknown_count": int(self.cost_unknown_count),
                "attempt_count": int(self.attempt_count),
            },
            "entries": [dict(entry) for entry in self.entries],
        }

    def _relative_result_path(self, result_path) -> str:
        """Run-relative result path: never a local absolute path (§7).

        ``summary.json`` is inlined into the published page, so an
        absolute operator path here would leak the operator's home
        directory. Absolute paths become relative to the run directory
        (or their basename when the run directory is unknown).
        """
        try:
            text = str(result_path) if result_path else ""
        except (TypeError, ValueError):
            text = ""
        if not text:
            return str(_config.RESULT_FILENAME)
        candidate = Path(text)
        if not candidate.is_absolute():
            cleaned = text.lstrip("/")
            return cleaned or str(_config.RESULT_FILENAME)
        if self._run_dir:
            try:
                return str(candidate.relative_to(Path(self._run_dir)))
            except ValueError:
                pass
        return candidate.name or str(_config.RESULT_FILENAME)

    def write_summary(self, result_path="", budget_outcome="completed",
                      run_dir=None) -> dict:
        """Aggregate the ledger into the part-12 §12 summary dict.

        Totals and the breakdown come from the ledger, never
        re-derived. Every path in the output is relative to the run
        directory (§7); the breakdown follows the subset rule (§2).
        """
        if budget_outcome not in (OUTCOME_COMPLETED, OUTCOME_BUDGET):
            raise ValueError(
                f"budget_outcome must be {OUTCOME_COMPLETED!r} or "
                f"{OUTCOME_BUDGET!r}, not {budget_outcome!r}")
        if run_dir is not None:
            self._run_dir = str(run_dir)
        total = (self.cost_spark_input + self.cost_spark_cached
                 + self.cost_spark_output + self.cost_sam
                 + self.cost_search)
        parts = {
            "total": total,
            "spark_input": float(self.cost_spark_input),
            "spark_cached": float(self.cost_spark_cached),
            "spark_output": float(self.cost_spark_output),
            "sam": float(self.cost_sam),
            "search": float(self.cost_search),
        }
        rounded = {key: round(float(value), 9)
                   for key, value in parts.items()}
        rounded["total"] = round(
            rounded["spark_input"] + rounded["spark_cached"]
            + rounded["spark_output"] + rounded["sam"]
            + rounded["search"], 9)
        return {
            "contract_version": int(_config.CONTRACT_VERSION),
            "run_id": self.run_id,
            "cost_usd": rounded,
            "turns": int(self.turns),
            "model": str(_config.SPARK_MODEL),
            "sam_frames_billed": int(self.sam_frames_billed),
            "searches": int(self.searches),
            "mask_checks": int(self.mask_checks),
            "wall_time_s": float(self.elapsed_s()),
            "budget_outcome": str(budget_outcome),
            "result_path": self._relative_result_path(result_path),
        }

    def write_ledger_log(self, run_dir) -> str:
        """Write the operator-side ledger log; return its run-relative path."""
        logs_dir = Path(str(run_dir)) / str(_config.LOGS_DIR_NAME)
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "ledger.json").write_text(
            json.dumps(self.ledger_record(), indent=2) + "\n",
            encoding="utf-8")
        return "logs/ledger.json"

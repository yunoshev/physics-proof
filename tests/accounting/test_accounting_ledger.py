# generated from brief/14 · part 14 owns this file
"""The ledger's counting rules (brief part 14 §2, PLAN.md).

Cost comes from the usage in the terminal event only; cached is part
of input and reasoning is part of output (subsets, never addends).
Incomplete terminals with usage still count; failed/transport deaths
record cost_unknown and mark the run estimated. SAM bills
max(50, frames) once per executed call — attempts never bill.
"""

from __future__ import annotations

import pytest

from src import config
from src.accounting import Ledger, price_call


def _event(terminal, usage):
    return {"type": terminal, "usage": dict(usage) if usage else usage}


def test_terminal_event_only_accounting(make_ledger, usage):
    """Streaming deltas carry no usage, so only the terminal event bills."""
    ledger = make_ledger()
    # A stream that dies with no terminal event: nothing to price.
    ledger.debit_terminal_event(1, {"type": None, "usage": None})
    assert ledger.total_cost_usd == pytest.approx(0.0)
    assert ledger.estimated is True
    # The terminal event prices exactly the subset formula, once.
    before = ledger.total_cost_usd
    cost = ledger.debit_terminal_event(
        1, _event("response.completed", usage()))
    assert cost == pytest.approx(
        (800 * 0.10 + 200 * 0.002 + 500 * 0.20) / 1_000_000)
    assert ledger.total_cost_usd == pytest.approx(before + cost)


def test_cached_subset_not_addend(make_ledger, usage):
    """Cached tokens are priced at the cached rate, not added on top."""
    ledger = make_ledger()
    cost = ledger.debit_terminal_event(
        1, _event("response.completed", usage()))
    # The pricing error this rule exists to prevent: pricing the full
    # input at the input rate AND the cached part again.
    double_count = ((1000 * 0.10 + 200 * 0.002 + 500 * 0.20)
                    / 1_000_000)
    assert cost == pytest.approx(
        (800 * 0.10 + 200 * 0.002 + 500 * 0.20) / 1_000_000)
    assert cost != pytest.approx(double_count)
    assert ledger.spark_input_tokens == 800
    assert ledger.spark_cached_tokens == 200
    assert ledger.cost_spark_input == pytest.approx(800 * 0.10 / 1e6)
    assert ledger.cost_spark_cached == pytest.approx(200 * 0.002 / 1e6)


def test_reasoning_inside_output_no_double_count(make_ledger, usage):
    """Reasoning tokens are diagnostics; output already pays for them."""
    with_reasoning = make_ledger()
    cost_r = with_reasoning.debit_terminal_event(
        1, _event("response.completed", usage(reasoning_tokens=400)))
    without = make_ledger()
    cost_0 = without.debit_terminal_event(
        1, _event("response.completed", usage(reasoning_tokens=0)))
    assert cost_r == pytest.approx(cost_0)
    assert cost_r != pytest.approx(cost_0 + 400 * 0.20 / 1_000_000)
    # ... but reasoning is still recorded for diagnostics.
    assert with_reasoning.spark_reasoning_tokens == 400
    assert with_reasoning.spark_output_tokens == 500


def test_incomplete_with_usage_counted(make_ledger, usage):
    """An incomplete turn still consumed tokens: counted, not retried."""
    ledger = make_ledger()
    cost = ledger.debit_terminal_event(
        2, _event("response.incomplete", usage()))
    assert cost == pytest.approx(price_call(1000, 200, 500))
    assert ledger.total_cost_usd == pytest.approx(cost)
    assert ledger.estimated is False
    assert ledger.spark_output_tokens == 500


def test_failed_transport_marks_cost_unknown_estimated(make_ledger):
    """Failed/transport deaths: cost_unknown with an estimate (§2)."""
    ledger = make_ledger()
    assert ledger.estimated is False
    ledger.debit_terminal_event(
        3, {"type": "response.failed", "usage": None})
    ledger.record_cost_unknown(3, kind="spark",
                               detail="connection reset")
    assert ledger.total_cost_usd == pytest.approx(0.0)
    assert ledger.estimated is True
    assert ledger.cost_unknown_count == 2
    unknowns = [e for e in ledger.entries
                if e.get("cost_unknown")]
    assert len(unknowns) == 2
    assert all(e["cost_usd"] == pytest.approx(0.0) for e in unknowns)
    snapshot = ledger.ledger_record()
    assert snapshot["totals"]["estimated"] is True


def test_price_call_clamps_subsets():
    """Over-claimed subsets never produce negative parts."""
    assert price_call(100, 500, 50) == pytest.approx(
        (0 * 0.10 + 100 * 0.002 + 50 * 0.20) / 1_000_000)
    assert price_call(0, 0, 0) == pytest.approx(0.0)


def test_sam_max50_no_double_bill_on_retry(make_ledger):
    """SAM bills max(50, requested) once; attempts are unbilled (§4)."""
    ledger = make_ledger()
    billed_small = ledger.debit_sam(1, 10)
    assert billed_small == 50
    assert ledger.sam_frames_billed == 50
    assert ledger.cost_sam == pytest.approx(50 * 0.20 / 1000)
    billed_big = ledger.debit_sam(2, 120)
    assert billed_big == 120
    assert ledger.sam_frames_billed == 170
    # A retry attempt is logged for visibility but debits nothing.
    before = ledger.total_cost_usd
    ledger.record_attempt(2, "segment", detail="timeout", attempt=1)
    ledger.record_attempt(2, "segment", detail="timeout", attempt=2)
    assert ledger.total_cost_usd == pytest.approx(before)
    assert ledger.sam_frames_billed == 170
    attempts = [e for e in ledger.entries if "attempt" in e]
    assert len(attempts) == 2
    assert all(e["cost_usd"] == pytest.approx(0.0) for e in attempts)
    assert all(e["billed"] is False for e in attempts)


def test_debit_search_and_exec(make_ledger):
    """Searches bill per call at call time; execs count without cost."""
    ledger = make_ledger()
    cost = ledger.debit_search(1)
    assert cost == pytest.approx(config.PRICE_SEARCH_PER_CALL)
    ledger.debit_search(2)
    assert ledger.searches == 2
    assert ledger.cost_search == pytest.approx(
        2 * config.PRICE_SEARCH_PER_CALL)
    ledger.record_exec(2, "artifacts/t2_run_python_0.stdout.txt")
    assert ledger.execs == 1
    assert ledger.total_cost_usd == pytest.approx(
        2 * config.PRICE_SEARCH_PER_CALL)


def test_mask_check_folds_into_spark(make_ledger, usage):
    """Blind checks are Spark calls: tokens join the Spark buckets."""
    ledger = make_ledger()
    ledger.record_mask_check(1, usage(), "artifacts/t1_check_mask_0.json")
    assert ledger.mask_checks == 1
    assert ledger.spark_output_tokens == 500
    assert ledger.total_cost_usd == pytest.approx(
        price_call(1000, 200, 500))
    # Without usage the check still counts, but the run is estimated.
    ledger.record_mask_check(2, None, "artifacts/t2_check_mask_0.json")
    assert ledger.mask_checks == 2
    assert ledger.estimated is True

# generated from brief/14 · part 14 owns this file
"""Summary, caps and run outputs (part 14 §§2–3, §7 addendum).

The summary is aggregated from the ledger, never re-derived; the loop
checks the ledger before every call so a call after a hard cap is
never made. Every path written into ``summary.json`` is relative to
the run directory — after a stubbed run it contains no absolute path.
"""

from __future__ import annotations

import json
import os

import pytest

from src import config
from src.accounting import Ledger, price_call
from src.contract import validate_summary
from src.loop import run_loop


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _strings(value)


def _debit_all(ledger):
    ledger.count_turn()
    ledger.debit_terminal_event(1, {
        "type": "response.completed",
        "usage": {"input_tokens": 1000, "cached_tokens": 200,
                  "output_tokens": 500, "reasoning_tokens": 100}})
    ledger.debit_sam(1, 10)
    ledger.debit_search(1)
    ledger.record_mask_check(
        1, {"input_tokens": 100, "cached_tokens": 90,
            "output_tokens": 20, "reasoning_tokens": 5},
        "artifacts/t1_check_mask_0.json")
    return ledger


def test_summary_breakdown_matches_ledger(make_ledger):
    """Total + breakdown come from the ledger, never re-derived (§2)."""
    ledger = _debit_all(make_ledger())
    summary = ledger.write_summary(result_path="result.json",
                                   budget_outcome="completed")
    assert validate_summary(summary) == []
    spark = price_call(1000, 200, 500)
    blind = price_call(100, 90, 20)
    assert summary["cost_usd"]["spark_input"] == pytest.approx(
        800 * 0.10 / 1e6 + 10 * 0.10 / 1e6)
    assert summary["cost_usd"]["spark_cached"] == pytest.approx(
        200 * 0.002 / 1e6 + 90 * 0.002 / 1e6)
    assert summary["cost_usd"]["spark_output"] == pytest.approx(
        500 * 0.20 / 1e6 + 20 * 0.20 / 1e6)
    assert summary["cost_usd"]["sam"] == pytest.approx(50 * 0.20 / 1000)
    assert summary["cost_usd"]["search"] == pytest.approx(
        config.PRICE_SEARCH_PER_CALL)
    assert summary["cost_usd"]["total"] == pytest.approx(
        summary["cost_usd"]["spark_input"]
        + summary["cost_usd"]["spark_cached"]
        + summary["cost_usd"]["spark_output"] + summary["cost_usd"]["sam"]
        + summary["cost_usd"]["search"])
    assert summary["cost_usd"]["total"] == pytest.approx(
        ledger.total_cost_usd)
    assert summary["turns"] == 1
    assert summary["model"] == config.SPARK_MODEL
    assert summary["sam_frames_billed"] == 50
    assert summary["searches"] == 1
    assert summary["mask_checks"] == 1
    assert summary["wall_time_s"] >= 0.0
    assert summary["contract_version"] == config.CONTRACT_VERSION == 2
    assert summary["result_path"] == "result.json"
    assert summary["budget_outcome"] == "completed"


def test_summary_rejects_unknown_outcome(make_ledger):
    """Only the two contract outcomes are writable (§12 schema)."""
    ledger = make_ledger()
    with pytest.raises(ValueError):
        ledger.write_summary(result_path="result.json",
                             budget_outcome="exploded")
    summary = ledger.write_summary(result_path="result.json",
                                   budget_outcome="budget_undetermined")
    assert validate_summary(summary) == []
    assert summary["budget_outcome"] == "budget_undetermined"


def test_summary_paths_relative_direct(make_ledger):
    """Absolute result paths never survive into the summary (§7)."""
    ledger = make_ledger("run-9")
    summary = ledger.write_summary(
        result_path="/Users/someone/Projects/x/runs/run-9/result.json",
        budget_outcome="completed")
    assert summary["result_path"] == "result.json"
    assert not os.path.isabs(summary["result_path"])
    for text in _strings(summary):
        assert not text.startswith("/"), text


def test_hard_caps_checked_pre_call(make_run, make_ledger):
    """Past the $2 hard cap the agent call is never made (§3)."""
    run_dir = make_run()
    ledger = make_ledger("over-cap")
    ledger.debit_terminal_event(0, {
        "type": "response.completed",
        "usage": {"input_tokens": 0, "cached_tokens": 0,
                  "output_tokens": 20_000_000, "reasoning_tokens": 0}})
    assert ledger.total_cost_usd >= config.HARD_CAP_COST_USD
    calls = []

    def _spark(request):
        calls.append(request)
        return {"terminal": "response.completed", "text": "hi",
                "tool_calls": [], "usage": {
                    "input_tokens": 10, "cached_tokens": 0,
                    "output_tokens": 5, "reasoning_tokens": 0}}

    outcome = run_loop(str(run_dir), "over-cap", spark_client=_spark,
                       ledger=ledger)
    assert calls == [], "a call after a hard cap is never made"
    assert outcome["status"] == "undetermined"
    assert "budget" in outcome["reason"]
    summary = json.loads(
        (run_dir / config.SUMMARY_FILENAME).read_text(encoding="utf-8"))
    assert validate_summary(summary) == []
    assert summary["budget_outcome"] == "budget_undetermined"


def _failing_spark(request):
    return {"terminal": "response.failed", "text": "", "tool_calls": [],
            "usage": None, "error": "boom"}


def test_summary_has_no_absolute_path_after_stubbed_run(make_run):
    """§7 addendum: no local path may reach a page-inlined file.

    Fails without the fix: ``summary.json`` carried the operator's
    home directory via the absolute ``result_path``. After a stubbed
    run (repeated agent-call failure → synthesised undetermined), no
    string in ``summary.json`` is absolute or starts with ``/``.
    """
    run_dir = make_run()
    ledger = Ledger(run_id=run_dir.name, run_dir=str(run_dir))
    outcome = run_loop(str(run_dir), run_dir.name,
                       spark_client=_failing_spark, ledger=ledger)
    assert outcome["status"] == "undetermined"
    summary_path = run_dir / config.SUMMARY_FILENAME
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert validate_summary(summary) == []
    assert summary["result_path"] == "result.json"
    for text in _strings(summary):
        assert not os.path.isabs(text), text
        assert not text.startswith("/"), text

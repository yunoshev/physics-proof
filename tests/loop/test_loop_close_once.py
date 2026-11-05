# generated from brief/06 · part 06 owns this file
"""A closing line for a tool is sent once (part 06 addendum 2026-11-04,
street-jump run 83).

Repeating the same closing line on every turn used to count as a loop
notice each time, pinning every turn to max effort. The loop records
each tool it has sent a closing line for and does not send it again;
only the first send counts as a loop notice for the reasoning effort.
Caps and efforts always come from :mod:`src.config` and
:mod:`src.loop.budgets`; no literal cap or effort appears here.
"""

from __future__ import annotations

import json

from src import config
from src.loop.budgets import MAX_EFFORT_FIRST_TURNS, ROUTINE_EFFORT


def _fake_python_ok(run_dir, turn, **kwargs):
    return {"ok": True, "summary": "ran", "files": [], "metrics": {}}


def _python_call(stub_responses, index):
    return stub_responses["call"](
        "run_python",
        {"code": f"print({index})", "timeout_s": None,
         "memory_mb": None},
        f"call-py-{index}")


def test_loop_closing_line_sent_once_effort_drops_back(
        script_spark, stub_responses, drive_loop, make_run, make_ledger,
        monkeypatch, accepting_validator):
    """With web searches at 5 of 6 for ten-plus turns, the closing
    line appears in the history once, and only the turn answering it
    carries max effort for that reason: later turns drop to routine."""
    import src.tools.run_python as run_python_mod

    monkeypatch.setattr(run_python_mod, "run_python", _fake_python_ok)
    run_dir = make_run("close-once")
    ledger = make_ledger("r", run_dir)
    ledger.searches = int(config.MAX_SEARCHES) - 1
    total = int(MAX_EFFORT_FIRST_TURNS) + 3
    script = []
    for index in range(total - 1):
        script.append(stub_responses["completed"](
            f"working {index}", [_python_call(stub_responses, index)]))
    script.append(stub_responses["completed"](
        "done", [stub_responses["call"](
            "submit", {"evidence": {"a": 1}, "evidence_path": None,
                       "dry_run": False}, "call-s")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark, ledger=ledger,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert len(spark.requests) == total
    closing = (f"web_search is closed for this run: the search budget "
               f"is nearly spent ({int(config.MAX_SEARCHES) - 1} of "
               f"{int(config.MAX_SEARCHES)} used)")
    # The history is cumulative: every request carries the messages so
    # far. Sent once means exactly one message holds the line, in the
    # final request that replays the whole history.
    final_messages = spark.requests[-1]["messages"]
    assert sum(1 for message in final_messages
               if closing in json.dumps(message)) == 1
    first_with_notice = next(
        index for index, request in enumerate(spark.requests)
        if closing in json.dumps(request["messages"]))
    assert (spark.requests[first_with_notice + 1]["reasoning_effort"]
            == config.SPARK_REASONING_EFFORT)
    assert (spark.requests[int(MAX_EFFORT_FIRST_TURNS)]
            ["reasoning_effort"] == ROUTINE_EFFORT)

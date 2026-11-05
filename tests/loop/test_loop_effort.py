# generated from brief/06 · part 06 owns this file
"""Max effort where judgment is made, high for routine turns (part 06
addendum 2026-11-04, street-jump run 82).

Every agent request carries ``reasoning_effort``: part 04's
``SPARK_REASONING_EFFORT`` on the first ``MAX_EFFORT_FIRST_TURNS``
turns, on a turn answering a ``submit`` result, and on a turn answering
a loop notice; ``ROUTINE_EFFORT`` everywhere else. ``logs/loop.jsonl``
records each turn's effort. Caps and efforts always come from
:mod:`src.config` and :mod:`src.loop.budgets`; no literal cap or
effort appears here.
"""

from __future__ import annotations

import json

from src import config
from src.loop.budgets import MAX_EFFORT_FIRST_TURNS, ROUTINE_EFFORT
from src.loop.run import _State, reasoning_effort_for_turn


def _fake_python_ok(run_dir, turn, **kwargs):
    return {"ok": True, "summary": "ran", "files": [], "metrics": {}}


def _use_fake_python(monkeypatch):
    import src.tools.run_python as run_python_mod
    monkeypatch.setattr(run_python_mod, "run_python", _fake_python_ok)


def _python_call(stub_responses, index):
    return stub_responses["call"](
        "run_python",
        {"code": f"print({index})", "timeout_s": None,
         "memory_mb": None},
        f"call-py-{index}")


def test_loop_effort_first_turns_max_then_routine(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """The first turns carry max effort; the next routine turn drops
    to routine effort."""
    _use_fake_python(monkeypatch)
    run_dir = make_run()
    total = int(MAX_EFFORT_FIRST_TURNS) + 2
    script = []
    for index in range(total - 1):
        script.append(stub_responses["completed"](
            f"working {index}", [_python_call(stub_responses, index)]))
    script.append(stub_responses["completed"](
        "done", [stub_responses["call"](
            "submit", {"evidence": {"a": 1}, "evidence_path": None,
                       "dry_run": False}, "call-s")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert len(spark.requests) == total
    for request in spark.requests[:int(MAX_EFFORT_FIRST_TURNS)]:
        assert (request["reasoning_effort"]
                == config.SPARK_REASONING_EFFORT)
    assert (spark.requests[int(MAX_EFFORT_FIRST_TURNS)]
            ["reasoning_effort"] == ROUTINE_EFFORT)


def test_loop_effort_dry_run_then_routine(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        rejecting_validator, measured_evidence):
    """The turn answering a dry-run ``submit`` carries max effort, and
    the next routine turn carries routine effort again."""
    _use_fake_python(monkeypatch)
    run_dir = make_run()
    validator = rejecting_validator(run_dir, [[
        {"code": "E1", "field": "evidence.segments",
         "detail": "the segment track is too short to fit"}]])
    measured = measured_evidence()
    # Turn 1 dry-runs; turns 2..MAX answer with max effort behind it;
    # the first turn past the max window drops back to routine effort.
    script = [stub_responses["completed"](
        "dry", [stub_responses["call"](
            "submit", {"evidence": measured, "evidence_path": None,
                       "dry_run": True}, "call-dry")])]
    for index in range(1, int(MAX_EFFORT_FIRST_TURNS) + 1):
        script.append(stub_responses["completed"](
            f"working {index}", [_python_call(stub_responses, index)]))
    script.append(stub_responses["completed"](
        "done", [stub_responses["call"](
            "submit", {"evidence": measured, "evidence_path": None,
                       "dry_run": False}, "call-s")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark, validator=validator)
    assert out["status"] == "submitted"
    total = int(MAX_EFFORT_FIRST_TURNS) + 2
    assert len(spark.requests) == total
    assert (spark.requests[1]["reasoning_effort"]
            == config.SPARK_REASONING_EFFORT)
    assert (spark.requests[int(MAX_EFFORT_FIRST_TURNS)]
            ["reasoning_effort"] == ROUTINE_EFFORT)
    assert (spark.requests[int(MAX_EFFORT_FIRST_TURNS) + 1]
            ["reasoning_effort"] == ROUTINE_EFFORT)
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert lines
    for line in lines:
        assert json.loads(line)["reasoning_effort"] in (
            config.SPARK_REASONING_EFFORT, ROUTINE_EFFORT)


def test_loop_effort_after_halfway_notice(
        script_spark, stub_responses, drive_loop, make_run, fake_clock,
        monkeypatch, accepting_validator):
    """The turn after the half-way notice carries max effort even past
    the first turns (the wall clock crosses half here)."""
    _use_fake_python(monkeypatch)
    run_dir = make_run()

    def _advance(request):
        fake_clock.advance(
            float(config.HARD_CAP_WALL_S) * 0.5 + 1.0)
        return stub_responses["completed"](
            "warming up", [_python_call(stub_responses, "warm")])

    script = []
    for index in range(int(MAX_EFFORT_FIRST_TURNS) - 1):
        script.append(stub_responses["completed"](
            f"working {index}", [_python_call(stub_responses, index)]))
    script.append(_advance)
    script.append(stub_responses["completed"](
        "done", [stub_responses["call"](
            "submit", {"evidence": {"a": 1}, "evidence_path": None,
                       "dry_run": False}, "call-s")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark, clock=fake_clock,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    halfway = spark.requests[int(MAX_EFFORT_FIRST_TURNS)]
    assert (halfway["reasoning_effort"]
            == config.SPARK_REASONING_EFFORT)
    assert "Half the time is used" in json.dumps(halfway["messages"])


def test_loop_effort_unit_routing():
    """``reasoning_effort_for_turn`` routes max to judgment turns and
    routine effort everywhere else."""
    state = _State()
    assert (reasoning_effort_for_turn(1, state)
            == config.SPARK_REASONING_EFFORT)
    assert (reasoning_effort_for_turn(int(MAX_EFFORT_FIRST_TURNS), state)
            == config.SPARK_REASONING_EFFORT)
    assert (reasoning_effort_for_turn(int(MAX_EFFORT_FIRST_TURNS) + 1,
                                      state) == ROUTINE_EFFORT)
    state.submit_pending = True
    assert (reasoning_effort_for_turn(int(MAX_EFFORT_FIRST_TURNS) + 1,
                                      state)
            == config.SPARK_REASONING_EFFORT)
    state.submit_pending = False
    state.notice_pending = True
    assert (reasoning_effort_for_turn(int(MAX_EFFORT_FIRST_TURNS) + 1,
                                      state)
            == config.SPARK_REASONING_EFFORT)

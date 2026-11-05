# generated from brief/06 · part 06 owns this file
"""No early real submit while pushes remain (part 06 addenda 2026-11-02).

A real submit never returns push codes (part 11 turns them into an
undetermined verdict), so before accepting an early real submit the loop
validates the same evidence as a dry run. When that dry run gives push
codes and no hard errors, the loop holds the submit back: the reply is
that dry run's reply with a ``Time remains`` first line, it counts as a
dry run, and the run goes on. From half of any run-level budget the loop
runs no extra dry run and the real submit goes on as usual.

Turn numbers always come from :mod:`src.config`; the suite pins no
literal cap.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import config
from src.validate import PUSH_CODES


def _submit_call(stub_responses, evidence=None, dry_run=False,
                 call_id="call-submit"):
    return stub_responses["call"](
        "submit", {"evidence": dict(evidence or {"a": 1}),
                   "evidence_path": None, "dry_run": dry_run},
        call_id)


def _rendered_of(run_dir, name):
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    return [tc.get("rendered", "")
            for entry in (json.loads(line) for line in lines)
            for tc in entry.get("tool_calls", [])
            if tc.get("rendered") and tc.get("name") == name]


def _thinking(stub_responses, n, prefix="thinking"):
    return [stub_responses["completed"](f"{prefix} {i}")
            for i in range(n)]


def _part11_like_validator(run_dir, push=None):
    """Stub validator behaving like part 11.

    A dry run returns the push list (or no errors when ``push`` is
    None); a real submit of the same evidence is accepted with no
    errors and writes ``result.json``.
    """
    calls: list = []
    push_item = (dict(push) if push is not None else None)

    def _validate(evidence, run_context=None, dry_run=False):
        calls.append({"evidence": evidence, "dry_run": bool(dry_run)})
        if bool(dry_run):
            if push_item is None:
                return {"accepted": False, "errors": []}
            return {"accepted": False, "errors": [dict(push_item)]}
        path = Path(str(run_dir)) / "result.json"
        path.write_text(json.dumps({"accepted": True}) + "\n",
                        encoding="utf-8")
        return {"accepted": True, "errors": [],
                "result": {"accepted": True},
                "result_path": str(path)}

    _validate.calls = calls
    return _validate


def _dry_run_count(run_dir) -> int:
    try:
        raw = json.loads((run_dir / "logs" / "dry_runs.json").read_text(
            encoding="utf-8"))
        if isinstance(raw, dict):
            return max(0, int(raw.get("dry_runs", 0)))
    except (OSError, ValueError, TypeError):
        pass
    return 0


def test_loop_early_real_submit_with_pushes_held_back(
        script_spark, stub_responses, drive_loop, make_run):
    """A real submit early in the run is not accepted.

    The stub behaves like part 11: the dry run returns one push, the
    real submit would be accepted with no errors. The loop runs the
    extra dry run first, holds the submit back, and the reply starts
    ``Time remains`` while the dry-run count goes up by one.
    """
    early_turn = min(20, config.MAX_TURNS // 2 - 1)
    assert early_turn < config.MAX_TURNS // 2
    run_dir = make_run()
    push = {"code": PUSH_CODES[0], "field": "references",
            "detail": "measure a second thing of known size"}
    validator = _part11_like_validator(run_dir, push=push)
    script = _thinking(stub_responses, early_turn - 1)
    script.append(stub_responses["completed"](
        "submit early", [_submit_call(stub_responses, dry_run=False,
                                      call_id="call-early")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark, validator=validator)
    assert validator.calls and validator.calls[0]["dry_run"] is True
    assert _dry_run_count(run_dir) == 1
    rendered = _rendered_of(run_dir, "submit")
    assert len(rendered) == 1
    first_body = rendered[0].splitlines()
    assert first_body[1].startswith("Time remains")
    assert (f"Time remains ({early_turn} of {config.MAX_TURNS} "
            f"turns,") in rendered[0]
    assert "pushes below" in rendered[0]
    assert PUSH_CODES[0] in rendered[0]


def test_loop_late_real_submit_with_pushes_accepted(
        script_spark, stub_responses, drive_loop, make_run):
    """The same real submit past half of a budget is accepted.

    The loop runs no extra dry run there: the stub sees only the real
    submit.
    """
    late_turn = config.MAX_TURNS // 2 + 5
    run_dir = make_run()
    push = {"code": PUSH_CODES[0], "field": "references",
            "detail": "measure a second thing of known size"}
    validator = _part11_like_validator(run_dir, push=push)
    script = _thinking(stub_responses, late_turn - 1)
    script.append(stub_responses["completed"](
        "submit late", [_submit_call(stub_responses, dry_run=False,
                                     call_id="call-late")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark, validator=validator)
    assert out["status"] == "submitted"
    assert [c["dry_run"] for c in validator.calls] == [False]
    assert _dry_run_count(run_dir) == 0
    log_text = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8")
    assert "Time remains" not in log_text


def test_loop_real_submit_without_pushes_accepted_early(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """A real submit whose dry run gives no pushes is accepted early."""
    early_turn = min(20, config.MAX_TURNS // 2 - 1)
    run_dir = make_run()
    validator = _part11_like_validator(run_dir, push=None)
    script = _thinking(stub_responses, early_turn - 1)
    script.append(stub_responses["completed"](
        "submit", [_submit_call(stub_responses, dry_run=False,
                                call_id="call-submit")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark, validator=validator)
    assert out["status"] == "submitted"
    assert [c["dry_run"] for c in validator.calls][-1] is False
    log_text = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8")
    assert "Time remains" not in log_text

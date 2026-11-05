# generated from brief/06 · part 06 owns this file
"""Dispatch behaviour: bad arguments, blind isolation, repeat rules,
submit accounting (part 06 addenda, second/fourth/fifth live runs)."""

from __future__ import annotations

import json

import pytest

from src import config


#: Dry runs carry a real measurement (a segment with frames): the
#: loop refuses a placeholder dry run (part 06 addendum 2026-10-31),
#: so a test that needs a dry run to reach the validator submits
#: this. Real submits keep the bare ``{"a": 1}`` — the refusal is
#: dry-run-only.
_MEASURED_DRY_EVIDENCE = {"segments": [{"frames": {"start": 1, "apex": 5,
                                                   "end": 9}}]}


def _submit_call(stub_responses, evidence=None, dry_run=False,
                 call_id="call-submit"):
    if evidence is None:
        evidence = (dict(_MEASURED_DRY_EVIDENCE) if dry_run else {"a": 1})
    return stub_responses["call"](
        "submit", {"evidence": evidence, "evidence_path": None,
                   "dry_run": dry_run},
        call_id)


def _rendered_of(run_dir, name):
    lines = (run_dir / "logs" / "loop.jsonl").read_text(
        encoding="utf-8").splitlines()
    return [tc.get("rendered", "")
            for entry in (json.loads(line) for line in lines)
            for tc in entry.get("tool_calls", [])
            if tc.get("rendered") and tc.get("name") == name]


def test_loop_bad_arguments_run_python_empty_continues(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """``run_python`` with ``{}`` gets ``bad_arguments`` and the run
    goes on (second live run)."""
    run_dir = make_run()
    spark = script_spark([
        stub_responses["completed"](
            "oops", [stub_responses["call"]("run_python", {},
                                            "call-1")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-2")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert out["turns"] == 2
    rendered = _rendered_of(run_dir, "run_python")
    assert len(rendered) == 1
    assert "bad_arguments" in rendered[0]


def test_loop_blind_calls_get_no_history(
        script_spark, stub_responses, drive_loop, make_run,
        accepting_validator):
    """Blind checks receive only image, extents and question — no run
    context by construction (§7)."""
    run_dir = make_run()
    (run_dir / "artifacts" / "shot.png").write_bytes(b"not-a-png-pad")
    blind_inputs: list = []

    def _blind(request):
        blind_inputs.append(request)
        return {"description": "covers the left half",
                "alternatives": ["could include the rim"]}

    spark = script_spark([
        stub_responses["completed"](
            "check", [stub_responses["call"](
                "check_mask",
                {"overlay_artifact": "artifacts/shot.png",
                 "extents": None}, "call-1")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-2")]),
    ])
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir),
                     blind_spark_client=_blind)
    assert out["status"] == "submitted"
    assert len(blind_inputs) == 1
    assert set(blind_inputs[0]) == {"image", "extents", "question"}
    assert "call-1" not in json.dumps(blind_inputs[0], default=str)


def test_loop_repeated_failures_noticed_then_closed(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """The same identical failure three times draws the notice; after
    five the tool is closed for the run (second live run)."""
    import src.tools.run_python as run_python_mod
    from src.tools.result import err_result
    invocations: list = []

    def _always_fails(run_dir, turn, **kwargs):
        invocations.append(dict(kwargs))
        return err_result("boom", "same detail every time")

    monkeypatch.setattr(run_python_mod, "run_python", _always_fails)
    run_dir = make_run()
    script = []
    for turn in range(1, 7):
        script.append(stub_responses["completed"](
            f"trying code {turn}",
            [stub_responses["call"]("run_python",
                                    {"code": f"print({turn})"},
                                    f"call-{turn}")]))
    script.append(stub_responses["completed"](
        "done", [_submit_call(stub_responses, call_id="call-submit")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    rendered = _rendered_of(run_dir, "run_python")
    assert len(rendered) == 6
    assert "stop calling it" not in rendered[0]
    assert "stop calling it" not in rendered[1]
    assert "stop calling it" in rendered[2]
    assert "stop calling it" in rendered[3]
    assert "stop calling it" in rendered[4]
    assert len(invocations) == 5
    assert "closed" in rendered[5]


def test_loop_different_details_do_not_count_as_repeated(
        script_spark, stub_responses, drive_loop, make_run, monkeypatch,
        accepting_validator):
    """A failure counts as repeated only when code and detail match
    (fifth live run): varying details never close the tool."""
    import src.tools.run_python as run_python_mod
    from src.tools.result import err_result
    invocations: list = []

    def _varies(run_dir, turn, **kwargs):
        invocations.append(dict(kwargs))
        return err_result("boom", f"detail attempt {len(invocations)}")

    monkeypatch.setattr(run_python_mod, "run_python", _varies)
    run_dir = make_run()
    script = []
    for turn in range(1, 6):
        script.append(stub_responses["completed"](
            f"trying code {turn}",
            [stub_responses["call"]("run_python",
                                    {"code": f"print({turn})"},
                                    f"call-{turn}")]))
    script.append(stub_responses["completed"](
        "done", [_submit_call(stub_responses, call_id="call-submit")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert len(invocations) == 5
    for text in _rendered_of(run_dir, "run_python"):
        assert "stop calling it" not in text
        assert "closed" not in text


def test_loop_submit_exempt_from_repeat_rule(
        script_spark, stub_responses, drive_loop, make_run,
        rejecting_validator):
    """Five rejected dry runs with shrinking error lists leave submit
    open; the next real attempt still runs (fifth live run)."""
    run_dir = make_run()
    error_lists = [
        [{"code": f"E{n}", "field": "evidence",
          "detail": f"problem {n}"} for n in range(5 - turn)]
        for turn in range(5)
    ]
    validator = rejecting_validator(run_dir, error_lists)
    script = [stub_responses["completed"](
        f"dry {n}", [_submit_call(stub_responses, dry_run=True,
                                  call_id=f"call-dry-{n}")])
        for n in range(5)]
    script.append(stub_responses["completed"](
        "real", [_submit_call(stub_responses, dry_run=False,
                              call_id="call-real")]))
    spark = script_spark(script)
    out = drive_loop(run_dir, spark, validator=validator)
    assert out["status"] == "submitted"
    # The early real submit is first validated as a dry run (part 06
    # addendum 2026-11-02, second): five dry runs plus the extra probe
    # plus the real submit.
    assert [c["dry_run"] for c in validator.calls] == (
        [True] * 6 + [False])
    for text in _rendered_of(run_dir, "submit"):
        assert "closed" not in text


def test_loop_dry_run_does_not_consume_attempts(
        script_spark, stub_responses, drive_loop, make_run,
        rejecting_validator):
    """Dry runs validate without consuming attempts; later real rejects
    still get their three tries (fourth live run)."""
    run_dir = make_run()
    validator = rejecting_validator(
        run_dir, [[{"code": "E1", "field": "evidence", "detail": "x"}],
                  [{"code": "E1", "field": "evidence", "detail": "x"}]])
    spark = script_spark([
        stub_responses["completed"](
            "dry", [_submit_call(stub_responses, dry_run=True,
                                 call_id="call-dry")]),
        stub_responses["completed"](
            "dry again", [_submit_call(stub_responses, dry_run=True,
                                       call_id="call-dry-2")]),
        stub_responses["completed"](
            "real", [_submit_call(stub_responses, dry_run=False,
                                  call_id="call-real")]),
    ])
    out = drive_loop(run_dir, spark, validator=validator)
    assert out["status"] == "submitted"
    # The early real submit carries its extra dry-run probe first.
    assert [c["dry_run"] for c in validator.calls] == [
        True, True, True, False]


def test_loop_rejected_submit_renders_all_errors(
        script_spark, stub_responses, drive_loop, make_run,
        rejecting_validator):
    """A rejected submit renders every error code and field in the text
    the agent receives (fourth live run)."""
    run_dir = make_run()
    errors = [{"code": f"E{n}", "field": f"field_{n}",
               "detail": f"detail {n}"} for n in range(1, 4)]
    # Two copies: the early extra dry-run probe sees the same hard
    # errors as the real submit it guards.
    validator = rejecting_validator(run_dir, [errors, errors])
    spark = script_spark([
        stub_responses["completed"](
            "try", [_submit_call(stub_responses, call_id="call-1")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-2")]),
    ])
    out = drive_loop(run_dir, spark, validator=validator)
    assert out["status"] == "submitted"
    rendered = _rendered_of(run_dir, "submit")
    assert len(rendered) == 1
    for n in range(1, 4):
        assert f"E{n}" in rendered[0]
        assert f"field_{n}" in rendered[0]
        assert f"detail {n}" in rendered[0]


def test_loop_three_rejected_submits_end_valid(
        script_spark, stub_responses, drive_loop, make_run,
        rejecting_validator):
    """Three rejected real submits end the run as a valid undetermined
    file with the last error list recorded (§2)."""
    from src.contract import validate_result
    run_dir = make_run()
    errors = [{"code": "E9", "field": "evidence", "detail": "nope"}]
    # Each early real submit is preceded by its extra dry-run probe,
    # so three real attempts need six queued rejections.
    validator = rejecting_validator(
        run_dir, [errors, errors, errors, errors, errors, errors])
    spark = script_spark([
        stub_responses["completed"](
            f"try {n}", [_submit_call(stub_responses,
                                      call_id=f"call-{n}")])
        for n in range(1, 6)
    ])
    out = drive_loop(run_dir, spark, validator=validator)
    assert out["status"] == "undetermined"
    assert len(validator.calls) == 6
    assert [c["dry_run"] for c in validator.calls] == [
        True, False, True, False, True, False]
    result = json.loads((run_dir / "result.json").read_text(
        encoding="utf-8"))
    assert validate_result(result) == []
    assert result["verdict"]["kind"] == "undetermined"
    last = json.loads(
        (run_dir / "logs" / "validator_last_errors.json").read_text(
            encoding="utf-8"))
    assert last == errors


def test_loop_mask_checks_exhausted_closes_tool(
        script_spark, stub_responses, drive_loop, make_run, make_ledger,
        accepting_validator):
    """An exhausted per-tool budget closes only that tool; the run goes
    on to its next turn (fifth live run)."""
    run_dir = make_run()
    ledger = make_ledger("r", run_dir)
    ledger.mask_checks = config.MAX_MASK_CHECKS
    spark = script_spark([
        stub_responses["completed"](
            "check", [stub_responses["call"](
                "check_mask",
                {"overlay_artifact": "artifacts/shot.png",
                 "extents": None}, "call-1")]),
        stub_responses["completed"](
            "done", [_submit_call(stub_responses, call_id="call-2")]),
    ])
    out = drive_loop(run_dir, spark, ledger=ledger,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    assert out["turns"] == 2
    rendered = _rendered_of(run_dir, "check_mask")
    assert len(rendered) == 1
    assert "closed" in rendered[0]
    assert "mask-check" in rendered[0]

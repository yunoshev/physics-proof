# generated from brief/11 · part 11 owns this file
"""The loop's own submit (brief §23: the `not finished` synthesis)."""

import json


def test_rejected_loop_submit_gives_not_finished(tmp_path):
    from src.contract import validate_result
    from src.validate import synthesize_undetermined

    run_dir = tmp_path / "run"
    errors = [
        {"code": "SECOND_REFERENCE_SAME_OBJECT",
         "field": "references[1].mask",
         "detail": "references[0].mask covers frame 10, "
                   "references[1].mask covers frame 20; the two masks "
                   "cannot be loaded on a common frame: segment one "
                   "of them again on frames that overlap the other"},
        {"code": "SECOND_REFERENCE_ABSENT_UNEXPLAINED",
         "field": "scale.second_reference_absent_reason",
         "detail": "scale rests on one reference with no reason: name "
                   "second_reference_absent_reason, or add a second "
                   "reference of a different thing"},
        {"code": "CLOCK_LOGIC", "field": "clock",
         "detail": "a third problem that must not appear"},
    ]
    result = synthesize_undetermined(str(run_dir), "run-n",
                                     "not finished",
                                     errors=list(errors))
    assert validate_result(result) == []
    assert result["verdict"]["kind"] == "undetermined"
    reason = result["verdict"]["reason"]
    assert reason.startswith("not finished: "), reason
    assert "third problem" not in reason
    assert result["sentence"].startswith(
        "Undetermined: not finished — "), result["sentence"]
    back = json.loads((run_dir / "logs"
                       / "validator_last_errors.json").read_text(
                           encoding="utf-8"))
    assert back == errors


def test_budget_reason_unchanged(tmp_path):
    from src.validate import synthesize_undetermined

    run_dir = tmp_path / "run"
    result = synthesize_undetermined(str(run_dir), "run-b", "budget")
    assert result["verdict"]["reason"].startswith("budget")
    assert result["sentence"].startswith("Undetermined: budget")

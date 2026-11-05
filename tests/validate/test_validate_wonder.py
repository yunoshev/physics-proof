# generated from brief/11 · part 11 owns this file
"""The plan travels to the page (brief §§21, 23)."""

import copy
import json


def _wonder():
    return {
        "question": "Could a person really run straight up a wall?",
        "claim": "a person runs straight up a tall wall",
        "checks": [
            {"what": "measure the climb's apparent gravity",
             "why": "a parabola separates climbing from falling",
             "compare_with": "Earth's 9.81 m/s2"},
        ],
        "realistic_if": "the motion fits a climb at real speed",
        "not_realistic_if": "no world or speed explains the motion",
    }


def test_assembled_result_carries_wonder(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    wonder = _wonder()
    (run_dir / "artifacts" / "wonder.json").write_text(
        json.dumps(wonder), encoding="utf-8")
    report = validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["first_look"]["wonder"] == {
        "claim": wonder["claim"], "checks": wonder["checks"],
        "realistic_if": wonder["realistic_if"],
        "not_realistic_if": wonder["not_realistic_if"]}


def test_assembled_result_without_plan_has_null_wonder(
        baseline, tmp_path):
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["first_look"]["wonder"] is None


def test_synthesised_budget_carries_question_and_plan(tmp_path):
    from src.contract import validate_result
    from src.validate import synthesize_undetermined

    run_dir = tmp_path / "run"
    (run_dir / "artifacts").mkdir(parents=True)
    wonder = _wonder()
    (run_dir / "artifacts" / "wonder.json").write_text(
        json.dumps(wonder), encoding="utf-8")
    result = synthesize_undetermined(str(run_dir), "run-w", "budget")
    assert validate_result(result) == []
    assert result["first_look"]["question"] == wonder["question"]
    assert result["first_look"]["wonder"]["claim"] == wonder["claim"]


def test_synthesised_budget_without_plan_falls_back(tmp_path):
    from src.validate import synthesize_undetermined

    run_dir = tmp_path / "run"
    result = synthesize_undetermined(str(run_dir), "run-w", "budget")
    assert result["first_look"]["question"] == \
        "Does the physics add up?"
    assert result["first_look"]["wonder"] is None

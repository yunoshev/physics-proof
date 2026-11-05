# generated from brief/11 · part 11 owns this file
"""Hard errors before pushes in a dry run's reply (brief §25)."""

import copy


def _one_hard_one_push(evidence):
    """Single reference (push) plus a broken error budget (hard)."""
    bad = copy.deepcopy(evidence)
    bad["references"] = bad["references"][:1]
    bad["scale"]["second_reference_index"] = None
    bad["scale"]["second_reference_absent_reason"] = \
        "only one thing of known size at the depth of the motion"
    bad["error_budget"]["components"] = [
        comp for comp in bad["error_budget"]["components"]
        if comp.get("name") != "fit"]
    return bad


def test_dry_run_lists_hard_errors_before_pushes(baseline, tmp_path):
    from src.validate import (
        DRY_RUN_HARD_HEADER,
        DRY_RUN_PUSH_HEADER,
        validate,
    )

    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = validate(_one_hard_one_push(evidence), dict(ctx),
                      dry_run=True)
    assert report["accepted"] is False
    codes = [e["code"] for e in report["errors"]]
    assert "ERROR_BUDGET_INCOMPLETE" in codes
    assert "SECOND_REFERENCE_REQUIRED" in codes
    assert (codes.index("ERROR_BUDGET_INCOMPLETE")
            < codes.index("SECOND_REFERENCE_REQUIRED"))
    pushes = [e for e in report["errors"]
              if e["code"] == "SECOND_REFERENCE_REQUIRED"]
    assert pushes and all(p.get("push") is True for p in pushes)
    hard = [e for e in report["errors"]
            if e["code"] == "ERROR_BUDGET_INCOMPLETE"]
    assert hard and all("push" not in h for h in hard)
    reply = report["reply"]
    assert DRY_RUN_HARD_HEADER in reply
    assert DRY_RUN_PUSH_HEADER in reply
    assert reply.index(DRY_RUN_HARD_HEADER) < reply.index(
        DRY_RUN_PUSH_HEADER)
    assert reply.index("ERROR_BUDGET_INCOMPLETE") < reply.index(
        DRY_RUN_PUSH_HEADER)
    assert reply.index("SECOND_REFERENCE_REQUIRED") > reply.index(
        DRY_RUN_PUSH_HEADER)


def test_dry_run_reply_sections_only_when_present(baseline, tmp_path):
    from src.validate import format_dry_run_reply, validate

    assert format_dry_run_reply([]) == ""
    evidence, _run, ctx, _produced = baseline(tmp_path)
    # A reference on the moving thing, or the dry run lists the
    # SELF_REFERENCE_REQUIRED push (brief §53, R-S16).
    evidence["references"][1]["mask"] = {
        "artifact": "artifacts/masks_all.npz", "object_id": "0",
        "frame": 10,
        "outline": [[100.0, 20.0], [271.0, 20.0],
                    [271.0, 191.0], [100.0, 191.0]]}
    clean = validate(copy.deepcopy(evidence), dict(ctx), dry_run=True)
    assert clean["accepted"] is True, clean["errors"]
    assert clean["errors"] == []
    assert clean["reply"] == ""

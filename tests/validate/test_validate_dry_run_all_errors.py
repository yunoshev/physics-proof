# generated from brief/11 · part 11 owns this file
"""One dry run reports every error at once (brief §30).

A push such as ``SECOND_REFERENCE_REQUIRED`` never replaces the
per-reference checks: mask check present and real, alternatives
answered, extents on the mask, source quote in the search. Errors
come first, pushes after.
"""

import copy
import json


def _single_ref(evidence):
    evidence = copy.deepcopy(evidence)
    evidence["references"] = evidence["references"][:1]
    evidence["scale"]["second_reference_index"] = None
    evidence["scale"]["second_reference_absent_reason"] = \
        "only one thing of known size at the depth of the motion"
    return evidence


def test_fabricated_mask_check_and_push_together(baseline, tmp_path):
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = _single_ref(evidence)
    # The agent pointed its mask check at a segment preview instead
    # of a check_mask artifact, with a typed coverage answer.
    bad["references"][0]["mask_check"]["artifact"] = \
        "artifacts/view_0.jpg"
    bad["references"][0]["mask_check"]["coverage_answer"] = \
        "covers the whole block"
    report = validate(bad, dict(ctx), dry_run=True)
    assert report["accepted"] is False
    codes = [e["code"] for e in report["errors"]]
    assert "MASK_CHECK_MISSING" in codes, report["errors"]
    assert "SECOND_REFERENCE_REQUIRED" in codes, report["errors"]
    assert (codes.index("MASK_CHECK_MISSING")
            < codes.index("SECOND_REFERENCE_REQUIRED"))
    missing = [e for e in report["errors"]
               if e["code"] == "MASK_CHECK_MISSING"]
    assert missing[0]["field"].startswith("references[0]"), \
        report["errors"]


def test_unanswered_alternatives_and_push_together(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    # The same evidence with a real mask check whose blind
    # alternatives are unanswered.
    check_path = run_dir / "artifacts" / "check_a.json"
    check = json.loads(check_path.read_text(encoding="utf-8"))
    check["alternatives"] = [
        "a smaller upper block stacked on top of a larger lower "
        "block",
        "the figure's legs below the measured extent",
    ]
    check_path.write_text(json.dumps(check), encoding="utf-8")
    bad = _single_ref(evidence)
    report = validate(bad, dict(ctx), dry_run=True)
    assert report["accepted"] is False
    codes = [e["code"] for e in report["errors"]]
    assert "ALTERNATIVE_NOT_ADDRESSED" in codes, report["errors"]
    assert "SECOND_REFERENCE_REQUIRED" in codes, report["errors"]
    assert (codes.index("ALTERNATIVE_NOT_ADDRESSED")
            < codes.index("SECOND_REFERENCE_REQUIRED"))

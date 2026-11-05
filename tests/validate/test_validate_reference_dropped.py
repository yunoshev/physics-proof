# generated from brief/11 · part 11 owns this file
"""A reference is not dropped to escape a disagreement (brief §37).

When an earlier dry run carried two references and a dry run
reported the disagreement, the final evidence may not rest on one
reference with a ``second_reference_absent_reason``.
"""

import copy
import json


def _write_earlier(run_dir, produced, name, value):
    rel = f"artifacts/{name}"
    target = run_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value), encoding="utf-8")
    if rel not in produced:
        produced.append(rel)
    return rel


def _two_ref_evidence(evidence):
    """Earlier evidence with two disagreeing references."""
    early = copy.deepcopy(evidence)
    first = early["references"][0]
    first["name"] = "backpack height"
    first["size_m"] = 0.66
    first["size_tolerance_m"] = 0.02
    first["extent_px"] = {"x1": 20.0, "y1": 20.0, "x2": 20.0,
                          "y2": 88.0, "length_px": 68.0, "frame": 10}
    second = early["references"][1]
    second["name"] = "suited height"
    second["size_m"] = 1.7
    second["size_tolerance_m"] = 0.02
    second["extent_px"] = {"x1": 100.0, "y1": 20.0, "x2": 100.0,
                           "y2": 164.0, "length_px": 144.0,
                           "frame": 10}
    return early


def _moon23_run(baseline, tmp_path, codes):
    """Final one-reference evidence plus disagreeing dry runs."""
    from src.validate import validate  # noqa: F401

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    early = _two_ref_evidence(evidence)
    _write_earlier(run_dir, produced, "t20_evidence.json", early)
    _write_earlier(run_dir, produced, "t20_submit_errors.json", [
        {"code": code, "field": "references",
         "detail": "scale disagreement reported"} for code in codes])
    ctx = dict(ctx, artifacts=sorted(
        {*ctx.get("artifacts", []),
         "artifacts/t20_evidence.json",
         "artifacts/t20_submit_errors.json"}),
        produced_files=list(produced))
    final = copy.deepcopy(evidence)
    final["references"] = [copy.deepcopy(early["references"][0])]
    final["scale"]["second_reference_index"] = None
    final["scale"]["second_reference_absent_reason"] = (
        "suited height was posture-biased fourteen percent off "
        "the backpack scale")
    return final, ctx


def test_dropped_reference_after_reported_disagreement_refused(
        baseline, tmp_path):
    # Moon run 23: two references disagreed, the dry runs reported
    # THIRD_REFERENCE_REQUIRED, and the final submit kept only the
    # backpack. Refused with REFERENCE_DROPPED.
    from src.validate import validate

    final, ctx = _moon23_run(baseline, tmp_path,
                             ["THIRD_REFERENCE_REQUIRED"])
    dry = validate(copy.deepcopy(final), dict(ctx), dry_run=True)
    assert dry["accepted"] is False, dry["errors"]
    matches = [e for e in dry["errors"]
               if e.get("code") == "REFERENCE_DROPPED"]
    assert matches, dry["errors"]
    detail = matches[0]["detail"]
    assert "suited height" in detail, detail
    assert "t20_evidence.json" in detail, detail
    # A real submit is refused too, not accepted as undetermined.
    real = validate(copy.deepcopy(final), dict(ctx))
    assert real["accepted"] is False, real["errors"]
    assert any(e.get("code") == "REFERENCE_DROPPED"
               for e in real["errors"]), real["errors"]


def test_disagreement_report_also_triggers(baseline, tmp_path):
    from src.validate import validate

    final, ctx = _moon23_run(baseline, tmp_path,
                             ["REFERENCES_DISAGREE"])
    dry = validate(copy.deepcopy(final), dict(ctx), dry_run=True)
    assert any(e.get("code") == "REFERENCE_DROPPED"
               for e in dry["errors"]), dry["errors"]


def test_absence_reason_stands_without_earlier_reference(
        baseline, tmp_path):
    # A run that never measured a second reference may still state
    # an absence reason, as before.
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    final = copy.deepcopy(evidence)
    final["references"] = [copy.deepcopy(final["references"][0])]
    final["scale"]["second_reference_index"] = None
    final["scale"]["second_reference_absent_reason"] = (
        "only one thing of known size at the depth of the motion")
    report = validate(final, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert not any(e.get("code") == "REFERENCE_DROPPED"
                   for e in report["errors"]), report["errors"]
    assert "one reference" in (
        report["result"]["verdict"]["reason"] or ""), \
        report["result"]["verdict"]

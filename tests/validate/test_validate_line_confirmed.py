# generated from brief/11 · part 11 owns this file
"""A line the second look rejected is never used (brief §36).

Every measured reference or scale line that has a ``check_line``
record must have a confirming one. Range-check extents keep §28's
stronger rule and are not rechecked here.
"""

import copy
import json


def _write_journal(run_dir, ctx, records):
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    for rel in ("artifacts/line_checks.jsonl",):
        if rel not in ctx["artifacts"]:
            ctx["artifacts"].append(rel)
    ctx["artifacts"].sort()
    if "artifacts/line_checks.jsonl" not in ctx["produced_files"]:
        ctx["produced_files"].append("artifacts/line_checks.jsonl")


def _record(frame, x1, y1, x2, y2, agrees, description):
    return {"frame": frame,
            "lines": [{"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                       "claim": "reference block height",
                       "description": description,
                       "agrees": agrees,
                       "why": "the description matches the claim"}],
            "overlay_artifact": "artifacts/t1_check_line_0.png",
            "turn": 1}


def _refusal(baseline, tmp_path, records):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    _write_journal(run_dir, ctx, records)
    return validate(copy.deepcopy(evidence), ctx, dry_run=True)


def test_disagreeing_reference_line_refused(baseline, tmp_path):
    # The wall-run-16 shape: the only scale reference was checked
    # with check_line and the blind look did not confirm it.
    report = _refusal(
        baseline, tmp_path,
        [_record(10, 20.0, 20.0, 20.0, 86.0, False,
                "the line crosses the empty floor")])
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e.get("code") == "LINE_NOT_CONFIRMED"]
    assert matches, report["errors"]
    fields = {e["field"] for e in matches}
    assert "references[0].extent_px" in fields, fields
    detail = [e for e in matches
              if e["field"] == "references[0].extent_px"][0]["detail"]
    assert "the line crosses the empty floor" in detail, detail


def test_later_agreeing_record_passes(baseline, tmp_path):
    # When a later record for that line agrees, the evidence passes:
    # the agent re-measured and checked again.
    report = _refusal(
        baseline, tmp_path,
        [_record(10, 20.0, 20.0, 20.0, 86.0, False,
                "the line crosses the empty floor"),
         _record(10, 20.0, 20.0, 20.0, 86.0, True,
                "the line runs along the block")])
    assert not any(e.get("code") == "LINE_NOT_CONFIRMED"
                   for e in report["errors"]), report["errors"]


def test_reference_without_record_passes(baseline, tmp_path):
    # Evidence with no check_line record for a reference passes as
    # before: only a rejected line is refused.
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = validate(copy.deepcopy(evidence), dict(ctx), dry_run=True)
    assert not any(e.get("code") == "LINE_NOT_CONFIRMED"
                   for e in report["errors"]), report["errors"]

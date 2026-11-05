# generated from brief/11 · part 11 owns this file
"""Every reference line is confirmed blind (brief §50).

Every reference's ``extent_px`` needs a ``check_line`` record of
this run matching it as §28 says (the same frame, both endpoints
within 2 px) with ``agrees: true`` and a ``dimension`` other than
``"unclear"`` (part 07 §22). Seen: Moon run
``20261102T133200Z-4cd1c236`` used a suited-figure width line and an
unconfirmed pack line; both wrong sizes agreed and the verdict said
"slowed down ×1.16".
"""

import copy
import json


def _without_journal(run_dir, ctx):
    """A context whose run has no ``check_line`` journal at all."""
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    if journal.exists():
        journal.unlink()
    ctx = dict(ctx)
    ctx["artifacts"] = [rel for rel in ctx["artifacts"]
                        if rel != "artifacts/line_checks.jsonl"]
    ctx["produced_files"] = [rel for rel in ctx["produced_files"]
                             if rel != "artifacts/line_checks.jsonl"]
    return ctx


def _write_records(run_dir, ctx, records):
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    if journal.exists():
        journal.unlink()
    with journal.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    if "artifacts/line_checks.jsonl" not in ctx["artifacts"]:
        ctx["artifacts"] = sorted(
            ctx["artifacts"] + ["artifacts/line_checks.jsonl"])
    if "artifacts/line_checks.jsonl" not in ctx["produced_files"]:
        ctx["produced_files"] = list(ctx["produced_files"]) + [
            "artifacts/line_checks.jsonl"]


def _record(frame, x1, y1, x2, y2, agrees=True, dimension="height",
            claim="height of the thing",
            description="the line runs along the thing"):
    return {"frame": frame,
            "lines": [{"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                       "claim": claim, "description": description,
                       "view": "side", "dimension": dimension,
                       "agrees": agrees,
                       "why": "the description matches the claim"}],
            "overlay_artifact": "artifacts/t1_check_line_0.png",
            "turn": 1}


def _run_4cd1c236_lines(evidence):
    """Moon run 4cd1c236's final shape: two unconfirmed lines."""
    evidence = copy.deepcopy(evidence)
    pack, figure = evidence["references"][:2]
    pack["name"] = "white pack"
    pack["extent_px"] = {"x1": 84.0, "y1": 65.0, "x2": 94.0,
                         "y2": 132.0, "length_px": 67.0, "frame": 234}
    figure["name"] = "suited figure width"
    figure["extent_px"] = {"x1": 69.0, "y1": 105.0, "x2": 148.0,
                           "y2": 70.0, "length_px": 86.4, "frame": 234}
    return evidence


def test_two_unconfirmed_references_refused(baseline, tmp_path):
    # Run 4cd1c236's final evidence: neither line has a check_line
    # record, so both references are refused.
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    bad = _run_4cd1c236_lines(evidence)
    ctx = _without_journal(run_dir, ctx)
    report = validate(bad, ctx, dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_LINE_NOT_CONFIRMED"]
    assert len(matches) == 2, report["errors"]
    fields = {e["field"] for e in matches}
    assert fields == {"references[0].extent_px",
                      "references[1].extent_px"}, fields
    for error in matches:
        assert "check_line" in error["detail"], error["detail"]
        assert "dimension" in error["detail"], error["detail"]
        assert "(R-S17)" in error["detail"], error["detail"]


def test_matching_record_with_named_dimension_passes(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = _run_4cd1c236_lines(evidence)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    _write_records(run_dir, ctx, [
        _record(234, 84.0, 65.0, 94.0, 132.0, agrees=True,
                dimension="height",
                claim="height of the white pack",
                description="the line runs along the white pack"),
        _record(234, 69.0, 105.0, 148.0, 70.0, agrees=True,
                dimension="width",
                claim="width of the suited figure",
                description="the line runs across the suited figure"),
    ])
    report = validate(good, ctx, dry_run=True)
    assert not any(e["code"] == "REFERENCE_LINE_NOT_CONFIRMED"
                   for e in report["errors"]), report["errors"]


def test_unclear_dimension_refused(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    bad = _run_4cd1c236_lines(evidence)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    _write_records(run_dir, ctx, [
        _record(234, 84.0, 65.0, 94.0, 132.0, agrees=True,
                dimension="height",
                claim="height of the white pack",
                description="the line runs along the white pack"),
        _record(234, 69.0, 105.0, 148.0, 70.0, agrees=True,
                dimension="unclear",
                claim="width of the suited figure",
                description="the line runs across the suited figure"),
    ])
    report = validate(bad, ctx, dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_LINE_NOT_CONFIRMED"]
    assert len(matches) == 1, report["errors"]
    assert matches[0]["field"] == "references[1].extent_px"
    assert "unclear" in matches[0]["detail"], matches[0]["detail"]
    assert "check_line" in matches[0]["detail"], matches[0]["detail"]


def test_record_three_px_off_refused(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    bad = _run_4cd1c236_lines(evidence)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    # One endpoint 3 px off the measured line: no match (§28's 2 px).
    _write_records(run_dir, ctx, [
        _record(234, 84.0, 65.0, 94.0, 132.0, agrees=True,
                dimension="height",
                claim="height of the white pack",
                description="the line runs along the white pack"),
        _record(234, 69.0, 108.0, 148.0, 70.0, agrees=True,
                dimension="width",
                claim="width of the suited figure",
                description="the line runs across the suited figure"),
    ])
    report = validate(bad, ctx, dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_LINE_NOT_CONFIRMED"]
    assert len(matches) == 1, report["errors"]
    assert matches[0]["field"] == "references[1].extent_px"


def test_disagreeing_reference_record_refused(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    bad = _run_4cd1c236_lines(evidence)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    _write_records(run_dir, ctx, [
        _record(234, 84.0, 65.0, 94.0, 132.0, agrees=True,
                dimension="height",
                claim="height of the white pack",
                description="the line runs along the white pack"),
        _record(234, 69.0, 105.0, 148.0, 70.0, agrees=False,
                dimension="depth",
                claim="width of the suited figure",
                description="the line crosses the empty floor"),
    ])
    report = validate(bad, ctx, dry_run=True)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_LINE_NOT_CONFIRMED"]
    assert len(matches) == 1, report["errors"]
    assert matches[0]["field"] == "references[1].extent_px"
    assert "empty floor" in matches[0]["detail"], matches[0]["detail"]

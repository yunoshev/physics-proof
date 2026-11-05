# generated from brief/11 · part 11 owns this file
"""The example is not the clip (brief §23: EXAMPLE_VALUE_COPIED)."""

import copy


def test_example_reference_name_rejected(baseline, tmp_path):
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["references"][0]["name"] = "backpack height"
    dry = validate(bad, dict(ctx), dry_run=True)
    assert dry["accepted"] is False
    assert any(e["code"] == "EXAMPLE_VALUE_COPIED"
               and e["field"] == "references[0].name"
               for e in dry["errors"]), dry["errors"]
    real = validate(copy.deepcopy(bad), dict(ctx))
    assert real["accepted"] is False
    assert any(e["code"] == "EXAMPLE_VALUE_COPIED"
               for e in real["errors"]), real["errors"]


def test_example_source_url_rejected(baseline, tmp_path):
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["references"][0]["sources"][0]["url"] = \
        "https://example.com/pack"
    report = validate(bad, dict(ctx), dry_run=True)
    assert report["accepted"] is False
    assert any(e["code"] == "EXAMPLE_VALUE_COPIED"
               for e in report["errors"]), report["errors"]


def test_own_records_excuse_the_name(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    (run_dir / "workspace" / "t3_run_python_0.py").write_text(
        "# measures the backpack height from the mask\n", encoding="utf-8")
    ctx["produced_files"].append("workspace/t3_run_python_0.py")
    bad = copy.deepcopy(evidence)
    bad["references"][0]["name"] = "backpack height"
    report = validate(bad, ctx, dry_run=True)
    assert not any(e["code"] == "EXAMPLE_VALUE_COPIED"
                   for e in report["errors"]), report["errors"]

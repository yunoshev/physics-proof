# generated from brief/11 · part 11 owns this file
"""Digit-free prose and the self-built registry (V12)."""

import copy
import json


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def test_digits_in_caption_rejected(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["segments"][0]["key_moments"][0]["caption"] = \
        "leaving the ground at frame 30"
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "UNMEASURED_NUMBER_IN_TEXT"
               and "caption" in e["field"] for e in report["errors"])


def test_digits_in_page_texts_rejected(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["page_texts"] = {"heading": "Jump 1 results"}
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "UNMEASURED_NUMBER_IN_TEXT"
               and e["field"] == "page_texts.heading"
               for e in report["errors"])


def test_placeholders_unaffected(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["page_texts"] = {"heading": "Measured on {world}: {g}"}
    good["segments"][0]["key_moments"][0]["caption"] = \
        "leaving the ground at {g}"
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]


def _register(run_dir, name, status="passed", digest=None):
    import hashlib

    module = run_dir / "workspace" / "selfbuilt" / f"{name}.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("VALUE = 1\n", encoding="utf-8")
    stem = name[3:] if name.startswith("sb_") else name
    test = run_dir / "workspace" / "selfbuilt" / f"test_sb_{stem}.py"
    test.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    module_sha = hashlib.sha256(
        module.read_bytes()).hexdigest()
    test_sha = hashlib.sha256(test.read_bytes()).hexdigest()
    registry = {"tools": [{
        "name": name,
        "module_sha256": digest if digest is not None else module_sha,
        "test_sha256": test_sha,
        "attempts": 1,
        "status": status,
        "purpose": "test helper",
        "registered_at_turn": 1}]}
    reg = run_dir / "workspace" / "selfbuilt" / "registry.json"
    reg.write_text(json.dumps(registry), encoding="utf-8")
    return f"workspace/selfbuilt/{name}.py"


def test_registered_tool_passes(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    rel = _register(run_dir, "sb_hop")
    good["provenance"]["artifacts"].append(
        {"name": "self-built hop tool", "path": rel})
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]


def test_unregistered_tool_rejected(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    module = run_dir / "workspace" / "selfbuilt" / "sb_ghost.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("VALUE = 2\n", encoding="utf-8")
    bad["provenance"]["artifacts"].append(
        {"name": "self-built ghost tool",
         "path": "workspace/selfbuilt/sb_ghost.py"})
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "UNMEASURED_NUMBER_IN_TEXT"
               for e in report["errors"])


def test_hash_mismatch_rejected(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    rel = _register(run_dir, "sb_hop", digest="0" * 64)
    bad["provenance"]["artifacts"].append(
        {"name": "self-built hop tool", "path": rel})
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "UNMEASURED_NUMBER_IN_TEXT"
               for e in report["errors"])

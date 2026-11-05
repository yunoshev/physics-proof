# generated from brief/11 · part 11 owns this file
"""A corrected reference settles a gap; one reference never gives a
verdict; unanswered alternatives come in one list (brief §46)."""

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


def _moon46_run(baseline, tmp_path):
    """Dry run with a disagreeing pair; final with the pack corrected.

    The dry run carries the backpack at 0.66 m (``single``) and the
    suited figure at 1.71 m on genuinely disagreeing scales. The
    final evidence corrects the pack to 0.914 m (``sum`` of the quoted
    0.66 and 0.254 m) on the same mask, and the two scales agree.
    """
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    early = copy.deepcopy(evidence)
    pack, figure = early["references"]
    pack["name"] = "backpack height"
    pack["size_m"] = 0.66
    pack["size_tolerance_m"] = 0.02
    pack["extent_px"] = {"x1": 20.0, "y1": 20.0, "x2": 20.0,
                         "y2": 78.0, "length_px": 58.0, "frame": 10}
    figure["name"] = "suited figure"
    figure["size_tolerance_m"] = 0.02
    _write_earlier(run_dir, produced, "t20_evidence.json", early)
    _write_earlier(run_dir, produced, "t20_submit_errors.json", [
        {"code": "THIRD_REFERENCE_REQUIRED", "field": "references",
         "detail": "scale disagreement reported"}])
    ctx = dict(ctx, artifacts=sorted(
        {*ctx.get("artifacts", []),
         "artifacts/t20_evidence.json",
         "artifacts/t20_submit_errors.json"}),
        produced_files=list(produced))
    # The top-unit source the corrected size sums in: quoted in the
    # run's own web search, as the reference-source rule requires.
    search_rel = "artifacts/t0_web_search_0.json"
    search = json.loads(
        (run_dir / search_rel).read_text(encoding="utf-8"))
    search["facts"].append(
        {"url": "https://example.com/ops",
         "quote": "the top unit is 25.4 cm tall",
         "text": "the top unit is 25.4 cm tall"})
    (run_dir / search_rel).write_text(json.dumps(search),
                                      encoding="utf-8")
    final = copy.deepcopy(evidence)
    fpack, ffigure = final["references"]
    fpack["name"] = "backpack with top unit"
    fpack["size_m"] = 0.914
    fpack["size_tolerance_m"] = 0.03
    fpack["extent_px"] = {"x1": 20.0, "y1": 20.0, "x2": 20.0,
                          "y2": 111.4, "length_px": 91.4,
                          "frame": 10}
    fpack["size_derivation"] = {
        "mode": "sum",
        "note": "pack plus its top unit, both quoted",
        "state_match": {
            "shown_and_covered": "pack body shown and covered",
            "shown_not_covered": "lid shown but not covered"}}
    fpack["sources"] = [
        {"url": "https://example.com/block",
         "domain": "example.com",
         "quote": "the block is 66 cm tall",
         "quote_highlight": "66 cm",
         "value_m": 0.66,
         "source_type": "catalogue"},
        {"url": "https://example.com/ops",
         "domain": "example.com",
         "quote": "the top unit is 25.4 cm tall",
         "quote_highlight": "25.4 cm",
         "value_m": 0.254,
         "source_type": "catalogue"},
    ]
    ffigure["name"] = "suited figure"
    ffigure["size_tolerance_m"] = 0.02
    # The corrected pack line needs its own blind check (§50); the
    # baseline journal covers the uncorrected extent.
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "frame": 10,
            "lines": [{"x1": 20.0, "y1": 20.0, "x2": 20.0,
                       "y2": 111.4,
                       "claim": "height of the backpack with top unit",
                       "description":
                           "the line runs along the backpack with top unit",
                       "view": "front", "dimension": "height",
                       "agrees": True,
                       "why": "the description matches the claim"}],
            "overlay_artifact": "artifacts/t1_check_line_0.png",
            "turn": 1}) + "\n")
    return final, ctx


def test_settled_reference_clears_disagreement(baseline, tmp_path):
    # The corrected pack (sum including the earlier 0.66 m, same
    # mask) settles the dry-run disagreement: no REFERENCE_DROPPED,
    # no THIRD_REFERENCE_REQUIRED, and the verdict is not
    # undetermined.
    from src.validate import validate

    final, ctx = _moon46_run(baseline, tmp_path)
    report = validate(copy.deepcopy(final), dict(ctx))
    assert report["accepted"] is True, report["errors"]
    codes = [e.get("code") for e in report["errors"]]
    assert "REFERENCE_DROPPED" not in codes, report["errors"]
    assert "THIRD_REFERENCE_REQUIRED" not in codes, report["errors"]
    verdict = report["result"]["verdict"]
    assert verdict["kind"] != "undetermined", verdict


def test_same_final_without_backpack_still_dropped(baseline, tmp_path):
    # The same final evidence without the backpack leaves the
    # disagreement unsettled: REFERENCE_DROPPED, as before.
    from src.validate import validate

    final, ctx = _moon46_run(baseline, tmp_path)
    final["references"] = [final["references"][1]]
    final["scale"]["second_reference_index"] = None
    final["scale"]["second_reference_absent_reason"] = (
        "suited figure measured; the pack scale disagrees")
    dry = validate(copy.deepcopy(final), dict(ctx), dry_run=True)
    assert dry["accepted"] is False, dry["errors"]
    matches = [e for e in dry["errors"]
               if e.get("code") == "REFERENCE_DROPPED"]
    assert matches, dry["errors"]
    assert "backpack" in matches[0]["detail"], matches[0]["detail"]
    real = validate(copy.deepcopy(final), dict(ctx))
    assert real["accepted"] is False, real["errors"]
    assert any(e.get("code") == "REFERENCE_DROPPED"
               for e in real["errors"]), real["errors"]


def test_one_reference_scene_pinned_stays_undetermined(
        baseline, tmp_path):
    # One reference with an absence reason and a retimed preview with
    # clock: none, scene-pinned: accepted, verdict undetermined with
    # "one reference" in its reason, g_measured present.
    import json as _json

    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    for row in rows:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * (0.79 / 1.62)
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        _json.dumps(rows), encoding="utf-8")
    good = copy.deepcopy(evidence)
    curve = good["segments"][0]["fit_curve_px"]
    for sample, row in zip(curve, rows):
        sample["y_px"] = row["y_px"]
    good["references"] = good["references"][:1]
    good["scale"]["second_reference_index"] = None
    good["scale"]["second_reference_absent_reason"] = (
        "only backpack measured so far")
    good["worlds"]["candidates"] = [{"world": "Moon"}]
    good["clock"] = None
    good["clock_absent_reason"] = "no visible independent rhythm"
    report = validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "undetermined", verdict
    assert "one reference" in (verdict["reason"] or ""), verdict
    assert verdict["g_measured"] is not None, verdict


def test_unanswered_alternatives_come_in_one_list(
        baseline, tmp_path):
    # A reference whose blind check lists 5 alternatives, none
    # answered: exactly one ALTERNATIVE_NOT_ADDRESSED for it, its
    # detail containing all 5 texts numbered 1-5.
    import json as _json

    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    alternatives = [
        "a vertical pole beside the crate",
        "the walker's boot near the marker",
        "a dark cable across the gravel",
        "a bright patch of sunlit dust",
        "the horizon line above the ridge",
    ]
    check_path = run_dir / "artifacts" / "check_a.json"
    check = _json.loads(check_path.read_text(encoding="utf-8"))
    check["alternatives"] = list(alternatives)
    check_path.write_text(_json.dumps(check), encoding="utf-8")
    report = validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e.get("code") == "ALTERNATIVE_NOT_ADDRESSED"]
    assert len(matches) == 1, report["errors"]
    detail = matches[0]["detail"]
    for num, alt in enumerate(alternatives, 1):
        assert alt in detail, detail
        assert f"{num}." in detail, detail
    assert "does not apply because" in detail, detail

# generated from brief/11 · part 11 owns this file
"""Scale cross-checks (V3/V4/V5, §§9, 12, 13, 15)."""

import copy
import json
import math


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def test_mask_check_gate(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["references"][0]["mask_check"]["artifact"] = \
        "artifacts/check_missing.json"
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "MASK_CHECK_MISSING"
               for e in report["errors"]), report["errors"]


def test_absent_reason_required(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["references"] = bad["references"][:1]
    bad["scale"]["second_reference_index"] = None
    bad["scale"]["second_reference_absent_reason"] = None
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "SECOND_REFERENCE_ABSENT_UNEXPLAINED"
               and e["field"] ==
               "scale.second_reference_absent_reason"
               for e in report["errors"]), report["errors"]


def test_single_reference_accepted_undetermined(baseline, tmp_path):
    from src.contract import validate_result

    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["references"] = good["references"][:1]
    good["scale"]["second_reference_index"] = None
    good["scale"]["second_reference_absent_reason"] = \
        "no second independent object visible at the same depth"
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert validate_result(report["result"]) == []
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "undetermined"
    assert "one reference" in verdict["reason"]
    assert verdict["g_measured"] is not None


def test_nested_masks_pass_v4(baseline, tmp_path):
    import numpy as np

    from src.helpers.masks_io import save_masks

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    # Backpack nested in the body mask: high intersection over the
    # small mask, low IoU — passes V4 (brief §13.4).
    body = np.zeros((240, 352), dtype=bool)
    body[20:200, 50:150] = True
    pack = np.zeros((240, 352), dtype=bool)
    pack[30:96, 60:120] = True
    path = run_dir / "artifacts" / "nested.npz"
    save_masks(str(path), {"0": {10: body}, "1": {10: pack}})
    produced.append("artifacts/nested.npz")
    good = copy.deepcopy(evidence)
    good["references"][0]["mask"] = {
        "artifact": "artifacts/nested.npz", "object_id": "1",
        "frame": 10,
        "outline": [[60.0, 30.0], [120.0, 30.0], [120.0, 96.0],
                    [60.0, 96.0]]}
    good["references"][1]["mask"] = {
        "artifact": "artifacts/nested.npz", "object_id": "0",
        "frame": 10,
        "outline": [[50.0, 20.0], [150.0, 20.0], [150.0, 200.0],
                    [50.0, 200.0]]}
    ctx = dict(ctx, produced_files=list(produced))
    report = _validate(good, ctx)
    assert report["accepted"] is True, report["errors"]


def test_same_mask_twice_fails_v4(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["references"][1]["mask"] = copy.deepcopy(
        bad["references"][0]["mask"])
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "SECOND_REFERENCE_SAME_OBJECT"
               for e in report["errors"]), report["errors"]


def test_no_code_reads_descriptive_kind():
    from pathlib import Path

    for path in (Path(__file__).parent.parent.parent
                 / "src" / "validate").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert '"subject"' not in text and "'subject'" not in text, \
            path.name


def test_equal_alternatives_need_no_spread(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["references"][0]["mask_check"]["alternative_readings"] = [
        {"description": "same block seen from the side",
         "size_m": 0.66}]
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]


def _one_reference(evidence):
    """Single-reference evidence: no second object can excuse a spread."""
    evidence = copy.deepcopy(evidence)
    evidence["references"] = evidence["references"][:1]
    evidence["scale"]["second_reference_index"] = None
    evidence["scale"]["second_reference_absent_reason"] = \
        "no second independent object visible at the same depth"
    return evidence


def test_differing_reading_without_spread(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = _one_reference(evidence)
    bad["references"][0]["mask_check"]["alternative_readings"] = [
        {"description": "block with its lid stacked on top",
         "size_m": 0.91}]
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "REFERENCE_READING_UNPRICED"
               for e in report["errors"]), report["errors"]


def test_small_spread_rejected_with_numbers(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = _one_reference(evidence)
    bad["references"][0]["mask_check"]["alternative_readings"] = [
        {"description": "block with its lid stacked on top",
         "size_m": 0.91}]
    bad["error_budget"]["components"].append(
        {"name": "reading_spread", "sigma_contribution": 0.05,
         "basis": "lid alternative"})
    required = abs(0.91 - 0.66) / (2.0 * 0.66)
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "READING_SPREAD_TOO_SMALL"]
    assert matches, report["errors"]
    assert f"{required:.3f}" in matches[0]["detail"]
    assert "0.05" in matches[0]["detail"]


def test_second_reference_excuses_spread(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    # The standing figure agrees with the headline scale within 2σ
    # but disagrees under the lid reading, so the lid is ruled out.
    good["references"][0]["mask_check"]["alternative_readings"] = [
        {"description": "block with its lid on top", "size_m": 0.80}]
    _set_size(good["references"][1], 1.683)
    good["references"][1]["size_tolerance_m"] = 0.05
    good["references"][1]["extent_px"]["length_px"] = 171.0
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]


def test_state_match_missing(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    del bad["references"][0]["size_derivation"]["state_match"]
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] in ("STATE_MATCH_MISSING", "MISSING_FIELD")
               for e in report["errors"]), report["errors"]


def test_unanswered_alternative_rejected(baseline, tmp_path):
    import json as _json

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    check = _json.loads(
        (run_dir / "artifacts" / "check_a.json").read_text(
            encoding="utf-8"))
    check["alternatives"] = [
        "a smaller upper block stacked on top of a larger lower block"]
    (run_dir / "artifacts" / "check_a.json").write_text(
        _json.dumps(check), encoding="utf-8")
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "ALTERNATIVE_NOT_ADDRESSED"
               for e in report["errors"]), report["errors"]


def _write_third_mask(run_dir, produced, rel="artifacts/ref_c.npz"):
    """A third reference mask, disjoint from the baseline two."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    canvas = np.zeros((240, 352), dtype=bool)
    canvas[120:186, 200:300] = True
    path = run_dir / rel
    save_masks(str(path), {"0": {10: canvas}})
    produced.append(rel)
    return rel


def _set_size(ref, size_m):
    """Set a reference size with quoting sources (brief §44, R-S13).

    Tests that move a size keep it quoted: every source carries the
    new size as its value, so the size stays within 1 % of a quoted
    value in ``single`` mode.
    """
    ref["size_m"] = size_m
    for source in ref.get("sources", []) or []:
        if isinstance(source, dict):
            source["value_m"] = size_m
    return ref


def test_three_refs_one_outlier_rejected(baseline, tmp_path):
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    mask_c = _write_third_mask(run_dir, produced)
    bad = copy.deepcopy(evidence)
    third = copy.deepcopy(bad["references"][1])
    third["name"] = "distant pole"
    third["mask"] = {"artifact": mask_c, "object_id": "0", "frame": 10,
                     "outline": [[200.0, 120.0], [300.0, 120.0],
                                 [300.0, 186.0], [200.0, 186.0]]}
    third["extent_px"] = {"x1": 0.0, "y1": 0.0, "x2": 0.0,
                          "y2": 100.0, "length_px": 100.0,
                          "frame": 10}
    _set_size(third, 1.36)
    third["size_tolerance_m"] = 0.03
    bad["references"].append(third)
    ctx = dict(ctx, produced_files=list(produced),
               artifacts=sorted(
                   str(p.relative_to(run_dir)) for p in
                   (run_dir / "artifacts").rglob("*") if p.is_file()))
    report = _validate(bad, ctx)
    assert report["accepted"] is False
    refs = [e for e in report["errors"]
            if e["code"] == "REFERENCES_DISAGREE"]
    assert len(refs) == 2, report["errors"]
    assert any("distant pole" in e["detail"] for e in refs)


def test_weighted_scale_and_indices(baseline, tmp_path):
    from src.contract import validate_result

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    mask_c = _write_third_mask(run_dir, produced)
    good = copy.deepcopy(evidence)
    targets = [0.0136, 0.0138]
    for pos, m_per_px in enumerate(targets):
        length = 100.0
        _set_size(good["references"][pos], m_per_px * length)
        good["references"][pos]["size_tolerance_m"] = \
            0.03 * m_per_px * length
        good["references"][pos]["extent_px"]["length_px"] = length
    third = copy.deepcopy(good["references"][0])
    third["name"] = "third block"
    _set_size(third, 0.0137 * 100.0)
    # Its own quoted thing (brief §53): the same size from the
    # same sources would be one reference measured twice.
    third["sources"] = [
        {"url": "https://example.com/block-c",
         "domain": "example.com",
         "quote": "the third block is 137 cm tall",
         "quote_highlight": "137 cm",
         "value_m": 0.0137 * 100.0,
         "source_type": "catalogue"}]
    third["size_tolerance_m"] = 0.03 * 0.0137 * 100.0
    third["mask"] = {"artifact": mask_c, "object_id": "0", "frame": 10,
                     "outline": [[200.0, 120.0], [300.0, 120.0],
                                 [300.0, 186.0], [200.0, 186.0]]}
    facts = json.loads(
        (run_dir / "artifacts" / "t0_web_search_0.json").read_text(
            encoding="utf-8"))
    facts["facts"].append(
        {"url": "https://example.com/block-c",
         "quote": "the third block is 137 cm tall",
         "text": "the third block is 137 cm tall"})
    (run_dir / "artifacts" / "t0_web_search_0.json").write_text(
        json.dumps(facts), encoding="utf-8")
    good["references"].append(third)
    good["scale"]["second_reference_index"] = 1
    ctx = dict(ctx, produced_files=list(produced),
               artifacts=sorted(
                   str(p.relative_to(run_dir)) for p in
                   (run_dir / "artifacts").rglob("*") if p.is_file()))
    report = _validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    assert validate_result(report["result"]) == []
    scale = report["result"]["scale"]
    assert scale["reference_indices"] == [0, 1, 2]
    pairs = [(0.0136, 0.0136 * 0.03), (0.0138, 0.0138 * 0.03),
             (0.0137, 0.0137 * 0.03)]
    weights = [1.0 / (s ** 2) for _, s in pairs]
    expected = sum(v * w for (v, _), w in zip(pairs, weights)) / sum(
        weights)
    assert abs(scale["m_per_px"] - expected) < 1e-12


def test_run8_narrow_spread_rejected(run8_copy, patch_run8, tmp_path):
    evidence, _run_dir, ctx = run8_copy(tmp_path)
    evidence = patch_run8(evidence)
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "READING_SPREAD_TOO_SMALL"]
    assert matches, [e["code"] for e in report["errors"]]
    assert "0.189" in matches[0]["detail"]
    assert "0.12" in matches[0]["detail"]


def _write_reference_lines(run_dir, ctx, evidence):
    """Agreeing blind line checks for an evidence's references (§50).

    Each reference's ``extent_px`` gains a journal record on its own
    frame with both endpoints exact, ``agrees: true`` and a named
    ``dimension``. Appends to ``artifacts/line_checks.jsonl``.
    """
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        for ref in evidence.get("references", []) or []:
            if not isinstance(ref, dict):
                continue
            extent = ref.get("extent_px") or {}
            try:
                frame = int(extent.get("frame", 0))
                coords = (float(extent["x1"]), float(extent["y1"]),
                          float(extent["x2"]), float(extent["y2"]))
            except (KeyError, TypeError, ValueError):
                continue
            name = ref.get("name")
            if not isinstance(name, str) or not name.strip():
                name = "reference"
            name = name.strip()
            handle.write(json.dumps({
                "frame": frame,
                "lines": [{"x1": coords[0], "y1": coords[1],
                           "x2": coords[2], "y2": coords[3],
                           "claim": f"height of the {name}",
                           "description": f"the line runs along {name}",
                           "view": "front", "dimension": "height",
                           "agrees": True,
                           "why": "the description matches the claim"}],
                "overlay_artifact": "artifacts/t1_check_line_0.png",
                "turn": 1}) + "\n")
    ctx["artifacts"] = sorted(set(ctx["artifacts"]) | {
        "artifacts/line_checks.jsonl"})
    ctx["produced_files"] = list(ctx["produced_files"]) + [
        "artifacts/line_checks.jsonl"]


def test_run8_widened_spread_accepted_undetermined(run8_copy, patch_run8,
                                                   tmp_path):
    from src.contract import validate_result

    evidence, run_dir, ctx = run8_copy(tmp_path)
    evidence = patch_run8(evidence)
    ctx = dict(ctx)
    # Single reference with a reason: the scale rests on one object.
    evidence["references"] = evidence["references"][:1]
    alt = {"description": "dark-suited lower body and legs left "
                          "outside the tint",
           "size_m": 0.66}
    readings = evidence["references"][0]["mask_check"][
        "alternative_readings"]
    if not any("lower body" in r.get("description", "")
               for r in readings):
        readings.append(alt)
    for comp in evidence["error_budget"]["components"]:
        if comp["name"] == "reading_spread":
            comp["sigma_contribution"] = 0.19
    evidence["error_budget"]["sigma_relative"] = 0.21
    evidence["scale"]["second_reference_index"] = None
    evidence["scale"]["second_reference_absent_reason"] = \
        "no second independent object visible at the same depth"
    # The kept reference's line needs its blind check (§50).
    _write_reference_lines(run_dir, ctx, evidence)
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert validate_result(report["result"]) == []
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "undetermined"
    assert "one reference" in verdict["reason"]
    assert verdict["g_measured"] is not None


def test_run9_pair_needs_third_reference(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    # Run 9's pair: 0.66 m over 65 px against 1.71 m over 152 px.
    bad["references"][0]["size_m"] = 0.66
    bad["references"][0]["extent_px"]["length_px"] = 65.0
    bad["references"][1]["size_m"] = 1.71
    bad["references"][1]["size_tolerance_m"] = 0.05
    bad["references"][1]["extent_px"]["length_px"] = 152.0
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "THIRD_REFERENCE_REQUIRED"
               for e in report["errors"]), report["errors"]


def test_third_reference_within_2sigma_passes(baseline, tmp_path):
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    mask_c = _write_third_mask(run_dir, produced)
    good = copy.deepcopy(evidence)
    good["references"][0]["size_m"] = 0.66
    good["references"][0]["extent_px"]["length_px"] = 65.0
    good["references"][1]["size_m"] = 1.71
    good["references"][1]["size_tolerance_m"] = 0.05
    good["references"][1]["extent_px"]["length_px"] = 152.0
    third = copy.deepcopy(good["references"][0])
    third["name"] = "mid block"
    _set_size(third, 0.0108 * 65.0)
    third["size_tolerance_m"] = 0.03 * 0.0108 * 65.0
    third["mask"] = {"artifact": mask_c, "object_id": "0", "frame": 10,
                     "outline": [[200.0, 120.0], [300.0, 120.0],
                                 [300.0, 186.0], [200.0, 186.0]]}
    good["references"].append(third)
    # Brief §39: the settler is tight enough to tell the two sides
    # apart (relative σ at most 5%).
    from src.validate.io import reference_scale as _scale

    _m, _s = _scale(third)
    assert _s / _m <= 0.05, _s / _m
    ctx = dict(ctx, produced_files=list(produced),
               artifacts=sorted(
                   str(p.relative_to(run_dir)) for p in
                   (run_dir / "artifacts").rglob("*") if p.is_file()))
    report = _validate(good, ctx)
    codes = [e["code"] for e in report["errors"]]
    assert "THIRD_REFERENCE_REQUIRED" not in codes, report["errors"]


def test_common_frame_error_names_both_frame_ranges(
        baseline, tmp_path):
    import numpy as np

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    # The second reference lives on frame 20 only: the pair shares
    # no common frame (brief §23).
    from src.helpers.masks_io import save_masks

    canvas = np.zeros((240, 352), dtype=bool)
    canvas[20:86, 100:271] = True
    path = run_dir / "artifacts" / "ref_b_20.npz"
    save_masks(str(path), {"0": {20: canvas}})
    produced.append("artifacts/ref_b_20.npz")
    bad = copy.deepcopy(evidence)
    bad["references"][1]["mask"] = {
        "artifact": "artifacts/ref_b_20.npz", "object_id": "0",
        "frame": 20,
        "outline": [[100.0, 20.0], [271.0, 20.0], [271.0, 86.0],
                    [100.0, 86.0]]}
    ctx = dict(ctx, produced_files=list(produced),
               artifacts=sorted(
                   str(p.relative_to(run_dir)) for p in
                   (run_dir / "artifacts").rglob("*") if p.is_file()))
    report = _validate(bad, ctx, dry_run=True)
    matches = [e for e in report["errors"]
               if e["field"] == "references[1].mask"]
    assert matches, report["errors"]
    detail = matches[0]["detail"]
    assert "frame 10" in detail and "frame 20" in detail, detail
    assert "overlap" in detail, detail


def _moon20_alternatives():
    """Seven blind alternatives from Moon run 20 (brief §27)."""
    return [
        "the upper smaller cap-like section",
        "the larger main rectangular volume below that cap",
        "the suited figure's legs extending below the pack",
        "the figure's left arm outside the tinted box",
        "the thin margin of background around the mask edge",
        "the helmet above the pack top edge",
        "the shadow under the lower block edge",
    ]


def _write_alternatives(run_dir, rel, alternatives):
    import json as _json

    path = run_dir / rel
    check = _json.loads(path.read_text(encoding="utf-8"))
    check["alternatives"] = list(alternatives)
    path.write_text(_json.dumps(check), encoding="utf-8")


def test_moon20_seven_alternatives_answered_by_reasons(baseline, tmp_path):
    import json as _json

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    alternatives = _moon20_alternatives()
    _write_alternatives(run_dir, "artifacts/check_a.json", alternatives)
    good = copy.deepcopy(evidence)
    # Two real size readings, answered with sizes (priced below).
    good["references"][0]["mask_check"]["alternative_readings"] = [
        {"description": alternatives[0], "size_m": 0.80},
        {"description": alternatives[1], "size_m": 0.75},
    ]
    # The other five name things the size does not depend on: each is
    # answered by a sentence in size_derivation quoting the alternative
    # and saying why it does not change the size (brief §27).
    sentences = [
        f"{alt}: does not apply because it is outside the measured extent"
        for alt in alternatives[2:]
    ]
    note = good["references"][0]["size_derivation"]["note"]
    good["references"][0]["size_derivation"]["note"] = \
        note + ". " + ". ".join(sentences)
    required = max(abs(0.80 - 0.66), abs(0.75 - 0.66)) / (2.0 * 0.66)
    good["error_budget"]["components"].append(
        {"name": "reading_spread",
         "sigma_contribution": required + 0.05,
         "basis": "two stacked readings"})
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]


def test_moon20_unanswered_alternative_two_form_detail(
        baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    alternatives = _moon20_alternatives()
    _write_alternatives(run_dir, "artifacts/check_a.json", alternatives)
    bad = copy.deepcopy(evidence)
    bad["references"][0]["mask_check"]["alternative_readings"] = [
        {"description": alternatives[0], "size_m": 0.80},
        {"description": alternatives[1], "size_m": 0.75},
    ]
    # Answer only four of the five non-sized alternatives; leave the
    # shadow one unanswered.
    sentences = [
        f"{alt}: does not apply because it is outside the measured extent"
        for alt in alternatives[2:6]
    ]
    note = bad["references"][0]["size_derivation"]["note"]
    bad["references"][0]["size_derivation"]["note"] = \
        note + ". " + ". ".join(sentences)
    bad["error_budget"]["components"].append(
        {"name": "reading_spread", "sigma_contribution": 0.20,
         "basis": "two stacked readings"})
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "ALTERNATIVE_NOT_ADDRESSED"]
    assert matches, report["errors"]
    detail = matches[0]["detail"]
    assert alternatives[6] in detail, detail
    assert "alternative_readings" in detail, detail
    assert "size_derivation" in detail, detail
    assert "does not apply because" in detail, detail


def _moon24_pair(evidence):
    """Moon run 24's disagreeing pair (brief §39): 7.6% apart."""
    evidence = copy.deepcopy(evidence)
    pack, width = evidence["references"]
    pack["name"] = "pack panel"
    _set_size(pack, 0.66)
    pack["size_tolerance_m"] = 0.02
    pack["extent_px"]["length_px"] = 69.87
    width["name"] = "suited width"
    _set_size(width, 0.82)
    width["size_tolerance_m"] = 0.05
    width["extent_px"]["length_px"] = 80.41
    return evidence


def _add_third_reference(evidence, run_dir, produced, name, size_m,
                         size_tolerance_m, length_px):
    """A disjoint third reference mask on the common frame (brief §39)."""
    mask_c = _write_third_mask(run_dir, produced)
    third = copy.deepcopy(evidence["references"][0])
    third["name"] = name
    _set_size(third, size_m)
    third["size_tolerance_m"] = size_tolerance_m
    third["extent_px"]["length_px"] = length_px
    third["mask"] = {"artifact": mask_c, "object_id": "0", "frame": 10,
                     "outline": [[200.0, 120.0], [300.0, 120.0],
                                 [300.0, 186.0], [200.0, 186.0]]}
    evidence["references"].append(third)
    return evidence


def _refresh_ctx(run_dir, produced):
    return {"run_dir": str(run_dir), "run_id": run_dir.name,
            "timing": json.loads(
                (run_dir / "input" / "timing.json").read_text(
                    encoding="utf-8")),
            "artifacts": sorted(
                str(p.relative_to(run_dir)) for p in
                (run_dir / "artifacts").rglob("*") if p.is_file()),
            "produced_files": list(produced), "mask_checks": []}


def test_loose_reference_does_not_settle_gap(baseline, tmp_path):
    evidence, run_dir, _ctx, produced = baseline(tmp_path)
    bad = _moon24_pair(evidence)
    # The flagpole: 2.4384 ± 0.8 m over 98.18 px, 2.6 times the other
    # two, with a 33% tolerance that agrees with almost any scale.
    bad = _add_third_reference(bad, run_dir, produced, "flagpole",
                               2.4384, 0.8, 98.18)
    ctx = _refresh_ctx(run_dir, produced)
    report = _validate(bad, ctx)
    assert report["accepted"] is False
    matches = [e for e in report["errors"]
               if e["code"] == "THIRD_REFERENCE_REQUIRED"]
    assert matches, report["errors"]
    detail = matches[0]["detail"]
    assert "flagpole" in detail, detail
    assert "32.9%" in detail, detail


def test_tight_third_reference_settles_gap(baseline, tmp_path):
    evidence, run_dir, _ctx, produced = baseline(tmp_path)
    good = _moon24_pair(evidence)
    # A tight third at 0.00985 m/px with 3% σ, within 2σ of both.
    good = _add_third_reference(good, run_dir, produced, "mid block",
                                0.00985 * 100.0, 0.022, 100.0)
    ctx = _refresh_ctx(run_dir, produced)
    report = _validate(good, ctx)
    codes = [e["code"] for e in report["errors"]]
    assert "THIRD_REFERENCE_REQUIRED" not in codes, report["errors"]
    assert report["accepted"] is True, report["errors"]


def test_close_pair_needs_no_third(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    # Moon run 22's shape: two references 0.3% apart pass as before.
    good = copy.deepcopy(evidence)
    good["references"][1]["size_m"] = 1.715
    report = _validate(good, dict(ctx))
    codes = [e["code"] for e in report["errors"]]
    assert "THIRD_REFERENCE_REQUIRED" not in codes, report["errors"]
    assert report["accepted"] is True, report["errors"]


def test_moon20_sized_reading_still_needs_spread(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    alternatives = _moon20_alternatives()
    _write_alternatives(run_dir, "artifacts/check_a.json", alternatives)
    bad = copy.deepcopy(evidence)
    bad["references"][0]["mask_check"]["alternative_readings"] = [
        {"description": alternatives[0], "size_m": 0.80},
        {"description": alternatives[1], "size_m": 0.75},
    ]
    sentences = [
        f"{alt}: does not apply because it is outside the measured extent"
        for alt in alternatives[2:]
    ]
    note = bad["references"][0]["size_derivation"]["note"]
    bad["references"][0]["size_derivation"]["note"] = \
        note + ". " + ". ".join(sentences)
    # No reading_spread component: the sized readings are unpriced.
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] in ("REFERENCE_READING_UNPRICED",
                             "READING_SPREAD_TOO_SMALL")
               for e in report["errors"]), report["errors"]

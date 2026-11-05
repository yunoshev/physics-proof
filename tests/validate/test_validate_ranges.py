# generated from brief/11 · part 11 owns this file
"""Range checks, scored and combined (brief §20, part 02 §9)."""

import copy
import json

STILL = "fixtures/still-range"


def _still_evidence():
    import pathlib

    repo = pathlib.Path(__file__).resolve().parent.parent.parent
    return json.loads((repo / STILL / "evidence.json").read_text(
        encoding="utf-8"))


def _still_context():
    import pathlib

    repo = pathlib.Path(__file__).resolve().parent.parent.parent
    base = repo / STILL
    artifacts = sorted(
        str(p.relative_to(base)) for p in (base / "artifacts").rglob("*")
        if p.is_file())
    produced = list(artifacts) + sorted(
        str(p.relative_to(base)) for p in (base / "workspace").rglob("*")
        if p.is_file())
    return {"run_dir": str(base), "run_id": base.name, "timing": {},
            "artifacts": artifacts, "produced_files": produced,
            "mask_checks": []}


def test_still_range_assembles_impossible_decided_by_outside(tmp_path):
    # Part 12 §22's fixture, assembled the way the run-7 fixture is:
    # assembly without the rejecting checks (its sources carry no
    # run web_search ledger). The outside check decides.
    # §25: the typed extents must lie on a mask from the run, so the
    # temporary copy gains a covering mask; the committed fixture is
    # untouched.
    import shutil

    import numpy as np

    from src.helpers.masks_io import save_masks
    from src.validate.validate import assemble_result, run_checks

    import pathlib

    repo = pathlib.Path(__file__).resolve().parent.parent.parent / STILL
    base = tmp_path / "still-range"
    shutil.copytree(str(repo), str(base))
    canvas = np.zeros((300, 400), dtype=bool)
    canvas[40:241, 45:55] = True
    canvas[40:181, 145:155] = True
    save_masks(str(base / "artifacts" / "extent_cover.npz"),
               {"cover": {0: canvas}})
    artifacts = sorted(
        str(p.relative_to(base)) for p in
        (base / "artifacts").rglob("*") if p.is_file())
    produced = list(artifacts) + sorted(
        str(p.relative_to(base)) for p in
        (base / "workspace").rglob("*") if p.is_file())
    ctx = {"run_dir": str(base), "run_id": base.name, "timing": {},
           "artifacts": artifacts, "produced_files": produced,
           "mask_checks": []}
    evidence = _still_evidence()
    _errors, computed = run_checks(evidence, dict(ctx), dry_run=True)
    result = assemble_result(evidence, dict(ctx), computed)
    scored = {c["id"]: c for c in result["range_checks"]}
    assert scored["palm_hand_ratio"]["outcome"] == "inside"
    assert scored["finger_hand_ratio"]["outcome"] == "outside"
    assert scored["finger_hand_ratio"]["side"] == "above"
    verdict = result["verdict"]
    assert verdict["kind"] == "impossible"
    assert verdict["decided_by"] == "finger_hand_ratio"
    assert verdict["g_measured"] is None
    assert verdict["sigma_g"] is None
    sentence = result["sentence"]
    assert sentence.startswith("Not realistic on Earth: ")
    assert "finger / hand length" in sentence
    assert "above" in sentence
    assert "maximum" in sentence


def _hand_evidence(baseline_evidence):
    """Hand-run shape (§23): no segments, one reference, two checks."""
    evidence = copy.deepcopy(baseline_evidence)
    evidence["segments"] = []
    # Range-only evidence measures no motion, so it carries no survey.
    evidence["first_look"].pop("overview", None)
    evidence["references"] = [evidence["references"][0]]
    ref = evidence["references"][0]
    ref["name"] = "phone long edge"
    ref["extent_description"] = "long edge of the phone"
    ref["extent_px"] = {"x1": 10.0, "y1": 300.0, "x2": 10.0,
                        "y2": 339.2, "length_px": 329.2, "frame": 0}
    ref["size_m"] = 0.1646
    ref["size_tolerance_m"] = 0.001
    ref["size_derivation"] = {
        "mode": "single", "note": "maker specification",
        "state_match": {
            "shown_and_covered": "phone edge shown and covered",
            "shown_not_covered": "hand shown but outside the edge"}}
    ref["sources"] = [
        {"url": "https://example.com/phonespec",
         "domain": "example.com",
         "quote": "height 164.6 mm",
         "quote_highlight": "164.6 mm",
         "value_m": 0.1646,
         "source_type": "maker specification"}]
    evidence["scale"] = {
        "frame": 0,
        "m_per_px": 0.0005,
        "sigma_m_per_px": 0.000005,
        "reference_index": 0,
        "extent_px": dict(ref["extent_px"]),
        "second_reference_index": None,
        "second_reference_absent_reason":
            "no second object of known size in the still frame",
        "check_scale": None,
    }
    evidence["first_look"]["question"] = "Is this hand the size it is?"
    evidence["first_look"]["motions"] = [
        {"frame_start": 0, "frame_end": 0,
         "description": "hand held still for the still frame",
         "segment_id": None,
         "skip_reason": "still frame: no motion to measure"}]
    evidence["clock"] = None
    evidence["clock_absent_reason"] = "no motion measured"
    evidence["worlds"] = {"candidates": [{"world": "Earth"}],
                          "excluded": []}
    evidence["error_budget"] = {"components": [], "sigma_relative": 0.0}
    evidence["range_checks"] = [
        {
            "id": "hand_length",
            "label": "hand length",
            "answers": "It settles whether the hand length is adult.",
            "unit": "m",
            "frame": 0,
            "extents": [
                {"name": "hand length", "x1": 50.0, "y1": 40.0,
                 "x2": 50.0, "y2": 422.0, "length_px": 382.0,
                 "frame": 0}],
            "value": 0.191,
            "sigma": 0.012,
            "formula": "length_px x m_per_px",
            "uses_scale": True,
            "measurement_artifact": "artifacts/measure_hand.txt",
            "range": {
                "min": 0.171, "max": 0.214, "typical": 0.19,
                "what": "adult hands, survey of adults, 2012",
                "bounds_kind": "min-max", "percentiles": None,
                "sources": [
                    {"url": "https://example.com/handsurvey",
                     "domain": "example.com",
                     "quote": "smallest adult hand length 171 mm",
                     "quote_highlight": "171 mm",
                     "value": 0.171, "bound": "min",
                     "source_type": "survey report"},
                    {"url": "https://example.com/handsurvey",
                     "domain": "example.com",
                     "quote": "largest adult hand length 214 mm",
                     "quote_highlight": "214 mm",
                     "value": 0.214, "bound": "max",
                     "source_type": "survey report"}],
            },
        },
        {
            "id": "palm_length",
            "label": "palm length",
            "answers": "It settles whether the palm length is adult.",
            "unit": "m",
            "frame": 0,
            "extents": [
                {"name": "palm length", "x1": 60.0, "y1": 192.0,
                 "x2": 60.0, "y2": 422.0, "length_px": 230.0,
                 "frame": 0}],
            "value": 0.115,
            "sigma": 0.009,
            "formula": "length_px x m_per_px",
            "uses_scale": True,
            "measurement_artifact": "artifacts/measure_palm.txt",
            "range": {
                "min": 0.082, "max": 0.133, "typical": 0.105,
                "what": "adult hands, survey of adults, 2012",
                "bounds_kind": "min-max", "percentiles": None,
                "sources": [
                    {"url": "https://example.com/handsurvey",
                     "domain": "example.com",
                     "quote": "smallest adult palm length 82 mm",
                     "quote_highlight": "82 mm",
                     "value": 0.082, "bound": "min",
                     "source_type": "survey report"},
                    {"url": "https://example.com/handsurvey",
                     "domain": "example.com",
                     "quote": "largest adult palm length 133 mm",
                     "quote_highlight": "133 mm",
                     "value": 0.133, "bound": "max",
                     "source_type": "survey report"}],
            },
        },
    ]
    return evidence


def _write_line_checks(run_dir, ctx, items):
    """Agreeing ``check_line`` records for ``items`` (brief §28).

    ``items`` are ``(frame, x1, y1, x2, y2, name)``; each gains a
    journal record with both endpoints exact and ``agrees: true``.
    Appends to ``artifacts/line_checks.jsonl`` so several extent
    groups can accumulate.
    """
    by_frame: dict = {}
    for frame, x1, y1, x2, y2, name in items:
        by_frame.setdefault(int(frame), []).append({
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "claim": name,
            "description": f"the line runs along {name}",
            "agrees": True,
            "why": "the description matches the claim"})
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        for frame, line_items in sorted(by_frame.items()):
            handle.write(json.dumps({
                "frame": frame, "lines": line_items,
                "overlay_artifact": "artifacts/t1_check_line_0.png",
                "turn": 1}) + "\n")
    for rel in ("artifacts/line_checks.jsonl",):
        if rel not in ctx["artifacts"]:
            ctx["artifacts"].append(rel)
    ctx["artifacts"].sort()
    if "artifacts/line_checks.jsonl" not in ctx["produced_files"]:
        ctx["produced_files"].append("artifacts/line_checks.jsonl")


def _write_hand_files(run_dir, ctx, hand_sigma=0.012,
                      palm_sigma=0.009):
    import numpy as np

    from src.helpers.masks_io import save_masks

    run_dir = run_dir
    hand_text = ("hand_px = 382.0\nx1 = 50.0\ny1 = 40.0\nx2 = 50.0\n"
                 "y2 = 422.0\nlength_px = 382.0\nvalue = 0.191\n"
                 f"sigma = {hand_sigma}\n"
                 "formula = length_px x m_per_px\n")
    palm_text = ("palm_px = 230.0\nx1 = 60.0\ny1 = 192.0\nx2 = 60.0\n"
                 "y2 = 422.0\nlength_px = 230.0\nvalue = 0.115\n"
                 f"sigma = {palm_sigma}\n"
                 "formula = length_px x m_per_px\n")
    # The typed extents must lie on a mask from this run (brief §25).
    canvas = np.zeros((500, 200), dtype=bool)
    canvas[40:423, 45:55] = True
    canvas[192:423, 55:65] = True
    save_masks(str(run_dir / "artifacts" / "extent_cover.npz"),
               {"cover": {0: canvas}})
    search_text = json.dumps({
        "query": "adult hand length survey",
        "facts": [
            {"text": "smallest adult hand length 171 mm",
             "url": "https://example.com/handsurvey",
             "quote": "smallest adult hand length 171 mm"},
            {"text": "largest adult hand length 214 mm",
             "url": "https://example.com/handsurvey",
             "quote": "largest adult hand length 214 mm"},
            {"text": "smallest adult palm length 82 mm",
             "url": "https://example.com/handsurvey",
             "quote": "smallest adult palm length 82 mm"},
            {"text": "largest adult palm length 133 mm",
             "url": "https://example.com/handsurvey",
             "quote": "largest adult palm length 133 mm"},
            {"text": "smallest quoted palm-to-hand ratio 50 %",
             "url": "https://example.com/handsurvey",
             "quote": "smallest quoted palm-to-hand ratio 50 %"},
            {"text": "largest quoted palm-to-hand ratio 60 %",
             "url": "https://example.com/handsurvey",
             "quote": "largest quoted palm-to-hand ratio 60 %"},
            {"text": "5th percentile palm-to-hand ratio 40 %",
             "url": "https://example.com/handsurvey",
             "quote": "5th percentile palm-to-hand ratio 40 %"},
            {"text": "95th percentile palm-to-hand ratio 52 %",
             "url": "https://example.com/handsurvey",
             "quote": "95th percentile palm-to-hand ratio 52 %"},
            {"text": "phone height 164.6 mm",
             "url": "https://example.com/phonespec",
             "quote": "height 164.6 mm"},
        ]})
    for rel, text in (("artifacts/measure_hand.txt", hand_text),
                      ("artifacts/measure_palm.txt", palm_text),
                      ("artifacts/t1_web_search_0.json", search_text)):
        (run_dir / rel).write_text(text, encoding="utf-8")
        ctx["artifacts"].append(rel)
        ctx["artifacts"].sort()
        ctx["produced_files"].append(rel)
    ctx["artifacts"].append("artifacts/extent_cover.npz")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/extent_cover.npz")
    # Every range-check extent needs an agreeing check_line record
    # (brief §28): the two hand extents above.
    _write_line_checks(run_dir, ctx, [
        (0, 50.0, 40.0, 50.0, 422.0, "hand length"),
        (0, 60.0, 192.0, 60.0, 422.0, "palm length"),
    ])


def test_hand_run_two_inside_realistic_on_earth(baseline, tmp_path):
    # Brief §51: with two references the range checks decide as
    # before — the one-reference rule needs a lone scale reference.
    from src.contract import validate_result
    from src.validate import validate

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = _hand_evidence(evidence)
    _write_hand_files(run_dir, ctx)
    good = _add_second_phone_reference(run_dir, ctx, produced, good)
    _write_reference_line(run_dir, ctx, good)
    report = validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    assert validate_result(report["result"]) == []
    scored = {c["id"]: c for c in report["result"]["range_checks"]}
    assert scored["hand_length"]["outcome"] == "inside"
    assert scored["palm_length"]["outcome"] == "inside"
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "world"
    assert verdict["world"] == "Earth"
    assert report["result"]["sentence"].startswith(
        "Realistic on Earth")


def test_hand_run_calculation_steps(baseline, tmp_path):
    from src.validate import validate

    good, _run, ctx = _hand_ctx(baseline, tmp_path)
    report = validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    steps = report["result"]["calculation_steps"]
    titles = [s["title"] for s in steps]
    assert "Range check hand length" in titles
    assert "Range check palm length" in titles
    assert titles[-1] == "Verdict"
    hand = steps[titles.index("Range check hand length")]
    formula = hand["short"][1]
    assert formula["type"] == "formula"
    assert "m/px" in formula["fallback"]
    assert "19.1" in formula["fallback"]
    assert formula["chip"] == {"text": "inside",
                               "tone": "intermediate"}
    assert "inside" in hand["full"][0]["text"]


def _write_reference_line(run_dir, ctx, evidence):
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
    if "artifacts/line_checks.jsonl" not in ctx["artifacts"]:
        ctx["artifacts"] = sorted(
            ctx["artifacts"] + ["artifacts/line_checks.jsonl"])
    if "artifacts/line_checks.jsonl" not in ctx["produced_files"]:
        ctx["produced_files"] = list(ctx["produced_files"]) + [
            "artifacts/line_checks.jsonl"]


def _hand_ctx(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = _hand_evidence(evidence)
    _write_hand_files(run_dir, ctx)
    # The phone reference line needs its own blind check (§50); the
    # baseline journal covers the baseline extents, not the phone's.
    _write_reference_line(run_dir, ctx, good)
    return good, run_dir, ctx


def _add_second_phone_reference(run_dir, ctx, produced, good):
    """Hand run 1's evidence with two references (brief §51).

    The phone's short edge at the same scale (0.02 m over 40 px, the
    same 0.0005 m/px as the long edge), with its own mask, blind
    mask check, source quote and search fact. The scale then rests
    on two agreeing references, so the range checks decide as
    before. Returns the evidence; call ``_write_reference_line``
    after this so both references gain a blind line check.
    """
    import numpy as np

    from src.helpers.masks_io import save_masks

    short = {
        "name": "phone short edge",
        "extent_description": "short edge of the phone",
        "extent_type": "face_on",
        "extent_px": {"x1": 150.0, "y1": 10.0, "x2": 190.0,
                      "y2": 10.0, "length_px": 40.0, "frame": 0},
        "size_m": 0.02,
        "size_tolerance_m": 0.001,
        "size_derivation": {
            "mode": "single", "note": "maker specification",
            "state_match": {
                "shown_and_covered": "phone edge shown and covered",
                "shown_not_covered": "hand shown but outside the edge"}},
        "sources": [
            {"url": "https://example.com/phonespec",
             "domain": "example.com",
             "quote": "width 20 mm",
             "quote_highlight": "20 mm",
             "value_m": 0.02,
             "source_type": "maker specification"}],
        "mask": {"artifact": "artifacts/ref_short.npz",
                 "object_id": "1", "frame": 0,
                 "outline": [[150.0, 10.0], [190.0, 10.0],
                             [190.0, 30.0], [150.0, 30.0]]},
        "mask_check": {
            "artifact": "artifacts/check_short.json",
            "coverage_answer": "covers the whole phone edge",
            "confidence": None, "alternative_readings": []},
    }
    short_masks = {}
    for frame in range(0, 21):
        canvas = np.zeros((240, 352), dtype=bool)
        canvas[10:30, 150:190] = True
        short_masks[frame] = canvas
    save_masks(str(run_dir / "artifacts" / "ref_short.npz"),
               {"1": short_masks})
    produced.append("artifacts/ref_short.npz")
    check = {"overlay_artifact": "artifacts/view_0.jpg",
             "coverage_answer": "covers the whole phone edge",
             "alternatives": [], "confidence": None, "turn": 1}
    (run_dir / "artifacts" / "check_short.json").write_text(
        json.dumps(check), encoding="utf-8")
    produced.append("artifacts/check_short.json")
    search_rel = "artifacts/t1_web_search_0.json"
    search = json.loads(
        (run_dir / search_rel).read_text(encoding="utf-8"))
    search["facts"].append(
        {"text": "phone width 20 mm",
         "url": "https://example.com/phonespec",
         "quote": "width 20 mm"})
    (run_dir / search_rel).write_text(json.dumps(search),
                                      encoding="utf-8")
    ctx["artifacts"] = sorted(set(ctx["artifacts"]) | {
        "artifacts/ref_short.npz", "artifacts/check_short.json"})
    ctx["produced_files"] = sorted(set(ctx["produced_files"]) | {
        "artifacts/ref_short.npz", "artifacts/check_short.json"})
    good["references"].append(short)
    good["scale"]["second_reference_index"] = 1
    good["scale"]["second_reference_absent_reason"] = None
    return good


def test_range_only_steps_order(baseline, tmp_path):
    # Brief §29: a synthetic range-only evidence yields
    # time_from_frames, mask_check, scale, scale(range),
    # uncertainty, verdict — and no step is a motion description.
    from src.contract import validate_result
    from src.validate import validate

    good, _run, ctx = _hand_ctx(baseline, tmp_path)
    good["range_checks"] = good["range_checks"][:1]
    report = validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    result = report["result"]
    assert validate_result(result) == []
    steps = result["calculation_steps"]
    assert [s["id"] for s in steps] == [
        "time_from_frames", "mask_check", "scale", "scale",
        "uncertainty", "verdict",
    ]
    assert steps[3]["title"] == "Range check hand length"
    formula = steps[3]["short"][1]
    assert formula["type"] == "formula"
    assert "382.0 px" in formula["fallback"]
    assert "m/px" in formula["fallback"]
    assert "19.1" in formula["fallback"]
    assert formula["chip"] == {"text": "inside",
                               "tone": "intermediate"}
    titles = [s["title"] for s in steps]
    for motion in result["first_look"]["motions"]:
        assert motion["description"] not in titles


def test_range_number_without_provenance(baseline, tmp_path):
    from src.validate import validate

    good, run_dir, ctx = _hand_ctx(baseline, tmp_path)
    (run_dir / "artifacts" / "measure_hand.txt").write_text(
        "hand_px = 382.0\nvalue = 0.191\nformula = length_px x m_per_px\n",
        encoding="utf-8")
    report = validate(good, ctx, dry_run=True)
    assert report["accepted"] is False
    assert any(e["code"] == "RANGE_NUMBER_WITHOUT_PROVENANCE"
               for e in report["errors"]), report["errors"]


def test_range_formula_mismatch(baseline, tmp_path):
    from src.validate import validate

    good, _run, ctx = _hand_ctx(baseline, tmp_path)
    good["range_checks"][0]["value"] = 0.20
    report = validate(good, ctx, dry_run=True)
    assert report["accepted"] is False
    assert any(e["code"] == "RANGE_FORMULA_MISMATCH"
               for e in report["errors"]), report["errors"]


def test_range_source_missing(baseline, tmp_path):
    from src.validate import validate

    good, _run, ctx = _hand_ctx(baseline, tmp_path)
    sources = good["range_checks"][0]["range"]["sources"]
    sources[0]["quote"] = "hands vary in size"
    sources[0]["quote_highlight"] = "vary"
    report = validate(good, ctx, dry_run=True)
    assert report["accepted"] is False
    assert any(e["code"] == "RANGE_SOURCE_MISSING"
               for e in report["errors"]), report["errors"]


def test_range_sigma_too_small(baseline, tmp_path):
    # Brief §33: a σ that is not a finite positive number is still
    # refused. A zero σ fails the range check; a missing or negative
    # σ never reaches it (the evidence schema refuses those first).
    from src.validate import validate

    good, run_dir, ctx = _hand_ctx(baseline, tmp_path)
    good["range_checks"][0]["sigma"] = 0.0
    (run_dir / "artifacts" / "measure_hand.txt").write_text(
        "hand_px = 382.0\nx1 = 50.0\ny1 = 40.0\nx2 = 50.0\n"
        "y2 = 422.0\nlength_px = 382.0\nvalue = 0.191\n"
        "sigma = 0.0\nformula = length_px x m_per_px\n",
        encoding="utf-8")
    report = validate(good, ctx, dry_run=True)
    assert report["accepted"] is False
    assert any(e["code"] == "RANGE_SIGMA_TOO_SMALL"
               for e in report["errors"]), report["errors"]
    bad = copy.deepcopy(good)
    bad["range_checks"][0]["sigma"] = -0.001
    report = validate(bad, ctx, dry_run=True)
    assert report["accepted"] is False, report["errors"]
    missing = copy.deepcopy(good)
    del missing["range_checks"][0]["sigma"]
    report = validate(missing, ctx, dry_run=True)
    assert report["accepted"] is False, report["errors"]


def test_range_sigma_below_floor_raised_with_caveat(
        baseline, tmp_path):
    # Brief §33, hand run 8's shape: σ 0.0016 against a floor near
    # 0.0019 is accepted, scored on the floor, with the raise as a
    # caveat on the range check's step.
    from src.contract import validate_result
    from src.validate import validate

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = _hand_evidence(evidence)
    good["range_checks"][0]["sigma"] = 0.0016
    _write_hand_files(run_dir, ctx, hand_sigma=0.0016)
    # Two references, so the inside check still decides (§51).
    good = _add_second_phone_reference(run_dir, ctx, produced, good)
    _write_reference_line(run_dir, ctx, good)
    report = validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    result = report["result"]
    assert validate_result(result) == []
    scored = {c["id"]: c for c in result["range_checks"]}
    assert scored["hand_length"]["outcome"] == "inside"
    raised = scored["hand_length"]["sigma"]
    # The floor is the endpoint error plus the validator's scale σ
    # (hand run 8's shape: near 0.0019 m).
    assert raised > 0.0016
    assert abs(raised - 0.0019) < 2e-4
    assert result["sentence"].startswith("Realistic on Earth")
    steps = result["calculation_steps"]
    hand = [s for s in steps
            if s["title"] == "Range check hand length"][0]
    caveats = [c["text"] for c in hand["caveats"]]
    assert len(caveats) == 1
    assert caveats[0] == (
        f"σ raised from 0.0016 m to {raised:g} m "
        "(endpoint and scale floor)")


def test_range_sigma_above_floor_used_unchanged(baseline, tmp_path):
    # A σ above the floor is used unchanged, with no caveat.
    from src.validate import validate

    good, _run, ctx = _hand_ctx(baseline, tmp_path)
    report = validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    scored = {c["id"]: c for c in
              report["result"]["range_checks"]}
    assert scored["hand_length"]["sigma"] == 0.012
    steps = report["result"]["calculation_steps"]
    hand = [s for s in steps
            if s["title"] == "Range check hand length"][0]
    assert hand["caveats"] == []


def test_measurement_missing(baseline, tmp_path):
    from src.validate import validate

    good, _run, ctx = _hand_ctx(baseline, tmp_path)
    good["range_checks"] = []
    report = validate(good, ctx, dry_run=True)
    assert report["accepted"] is False
    assert any(e["code"] == "MEASUREMENT_MISSING"
               for e in report["errors"]), report["errors"]


def test_ratio_recompute_three_percent_off_rejected(baseline, tmp_path):
    from src.validate import validate

    good, run_dir, ctx = _hand_ctx(baseline, tmp_path)
    check = {
        "id": "palm_hand_ratio",
        "label": "palm / hand length",
        "answers": "It settles whether the proportions are adult.",
        "unit": "ratio",
        "frame": 0,
        "extents": [
            {"name": "hand length", "x1": 50.0, "y1": 40.0,
             "x2": 50.0, "y2": 240.0, "length_px": 200.0,
             "frame": 0},
            {"name": "palm length", "x1": 50.0, "y1": 140.0,
             "x2": 50.0, "y2": 230.0, "length_px": 90.0,
             "frame": 0}],
        "value": 0.45 * 1.03,
        "sigma": 0.02,
        "formula": "palm_px / hand_px",
        "uses_scale": False,
        "measurement_artifact": "artifacts/measure_ratio.txt",
        "range": {
            "min": 0.4, "max": 0.52, "typical": 0.46,
            "what": "adult hands, survey of adults, 2012",
            "bounds_kind": "percentile", "percentiles": [5, 95],
            "sources": [
                {"url": "https://example.com/handsurvey",
                 "domain": "example.com",
                 "quote": "5th percentile palm-to-hand ratio 40 %",
                 "quote_highlight": "40 %",
                 "value": 0.4, "bound": "min",
                 "source_type": "survey report"},
                {"url": "https://example.com/handsurvey",
                 "domain": "example.com",
                 "quote": "95th percentile palm-to-hand ratio 52 %",
                 "quote_highlight": "52 %",
                 "value": 0.52, "bound": "max",
                 "source_type": "survey report"}],
        },
    }
    good["range_checks"] = [check]
    (run_dir / "artifacts" / "measure_ratio.txt").write_text(
        "hand_px = 200.0\nx1 = 50.0\ny1 = 40.0\nx2 = 50.0\ny2 = 240.0\n"
        "palm_px = 90.0\nx1 = 50.0\ny1 = 140.0\nx2 = 50.0\ny2 = 230.0\n"
        "length_px = 200.0\nlength_px = 90.0\nvalue = 0.4635\n"
        "sigma = 0.02\nformula = palm_px / hand_px\n",
        encoding="utf-8")
    ctx["artifacts"].append("artifacts/measure_ratio.txt")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/measure_ratio.txt")
    report = validate(good, ctx, dry_run=True)
    assert any(e["code"] == "RANGE_FORMULA_MISMATCH"
               for e in report["errors"]), report["errors"]


def test_gravity_fit_plus_outside_check_gives_impossible(
        baseline, tmp_path):
    # Part 02 §9: any part not realistic decides impossible, even
    # when gravity fits a world on its own.
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    _write_hand_files(run_dir, ctx)
    good = copy.deepcopy(evidence)
    check = {
        "id": "palm_hand_ratio",
        "label": "palm / hand length",
        "answers": "It settles whether the proportions are adult.",
        "unit": "ratio",
        "frame": 0,
        "extents": [
            {"name": "hand length", "x1": 50.0, "y1": 40.0,
             "x2": 50.0, "y2": 170.0, "length_px": 130.0,
             "frame": 0},
            {"name": "palm length", "x1": 50.0, "y1": 140.0,
             "x2": 50.0, "y2": 230.0, "length_px": 90.0,
             "frame": 0}],
        "value": 0.69,
        "sigma": 0.02,
        "formula": "palm_px / hand_px",
        "uses_scale": False,
        "measurement_artifact": "artifacts/measure_ratio.txt",
        "range": {
            "min": 0.5, "max": 0.6, "typical": 0.55,
            "what": "adult hands, survey of adults, 2012",
            "bounds_kind": "min-max", "percentiles": None,
            "sources": [
                {"url": "https://example.com/handsurvey",
                 "domain": "example.com",
                 "quote": "smallest quoted palm-to-hand ratio 50 %",
                 "quote_highlight": "50 %",
                 "value": 0.5, "bound": "min",
                 "source_type": "survey report"},
                {"url": "https://example.com/handsurvey",
                 "domain": "example.com",
                 "quote": "largest quoted palm-to-hand ratio 60 %",
                 "quote_highlight": "60 %",
                 "value": 0.6, "bound": "max",
                 "source_type": "survey report"}],
        },
    }
    good["range_checks"] = [check]
    (run_dir / "artifacts" / "measure_ratio.txt").write_text(
        "hand_px = 130.0\nx1 = 50.0\ny1 = 40.0\nx2 = 50.0\ny2 = 170.0\n"
        "palm_px = 90.0\nx1 = 50.0\ny1 = 140.0\nx2 = 50.0\ny2 = 230.0\n"
        "length_px = 130.0\nlength_px = 90.0\nvalue = 0.69\n"
        "sigma = 0.02\nformula = palm_px / hand_px\n",
        encoding="utf-8")
    ctx["artifacts"].append("artifacts/measure_ratio.txt")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/measure_ratio.txt")
    _write_line_checks(run_dir, ctx, [
        (0, 50.0, 40.0, 50.0, 170.0, "hand length"),
        (0, 50.0, 140.0, 50.0, 230.0, "palm length"),
    ])
    report = validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    # Above the maximum keeps its current meaning (brief §38):
    # the ratio 0.69 against a 0.6 maximum decides impossible even
    # though gravity fits a world on its own.
    scored = {c["id"]: c for c in report["result"]["range_checks"]}
    assert scored["palm_hand_ratio"]["outcome"] == "outside"
    assert scored["palm_hand_ratio"]["side"] == "above"
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "impossible"
    assert verdict["decided_by"] == "palm_hand_ratio"
    assert report["result"]["sentence"].startswith(
        "Not realistic on")


def test_ratio_recompute_one_percent_off_passes(baseline, tmp_path):
    from src.validate import validate

    good, run_dir, ctx = _hand_ctx(baseline, tmp_path)
    check = {
        "id": "palm_hand_ratio",
        "label": "palm / hand length",
        "answers": "It settles whether the proportions are adult.",
        "unit": "ratio",
        "frame": 0,
        "extents": [
            {"name": "hand length", "x1": 50.0, "y1": 40.0,
             "x2": 50.0, "y2": 240.0, "length_px": 200.0,
             "frame": 0},
            {"name": "palm length", "x1": 50.0, "y1": 140.0,
             "x2": 50.0, "y2": 230.0, "length_px": 90.0,
             "frame": 0}],
        "value": 0.45 * 1.01,
        "sigma": 0.02,
        "formula": "palm_px / hand_px",
        "uses_scale": False,
        "measurement_artifact": "artifacts/measure_ratio.txt",
        "range": {
            "min": 0.4, "max": 0.52, "typical": 0.46,
            "what": "adult hands, survey of adults, 2012",
            "bounds_kind": "percentile", "percentiles": [5, 95],
            "sources": [
                {"url": "https://example.com/handsurvey",
                 "domain": "example.com",
                 "quote": "5th percentile palm-to-hand ratio 40 %",
                 "quote_highlight": "40 %",
                 "value": 0.4, "bound": "min",
                 "source_type": "survey report"},
                {"url": "https://example.com/handsurvey",
                 "domain": "example.com",
                 "quote": "95th percentile palm-to-hand ratio 52 %",
                 "quote_highlight": "52 %",
                 "value": 0.52, "bound": "max",
                 "source_type": "survey report"}],
        },
    }
    good["range_checks"] = [check]
    (run_dir / "artifacts" / "measure_ratio.txt").write_text(
        "hand_px = 200.0\nx1 = 50.0\ny1 = 40.0\nx2 = 50.0\ny2 = 240.0\n"
        "palm_px = 90.0\nx1 = 50.0\ny1 = 140.0\nx2 = 50.0\ny2 = 230.0\n"
        "length_px = 200.0\nlength_px = 90.0\nvalue = 0.4545\n"
        "sigma = 0.02\nformula = palm_px / hand_px\n",
        encoding="utf-8")
    ctx["artifacts"].append("artifacts/measure_ratio.txt")
    ctx["artifacts"].sort()
    ctx["produced_files"].append("artifacts/measure_ratio.txt")
    _write_line_checks(run_dir, ctx, [
        (0, 50.0, 40.0, 50.0, 240.0, "hand length"),
        (0, 50.0, 140.0, 50.0, 230.0, "palm length"),
    ])
    report = validate(good, ctx, dry_run=True)
    assert not any(e["code"] == "RANGE_FORMULA_MISMATCH"
                   for e in report["errors"]), report["errors"]
    assert not any(e["code"] == "RANGE_LINE_NOT_CONFIRMED"
                   for e in report["errors"]), report["errors"]

# generated from brief/11 · part 11 owns this file
"""One reference gives no verdict from range checks either; a range
check never re-measures a reference's object (brief §51)."""

import copy
import json


def _add_artifact(run_dir, produced, ctx, rel, content):
    target = run_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    if rel not in produced:
        produced.append(rel)
    for key in ("artifacts", "produced_files"):
        items = list(ctx.get(key, []))
        if rel not in items:
            items.append(rel)
            ctx[key] = sorted(items)


def _journal(run_dir, ctx, frame, x1, y1, x2, y2, name):
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "frame": frame,
            "lines": [{"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                       "claim": name,
                       "description": f"the line runs along {name}",
                       "view": "front", "dimension": "height",
                       "agrees": True,
                       "why": "the description matches the claim"}],
            "overlay_artifact": "artifacts/t1_check_line_0.png",
            "turn": 1}) + "\n")
    for key in ("artifacts", "produced_files"):
        items = list(ctx.get(key, []))
        if "artifacts/line_checks.jsonl" not in items:
            items.append("artifacts/line_checks.jsonl")
            ctx[key] = sorted(items)


def _bf0cf9f7_run(baseline, tmp_path):
    """Moon run bf0cf9f7's shape: one reference, two scale checks.

    The backpack reference stands alone with an absence reason. The
    "suited figure height" check reads below its range (a signal, per
    §38, that decides nothing), and the "backpack height" check sits
    on the reference's own object on frame 240, where the run's
    masks of that object cover it.
    """
    import numpy as np

    from src.helpers.masks_io import save_masks

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = copy.deepcopy(evidence)
    ref = good["references"][0]
    ref["name"] = "backpack"
    good["references"] = [ref]
    good["scale"]["second_reference_index"] = None
    good["scale"]["second_reference_absent_reason"] = (
        "only one familiar thing at the depth of the motion")
    # The run's masks of the backpack: steady on frames 0-20 (the
    # reference's rest frames near its measuring frame 10) and below
    # it on frame 240.
    wide = {}
    for frame in range(0, 21):
        canvas = np.zeros((240, 352), dtype=bool)
        canvas[20:86, 20:40] = True
        wide[frame] = canvas
    low = np.zeros((240, 352), dtype=bool)
    low[170:240, 20:40] = True
    wide[240] = low
    save_masks(str(run_dir / "artifacts" / "t50_segment_9.npz"),
               {"0": wide})
    produced.append("artifacts/t50_segment_9.npz")
    ctx["artifacts"] = sorted(
        ctx["artifacts"] + ["artifacts/t50_segment_9.npz"])
    ctx["produced_files"] = sorted(
        ctx["produced_files"] + ["artifacts/t50_segment_9.npz"])
    # A cover mask for the figure check's extent on frame 205, far
    # from the backpack's object.
    cover = np.zeros((240, 352), dtype=bool)
    cover[55:195, 175:185] = True
    save_masks(str(run_dir / "artifacts" / "cover_fig.npz"),
               {"cover": {205: cover}})
    produced.append("artifacts/cover_fig.npz")
    ctx["artifacts"] = sorted(
        ctx["artifacts"] + ["artifacts/cover_fig.npz"])
    ctx["produced_files"] = sorted(
        ctx["produced_files"] + ["artifacts/cover_fig.npz"])
    good["range_checks"] = [
        {
            "id": "figure_height",
            "label": "suited figure height",
            "answers": "It settles whether the scale suits the figure.",
            "unit": "m",
            "frame": 205,
            "extents": [
                {"name": "suited figure height", "x1": 180.0,
                 "y1": 60.0, "x2": 180.0, "y2": 189.0,
                 "length_px": 129.0, "frame": 205}],
            "value": 1.29,
            "sigma": 0.05,
            "formula": "length_px x m_per_px",
            "uses_scale": True,
            "measurement_artifact": "artifacts/measure_fig.txt",
            "range": {
                "min": 1.6764, "max": 1.7002, "typical": 1.69,
                "what": "suited men standing height, survey, 1970",
                "bounds_kind": "min-max", "percentiles": None,
                "sources": [
                    {"url": "https://example.com/suit",
                     "domain": "example.com",
                     "quote": "minimum suited height 167.64 cm",
                     "quote_highlight": "167.64 cm",
                     "value": 1.6764, "bound": "min",
                     "source_type": "survey report"},
                    {"url": "https://example.com/suit",
                     "domain": "example.com",
                     "quote": "maximum suited height 170.02 cm",
                     "quote_highlight": "170.02 cm",
                     "value": 1.7002, "bound": "max",
                     "source_type": "survey report"}],
            },
        },
        {
            "id": "backpack_height",
            "label": "backpack height",
            "answers": "It settles the stacked pack's height.",
            "unit": "m",
            "frame": 240,
            "extents": [
                {"name": "backpack height", "x1": 30.0, "y1": 172.0,
                 "x2": 30.0, "y2": 238.0, "length_px": 66.0,
                 "frame": 240}],
            "value": 0.66,
            "sigma": 0.03,
            "formula": "length_px x m_per_px",
            "uses_scale": True,
            "measurement_artifact": "artifacts/measure_pack.txt",
            "range": {
                "min": 0.25, "max": 0.66, "typical": 0.5,
                "what": "backpack part heights, maker survey, 1969",
                "bounds_kind": "min-max", "percentiles": None,
                "sources": [
                    {"url": "https://example.com/pack",
                     "domain": "example.com",
                     "quote": "shortest backpack part height 25 cm",
                     "quote_highlight": "25 cm",
                     "value": 0.25, "bound": "min",
                     "source_type": "survey report"},
                    {"url": "https://example.com/pack",
                     "domain": "example.com",
                     "quote": "tallest backpack part height 66 cm",
                     "quote_highlight": "66 cm",
                     "value": 0.66, "bound": "max",
                     "source_type": "survey report"}],
            },
        },
    ]
    _add_artifact(
        run_dir, produced, ctx, "artifacts/measure_fig.txt",
        "x1 = 180.0\ny1 = 60.0\nx2 = 180.0\ny2 = 189.0\n"
        "length_px = 129.0\nvalue = 1.29\nsigma = 0.05\n"
        "formula = length_px x m_per_px\n")
    _add_artifact(
        run_dir, produced, ctx, "artifacts/measure_pack.txt",
        "x1 = 30.0\ny1 = 172.0\nx2 = 30.0\ny2 = 238.0\n"
        "length_px = 66.0\nvalue = 0.66\nsigma = 0.03\n"
        "formula = length_px x m_per_px\n")
    _journal(run_dir, ctx, 205, 180.0, 60.0, 180.0, 189.0,
             "suited figure height")
    _journal(run_dir, ctx, 240, 30.0, 172.0, 30.0, 238.0,
             "backpack height")
    search = {"query": "suited height backpack parts",
              "facts": [
                  {"url": "https://example.com/suit",
                   "quote": "minimum suited height 167.64 cm",
                   "text": "minimum suited height 167.64 cm"},
                  {"url": "https://example.com/suit",
                   "quote": "maximum suited height 170.02 cm",
                   "text": "maximum suited height 170.02 cm"},
                  {"url": "https://example.com/pack",
                   "quote": "shortest backpack part height 25 cm",
                   "text": "shortest backpack part height 25 cm"},
                  {"url": "https://example.com/pack",
                   "quote": "tallest backpack part height 66 cm",
                   "text": "tallest backpack part height 66 cm"},
              ]}
    _add_artifact(run_dir, produced, ctx,
                  "artifacts/t2_web_search_2.json", json.dumps(search))
    return good, run_dir, ctx


def test_one_reference_range_checks_decide_nothing(baseline, tmp_path):
    # Moon run bf0cf9f7's final evidence: one reference, a below
    # figure check and a backpack check on the reference's own
    # object. The verdict is undetermined, "scale rests on one
    # reference", with the measured g still in the result — and the
    # backpack check is refused for re-measuring the reference.
    from src.validate import validate
    from src.validate.validate import assemble_result, run_checks

    good, _run, ctx = _bf0cf9f7_run(baseline, tmp_path)
    dry = validate(copy.deepcopy(good), dict(ctx), dry_run=True)
    assert dry["accepted"] is False, dry["errors"]
    pack = [e for e in dry["errors"]
            if e["code"] == "RANGE_CHECK_ON_REFERENCE"
            and e["field"] == "range_checks[1]"]
    assert len(pack) == 1, dry["errors"]
    assert "re-measures the reference 'backpack'" in pack[0][
        "detail"], pack[0]["detail"]
    assert "frame 240" in pack[0]["detail"], pack[0]["detail"]
    _errors, computed = run_checks(copy.deepcopy(good), dict(ctx),
                                   dry_run=True)
    result = assemble_result(copy.deepcopy(good), dict(ctx), computed)
    scored = {c["id"]: c for c in result["range_checks"]}
    assert scored["backpack_height"]["outcome"] == "not_counted"
    assert scored["figure_height"]["outcome"] == "below"
    verdict = result["verdict"]
    assert verdict["kind"] == "undetermined", verdict
    assert "scale rests on one reference" in (
        verdict["reason"] or ""), verdict
    assert verdict["g_measured"] is not None, verdict


def _hand_two_refs(baseline, tmp_path):
    """Hand run 1's shape with two references (brief §51)."""
    from test_validate_ranges import (
        _add_second_phone_reference, _hand_evidence, _write_hand_files,
        _write_reference_line)

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = _hand_evidence(evidence)
    _write_hand_files(run_dir, ctx)
    good = _add_second_phone_reference(run_dir, ctx, produced, good)
    _write_reference_line(run_dir, ctx, good)
    return good, run_dir, ctx


def test_hand_two_references_keep_verdict(baseline, tmp_path):
    # Hand run 1's evidence with two references and two range checks
    # on other lines keeps its verdict: Realistic on Earth.
    from src.contract import validate_result
    from src.validate import validate

    good, _run, ctx = _hand_two_refs(baseline, tmp_path)
    report = validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    assert validate_result(report["result"]) == []
    scored = {c["id"]: c for c in report["result"]["range_checks"]}
    assert scored["hand_length"]["outcome"] == "inside"
    assert scored["palm_length"]["outcome"] == "inside"
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "world", verdict
    assert verdict["world"] == "Earth", verdict
    assert report["result"]["sentence"].startswith(
        "Realistic on Earth")


def test_scaleless_range_check_still_decides(baseline, tmp_path):
    # A range check that does not use the scale (a ratio) still
    # decides with one reference: outside stays impossible,
    # decided by the check.
    import copy as _copy

    from src.validate import validate
    from test_validate_ranges import (
        _hand_evidence, _write_hand_files)

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    ctx = dict(ctx)
    ctx["artifacts"] = list(ctx["artifacts"])
    ctx["produced_files"] = list(ctx["produced_files"])
    good = _hand_evidence(evidence)
    _write_hand_files(run_dir, ctx)
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
        "value": 0.6923,
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
        "length_px = 130.0\nlength_px = 90.0\nvalue = 0.6923\n"
        "sigma = 0.02\nformula = palm_px / hand_px\n",
        encoding="utf-8")
    ctx["artifacts"] = sorted(
        ctx["artifacts"] + ["artifacts/measure_ratio.txt"])
    ctx["produced_files"] = sorted(
        ctx["produced_files"] + ["artifacts/measure_ratio.txt"])
    from test_validate_ranges import (
        _write_line_checks, _write_reference_line)

    _write_line_checks(run_dir, ctx, [
        (0, 50.0, 40.0, 50.0, 170.0, "hand length"),
        (0, 50.0, 140.0, 50.0, 230.0, "palm length"),
    ])
    # The phone reference line needs its own blind check (§50).
    _write_reference_line(run_dir, ctx, good)
    report = validate(_copy.deepcopy(good), dict(ctx))
    assert report["accepted"] is True, report["errors"]
    scored = {c["id"]: c for c in report["result"]["range_checks"]}
    assert scored["palm_hand_ratio"]["outcome"] == "outside"
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "impossible", verdict
    assert verdict["decided_by"] == "palm_hand_ratio", verdict

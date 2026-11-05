# generated from brief/11 · part 11 owns this file
"""One quoted thing is one reference; a dry run asks for the moving
thing (brief §53, R-S6b, R-S16).

Two references quoting the same size from the same sources are one
quoted thing measured twice (``REFERENCE_SAME_THING``, in a dry run
and a real submit alike). A dry run with an overview and no reference
on the moving thing lists the ``SELF_REFERENCE_REQUIRED`` push; the
moving thing's own mask counts, a missing overview never lists it,
and a real submit is never refused for it.
"""

import copy
import json


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _refresh(run_dir, produced):
    timing = json.loads(
        (run_dir / "input" / "timing.json").read_text(encoding="utf-8"))
    artifacts = sorted(
        str(p.relative_to(run_dir)) for p in
        (run_dir / "artifacts").rglob("*") if p.is_file())
    return {"run_dir": str(run_dir), "run_id": run_dir.name,
            "timing": timing, "artifacts": artifacts,
            "produced_files": list(produced), "mask_checks": []}


def _same_size_sources(evidence):
    """Both references quoting 0.66 m from the block's sources."""
    evidence = copy.deepcopy(evidence)
    block_sources = copy.deepcopy(
        evidence["references"][0]["sources"])
    figure = evidence["references"][1]
    figure["size_m"] = 0.66
    figure["size_tolerance_m"] = 0.03
    figure["sources"] = block_sources
    figure["size_derivation"]["mode"] = "single"
    return evidence


def test_same_size_same_sources_refused(baseline, tmp_path):
    """Run 258d5f07's shape: the same quote twice is one reference."""
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = _same_size_sources(evidence)
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False, report["errors"]
    matches = [e for e in report["errors"]
               if e["code"] == "REFERENCE_SAME_THING"]
    assert matches, report["errors"]
    detail = matches[0]["detail"]
    assert "references[0]" in detail, detail
    assert "references[1]" in detail, detail
    assert "one quoted thing" in detail or (
        "one thing measured twice" in detail), detail
    dry = _validate(copy.deepcopy(bad), dict(ctx), dry_run=True)
    assert any(e["code"] == "REFERENCE_SAME_THING"
               for e in dry["errors"]), dry["errors"]


def _add_search_fact(run_dir, url, quote):
    facts = json.loads(
        (run_dir / "artifacts" / "t0_web_search_0.json").read_text(
            encoding="utf-8"))
    facts["facts"].append(
        {"url": url, "quote": quote, "text": quote})
    (run_dir / "artifacts" / "t0_web_search_0.json").write_text(
        json.dumps(facts), encoding="utf-8")


def test_different_size_different_sources_pass(baseline, tmp_path):
    """0.914 m from two sources is a different quoted thing."""
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    figure = good["references"][1]
    figure["size_m"] = 0.914
    figure["size_derivation"]["mode"] = "sum"
    figure["sources"] = [
        {"url": "https://example.com/plss",
         "domain": "example.com",
         "quote": "the pack is 66 cm tall",
         "quote_highlight": "66 cm",
         "value_m": 0.66,
         "source_type": "catalogue"},
        {"url": "https://example.com/ops",
         "domain": "example.com",
         "quote": "the top unit is 25.4 cm tall",
         "quote_highlight": "25.4 cm",
         "value_m": 0.254,
         "source_type": "catalogue"}]
    _add_search_fact(run_dir, "https://example.com/plss",
                     "the pack is 66 cm tall")
    _add_search_fact(run_dir, "https://example.com/ops",
                     "the top unit is 25.4 cm tall")
    report = _validate(good, dict(ctx))
    assert not [e for e in report["errors"]
                if e["code"] == "REFERENCE_SAME_THING"], \
        report["errors"]


def _off_moving_thing_mask(run_dir, produced):
    """A figure mask disjoint from the survey's ground box."""
    import numpy as np

    from src.helpers.masks_io import save_masks

    masks = {}
    for frame in range(0, 21):
        canvas = np.zeros((240, 352), dtype=bool)
        canvas[20:90, 20:90] = True
        masks[int(frame)] = canvas
    path = run_dir / "artifacts" / "ref_fig.npz"
    save_masks(str(path), {"0": masks})
    produced.append("artifacts/ref_fig.npz")
    return "artifacts/ref_fig.npz"


def _no_self_reference(baseline, tmp_path):
    """Baseline with neither reference on the moving thing."""
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["references"][1]["mask"] = {
        "artifact": _off_moving_thing_mask(run_dir, produced),
        "object_id": "0", "frame": 10,
        "outline": [[20.0, 20.0], [90.0, 20.0],
                    [90.0, 90.0], [20.0, 90.0]]}
    return good, _refresh(run_dir, produced)


def test_dry_run_lists_self_reference_push(baseline, tmp_path):
    """Runs bce08ba3/e84d1289 as a dry run: the push is listed."""
    good, ctx = _no_self_reference(baseline, tmp_path)
    dry = _validate(copy.deepcopy(good), dict(ctx), dry_run=True)
    assert dry["accepted"] is False, dry["errors"]
    pushes = [e for e in dry["errors"]
              if e["code"] == "SELF_REFERENCE_REQUIRED"]
    assert len(pushes) == 1, dry["errors"]
    assert pushes[0].get("push") is True, pushes[0]
    detail = pushes[0]["detail"]
    assert "none of them is the moving thing" in detail, detail
    assert "object 0 of artifacts/masks_all.npz" in detail, detail
    assert "R-S16" in detail, detail


def test_real_submit_never_refused_for_self_reference(
        baseline, tmp_path):
    """A real submit of that evidence carries no such error."""
    good, ctx = _no_self_reference(baseline, tmp_path)
    real = _validate(good, dict(ctx))
    assert real["accepted"] is True, real["errors"]
    assert not [e for e in real["errors"]
                if e["code"] == "SELF_REFERENCE_REQUIRED"], \
        real["errors"]


def test_self_reference_present_gives_no_push(baseline, tmp_path):
    """Run 02dc5ade's shape: the mask is the overview's object."""
    evidence, _run, ctx, _produced = baseline(tmp_path)
    evidence = copy.deepcopy(evidence)
    evidence["references"][1]["mask"] = {
        "artifact": "artifacts/masks_all.npz", "object_id": "0",
        "frame": 10,
        "outline": [[100.0, 20.0], [271.0, 20.0],
                    [271.0, 191.0], [100.0, 191.0]]}
    dry = _validate(evidence, dict(ctx), dry_run=True)
    assert not [e for e in dry["errors"]
                if e["code"] == "SELF_REFERENCE_REQUIRED"], \
        dry["errors"]


def test_no_overview_gives_no_self_reference(baseline, tmp_path):
    """Without first_look.overview there is no moving thing to ask."""
    evidence, _run, ctx, _produced = baseline(tmp_path)
    evidence = copy.deepcopy(evidence)
    del evidence["first_look"]["overview"]
    dry = _validate(evidence, dict(ctx), dry_run=True)
    assert not [e for e in dry["errors"]
                if e["code"] == "SELF_REFERENCE_REQUIRED"], \
        dry["errors"]

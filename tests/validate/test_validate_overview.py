# generated from brief/11 · part 11 owns this file
"""Every candidate flight is decided; several flights give one g (§43)."""

import copy
import json
import shutil

import pytest

from src.validate import validate

FAKE1 = "fixtures/source/fake-1"


def _fake1_run(tmp_path):
    from src.validate.fixture import collect

    run_dir = tmp_path / "fake-1"
    shutil.copytree(FAKE1, str(run_dir),
                    ignore=shutil.ignore_patterns("logs"))
    ctx = collect(run_dir)
    evidence = json.loads(
        (run_dir / "artifacts" / "t53_evidence.json").read_text(
            encoding="utf-8"))
    # The fake-1 references carry no check_line journal; the tests
    # about the motion survey confirm their lines here (§50).
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
    produced = list(ctx.get("produced_files", []))
    if "artifacts/line_checks.jsonl" not in produced:
        produced.append("artifacts/line_checks.jsonl")
    artifacts = sorted(set(ctx.get("artifacts", [])) | {
        "artifacts/line_checks.jsonl"})
    ctx = dict(ctx, artifacts=artifacts, produced_files=produced)
    return evidence, run_dir, ctx


def _with_overview(evidence, run_dir):
    evidence = copy.deepcopy(evidence)
    (run_dir / "artifacts" / "overview.json").write_text(
        json.dumps({"masks_artifact":
                    "artifacts/t9_segment_0.npz",
                    "object_id": "1"}),
        encoding="utf-8")
    evidence["first_look"]["overview"] = {
        "artifact": "artifacts/t9_segment_0.npz",
        "object_id": "1",
        "tool_result": "artifacts/overview.json",
        "candidates": [
            {"id": "cand_1", "frame_start": 135, "frame_end": 152,
             "airtime_s": 0.57, "peak_rise_px": 45.0,
             "decision": "measured", "segment_id": "hop_a",
             "reason": None}],
        "first_check": {"segment_id": "hop_a",
                        "why": "longest clear flight"},
    }
    return evidence


def test_fake1_unconsidered_flight_pushed(tmp_path):
    """An overview listing only the measured flight pushes the rest.

    The whole-clip masks also carry flights at frames 20-38, 101-113
    and 181-191: the dry run pushes FLIGHT_NOT_CONSIDERED naming,
    among others, frames 101-113.
    """
    evidence, run_dir, ctx = _fake1_run(tmp_path)
    evidence = _with_overview(evidence, run_dir)
    report = validate(evidence, dict(ctx), dry_run=True)
    assert report["accepted"] is False
    flights = [e for e in report["errors"]
               if e["code"] == "FLIGHT_NOT_CONSIDERED"]
    assert flights, report["errors"]
    assert any("101" in e["detail"] and "113" in e["detail"]
               for e in flights), flights
    assert all(e.get("push") is True for e in flights)


def test_fake1_without_overview_missing_push_and_undetermined(tmp_path):
    """No overview while the result measures a motion (§43)."""
    evidence, _run_dir, ctx = _fake1_run(tmp_path)
    assert "overview" not in evidence["first_look"]
    # Brief §48: this fixture's range check re-measures the suited
    # figure reference line, which is refused in a real submit now;
    # this test is about the missing overview, so it drops it.
    evidence["range_checks"] = []
    dry = validate(copy.deepcopy(evidence), dict(ctx), dry_run=True)
    assert dry["accepted"] is False
    assert any(e["code"] == "MOTION_OVERVIEW_MISSING"
               and "motion_overview" in e["detail"]
               for e in dry["errors"]), dry["errors"]
    real = validate(evidence, dict(ctx))
    assert real["accepted"] is True, real["errors"]
    verdict = real["result"]["verdict"]
    assert verdict["kind"] == "undetermined"
    assert verdict["reason"] == ("the motions in the clip were not "
                                 "surveyed")
    assert verdict["g_measured"] is not None


def _noisy_rows(g, sigma, seed, start=30, end=60, level=200.0,
                fps=30.0, scale=0.01):
    """Deterministic noisy free-flight rows refitting near (g, sigma)."""
    import random

    rng = random.Random(seed)
    # Gaussian noise has unit rms, like the calibrated alternating
    # pattern (sigma 0.0475 per px of noise): scale to the target.
    amplitude_px = sigma / 0.0475
    airtime = (end - start) / fps
    vy = g * airtime / 2.0
    rows = []
    for frame in range(start, end + 1):
        moment = (frame - start) / fps
        y_m = vy * moment - 0.5 * g * moment * moment
        rows.append({"frame": frame, "x_px": 100.0,
                     "y_px": level - y_m / scale
                     + rng.gauss(0.0, 1.0) * amplitude_px})
    return rows


def test_two_flights_weighted_mean_and_jumps_agree(baseline, tmp_path):
    """Two flights give one g: the inverse-variance weighted mean."""
    import json as _json

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    rows_a = _noisy_rows(1.60, 0.10, seed=1234)
    rows_b = _noisy_rows(1.70, 0.20, seed=987)
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        _json.dumps(rows_a), encoding="utf-8")
    (run_dir / "workspace" / "track_hop_b.json").write_text(
        _json.dumps(rows_b), encoding="utf-8")
    produced.append("workspace/track_hop_b.json")
    good = copy.deepcopy(evidence)
    first = good["segments"][0]
    first["track_artifact"] = "workspace/track_hop_a.json"
    first["label"] = "Jump 1"
    first["fit_curve_px"] = [
        {"t_s": r["frame"] / 30.0, "x_px": r["x_px"],
         "y_px": r["y_px"]} for r in rows_a]
    second = copy.deepcopy(first)
    second["id"] = "hop_b"
    second["label"] = "Jump 2"
    second["track_artifact"] = "workspace/track_hop_b.json"
    second["fit_curve_px"] = [
        {"t_s": r["frame"] / 30.0, "x_px": r["x_px"],
         "y_px": r["y_px"]} for r in rows_b]
    good["segments"] = [first, second]
    good["first_look"]["motions"] = [
        {"frame_start": 30, "frame_end": 60,
         "description": "first hop", "segment_id": "hop_a",
         "skip_reason": None},
        {"frame_start": 90, "frame_end": 120,
         "description": "second hop", "segment_id": "hop_b",
         "skip_reason": None}]
    good["first_look"]["overview"]["candidates"].append(
        {"id": "cand_2", "frame_start": 30, "frame_end": 60,
         "airtime_s": 1.0, "peak_rise_px": 60.0,
         "decision": "measured", "segment_id": "hop_b",
         "reason": None})
    ctx = dict(ctx, produced_files=list(produced))

    from src.validate.validate import run_checks

    _errors, computed = run_checks(copy.deepcopy(good), dict(ctx))
    assert _errors == [], _errors
    fits = [info["fit"] for info in computed["segments"]]
    assert len(fits) == 2
    values = [float(f["g_app"]) for f in fits]
    sigmas = [float(f["g_app_sigma"]) for f in fits]
    assert all(s > 0 for s in sigmas)
    expected = sum(g / (s * s) for g, s in zip(values, sigmas)) / sum(
        1.0 / (s * s) for s in sigmas)
    simple = sum(values) / len(values)
    # Near the nominal 1.60/1.70 pair, and the weighting matters.
    assert expected == pytest.approx(1.62, abs=0.12)
    assert abs(simple - expected) > 0.01

    report = validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    verdict = report["result"]["verdict"]
    assert verdict["g_measured"] == pytest.approx(expected)
    steps = report["result"]["calculation_steps"]
    ids = [s["id"] for s in steps]
    assert ids == ["time_from_frames", "mask_check", "mask_check",
                   "scale", "segment", "fit", "segment", "fit",
                   "measured_g", "clock", "uncertainty", "verdict"]
    agree = next(s for s in steps if s["title"] == "Jumps agree")
    assert agree["id"] == "measured_g"
    texts = [b.get("fallback", "") + b.get("text", "")
             for b in agree["short"]]
    assert any("Jump 1" in t for t in texts)
    assert any("Jump 2" in t for t in texts)
    assert any("combined g" in t for t in texts)


def test_reference_far_from_motion_push(baseline, tmp_path):
    """A reference far from the first-check takeoff is pushed (§43)."""
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    # Takeoff is frame 30 (1.0 s); the reference at frame 100 is
    # 2.33 s away with no timing reason.
    evidence["references"][0]["extent_px"]["frame"] = 100
    evidence["references"][0]["size_derivation"]["note"] = ""
    # The moved measuring frame needs its own blind check (§50).
    extent = evidence["references"][0]["extent_px"]
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "frame": 100,
            "lines": [{"x1": extent["x1"], "y1": extent["y1"],
                       "x2": extent["x2"], "y2": extent["y2"],
                       "claim": "height of the reference block",
                       "description": "the line runs along the block",
                       "view": "front", "dimension": "height",
                       "agrees": True,
                       "why": "the description matches the claim"}],
            "overlay_artifact": "artifacts/t1_check_line_0.png",
            "turn": 1}) + "\n")
    dry = validate(copy.deepcopy(evidence), dict(ctx), dry_run=True)
    assert dry["accepted"] is False
    far = [e for e in dry["errors"]
           if e["code"] == "REFERENCE_FAR_FROM_MOTION"]
    assert len(far) == 1, dry["errors"]
    assert "references[0]" in far[0]["field"]
    assert far[0].get("push") is True
    real = validate(evidence, dict(ctx))
    assert real["accepted"] is True, real["errors"]
    scale_step = next(s for s in
                      real["result"]["calculation_steps"]
                      if s["id"] == "scale")
    assert any("more than 2 s" in c.get("text", "")
               for c in scale_step["caveats"])


def test_partial_coverage_push_and_undetermined(baseline, tmp_path):
    """Overview masks that stop mid-clip are partial (§43)."""
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    import numpy as np

    from src.helpers.masks_io import save_masks

    partial = {}
    for frame in range(101):
        if 30 <= frame <= 60:
            unit = (frame - 45) / 15.0
            bottom = int(round(160 - 60 * (1 - unit * unit)))
            box = [(bottom - 60, 150, bottom, 210)]
        else:
            box = [(100, 150, 160, 210)]
        canvas = np.zeros((240, 352), dtype=bool)
        r0, c0, r1, c1 = box[0]
        canvas[r0:r1, c0:c1] = True
        partial[frame] = canvas
    save_masks(str(run_dir / "artifacts" / "masks_part.npz"),
               {"0": partial})
    produced.append("artifacts/masks_part.npz")
    evidence["first_look"]["overview"]["artifact"] = \
        "artifacts/masks_part.npz"
    evidence["first_look"]["overview"]["tool_result"] = \
        "artifacts/overview.json"
    ctx = dict(ctx, produced_files=list(produced))
    dry = validate(copy.deepcopy(evidence), dict(ctx), dry_run=True)
    assert any(e["code"] == "MOTION_OVERVIEW_PARTIAL"
               for e in dry["errors"]), dry["errors"]
    real = validate(evidence, dict(ctx))
    assert real["accepted"] is True, real["errors"]
    assert real["result"]["verdict"]["reason"] == (
        "the motions in the clip were not surveyed")


def test_measured_candidate_without_segment_rejected(baseline, tmp_path):
    """A measured candidate naming no segment is MOTION_NOT_MEASURED."""
    evidence, _run, ctx, _produced = baseline(tmp_path)
    evidence["first_look"]["overview"]["candidates"][0][
        "segment_id"] = "hop_missing"
    report = validate(evidence, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "MOTION_NOT_MEASURED"
               for e in report["errors"]), report["errors"]


def test_presurvey_run_without_survey_masks_skips_overview_push(
        baseline, tmp_path):
    """A run with only single-frame masks predates the survey (§43).

    Part 07's default-valid-run mirror carries two single-frame
    reference masks and no whole-clip survey, so the overview
    recompute has nothing to judge. Such a run is judged as before
    §43: no MOTION_OVERVIEW_MISSING in a dry run. Once any object
    spans a candidate-length run (fake-1's whole-clip masks) the
    missing overview is pushed, as test_fake1_without_overview
    shows.
    """
    import copy

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    del evidence["first_look"]["overview"]
    for rel in ("artifacts/masks_all.npz", "artifacts/overview.json",
                "artifacts/seg_hop_a.npz"):
        try:
            (run_dir / rel).unlink()
        except OSError:
            pass
    evidence["segments"][0]["mask"] = {"artifact": "artifacts/ref_b.npz",
                                       "object_id": "0"}
    ctx = dict(ctx)
    ctx["artifacts"] = [a for a in ctx["artifacts"]
                        if a not in ("artifacts/masks_all.npz",
                                     "artifacts/overview.json",
                                     "artifacts/seg_hop_a.npz")]
    ctx["produced_files"] = [
        p for p in ctx["produced_files"]
        if p not in ("artifacts/masks_all.npz",
                     "artifacts/overview.json",
                     "artifacts/seg_hop_a.npz")]
    dry = validate(copy.deepcopy(evidence), dict(ctx), dry_run=True)
    assert not any(e["code"] == "MOTION_OVERVIEW_MISSING"
                   for e in dry["errors"]), dry["errors"]
    assert dry["accepted"] is True, dry["errors"]
    real = validate(evidence, dict(ctx))
    assert real["accepted"] is True, real["errors"]


def test_segment_in_no_candidate_rejected(baseline, tmp_path):
    """A segment in no overview candidate is MOTION_NOT_MEASURED."""
    evidence, _run, ctx, _produced = baseline(tmp_path)
    candidate = evidence["first_look"]["overview"]["candidates"][0]
    candidate["decision"] = "not_a_flight"
    candidate["segment_id"] = None
    candidate["reason"] = "a passing shadow, not a free flight"
    report = validate(evidence, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "MOTION_NOT_MEASURED"
               for e in report["errors"]), report["errors"]

# generated from brief/11 · part 11 owns this file
"""A named free flight is measured, not replaced (brief §56)."""

import copy


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _strip_to_no_segments(evidence):
    evidence["segments"] = []
    evidence["first_look"].pop("overview", None)
    # Range-only evidence needs a measurement so the skip rule is the
    # focus, not MEASUREMENT_MISSING: keep the baseline references
    # and add a minimal passing range check below in each test via
    # _with_range below. Here just clear segments/overview.
    return evidence


def _motion(start, end, reason, desc="jump over the car"):
    return {"frame_start": start, "frame_end": end,
            "description": desc, "segment_id": None,
            "skip_reason": reason}


def test_free_text_skip_refused(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    _strip_to_no_segments(bad)
    bad["first_look"]["motions"] = [
        _motion(63, 111,
                "height measured as range check against human norms, "
                "not as gravity fit")]
    dry = _validate(bad, dict(ctx), dry_run=True)
    assert dry["accepted"] is False
    skips = [e for e in dry["errors"]
             if e["code"] == "MOTION_SKIP_REASON"]
    assert skips, dry["errors"]
    assert any("first_look.motions[0]" in e["field"]
               and "63" in e["detail"] and "111" in e["detail"]
               for e in skips), skips
    real = _validate(bad, dict(ctx))
    assert real["accepted"] is False
    assert any(e["code"] == "MOTION_SKIP_REASON" for e in real["errors"])


def test_too_short_long_fails_short_passes(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    _strip_to_no_segments(bad)
    bad["first_look"]["motions"] = [_motion(63, 111, "too short: brief hop")]
    report = _validate(bad, dict(ctx), dry_run=True)
    skips = [e for e in report["errors"]
             if e["code"] == "MOTION_SKIP_REASON"]
    assert skips, report["errors"]
    assert any("too short" in e["detail"].lower() for e in skips), skips
    good = copy.deepcopy(evidence)
    _strip_to_no_segments(good)
    good["first_look"]["motions"] = [_motion(63, 67, "too short: brief hop")]
    report2 = _validate(good, dict(ctx), dry_run=True)
    assert not [e for e in report2["errors"]
                if e["code"] == "MOTION_SKIP_REASON"], report2["errors"]


def test_cut_without_cut_fails_with_cut_passes(baseline, tmp_path):
    import json

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    _strip_to_no_segments(bad)
    bad["first_look"]["motions"] = [_motion(63, 111, "cut: jump is cut")]
    report = _validate(bad, dict(ctx), dry_run=True)
    assert any(e["code"] == "MOTION_SKIP_REASON"
               and "cut" in e["detail"].lower()
               for e in report["errors"]), report["errors"]
    # A cut inside the entry's frames satisfies the reason.
    timing_path = run_dir / "input" / "timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    timing["cuts"] = [80]
    timing_path.write_text(json.dumps(timing), encoding="utf-8")
    ctx2 = dict(ctx)
    ctx2["timing"] = timing
    report2 = _validate(bad, ctx2, dry_run=True)
    assert not [e for e in report2["errors"]
                if e["code"] == "MOTION_SKIP_REASON"], report2["errors"]


def test_no_flight_without_overview_pushes(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    _strip_to_no_segments(bad)
    bad["first_look"]["motions"] = [_motion(63, 111, "no flight: blur")]
    assert "overview" not in bad["first_look"]
    dry = _validate(bad, dict(ctx), dry_run=True)
    assert any(e["code"] == "MOTION_OVERVIEW_MISSING"
               for e in dry["errors"]), dry["errors"]
    assert not [e for e in dry["errors"]
                if e["code"] == "MOTION_SKIP_REASON"], dry["errors"]


def test_no_flight_with_overlapping_candidate_fails(baseline, tmp_path):
    evidence, run_dir, ctx, produced = baseline(tmp_path)
    from tests.validate.conftest import write_mask

    bad = copy.deepcopy(evidence)
    bad["segments"] = []
    # Whole-clip masks with a hump over 60-115, so the recomputed
    # overview has a candidate overlapping the 63-111 motion.
    ground = {frame: [(100, 150, 160, 210)] for frame in range(300)}
    for frame in range(60, 116):
        unit = (frame - 87.5) / 27.5
        bottom = int(round(160 - 60 * (1 - unit * unit)))
        ground[frame] = [(bottom - 60, 150, bottom, 210)]
    write_mask(run_dir, "artifacts/masks_all2.npz", {"0": ground},
               produced, shape=(240, 352))
    (run_dir / "artifacts" / "overview2.json").write_text(
        __import__("json").dumps(
            {"masks_artifact": "artifacts/masks_all2.npz",
             "object_id": "0",
             "candidates": [{"id": "F1", "frame_start": 60,
                             "frame_end": 115}]}),
        encoding="utf-8")
    produced.append("artifacts/overview2.json")
    bad["first_look"]["overview"] = {
        "artifact": "artifacts/masks_all2.npz",
        "object_id": "0",
        "tool_result": "artifacts/overview2.json",
        "candidates": [
            {"id": "cand_1", "frame_start": 60, "frame_end": 115,
             "airtime_s": 1.0, "peak_rise_px": 60.0,
             "decision": "not_a_flight",
             "segment_id": None,
             "reason": "blur"}],
        "first_check": {"segment_id": "hop_a",
                        "why": "longest clear flight"},
    }
    # The overview decision must still satisfy V1: measured needs a
    # segment; not_a_flight carries a reason. No segments exist, so
    # the candidate is decided otherwise and MOTION_NOT_MEASURED
    # from overview decisions stays silent.
    bad["first_look"]["motions"] = [_motion(63, 111, "no flight: blur")]
    ctx = dict(ctx, produced_files=list(produced))
    import json as _json

    ctx["artifacts"] = sorted(
        str(p.relative_to(run_dir)) for p in
        (run_dir / "artifacts").rglob("*") if p.is_file())
    dry = _validate(bad, ctx, dry_run=True)
    skips = [e for e in dry["errors"]
             if e["code"] == "MOTION_SKIP_REASON"]
    assert skips, dry["errors"]
    assert any("no flight" in e["detail"].lower() for e in skips), skips


def test_segment_present_keeps_free_text(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["first_look"]["motions"] = [
        {"frame_start": 30, "frame_end": 60,
         "description": "foreground hop", "segment_id": "hop_a",
         "skip_reason": None},
        {"frame_start": 63, "frame_end": 111,
         "description": "jump over the car", "segment_id": None,
         "skip_reason": "height measured as range check"}]
    report = _validate(good, dict(ctx), dry_run=True)
    assert not [e for e in report["errors"]
                if e["code"] == "MOTION_SKIP_REASON"], report["errors"]


def test_short_only_needs_no_prefix(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["segments"] = []
    good["first_look"].pop("overview", None)
    good["first_look"]["motions"] = [
        _motion(63, 67, "still: hand held still")]
    report = _validate(good, dict(ctx), dry_run=True)
    # No 8-frame entry: the §56 rule does not apply.
    assert not [e for e in report["errors"]
                if e["code"] == "MOTION_SKIP_REASON"], report["errors"]

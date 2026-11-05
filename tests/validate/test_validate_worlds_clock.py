# generated from brief/11 · part 11 owns this file
"""Worlds and the honest clock (V10/V11, §§3, 9)."""

import copy


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _clock(rate, sigma=0.05, lo=1.0, hi=2.0, interpretation="step"):
    return {
        "signal_description": "width of the lowest thirty percent",
        "measured_rate_hz": rate,
        "measured_rate_sigma_hz": sigma,
        "interpretation": interpretation,
        "band_hz": [0.5, 4.0],
        "natural_range_hz": [lo, hi],
        "natural_range_source": {
            "url": "https://example.com/gait",
            "quote": "preferred frequency is 1 to 2 Hz"},
    }


def test_exclusion_without_frames_rejected(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["worlds"]["excluded"][0]["evidence_frames"] = []
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "WORLD_NOT_FROM_SCENE"
               for e in report["errors"]), report["errors"]


def test_unknown_world_rejected(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["worlds"]["candidates"].append({"world": "Jupiter"})
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "WORLD_NOT_FROM_SCENE"
               for e in report["errors"]), report["errors"]


def test_world_both_candidate_and_excluded(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["worlds"]["excluded"].append({
        "world": "Moon", "evidence_text": "grey ground",
        "evidence_frames": [0],
        "evidence_artifact": "artifacts/view_0.jpg"})
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert any(e["code"] == "WORLD_NOT_FROM_SCENE"
               for e in report["errors"]), report["errors"]


def test_clock_branches(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    # Native Moon fit needs no clock.
    report = _validate(copy.deepcopy(evidence), dict(ctx))
    assert report["accepted"] is True
    assert report["result"]["verdict"]["world"] == "Moon"


def test_normal_clock_never_retimes(baseline, tmp_path):
    import json as _json

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    # g = 1.177 at normal speed fits no world: never retimed.
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    for row in rows:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * (1.177 / 1.62)
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        _json.dumps(rows), encoding="utf-8")
    bad = copy.deepcopy(evidence)
    curve = bad["segments"][0]["fit_curve_px"]
    for sample, row in zip(curve, rows):
        sample["y_px"] = row["y_px"]
    bad["clock"] = _clock(1.288, sigma=0.2)
    bad["clock_absent_reason"] = None
    bad["error_budget"]["sigma_relative"] = 0.0736
    report = _validate(bad, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["verdict"]["kind"] != "retimed"
    assert "cannot separate" in \
        report["result"]["verdict"]["reason"]


def test_retimed_end_to_end(baseline, tmp_path):
    import json as _json

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
    good["clock"] = _clock(0.6, sigma=0.02, lo=1.4, hi=2.0,
                           interpretation="stride")
    good["clock_absent_reason"] = None
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "retimed", verdict
    assert verdict["world"] == "Moon"
    assert abs(verdict["factor"] - 1.43) < 0.05


def test_slow_clock_retimes_to_moon(baseline, tmp_path):
    import json as _json

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
    good["clock"] = _clock(0.6, sigma=0.02, lo=1.4, hi=2.0,
                           interpretation="stride")
    good["clock_absent_reason"] = None
    # A reference on the moving thing, or the dry run lists the
    # SELF_REFERENCE_REQUIRED push (brief §53, R-S16).
    good["references"][1]["mask"] = {
        "artifact": "artifacts/masks_all.npz", "object_id": "0",
        "frame": 10,
        "outline": [[100.0, 20.0], [271.0, 20.0],
                    [271.0, 191.0], [100.0, 191.0]]}
    report = _validate(good, dict(ctx), dry_run=True)
    assert report["accepted"] is True, report["errors"]


def test_scene_pinned_no_clock_retimes(baseline, tmp_path):
    import json as _json

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
    good["worlds"]["candidates"] = [{"world": "Moon"}]
    good["clock_absent_reason"] = "no visible independent rhythm"
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "retimed"
    assert verdict["world"] == "Moon"


def test_g_fitting_no_world_without_clock(baseline, tmp_path):
    import json as _json

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    for row in rows:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * (1.177 / 1.62)
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        _json.dumps(rows), encoding="utf-8")
    good = copy.deepcopy(evidence)
    curve = good["segments"][0]["fit_curve_px"]
    for sample, row in zip(curve, rows):
        sample["y_px"] = row["y_px"]
    good["clock_absent_reason"] = "no visible independent rhythm"
    good["error_budget"]["sigma_relative"] = 0.0736
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["verdict"]["kind"] == "undetermined"


def test_no_clock_two_candidates_undetermined(baseline, tmp_path):
    import json as _json

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    for row in rows:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * (5.0 / 1.62)
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        _json.dumps(rows), encoding="utf-8")
    good = copy.deepcopy(evidence)
    curve = good["segments"][0]["fit_curve_px"]
    for sample, row in zip(curve, rows):
        sample["y_px"] = row["y_px"]
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["verdict"]["kind"] == "undetermined"


def test_ambiguous_step_stride_forces_undetermined(baseline, tmp_path):
    import json as _json

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
    clock = _clock(0.6, sigma=0.02, lo=1.4, hi=2.0,
                   interpretation="stride")
    clock["ambiguous"] = True
    good["clock"] = clock
    good["clock_absent_reason"] = None
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    assert report["result"]["verdict"]["kind"] == "undetermined"


def test_conflicting_segments_undetermined(baseline, tmp_path):
    import json as _json

    evidence, run_dir, ctx, produced = baseline(tmp_path)
    rows = _json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    rows_b = copy.deepcopy(rows)
    for row in rows_b:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * (5.0 / 1.62)
    (run_dir / "workspace" / "track_hop_b.json").write_text(
        _json.dumps(rows_b), encoding="utf-8")
    produced.append("workspace/track_hop_b.json")
    good = copy.deepcopy(evidence)
    second = copy.deepcopy(good["segments"][0])
    second["id"] = "hop_b"
    second["track_artifact"] = "workspace/track_hop_b.json"
    second["fit_curve_px"] = [
        {"t_s": r["frame"] / 30.0, "x_px": r["x_px"],
         "y_px": r["y_px"]} for r in rows_b]
    good["segments"].append(second)
    good["error_budget"]["sigma_relative"] = 0.4
    good["first_look"]["overview"]["candidates"].append(
        {"id": "cand_2", "frame_start": 30, "frame_end": 60,
         "airtime_s": 1.0, "peak_rise_px": 60.0,
         "decision": "measured", "segment_id": "hop_b",
         "reason": None})
    good["first_look"]["motions"].append(
        {"frame_start": 90, "frame_end": 120,
         "description": "second hop", "segment_id": "hop_b",
         "skip_reason": None})
    ctx = dict(ctx, produced_files=list(produced))
    report = _validate(good, ctx)
    assert report["accepted"] is True, report["errors"]
    verdict = report["result"]["verdict"]
    assert verdict["kind"] == "undetermined"
    assert "conflicting" in verdict["reason"]

# generated from brief/11 · part 11 owns this file
"""Push codes: dry-run only (brief §16.2–16.3)."""

import copy
import json


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def test_push_codes_exact():
    from src.validate import PUSH_CODES

    assert tuple(PUSH_CODES) == ("SECOND_REFERENCE_REQUIRED",
                                 "CLOCK_REQUIRED",
                                 "MOTIONS_SCAN_MISSING",
                                 "MOTION_OVERVIEW_MISSING",
                                 "MOTION_OVERVIEW_PARTIAL",
                                 "FLIGHT_NOT_CONSIDERED",
                                 "REFERENCE_FAR_FROM_MOTION",
                                 "SELF_REFERENCE_REQUIRED")


def _single_ref(evidence):
    evidence = copy.deepcopy(evidence)
    evidence["references"] = evidence["references"][:1]
    evidence["scale"]["second_reference_index"] = None
    evidence["scale"]["second_reference_absent_reason"] = \
        "only one thing of known size at the depth of the motion"
    return evidence


def test_single_reference_push_dry_only(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    dry = _validate(_single_ref(evidence), dict(ctx), dry_run=True)
    assert dry["accepted"] is False
    assert any(e["code"] == "SECOND_REFERENCE_REQUIRED"
               and "R-S6" in e["detail"] for e in dry["errors"])
    real = _validate(_single_ref(evidence), dict(ctx))
    assert real["accepted"] is True, real["errors"]
    assert real["result"]["verdict"]["kind"] == "undetermined"


def test_clock_required_dry_only(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    rows = json.loads(
        (run_dir / "workspace" / "track_hop_a.json").read_text(
            encoding="utf-8"))
    for row in rows:
        row["y_px"] = 200.0 + (row["y_px"] - 200.0) * (5.0 / 1.62)
    (run_dir / "workspace" / "track_hop_a.json").write_text(
        json.dumps(rows), encoding="utf-8")
    good = copy.deepcopy(evidence)
    curve = good["segments"][0]["fit_curve_px"]
    for sample, row in zip(curve, rows):
        sample["y_px"] = row["y_px"]
    good["clock_absent_reason"] = "no visible independent rhythm"
    dry = _validate(copy.deepcopy(good), dict(ctx), dry_run=True)
    assert dry["accepted"] is False
    assert any(e["code"] == "CLOCK_REQUIRED"
               and "R-C1" in e["detail"] for e in dry["errors"])
    real = _validate(good, dict(ctx))
    assert real["accepted"] is True, real["errors"]
    assert real["result"]["verdict"]["kind"] == "undetermined"


def _write_turn(run_dir, name, calls):
    (run_dir / "logs" / name).write_text(
        json.dumps({"turn": 1, "tool_calls": calls}),
        encoding="utf-8")


def test_motions_scan_gap(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    _write_turn(run_dir, "turn_001.json", [
        {"tool": "view_frames",
         "arguments": {"frame_start": 0, "frame_end": 100,
                       "stride": 1}}])
    dry = _validate(copy.deepcopy(evidence), dict(ctx), dry_run=True)
    assert any(e["code"] == "MOTIONS_SCAN_MISSING"
               and "R-M4" in e["detail"] for e in dry["errors"]), \
        dry["errors"]


def test_motions_scan_covered(baseline, tmp_path):
    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    _write_turn(run_dir, "turn_001.json", [
        {"tool": "view_frames",
         "arguments": {"frame_start": 0, "frame_end": 239,
                       "stride": 6}},
        {"tool": "view_frames",
         "arguments": {"frame_start": 239, "frame_end": 299,
                       "stride": 6}}])
    dry = _validate(copy.deepcopy(evidence), dict(ctx), dry_run=True)
    assert not any(e["code"] == "MOTIONS_SCAN_MISSING"
                   for e in dry["errors"]), dry["errors"]


def _with_self_reference(evidence):
    """Point a reference at the survey object (brief §53, R-S16).

    Without a reference on the moving thing, a dry run lists the
    SELF_REFERENCE_REQUIRED push, so tests asserting a clean dry
    run set this up first.
    """
    evidence["references"][1]["mask"] = {
        "artifact": "artifacts/masks_all.npz", "object_id": "0",
        "frame": 10,
        "outline": [[100.0, 20.0], [271.0, 20.0],
                    [271.0, 191.0], [100.0, 191.0]]}
    return evidence


def test_no_turn_logs_no_scan_check(baseline, tmp_path):
    evidence, _run, ctx, _produced = baseline(tmp_path)
    dry = _validate(_with_self_reference(copy.deepcopy(evidence)),
                    dict(ctx), dry_run=True)
    assert dry["accepted"] is True, dry["errors"]

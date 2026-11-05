# generated from brief/11 · part 11 owns this file
"""V1: the evidence-schema gate (brief §§6.1, 6.3, 7, 17)."""

import copy


def _v1(evidence):
    from src.validate.v1 import check_v1

    return check_v1(evidence)


def test_v1_rejects_non_object():
    errors = _v1(["not", "an", "object"])
    assert len(errors) == 1
    assert errors[0]["code"] == "MISSING_FIELD"
    assert errors[0]["field"] == "evidence"


def test_v1_gates_the_rest(baseline, tmp_path):
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    del bad["scale"]
    # Also break a later check: the track rows no longer refit.
    bad["segments"][0]["track_artifact"] = "workspace/gone.json"
    report = validate(bad, dict(ctx))
    assert report["accepted"] is False
    assert report["errors"], "V1 must report the malformed input"
    assert {e["code"] for e in report["errors"]} == {"MISSING_FIELD"}
    assert all(e["field"].startswith("scale")
               for e in report["errors"])


def test_fields_name_exact_paths(baseline, tmp_path):
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["segments"][0]["track_artifact"] = "workspace/gone.json"
    report = validate(bad, dict(ctx))
    assert report["accepted"] is False
    fields = [e["field"] for e in report["errors"]]
    assert "segments[0].track_artifact" in fields
    assert not any("?" in f for f in fields)


def test_missing_track_states_row_format(baseline, tmp_path):
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["segments"][0]["track_artifact"] = "workspace/gone.json"
    report = validate(bad, dict(ctx))
    details = " ".join(e["detail"] for e in report["errors"])
    assert "{frame, x_px, y_px}" in details


def test_camera_branch_single_error(baseline, tmp_path):
    evidence, _run, _ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["camera"] = {"still": {"reference_phrase": "flag"}}
    errors = _v1(bad)
    assert len(errors) == 1, errors
    assert errors[0]["code"] == "MISSING_FIELD"
    assert errors[0]["field"] == \
        "camera.still.reference_track_artifact"


def test_camera_without_shape_names_allowed_keys(baseline, tmp_path):
    evidence, _run, _ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["camera"] = {"still": None,
                     "relative": {"reference_track_artifact": "x"}}
    errors = _v1(bad)
    assert len(errors) == 1, errors
    assert errors[0]["code"] == "MISSING_FIELD"
    assert errors[0]["field"] == "camera"
    assert "relative_track_artifact" in errors[0]["detail"]


def test_check_scale_object_branch_names_keys(baseline, tmp_path):
    # Brief §34, wall run 14's shape: check_scale carries
    # {m_per_px, sigma_m_per_px} while the schema wants
    # {m_per_px, sigma}. The error names the missing key and the
    # key that is not allowed, in exactly one record. A null and a
    # correct object both pass.
    evidence, _run, _ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["scale"]["check_scale"] = {"m_per_px": 0.01,
                                   "sigma_m_per_px": 0.0012}
    errors = _v1(bad)
    assert len(errors) == 1, errors
    assert errors[0]["code"] == "MISSING_FIELD"
    assert errors[0]["field"] == "scale.check_scale"
    assert "missing key 'sigma'" in errors[0]["detail"], errors[0]
    assert "key 'sigma_m_per_px' is not allowed" in errors[0][
        "detail"], errors[0]
    null = copy.deepcopy(evidence)
    null["scale"]["check_scale"] = None
    assert [e for e in _v1(null)
            if e["field"] == "scale.check_scale"] == []
    good = copy.deepcopy(evidence)
    good["scale"]["check_scale"] = {"m_per_px": 0.01,
                                    "sigma": 0.0012}
    assert [e for e in _v1(good)
            if e["field"] == "scale.check_scale"] == []


def test_crash_is_validator_fault_not_attempt(baseline, tmp_path):
    from src.validate import validate

    evidence, run_dir, ctx, _produced = baseline(tmp_path)
    # Schema-valid but perverse file contents: V1 passes, and the
    # later checks must stay total — structured errors, never raised.
    import json as _json

    track = run_dir / "workspace" / "track_hop_a.json"
    track.write_text(_json.dumps(["a", "string", "not", "rows"]),
                     encoding="utf-8")
    report = validate(copy.deepcopy(evidence), ctx)
    assert report["accepted"] is False
    codes = [e.get("code") for e in report.get("errors", [])]
    assert "VALIDATOR_FAULT" not in codes
    assert any(e["code"] == "MISSING_FIELD"
               and e["field"] == "segments[0].track_artifact"
               for e in report["errors"])
    assert not (run_dir / "logs" / "validator_fault.txt").exists()


def test_dry_run_fault_writes_nothing(baseline, tmp_path):
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    bad = copy.deepcopy(evidence)
    bad["segments"] = "not-a-list"
    before = {p.name for p in (_run / "logs").iterdir()} | {
        p.name for p in _run.iterdir()}
    report = validate(bad, dict(ctx), dry_run=True)
    assert report["accepted"] is False
    after = {p.name for p in (_run / "logs").iterdir()} | {
        p.name for p in _run.iterdir()}
    assert after == before
    assert "result" not in report

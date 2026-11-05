# generated from brief/11 · part 11 owns this file
"""Pinned interface tests (brief §10)."""

import copy
import json


def test_pinned_names_importable():
    import src.validate as v

    for name in ("validate", "synthesize_undetermined", "write_result",
                 "REQUIRED_COMPONENTS", "PUSH_CODES"):
        assert hasattr(v, name), name
    from src.validate import (  # noqa: F401
        PUSH_CODES,
        REQUIRED_COMPONENTS,
        synthesize_undetermined,
        validate,
        write_result,
    )
    assert tuple(PUSH_CODES) == ("SECOND_REFERENCE_REQUIRED",
                                 "CLOCK_REQUIRED",
                                 "MOTIONS_SCAN_MISSING",
                                 "MOTION_OVERVIEW_MISSING",
                                 "MOTION_OVERVIEW_PARTIAL",
                                 "FLIGHT_NOT_CONSIDERED",
                                 "REFERENCE_FAR_FROM_MOTION",
                                 "SELF_REFERENCE_REQUIRED")
    assert set(REQUIRED_COMPONENTS) == {"reference_size", "pixel_scale",
                                        "fit", "point_vs_com"}
    from src.validate.checks import REQUIRED_COMPONENTS as _rc

    assert set(_rc) == set(REQUIRED_COMPONENTS)
    from src.validate.synthesis import (  # noqa: F401
        synthesize_undetermined as _s,
        write_result as _w,
    )


def test_validate_signature_and_shapes(baseline, tmp_path):
    from src.validate import validate

    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = validate(copy.deepcopy(evidence), dict(ctx))
    assert set(report) >= {"accepted", "errors"}
    assert report["accepted"] is True
    assert report["errors"] == []
    assert "result" in report and "result_path" in report
    # A reference on the moving thing, or the dry run lists the
    # SELF_REFERENCE_REQUIRED push (brief §53, R-S16).
    evidence["references"][1]["mask"] = {
        "artifact": "artifacts/masks_all.npz", "object_id": "0",
        "frame": 10,
        "outline": [[100.0, 20.0], [271.0, 20.0],
                    [271.0, 191.0], [100.0, 191.0]]}
    dry = validate(copy.deepcopy(evidence), dict(ctx), dry_run=True)
    assert dry["accepted"] is True
    assert dry["errors"] == []
    assert "result" not in dry


def test_synthesize_signature_and_last_errors(tmp_path):
    from src.contract import validate_result
    from src.validate import synthesize_undetermined, write_result

    run_dir = tmp_path / "run"
    errors = [{"code": "E1", "field": "evidence",
               "detail": "first problem"},
              {"code": "E2", "field": "scale",
               "detail": "second problem"}]
    result = synthesize_undetermined(str(run_dir), "run-9", "budget",
                                     detail="turns >= 90",
                                     errors=list(errors))
    assert validate_result(result) == []
    assert result["verdict"]["kind"] == "undetermined"
    path = write_result(str(run_dir), result)
    assert path.endswith("result.json")
    back = json.loads((run_dir / "logs"
                       / "validator_last_errors.json").read_text(
                           encoding="utf-8"))
    assert back == errors


def test_synthesize_never_raises_on_content(tmp_path):
    from src.contract import validate_result
    from src.validate import synthesize_undetermined

    run_dir = tmp_path / "run"
    for bad in (None, "budget", 42, [{"code": 1}],
                {"not": "a list"}):
        result = synthesize_undetermined(str(run_dir), None, bad,
                                         detail=None, errors=bad)
        assert validate_result(result) == []
        assert result["verdict"]["kind"] == "undetermined"

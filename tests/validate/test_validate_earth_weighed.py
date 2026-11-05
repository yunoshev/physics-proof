# generated from brief/11 · part 11 owns this file
"""Earth is always weighed; a missing clock reads as a plain statement.

Brief §41: the evidence may name Earth neither as a candidate nor as
an excluded world — for a result with a measured g the validator adds
Earth (9.81 m/s²) to ``worlds.candidates`` with ``delta_sigma``,
``fits_native`` and ``retime_factor`` computed as for every other
candidate. The verdict is decided over the agent's candidates first
and does not change. A missing clock reads as a fixed sentence
written by the validator; ``clock_absent_reason`` stays in the result
but the step never prints the agent's text.
"""

import copy
import math

import pytest


def _validate(evidence, ctx, dry_run=False):
    from src.validate import validate

    return validate(evidence, ctx, dry_run=dry_run)


def _moon_only(evidence):
    good = copy.deepcopy(evidence)
    good["worlds"] = {
        "candidates": [{"world": "Moon"}],
        "excluded": [
            {"world": "Mars",
             "evidence_text": "grey ground, no red soil",
             "evidence_frames": [0],
             "evidence_artifact": "artifacts/excl_mars.jpg"}],
    }
    return good


def test_moon_only_evidence_gains_earth_chip(baseline, tmp_path):
    # Moon run 22's shape: the evidence names only the Moon, the
    # measured g fits it natively, and the result weighs Earth too.
    from src.contract import validate_result

    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = _moon_only(evidence)
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    result = report["result"]
    assert validate_result(result) == []
    # The verdict is decided over the agent's candidates: still
    # Realistic on the Moon.
    assert result["verdict"]["kind"] == "world"
    assert result["verdict"]["world"] == "Moon"
    assert result["sentence"].startswith("Realistic on the Moon: ")
    candidates = result["worlds"]["candidates"]
    assert [c["world"] for c in candidates] == ["Moon", "Earth"]
    moon, earth = candidates
    assert moon["fits_native"] is True
    assert earth["g_m_s2"] == pytest.approx(9.81)
    assert earth["fits_native"] is False
    g_measured = result["verdict"]["g_measured"]
    sigma_g = result["verdict"]["sigma_g"]
    assert earth["delta_sigma"] == pytest.approx(
        abs(9.81 - g_measured) / sigma_g)
    assert earth["retime_factor"] == pytest.approx(
        math.sqrt(9.81 / g_measured))
    assert earth["delta_sigma"] > 2.0


def test_excluded_earth_gets_no_earth_candidate(baseline, tmp_path):
    # Evidence that excludes Earth with frame evidence gets no Earth
    # candidate: the exclusion stands.
    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = _moon_only(evidence)
    good["worlds"]["excluded"].append(
        {"world": "Earth",
         "evidence_text": "grey ground and a slow hop, not Earth",
         "evidence_frames": [30],
         "evidence_artifact": "artifacts/excl_mars.jpg"})
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    candidates = report["result"]["worlds"]["candidates"]
    assert [c["world"] for c in candidates] == ["Moon"]
    assert report["result"]["verdict"]["world"] == "Moon"


def test_named_earth_keeps_exactly_one_entry(baseline, tmp_path):
    # Evidence that names Earth as a candidate keeps exactly one Earth
    # entry: the validator never duplicates it.
    evidence, _run, ctx, _produced = baseline(tmp_path)
    report = _validate(evidence, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    candidates = report["result"]["worlds"]["candidates"]
    assert [c["world"] for c in candidates].count("Earth") == 1


def test_missing_clock_reads_fixed_sentence(baseline, tmp_path):
    # The clock step never prints the agent's working note: it reads
    # exactly the validator's fixed sentence, while the result keeps
    # the agent's clock_absent_reason.
    evidence, _run, ctx, _produced = baseline(tmp_path)
    good = copy.deepcopy(evidence)
    good["clock"] = None
    good["clock_absent_reason"] = (
        "no independent rhythm needed for first dry run")
    report = _validate(good, dict(ctx))
    assert report["accepted"] is True, report["errors"]
    result = report["result"]
    assert result["clock"] is None
    assert result["clock_absent_reason"] == (
        "no independent rhythm needed for first dry run")
    steps = result["calculation_steps"]
    clock_steps = [s for s in steps if s["id"] == "clock"]
    assert len(clock_steps) == 1
    text = " ".join(
        block.get("fallback", block.get("text", ""))
        for block in clock_steps[0]["short"])
    assert text == ("No independent clock in this clip: the speed is "
                    "taken as filmed.")

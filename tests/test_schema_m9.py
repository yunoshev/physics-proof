"""M9 probes: validator on the fixtures, removals, tampers, combine, schema_doc."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from physics_proof import blocks
from physics_proof.schema import Issue, combine, load_schema, schema_doc, validate

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str) -> dict:
    """Load one fixture analysis."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# Probe 1: both fixtures validate with no issues.
def test_fixtures_validate_clean() -> None:
    """Both fixture analyses validate with no issues."""
    for name in ("analysis_ball.json", "analysis_ramp.json"):
        assert validate(load(name)) == [], name


def _required_paths(node: object, root: dict, base: tuple = ()) -> list[tuple]:
    """All schema-required field paths; 0 marks an array item, $refs resolved."""
    paths: list[tuple] = []
    if not isinstance(node, dict):
        return paths
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        target: object = root
        for part in ref[2:].split("/"):
            target = target[part]  # type: ignore[index]
        return _required_paths(target, root, base)
    for key in node.get("required") or []:
        paths.append(base + (key,))
    props = node.get("properties")
    if isinstance(props, dict):
        for key, sub in props.items():
            paths.extend(_required_paths(sub, root, base + (key,)))
    items = node.get("items")
    if isinstance(items, dict):
        paths.extend(_required_paths(items, root, base + (0,)))
    for alt in ("anyOf", "oneOf"):
        branches = node.get(alt)
        if isinstance(branches, list):
            for branch in branches:
                paths.extend(_required_paths(branch, root, base))
    seen, unique = set(), []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _has(node: object, path: tuple) -> bool:
    """True when the fixture actually contains this schema path."""
    for part in path:
        if isinstance(node, list):
            if part != 0 or not node:
                return False
            node = node[0]
        elif isinstance(node, dict):
            if part not in node:
                return False
            node = node[part]
        else:
            return False
    return True


def _delete(node: object, path: tuple) -> None:
    """Remove the field at path (lists are entered at index 0)."""
    for part in path[:-1]:
        node = node[part] if isinstance(node, dict) else node[0]  # type: ignore[index]
    last = path[-1]
    if isinstance(node, dict):
        del node[last]  # type: ignore[index]
    else:
        del node[last]


def _pointer(path: tuple) -> str:
    """JSON-pointer-like string for a path tuple."""
    return "/" + "/".join(str(part) for part in path)


# Probe 2: removing each required field in turn names that exact path.
def test_removing_each_required_field_names_its_path() -> None:
    """Every schema-required field present in a fixture is enforced by name."""
    schema = load_schema()
    paths = _required_paths(schema, schema)
    assert len(paths) > 50, "walker found too few required fields"
    fixtures = {
        "analysis_ball.json": load("analysis_ball.json"),
        "analysis_ramp.json": load("analysis_ramp.json"),
    }
    uncovered = []
    for path in paths:
        pointer = _pointer(path)
        covered = False
        for name, fixture in fixtures.items():
            if not _has(fixture, path):
                continue
            covered = True
            broken = copy.deepcopy(fixture)
            _delete(broken, path)
            issues = validate(broken)
            assert any(i.path == pointer for i in issues), (name, pointer)
        if not covered:
            uncovered.append(pointer)
    assert uncovered == []


def _tampered(name: str, mutate) -> list[Issue]:
    """Validate a fixture after applying mutate to a deep copy."""
    broken = load(name)
    mutate(broken)
    return validate(broken)


# Probe 3: each tamper class is rejected with a readable message.
def test_tampered_verdict_state_rejected() -> None:
    """A swapped verdict state fails the decide recomputation."""
    issues = _tampered("analysis_ball.json", lambda a: a["verdict"].update(state="fits:Moon"))
    assert issues
    assert any(i.path.startswith("/verdict") or i.path.startswith("/overall") for i in issues)
    assert all(len(i.message) > 10 for i in issues)


def test_tampered_flight_k_rejected() -> None:
    """A scaled flight k fails the decide recomputation."""
    def mutate(a: dict) -> None:
        a["flights"][0]["decide"]["k"] *= 1.5
    issues = _tampered("analysis_ball.json", mutate)
    assert any(i.path == "/flights/0/decide/k" for i in issues)


def test_wrong_duration_rejected() -> None:
    """A duration that disagrees with the frame span is rejected."""
    issues = _tampered("analysis_ball.json", lambda a: a["flights"][0].update(duration_s=2.0))
    assert any(i.path == "/flights/0/duration_s" for i in issues)


def test_wrong_rise_rejected() -> None:
    """A rise that disagrees with the track is rejected."""
    issues = _tampered("analysis_ball.json", lambda a: a["flights"][0].update(rise_m=9.9))
    assert any(i.path == "/flights/0/rise_m" for i in issues)


def test_frame_outside_clip_rejected() -> None:
    """A track point past the last frame is rejected."""
    def mutate(a: dict) -> None:
        a["track"]["points"].append({"frame": 999, "x": 0.0, "y": 0.0})
    issues = _tampered("analysis_ball.json", mutate)
    assert any(i.path == "/track/points/31/frame" for i in issues)


def test_wrong_overall_label_rejected() -> None:
    """An overall label that disagrees with combine is rejected."""
    issues = _tampered("analysis_ball.json", lambda a: a["overall"].update(label="Moon"))
    assert any(i.path == "/overall/label" for i in issues)


def test_unknown_fields_ignored() -> None:
    """Extra fields do not invalidate a fixture."""
    ball = load("analysis_ball.json")
    ball["extra_section"] = {"note": "ignored"}
    ball["flights"][0]["extra"] = 1
    assert validate(ball) == []


def test_clip_overrides() -> None:
    """clip_frames/fps overrides are honoured for frame checks."""
    assert validate(load("analysis_ramp.json"), clip_frames=240) == []
    assert validate(load("analysis_ramp.json"), clip_frames=150)


# Probe 4: the combine table.
def test_combine_fits() -> None:
    """fits:Earth gives the Earth label."""
    out = combine(blocks.decide(9.81, 0.3), None)
    assert out["label"] == "Earth"
    assert len(out["text"].split(". ")) == 1


def test_combine_undetermined() -> None:
    """An error spanning both worlds gives undetermined."""
    out = combine(blocks.decide(5.0, 5.0), None)
    assert out["label"] == "undetermined"


def test_combine_impossible() -> None:
    """none_fits at normal speed is impossible."""
    verdict = blocks.decide(4.0, 0.5, {"unsupported on Earth": 9.81})
    timescale = {"verdict": "normal"}
    out = combine(verdict, timescale)
    assert out["label"] == "impossible"
    assert "ignores gravity at normal speed" in out["text"]


def test_combine_none_fits_without_timescale() -> None:
    """none_fits with no timescale keeps the playback factor."""
    verdict = blocks.decide(4.0, 0.5, {"unsupported on Earth": 9.81})
    out = combine(verdict, None)
    assert out["label"] == "none_fits"
    assert "1.57" in out["text"]


def test_combine_retimed() -> None:
    """none_fits with a consistent slow timescale is retimed."""
    verdict = blocks.decide(4.0, 0.5, {"unsupported on Earth": 9.81})
    timescale = {
        "method": "step rate", "value": 3.2, "err": 0.3, "unit": "steps/s",
        "expected_range": [4.5, 5.2], "verdict": "slow",
    }
    out = combine(verdict, timescale)
    assert out["label"] == "retimed"
    assert "slowed" in out["text"]


# Probe M9-fix2: combine tests the retime explanation against the clock.
def _none_fits(k: float) -> dict:
    """A none_fits verdict dict with the given slowdown factor."""
    return {"state": "none_fits", "k": k}


def _clock(value: float, err: float, lo: float, hi: float, mark: str = "slow") -> dict:
    """A numeric timescale section with the given clock reading."""
    return {
        "method": "step rate", "value": value, "err": err, "unit": "steps/s",
        "expected_range": [lo, hi], "verdict": mark,
    }


def test_combine_clock_outside_is_impossible() -> None:
    """k=2.3, 2.6 +- 0.2 against 2.5-4.5: true rate 5.98, outside."""
    out = combine(_none_fits(2.3), _clock(2.6, 0.2, 2.5, 4.5))
    assert out["label"] == "impossible"
    assert "5.98" in out["text"] and "0.46" in out["text"]
    assert "2.5" in out["text"] and "4.5" in out["text"]


def test_combine_clock_inside_is_retimed() -> None:
    """k=1.5, 2.2 +- 0.2 against 2.5-4.5: true rate 3.3, natural.

    The agent's own mark (here normal) does not decide; the numbers do.
    """
    out = combine(_none_fits(1.5), _clock(2.2, 0.2, 2.5, 4.5, mark="normal"))
    assert out["label"] == "retimed"
    assert "1.50" in out["text"] and "3.30" in out["text"]
    assert "natural" in out["text"]


def test_combine_clock_error_too_large_is_none_fits() -> None:
    """k=1.5, 2.2 +- 2.0: the 2-sigma band reaches zero, undecidable."""
    out = combine(_none_fits(1.5), _clock(2.2, 2.0, 2.5, 4.5))
    assert out["label"] == "none_fits"
    assert "1.50" in out["text"]


def test_combine_clock_sped_up() -> None:
    """k < 1 reads as sped up: 4.4 * 0.5 = 2.2, outside 2.5-4.5."""
    out = combine(_none_fits(0.5), _clock(4.4, 0.2, 2.5, 4.5, mark="fast"))
    assert out["label"] == "impossible"
    assert "sped up" in out["text"] and "2.20" in out["text"]


# Probe 5: schema_doc is short and complete.
def test_schema_doc_short_and_complete() -> None:
    """schema_doc fits 6000 chars and names every top-level section."""
    doc = schema_doc()
    assert len(doc) <= 6000
    for section in (
        "type", "schema_version", "clip", "context", "first_look", "reference",
        "scale", "track", "masks", "flights", "timescale", "error_budget",
        "verdict", "overall", "page_texts",
    ):
        assert section in doc, section

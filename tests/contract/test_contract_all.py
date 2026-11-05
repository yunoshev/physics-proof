# generated from brief/12 · part 12 owns this file
"""Contract tests: schemas, fixtures, converter, evidence (brief §§11, 13–17)."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.contract import (
    CONTRACT_VERSION,
    load_evidence_schema,
    validate_evidence,
    validate_result,
    validate_summary,
)

REPO = Path(__file__).resolve().parent.parent.parent
FIX = REPO / "src" / "contract" / "fixtures"
CLIP_A = REPO / "fixtures" / "clip-a"
RUN_7 = REPO / "fixtures" / "run-7"
STILL = REPO / "fixtures" / "still-range"
SUFFIXES = (".png", ".jpg", ".jpeg", ".npz", ".json", ".jsonl", ".mp4")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _file_strings(node, found):
    if isinstance(node, dict):
        for v in node.values():
            _file_strings(v, found)
    elif isinstance(node, list):
        for v in node:
            _file_strings(v, found)
    elif (isinstance(node, str) and "://" not in node
            and node.lower().endswith(SUFFIXES)):
        found.append(node)


# --- schemas and synthetic fixtures (brief §11) ---------------------------

def test_contract_version_is_two():
    # Name predates the §22 bump (2 -> 3); pins the current version.
    assert CONTRACT_VERSION == 3
    assert _load(REPO / "src/contract/result.schema.json")[
        "properties"]["contract_version"] == {"type": "integer",
                                              "const": 3}
    assert _load(REPO / "src/contract/summary.schema.json")[
        "properties"]["contract_version"] == {"type": "integer",
                                               "const": 3}
    for path in (FIX / "moon_result.json",
                 FIX / "undetermined_result.json",
                 CLIP_A / "result.json", STILL / "result.json"):
        assert _load(path)["contract_version"] == 3, path
    for path in (FIX / "moon_summary.json",
                 FIX / "undetermined_summary.json",
                 CLIP_A / "summary.json"):
        assert _load(path)["contract_version"] == 3, path


def test_synthetic_fixtures_validate():
    for name in ("moon_result.json", "undetermined_result.json"):
        assert validate_result(_load(FIX / name)) == [], name
    for name in ("moon_summary.json", "undetermined_summary.json"):
        assert validate_summary(_load(FIX / name)) == [], name
    assert validate_result(_load(CLIP_A / "result.json")) == []
    assert validate_summary(_load(CLIP_A / "summary.json")) == []


def test_each_required_field_removed_fails():
    result = _load(FIX / "moon_result.json")
    schema = _load(REPO / "src/contract/result.schema.json")
    for field in schema["required"]:
        bad = {k: v for k, v in result.items() if k != field}
        assert validate_result(bad) != [], field
    bad = copy.deepcopy(result)
    del bad["segments"][0]["fit"]["g_app"]
    assert validate_result(bad) != []


def test_unknown_top_level_rejected():
    bad = _load(FIX / "moon_result.json")
    bad["zzz_unknown"] = 1
    assert validate_result(bad) != []


# --- clip-A owner review (brief §13) ---------------------------------------

def _clip_a_segment():
    return _load(CLIP_A / "result.json")["segments"][0]


def test_outlines_come_from_masks():
    seg = _clip_a_segment()
    by_frame = {o["frame"]: o for o in seg["overlay"]}
    for frame in (seg["frames"]["start"], seg["frames"]["apex"],
                  seg["frames"]["end"]):
        outline = by_frame[frame]["outline"]
        assert len(outline) >= 20, (frame, len(outline))
        ys = [p[1] for p in outline]
        assert max(ys) - min(ys) >= 50, (frame, max(ys) - min(ys))
        assert len(outline) <= 80


def test_ghosts_are_real_trajectories():
    seg = _clip_a_segment()
    by_world = {g["world"]: g for g in seg["ghosts"]}
    earth, moon = by_world["Earth"], by_world["Moon"]
    assert earth["landing"]["t_s"] < seg["times_s"]["end"]
    assert len(earth["points"]) >= 5
    assert abs(moon["landing"]["t_s"] - seg["times_s"]["end"]) <= 0.15
    assert moon["points"][0]["frame"] == seg["frames"]["start"]
    assert moon["points"][0]["y_px"] == pytest.approx(
        seg["takeoff_level_y_px"])


def test_every_freeze_event_is_in_data():
    result = _load(CLIP_A / "result.json")
    seg = result["segments"][0]
    frames = {m["frame"] for m in seg["key_moments"]}
    assert result["scale"]["frame"] is not None
    assert seg["frames"]["start"] in frames
    assert seg["frames"]["apex"] in frames
    assert seg["frames"]["end"] in frames
    verdict_steps = [s for s in result["calculation_steps"]
                     if s["id"] == "verdict"]
    assert verdict_steps
    assert verdict_steps[0]["frame"] == seg["frames"]["end"] + 1


def test_converter_is_deterministic():
    from src.contract.convert_source_fixture import convert

    def digest():
        out = {}
        for path in sorted(CLIP_A.rglob("*")):
            if path.is_file():
                out[str(path.relative_to(CLIP_A))] = hashlib.sha256(
                    path.read_bytes()).hexdigest()
        return out

    before = digest()
    convert()
    assert digest() == before


def test_missing_reference_fails_with_path():
    from src.contract.convert_source_fixture import (
        ConversionError,
        _rewrite_refs,
    )
    with pytest.raises(ConversionError) as exc:
        _rewrite_refs({"sheet": "gone.png"}, {}, {}, "owner")
    assert "gone.png" in str(exc.value)


# --- one frame of reference, real-run shapes (brief §16) ------------------

@pytest.mark.parametrize("fix", [CLIP_A, RUN_7])
def test_time_fields_within_duration(fix):
    result = _load(fix / "result.json")
    duration = result["video"]["duration_s"]
    bad = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif (isinstance(node, (int, float))
                and not isinstance(node, bool)
                and ("t_s" in path or "time" in path
                     or path.endswith("duration_s")
                     or path.endswith("airborne_s"))):
            if not 0 <= node <= duration:
                bad.append((path, node))

    walk(result, "")
    assert bad == []
    seg = result["segments"][0]
    assert seg["track"][0]["t_s"] == pytest.approx(seg["times_s"]["start"])
    assert [r["y_m"] for r in seg["track"]
            if r["frame"] == seg["frames"]["start"]] == pytest.approx([0.0])
    assert seg["apex_info"]["rise_m"] < 1.0


@pytest.mark.parametrize("fix", [CLIP_A, RUN_7])
def test_cited_artifact_paths_resolve(fix):
    result = _load(fix / "result.json")
    found: list[str] = []
    _file_strings(result, found)
    assert found
    missing = [p for p in found if not (fix / p).exists()]
    assert missing == []


# --- closed copy (brief §17) -----------------------------------------------

def test_fixture_carries_everything_it_points_to():
    for path in sorted(CLIP_A.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in (".json", ".jsonl"):
            continue
        found: list[str] = []
        if path.suffix == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    _file_strings(json.loads(line), found)
        else:
            _file_strings(json.loads(path.read_text(encoding="utf-8")),
                          found)
        missing = [p for p in found if not (CLIP_A / p).exists()]
        assert missing == [], (path, missing)
    assert (CLIP_A / "artifacts" / "flag_pole.240-270.0.2.png").exists()


# --- evidence schema (brief §§14–15) ---------------------------------------

def test_evidence_example_validates():
    example = _load(REPO / "src/contract/evidence.example.json")
    assert validate_evidence(example) == []
    names = {c["name"] for c in example["error_budget"]["components"]}
    assert {"reference_size", "pixel_scale", "fit",
            "point_vs_com"} <= names


def test_computed_fields_absent_from_evidence_schema():
    schema = load_evidence_schema()
    top = set(schema["properties"])
    for field in ("contract_version", "video", "calculation_steps",
                  "verdict", "sentence", "self_built_tools",
                  "takeoff_level_y_px"):
        assert field not in top, field
    seg = schema["properties"]["segments"]["items"]["properties"]
    for field in ("overlay", "fit", "ghosts", "world_outcomes",
                  "apex_info", "landing_info", "times_s", "track",
                  "takeoff_level_y_px"):
        assert field not in seg, field
    cand = schema["properties"]["worlds"]["properties"][
        "candidates"]["items"]["properties"]
    for field in ("g_m_s2", "fits_native", "delta_sigma",
                  "retime_factor"):
        assert field not in cand, field
    budget = schema["properties"]["error_budget"]["properties"]
    assert "sigma_total" not in budget
    assert "sigma_relative" in budget
    prov = schema["properties"]["provenance"]["properties"]
    assert set(prov) == {"artifacts"}
    art = prov["artifacts"]["items"]["properties"]
    assert set(art) == {"name", "path"}
    first_look = schema["properties"]["first_look"]["properties"]
    assert "wonder" not in first_look  # §23: the plan never travels via evidence
    rng = schema["properties"]["range_checks"]["items"]["properties"]
    for field in ("outcome", "delta_sigma", "side"):
        assert field not in rng, field  # §22: the validator adds these


def _described_nodes(node, out):
    if isinstance(node, dict):
        if "properties" in node:
            for value in node["properties"].values():
                assert isinstance(value, dict)
                assert value.get("description"), value
                _described_nodes(value, out)
        for key in ("items",):
            if isinstance(node.get(key), dict):
                item = node[key]
                if item.get("type") in ("object", "array"):
                    assert item.get("description"), item
                _described_nodes(item, out)
        for key in ("anyOf", "oneOf"):
            for branch in node.get(key, []) or []:
                if isinstance(branch, dict):
                    _described_nodes(branch, out)
        if isinstance(node.get("patternProperties"), dict):
            for value in node["patternProperties"].values():
                assert value.get("description"), value
                _described_nodes(value, out)


def test_every_evidence_property_has_description():
    _described_nodes(load_evidence_schema(), None)


# --- several references (brief §18) ------------------------------------------

def test_scale_accepts_reference_indices_1_to_5():
    base = _load(FIX / "moon_result.json")
    for n in (1, 2, 3, 4, 5):
        good = copy.deepcopy(base)
        good["scale"]["reference_indices"] = list(range(n))
        assert validate_result(good) == [], n
    bad = copy.deepcopy(base)
    bad["scale"]["reference_indices"] = []
    assert validate_result(bad) != []
    bad = copy.deepcopy(base)
    bad["scale"]["reference_indices"] = list(range(6))
    assert validate_result(bad) != []


def test_references_and_scale_descriptions_state_several_reference_rule():
    for name in ("result.schema.json", "evidence.schema.json"):
        schema = _load(REPO / "src/contract" / name)
        for key in ("references", "scale"):
            desc = schema["properties"][key].get("description", "")
            assert "two" in desc, (name, key)
            assert "person" not in desc.lower(), (name, key)


def test_error_budget_description_states_validator_rules():
    from src.validate.checks import REQUIRED_COMPONENTS

    desc = load_evidence_schema()["properties"]["error_budget"][
        "properties"]["components"]["description"]
    assert set(REQUIRED_COMPONENTS) == {"reference_size", "pixel_scale",
                                        "fit", "point_vs_com"}
    for name in REQUIRED_COMPONENTS:
        assert name in desc, name
    alt = load_evidence_schema()["properties"]["references"][
        "items"]["properties"]["mask_check"]["properties"][
        "alternative_readings"]["description"]
    assert "reading_spread" in alt


# --- every motion is listed (brief §19) -------------------------------------

def test_clip_a_motions_lists_two_intervals_first_names_segment():
    result = _load(CLIP_A / "result.json")
    motions = result["first_look"]["motions"]
    assert len(motions) == 2, motions
    assert motions[0]["segment_id"] == result["segments"][0]["id"]
    assert motions[0]["skip_reason"] is None
    assert motions[1]["segment_id"] is None
    assert motions[1]["skip_reason"]


def test_motions_rejects_entry_with_neither_segment_nor_skip():
    for loader, base_path in ((validate_result, FIX / "moon_result.json"),
                              (validate_evidence,
                               REPO / "src/contract/evidence.example.json")):
        base = _load(base_path)
        bad = copy.deepcopy(base)
        bad["first_look"]["motions"] = [{"frame_start": 0, "frame_end": 10,
                                         "description": "hop",
                                         "segment_id": None,
                                         "skip_reason": None}]
        assert loader(bad) != [], base_path
    # Required on new evidence; tolerated absent on assembled results
    # that predate it (real-run fixtures such as run-7).
    example = _load(REPO / "src/contract/evidence.example.json")
    bad = copy.deepcopy(example)
    del bad["first_look"]["motions"]
    assert validate_evidence(bad) != []
    bad = copy.deepcopy(example)
    bad["first_look"]["motions"] = []
    assert validate_evidence(bad) != []
    moon = _load(FIX / "moon_result.json")
    good = copy.deepcopy(moon)
    del good["first_look"]["motions"]
    assert validate_result(good) == []
    # Run 7 predates the v3 fields (§§22–23); it still loads (§22),
    # so it is never rejected for motions either.
    assert validate_result(_load(RUN_7 / "result.json")) == []


def test_motions_description_states_list_every_motion_rule():
    for name in ("result.schema.json", "evidence.schema.json"):
        schema = _load(REPO / "src/contract" / name)
        desc = schema["properties"]["first_look"]["properties"][
            "motions"]["description"]
        assert "R-M4" in desc, name
        assert "segment_id" in desc, name
        assert "skip_reason" in desc, name


# --- size-to-state match (brief §20) -----------------------------------------

def test_previous_version_result_still_loads():
    """A version-2 result still loads under version 3 (§22).

    Run 7 predates the §22 bump; only the §22 additions
    (``range_checks``, ``verdict.decided_by``) may be absent, and a
    version-3 document missing them still fails. This tolerance is
    what keeps the parts that still assemble version-2 results
    (part 11 and everything downstream of it) passing until they
    regenerate.
    """
    result = _load(RUN_7 / "result.json")
    assert result["contract_version"] == CONTRACT_VERSION - 1
    assert validate_result(result) == []
    broken = copy.deepcopy(result)
    del broken["video"]
    assert validate_result(broken) != []
    # The pre-§22 shape (neither range_checks nor decided_by) also
    # loads when stamped with the current version, which is what
    # part 11 assembles while it regenerates toward emitting them;
    # carrying either new field holds the document to the strict
    # schema (see test_result_range_checks_always_present_and_decided).
    reshaped = copy.deepcopy(_load(FIX / "moon_result.json"))
    del reshaped["range_checks"]
    del reshaped["verdict"]["decided_by"]
    reshaped["contract_version"] = CONTRACT_VERSION
    assert validate_result(reshaped) == []


def test_reference_without_state_match_rejected():
    # Required on new evidence; tolerated absent on assembled results
    # that predate it (real-run fixtures such as run-7).
    example = _load(REPO / "src/contract/evidence.example.json")
    bad = copy.deepcopy(example)
    del bad["references"][0]["size_derivation"]["state_match"]
    assert validate_evidence(bad) != []
    moon = _load(FIX / "moon_result.json")
    bad = copy.deepcopy(moon)
    del bad["references"][0]["size_derivation"]["state_match"]
    assert validate_result(bad) == []
    assert validate_result(_load(RUN_7 / "result.json")) == []


def test_clip_a_carries_state_match():
    result = _load(CLIP_A / "result.json")
    assert result["references"]
    for ref in result["references"]:
        match = ref["size_derivation"]["state_match"]
        assert match["shown_and_covered"], ref["name"]
        assert match["shown_not_covered"], ref["name"]


def test_state_match_description_states_r_s7_and_r_s8():
    for name in ("result.schema.json", "evidence.schema.json"):
        schema = _load(REPO / "src/contract" / name)
        sd = schema["properties"]["references"]["items"][
            "properties"]["size_derivation"]
        assert "R-S7" in sd.get("description", ""), (name, "size_derivation")
        assert "R-S8" in sd.get("description", ""), (name, "size_derivation")
        desc = sd["properties"]["state_match"]["description"]
        assert "R-S7" in desc, (name, "state_match")
        assert "R-S8" in desc, (name, "state_match")


# --- the viewer's question, in one world (brief §21) -------------------------

# --- range checks (brief §22) -------------------------------------------------

def test_still_range_fixture_validates():
    evidence = _load(STILL / "evidence.json")
    assert validate_evidence(evidence) == []
    result = _load(STILL / "result.json")
    assert validate_result(result) == []
    assert result["segments"] == []
    assert result["clock"] is None
    assert result["clock_absent_reason"] == "no motion measured"
    assert result["verdict"]["g_measured"] is None
    assert result["verdict"]["sigma_g"] is None
    assert result["verdict"]["decided_by"] == "finger_hand_ratio"
    by_id = {c["id"]: c for c in result["range_checks"]}
    assert set(by_id) == {"palm_hand_ratio", "finger_hand_ratio"}
    inside, outside = by_id["palm_hand_ratio"], by_id["finger_hand_ratio"]
    assert inside["outcome"] == "inside"
    assert inside["delta_sigma"] == 0
    assert inside["side"] is None
    assert inside["range"]["bounds_kind"] == "percentile"
    assert inside["range"]["percentiles"] == [5, 95]
    assert outside["outcome"] == "outside"
    assert outside["delta_sigma"] == 3.0
    assert outside["side"] == "above"
    assert outside["range"]["bounds_kind"] == "min-max"
    assert outside["range"]["percentiles"] is None
    for check in result["range_checks"]:
        assert check["unit"] == "ratio"
        assert 1 <= len(check["extents"]) <= 2
    found: list[str] = []
    _file_strings(result, found)
    _file_strings(evidence, found)
    assert found
    missing = [p for p in found if not (STILL / p).exists()]
    assert missing == []


def test_range_checks_evidence_shapes():
    example = _load(REPO / "src/contract/evidence.example.json")
    assert example["range_checks"] == []
    still = _load(STILL / "evidence.json")
    good = copy.deepcopy(example)
    good["segments"] = []
    good["range_checks"] = [copy.deepcopy(still["range_checks"][0])]
    assert validate_evidence(good) == []
    # No measurement at all passes the schema; only part 11's
    # MEASUREMENT_MISSING check rejects it, never the schema.
    neither = copy.deepcopy(example)
    neither["segments"] = []
    neither["range_checks"] = []
    assert validate_evidence(neither) == []
    absent = copy.deepcopy(example)
    absent["segments"] = []
    del absent["range_checks"]
    assert validate_evidence(absent) == []


def test_result_range_checks_always_present_and_decided():
    for path in (FIX / "moon_result.json", CLIP_A / "result.json"):
        result = _load(path)
        assert result["range_checks"] == []
        assert result["verdict"]["decided_by"] == "gravity"
    undetermined = _load(FIX / "undetermined_result.json")
    assert undetermined["range_checks"] == []
    assert undetermined["verdict"]["decided_by"] is None
    result = _load(STILL / "result.json")
    assert {c["id"] for c in result["range_checks"]} == {
        "palm_hand_ratio", "finger_hand_ratio"}
    bad = copy.deepcopy(result)
    del bad["range_checks"]
    assert validate_result(bad) != []
    bad = copy.deepcopy(result)
    del bad["range_checks"][0]["outcome"]
    assert validate_result(bad) != []
    bad = copy.deepcopy(_load(FIX / "moon_result.json"))
    del bad["verdict"]["decided_by"]
    assert validate_result(bad) != []


def test_range_check_description_carries_item_shape():
    desc = load_evidence_schema()["properties"]["range_checks"][
        "description"]
    for word in ("uses_scale", "measurement_artifact", "bounds_kind",
                 "percentiles", "min-max", "value", "bound"):
        assert word in desc, word
    schema = _load(REPO / "src/contract/result.schema.json")
    assert "range_checks" in schema["required"]
    desc = schema["properties"]["range_checks"]["description"]
    assert "outcome" in desc and "delta_sigma" in desc


# --- the viewer's question, in one world (brief §21) -------------------------

def test_example_asks_viewer_question_in_one_world():
    example = _load(REPO / "src/contract/evidence.example.json")
    assert validate_evidence(example) == []
    question = example["first_look"]["question"]
    assert "gravity" not in question and "physics" not in question
    assert "gravity" not in question.lower()
    assert "physics" not in question.lower()
    assert [c["world"] for c in example["worlds"]["candidates"]] == ["Moon"]
    assert example["worlds"]["excluded"] == []
    for name in ("result.schema.json", "evidence.schema.json"):
        schema = _load(REPO / "src/contract" / name)
        q = schema["properties"]["first_look"]["properties"][
            "question"].get("description", "")
        assert "viewer's question" in q, (name, "question")
        c = schema["properties"]["worlds"]["properties"][
            "candidates"].get("description", "")
        assert "scene's world only" in c, (name, "candidates")
        e = schema["properties"]["worlds"]["properties"][
            "excluded"].get("description", "")
        assert "earlier contract version" in e, (name, "excluded")


# --- the plan travels to the page (brief §23) --------------------------------

def test_first_look_wonder():
    clip_a = _load(CLIP_A / "result.json")
    wonder = clip_a["first_look"]["wonder"]
    assert wonder["claim"] == "the astronaut hops far too high for Earth"
    assert len(wonder["checks"]) == 1
    assert "1.62" in wonder["checks"][0]["compare_with"]
    assert wonder["realistic_if"] and wonder["not_realistic_if"]
    assert validate_result(clip_a) == []
    # A result with a null plan and one with no plan both validate.
    for first_look in ({"wonder": None}, {}):
        result = copy.deepcopy(_load(FIX / "moon_result.json"))
        result["first_look"].pop("wonder", None)
        result["first_look"].update(first_look)
        assert validate_result(result) == [], first_look
    # The evidence never carries the plan; the agent never retypes it.
    bad = copy.deepcopy(
        _load(REPO / "src/contract/evidence.example.json"))
    bad["first_look"]["wonder"] = None
    assert validate_evidence(bad) != []


# --- the trajectories the agent decided from (brief §24) ---------------------

def _overview_candidate(cid, start, end, decision, segment_id, reason):
    return {"id": cid, "frame_start": start, "frame_end": end,
            "airtime_s": 0.5, "peak_rise_px": 12.0, "decision": decision,
            "segment_id": segment_id, "reason": reason}


def _evidence_with_overview():
    good = copy.deepcopy(
        _load(REPO / "src/contract/evidence.example.json"))
    good["first_look"]["overview"] = {
        "artifact": "artifacts/t0_masks.npz",
        "object_id": "0",
        "tool_result": "artifacts/t0_overview.json",
        "candidates": [
            _overview_candidate("cand_1", 10, 30, "measured", "hop_a",
                               None),
            _overview_candidate("cand_2", 40, 70, "measured", "hop_b",
                               None),
            _overview_candidate("cand_3", 80, 90, "not_a_flight", None,
                               "walking step, rise 4 px"),
        ],
        "first_check": {"segment_id": "hop_a",
                        "why": "most frames with the whole body in frame"},
    }
    return good


def test_overview_two_measured_one_not_a_flight_validates():
    assert validate_evidence(_evidence_with_overview()) == []


def test_overview_measured_without_segment_id_rejected():
    bad = _evidence_with_overview()
    bad["first_look"]["overview"]["candidates"][0]["segment_id"] = None
    assert validate_evidence(bad) != []
    bad = _evidence_with_overview()
    del bad["first_look"]["overview"]["candidates"][1]["segment_id"]
    assert validate_evidence(bad) != []


def test_overview_unmeasured_without_reason_rejected():
    for decision in ("not_a_flight", "not_measurable"):
        bad = _evidence_with_overview()
        bad["first_look"]["overview"]["candidates"][2]["decision"] = decision
        bad["first_look"]["overview"]["candidates"][2]["reason"] = None
        assert validate_evidence(bad) != [], decision


def test_overview_optional_in_schema_required_by_validator():
    # Presence when a segment exists is enforced by part 11
    # (MOTION_OVERVIEW_MISSING), never by this schema: the range-only
    # still-range evidence carries no overview.
    still = _load(STILL / "evidence.json")
    assert validate_evidence(still) == []
    bare = copy.deepcopy(
        _load(REPO / "src/contract/evidence.example.json"))
    del bare["first_look"]["overview"]
    assert validate_evidence(bare) == []


def test_overview_description_states_r_m6_and_r_m7():
    desc = load_evidence_schema()["properties"]["first_look"][
        "properties"]["overview"]["description"]
    assert "R-M6" in desc
    assert "R-M7" in desc
    assert "segment_id" in desc
    assert "motion_overview" in desc

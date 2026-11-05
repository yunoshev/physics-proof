# generated from brief/07 · part 07 owns this file
"""Tool schemas: one source, strict shape, generated submit text."""

from __future__ import annotations

import json
from pathlib import Path

from src import config
from src.contract import validate_evidence
from src.tools import schemas


def _strict_params_ok(node) -> bool:
    """Independent copy of the stub's strict-shape grammar.

    Every ``type: object`` level needs ``additionalProperties: false``
    and a ``required`` list covering every property. (Reimplemented
    here rather than imported: test modules never import conftest by
    name, and this keeps the check independent of the client's copy.)
    """
    if isinstance(node, dict):
        if node.get("type") == "object":
            props = node.get("properties")
            required = node.get("required")
            if not isinstance(props, dict):
                return False
            if (node.get("additionalProperties") is not False
                    or sorted(required or []) != sorted(props)):
                return False
            return all(_strict_params_ok(v) for v in props.values())
        if node.get("type") == "array" and "items" in node:
            return _strict_params_ok(node["items"])
        for keyword in ("anyOf", "oneOf", "allOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                if not all(_strict_params_ok(b) for b in branches):
                    return False
        return all(_strict_params_ok(v) for v in node.values())
    if isinstance(node, list):
        return all(_strict_params_ok(v) for v in node)
    return True


def test_tool_names_match_loop_and_dispatch():
    from src.loop.dispatch import EXPECTED_PARAMS
    from src.loop.prefix import TOOL_SCHEMAS

    assert [s["name"] for s in TOOL_SCHEMAS] == list(schemas.TOOL_NAMES)
    assert set(EXPECTED_PARAMS) == set(schemas.TOOL_NAMES)
    assert set(EXPECTED_PARAMS) == set(schemas.EXPECTED_PARAMS)
    for name, expected in EXPECTED_PARAMS.items():
        assert tuple(expected) == schemas.EXPECTED_PARAMS[name]


def test_every_schema_is_stub_strict():
    for entry in schemas.TOOL_SCHEMAS:
        assert _strict_params_ok(entry["parameters"]), entry["name"]
        assert entry["description"].strip()
        assert entry["parameters"]["additionalProperties"] is False


def test_submit_description_names_every_required_path():
    schema = json.loads(
        (Path(schemas.__file__).resolve().parent.parent / "contract"
         / "evidence.schema.json").read_text(encoding="utf-8"))
    paths = schemas.required_evidence_paths(schema)
    assert len(paths) > 100  # the schema is wide; a stub list is short
    for path in paths:
        assert f"`{path}`" in schemas.SUBMIT_DESCRIPTION, path


def test_submit_description_embeds_valid_example():
    start = schemas.SUBMIT_DESCRIPTION.index("```json")
    block = schemas.SUBMIT_DESCRIPTION[start:].split("```")[1]
    example = json.loads("\n".join(block.splitlines()[1:]))
    assert validate_evidence(example) == []
    shipped = json.loads(
        (Path(schemas.__file__).resolve().parent.parent / "contract"
         / "evidence.example.json").read_text(encoding="utf-8"))
    assert example == shipped


def test_submit_description_holds_field_list_and_skeleton():
    assert "worlds" in schemas.SUBMIT_DESCRIPTION
    assert "dry_run" in schemas.SUBMIT_DESCRIPTION
    assert "`evidence`" in schemas.SUBMIT_DESCRIPTION
    assert "`evidence_path`" in schemas.SUBMIT_DESCRIPTION
    assert "artifacts/t<turn>_evidence.json" in schemas.SUBMIT_DESCRIPTION


def test_submit_schema_takes_evidence_or_path():
    params = schemas.TOOL_SCHEMAS[-1]["parameters"]
    assert params["properties"].keys() == {
        "evidence", "evidence_path", "dry_run"}
    assert params["required"] == ["evidence", "evidence_path", "dry_run"]
    by_name = {s["name"]: s for s in schemas.TOOL_SCHEMAS}
    assert by_name["submit"]["parameters"] is params


def test_submit_description_names_error_budget_parts():
    lines = schemas._error_budget_lines(
        json.loads(
            (Path(schemas.__file__).resolve().parent.parent
             / "contract"
             / "evidence.schema.json").read_text(encoding="utf-8")))
    assert lines, "the schema must state the error-budget rules"
    blob = "\n".join(lines)
    for name in ("reference_size", "pixel_scale", "fit", "point_vs_com"):
        assert f"`{name}`" in blob, name
    assert "`reading_spread`" in blob
    assert "`repetition_spread`" in blob
    description = schemas.SUBMIT_DESCRIPTION
    for name in ("reference_size", "pixel_scale", "fit", "point_vs_com",
                 "reading_spread", "repetition_spread"):
        assert f"`{name}`" in description, name


def test_submit_description_carries_scale_cross_check_rules():
    # Part 07 §16 (R-S6, part 11 §13): the generated submit description
    # carries two-or-three references in the validator's terms. The
    # withdrawn person rule and kind checks appear nowhere.
    description = schemas.SUBMIT_DESCRIPTION
    assert "subject" in description
    assert "two" in description
    assert "REFERENCES_DISAGREE" in description
    assert "SECOND_REFERENCE_SAME_OBJECT" in description
    assert "ALTERNATIVE_NOT_ADDRESSED" in description
    assert "scale rests on one reference" in description
    assert "SECOND_REFERENCE_REQUIRED_PERSON" not in description
    assert "SUBJECT_KIND" not in description


def test_scale_rules_section_is_generated_from_the_schema():
    # The scale cross-check section quotes the evidence schema's own
    # description texts (read off the schema, never hand-written): a
    # hand-written section with different wording fails here.
    schema = json.loads(
        (Path(schemas.__file__).resolve().parent.parent / "contract"
         / "evidence.schema.json").read_text(encoding="utf-8"))
    lines = schemas._scale_rules_lines(schema)
    assert lines, "the schema must state the scale cross-check rules"
    blob = "\n".join(lines)
    subject_desc = schema["properties"]["segments"]["items"][
        "properties"]["subject"]["description"]
    assert subject_desc in blob
    scale_desc = schema["properties"]["scale"]["description"]
    assert scale_desc in blob
    references_desc = schema["properties"]["references"]["description"]
    assert references_desc in blob
    readings_desc = schema["properties"]["references"]["items"][
        "properties"]["mask_check"]["properties"][
        "alternative_readings"]["description"]
    assert readings_desc in blob
    assert "two or three references" in blob
    assert "descriptive only" in blob
    description = schemas.SUBMIT_DESCRIPTION
    for line in lines:
        assert line in description


def test_named_scale_codes_are_real_validator_codes():
    # The enforcing codes the description names must be codes the
    # validator actually emits; a renamed code fails here instead of
    # drifting silently.
    checks_path = (Path(schemas.__file__).resolve().parent.parent
                   / "validate" / "checks.py")
    source = checks_path.read_text(encoding="utf-8")
    for code in ("REFERENCES_DISAGREE",
                 "SECOND_REFERENCE_SAME_OBJECT",
                 "ALTERNATIVE_NOT_ADDRESSED"):
        assert f'"{code}"' in source, code
        assert code in schemas.SUBMIT_DESCRIPTION, code


def test_descriptions_carry_no_identifying_patterns():
    blob = "\n".join(s["description"] for s in schemas.TOOL_SCHEMAS)
    lowered = blob.lower()
    for pattern in config.BLINDNESS_PATTERNS:
        assert str(pattern).lower() not in lowered, pattern

# generated from brief/12 · part 12 owns this file
"""Result data contract (brief part 12): schemas, validation, versioning.

The only interface between the analysis side (parts 05–11) and the
player (part 13). ``contract_version`` is 3: all geometry is in
source-video pixels, never normalised coordinates; v3 adds
``range_checks``, ``verdict.decided_by`` and ``first_look.wonder``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

__all__ = [
    "CONTRACT_VERSION",
    "load_result_schema",
    "load_summary_schema",
    "load_evidence_schema",
    "validate_result",
    "validate_summary",
    "validate_evidence",
]

#: Current contract version (brief part 12 §22). Parts 11 and 13
#: regenerate together on a bump.
CONTRACT_VERSION = 3

_SCHEMA_DIR = Path(__file__).resolve().parent


def _load(name):
    with open(_SCHEMA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def load_result_schema():
    """The ``result.json`` schema dict (brief part 12 §§0–10)."""
    return _load("result.schema.json")


def load_summary_schema():
    """The ``summary.json`` schema dict (brief part 12 §12)."""
    return _load("summary.schema.json")


def load_evidence_schema():
    """The agent-evidence schema dict (brief part 12 §14).

    Used by part 11's submit gate (V1) and by part 07 to describe the
    ``submit`` tool. Carries only agent-supplied fields: every computed
    field of §14 is absent here.
    """
    return _load("evidence.schema.json")


def _type_ok(node, name):
    if name == "object":
        return isinstance(node, dict)
    if name == "array":
        return isinstance(node, list)
    if name == "string":
        return isinstance(node, str)
    if name == "integer":
        return isinstance(node, int) and not isinstance(node, bool)
    if name == "number":
        return isinstance(node, (int, float)) and not isinstance(node, bool)
    if name == "boolean":
        return isinstance(node, bool)
    if name == "null":
        return node is None
    return False


def _walk(node, schema, path, errors):
    label = path or "value"
    if not isinstance(schema, dict):
        return
    if "anyOf" in schema or "oneOf" in schema:
        branches = schema.get("anyOf", schema.get("oneOf"))
        best = None
        for branch in branches:
            sub: list[str] = []
            _walk(node, branch if isinstance(branch, dict) else {}, path,
                  sub)
            if not sub:
                return
            if best is None or len(sub) < len(best):
                best = sub
        errors.extend(best or [])
        return
    if "const" in schema and node != schema["const"]:
        errors.append(f"{label}: must equal {schema['const']!r}")
        return
    if "enum" in schema and node not in schema["enum"]:
        errors.append(f"{label}: {node!r} is not an allowed value")
        return
    if "type" in schema:
        want = schema["type"]
        names = [want] if isinstance(want, str) else list(want)
        if not any(_type_ok(node, name) for name in names):
            errors.append(f"{label}: expected type {want}, got "
                          f"{type(node).__name__}")
            return
    if isinstance(node, dict):
        for key in schema.get("required", []):
            if key not in node:
                errors.append(f"{label}.{key}: required field missing")
        props = schema.get("properties", {})
        patterns = schema.get("patternProperties", {})
        extra = schema.get("additionalProperties", True)
        for key, value in node.items():
            sub = f"{label}.{key}"
            if key in props:
                _walk(value, props[key], sub, errors)
                continue
            matched = False
            for pattern, subschema in patterns.items():
                if re.search(pattern, key):
                    _walk(value, subschema, sub, errors)
                    matched = True
                    break
            if matched:
                continue
            if extra is False:
                errors.append(f"{sub}: unknown field (closed object)")
            elif isinstance(extra, dict):
                _walk(value, extra, sub, errors)
    elif isinstance(node, list):
        if "minItems" in schema and len(node) < schema["minItems"]:
            errors.append(f"{label}: need at least {schema['minItems']} "
                          f"items")
        if "maxItems" in schema and len(node) > schema["maxItems"]:
            errors.append(f"{label}: at most {schema['maxItems']} items "
                          f"allowed")
        items = schema.get("items")
        if isinstance(items, dict):
            for pos, value in enumerate(node):
                _walk(value, items, f"{label}[{pos}]", errors)
    elif isinstance(node, str):
        if "minLength" in schema and len(node) < schema["minLength"]:
            errors.append(f"{label}: string must not be empty")
        if "maxLength" in schema and len(node) > schema["maxLength"]:
            errors.append(f"{label}: string exceeds max length "
                          f"{schema['maxLength']}")
        if "pattern" in schema and re.search(schema["pattern"],
                                             node) is None:
            errors.append(f"{label}: string does not match "
                          f"{schema['pattern']!r}")
    elif isinstance(node, bool):
        pass
    elif isinstance(node, (int, float)):
        if "minimum" in schema and node < schema["minimum"]:
            errors.append(f"{label}: must be >= {schema['minimum']}")
        if ("exclusiveMinimum" in schema
                and node <= schema["exclusiveMinimum"]):
            errors.append(f"{label}: must be > "
                          f"{schema['exclusiveMinimum']}")
        if "maximum" in schema and node > schema["maximum"]:
            errors.append(f"{label}: must be <= {schema['maximum']}")
        if ("exclusiveMaximum" in schema
                and node >= schema["exclusiveMaximum"]):
            errors.append(f"{label}: must be < "
                          f"{schema['exclusiveMaximum']}")


def _check(obj, schema):
    errors: list[str] = []
    _walk(obj, schema, "", errors)
    return errors


def _relaxed_for_previous_version(schema):
    relaxed = json.loads(json.dumps(schema))
    required = [k for k in relaxed.get("required", [])
                if k != "range_checks"]
    relaxed["required"] = required
    props = relaxed.get("properties", {})
    if isinstance(props.get("contract_version"), dict):
        props["contract_version"] = {"type": "integer",
                                     "enum": [2, CONTRACT_VERSION]}
    verdict = props.get("verdict")
    if isinstance(verdict, dict):
        verdict["required"] = [k for k in verdict.get("required", [])
                               if k != "decided_by"]
    return relaxed


def _is_pre_range_checks_shape(obj):
    """True when a result predates the §22 ``range_checks`` addition.

    The §22 fields (``range_checks``, ``verdict.decided_by``) were
    added together; a document carrying neither is a pre-§22
    document, whatever stamp it carries — part 11 stamps the live
    ``CONTRACT_VERSION`` constant while it regenerates toward
    emitting them. A document carrying either one is held to the
    strict schema.
    """
    if "range_checks" in obj:
        return False
    verdict = obj.get("verdict")
    return isinstance(verdict, dict) and "decided_by" not in verdict


def validate_result(obj):
    """Check ``result.json`` against the contract; return [problems].

    Accepts the current version and the previous one: a version-2
    result still loads (§22), and so does the pre-§22 shape (neither
    ``range_checks`` nor ``verdict.decided_by``), with only those
    §22 additions tolerated as absent. Anything else must satisfy
    the strict schema.
    """
    if not isinstance(obj, dict):
        return ["result: must be a JSON object"]
    if (obj.get("contract_version") == CONTRACT_VERSION - 1
            or _is_pre_range_checks_shape(obj)):
        return _check(obj, _relaxed_for_previous_version(
            load_result_schema()))
    return _check(obj, load_result_schema())


def validate_summary(obj):
    """Check ``summary.json`` against the contract; return [problems].

    The summary gained nothing but the version number in §22, so a
    previous-version summary still loads under the same tolerance
    as a result.
    """
    if not isinstance(obj, dict):
        return ["summary: must be a JSON object"]
    if obj.get("contract_version") == CONTRACT_VERSION - 1:
        schema = json.loads(json.dumps(load_summary_schema()))
        props = schema.get("properties", {})
        if isinstance(props.get("contract_version"), dict):
            props["contract_version"] = {"type": "integer",
                                         "enum": [2, CONTRACT_VERSION]}
        return _check(obj, schema)
    return _check(obj, load_summary_schema())


def validate_evidence(obj):
    """Check agent evidence against the evidence schema; [problems]."""
    if not isinstance(obj, dict):
        return ["evidence: must be a JSON object"]
    return _check(obj, load_evidence_schema())

# generated from brief/11 · part 11 owns this file
"""V1: the evidence-schema gate (brief §§6.1, 7, 17).

V1 checks the evidence schema (part 12 §14), not the result schema,
and V1 gates the rest: when V1 fails, only V1's errors are returned.
For a ``oneOf``/``anyOf`` property the branch is picked by its
discriminating key (for ``camera``: ``still`` or
``relative_track_artifact``); a key whose value is ``null`` counts as
absent. Every V1 error under a shape choice ends with the allowed
shapes written out as minimal JSON on one line, built from the
schema's branches rather than hard-coded.
"""

from __future__ import annotations

import json
import re

from src.contract import load_evidence_schema, validate_evidence

__all__ = [
    "allowed_camera_shapes",
    "check_v1",
    "strip_prefix",
]

_MISSING = "MISSING_FIELD"


def strip_prefix(label: str) -> str:
    """Contract error label → evidence JSON path (``value.`` removed)."""
    if label in ("", "value"):
        return "evidence"
    if label.startswith("value."):
        return label[len("value."):]
    return label


def _field_of(message: str) -> str:
    head = message.split(":", 1)[0].strip()
    return strip_prefix(head)


def allowed_camera_shapes() -> str:
    """Minimal JSON of the camera shapes, from the evidence schema."""
    from src.contract import load_evidence_schema

    try:
        schema = load_evidence_schema()
        branches = schema["properties"]["camera"].get("anyOf", [])
        parts = []
        for branch in branches:
            props = branch.get("properties", {})
            required = branch.get("required", [])
            if "still" in required:
                still = props.get("still", {}).get("properties", {})
                inner = {
                    key: "..."
                    for key in still.get("required", [])
                    if isinstance(key, str)
                } or {"reference_phrase": "...",
                      "reference_track_artifact": "..."}
                parts.append(json.dumps({"still": inner},
                                        sort_keys=True))
            elif "relative_track_artifact" in required:
                parts.append(json.dumps({"relative_track_artifact": "..."},
                                        sort_keys=True))
        if parts:
            return "allowed: " + " or ".join(parts)
    except (KeyError, TypeError, ValueError):
        pass
    return ('allowed: {"still": {"reference_phrase": "...", '
            '"reference_track_artifact": "..."}} or '
            '{"relative_track_artifact": "..."}')


def _camera_errors(camera) -> list:
    """Branch-aware camera errors with exact paths (brief §§7, 17)."""
    suffix = " " + allowed_camera_shapes()
    if not isinstance(camera, dict):
        return [{"code": _MISSING, "field": "camera",
                 "detail": "camera must be an object" + suffix}]
    still_present = "still" in camera and camera["still"] is not None
    rel_present = ("relative_track_artifact" in camera
                   and camera["relative_track_artifact"] is not None)
    if still_present and rel_present:
        return [{"code": _MISSING, "field": "camera",
                 "detail": "camera must pick exactly one shape" + suffix}]
    if not still_present and not rel_present:
        return [{"code": _MISSING, "field": "camera",
                 "detail": ("camera does not match any allowed shape: "
                            "name the discriminating key "
                            "('still' or 'relative_track_artifact')")
                 + suffix}]
    errors = []
    if still_present:
        for key in camera:
            if key != "still":
                errors.append({
                    "code": _MISSING, "field": f"camera.{key}",
                    "detail": f"camera.{key}: unknown field" + suffix})
        still = camera["still"]
        if not isinstance(still, dict):
            return [{"code": _MISSING, "field": "camera.still",
                     "detail": ("camera.still: expected type object, got "
                                f"{type(still).__name__}") + suffix}]
        for key in still:
            if key not in ("reference_phrase", "reference_track_artifact"):
                errors.append({
                    "code": _MISSING,
                    "field": f"camera.still.{key}",
                    "detail": (f"camera.still.{key}: unknown field")
                    + suffix})
        phrase = still.get("reference_phrase")
        if not isinstance(phrase, str) or not phrase:
            errors.append({
                "code": _MISSING,
                "field": "camera.still.reference_phrase",
                "detail": ("camera.still.reference_phrase: required "
                           "field missing") + suffix})
        track = still.get("reference_track_artifact")
        if not isinstance(track, str) or not track:
            errors.append({
                "code": _MISSING,
                "field": "camera.still.reference_track_artifact",
                "detail": ("camera.still.reference_track_artifact: "
                           "required field missing") + suffix})
        return errors
    for key in camera:
        if key != "relative_track_artifact":
            errors.append({
                "code": _MISSING, "field": f"camera.{key}",
                "detail": f"camera.{key}: unknown field" + suffix})
    track = camera.get("relative_track_artifact")
    if not isinstance(track, str) or not track:
        errors.append({
            "code": _MISSING, "field": "camera.relative_track_artifact",
            "detail": ("camera.relative_track_artifact: required field "
                       "missing") + suffix})
    return errors


#: R-C3 step/stride carriers the clock helper may add; V1 reads
#: them in ``_check_clock`` and never rejects them as unknown.
_CLOCK_TOLERATED = frozenset({
    "ambiguous", "as_step_hz", "as_stride_hz", "ambiguity_resolved_by",
})

#: Required clock keys (evidence schema, brief §12.7).
_CLOCK_REQUIRED = (
    "signal_description", "measured_rate_hz",
    "measured_rate_sigma_hz", "interpretation", "band_hz",
    "natural_range_hz", "natural_range_source",
)


def _clock_errors(clock) -> list:
    """Branch-aware clock errors with exact paths (brief §7)."""
    if clock is None:
        return []
    if not isinstance(clock, dict):
        return [{"code": _MISSING, "field": "clock",
                 "detail": "clock: must be an object or null"}]
    errors = []
    for key in _CLOCK_REQUIRED:
        if key not in clock or clock[key] is None:
            errors.append({
                "code": _MISSING, "field": f"clock.{key}",
                "detail": f"clock.{key}: required field missing"})
    for key in clock:
        if key not in _CLOCK_REQUIRED and key not in _CLOCK_TOLERATED:
            errors.append({
                "code": _MISSING, "field": f"clock.{key}",
                "detail": f"clock.{key}: unknown field"})
    band = clock.get("band_hz")
    if (not isinstance(band, list) or len(band) != 2
            or not all(isinstance(v, (int, float))
                       and not isinstance(v, bool) for v in band)):
        errors.append({
            "code": _MISSING, "field": "clock.band_hz",
            "detail": "clock.band_hz must be [lo, hi] in Hz"})
    natural = clock.get("natural_range_hz")
    if (not isinstance(natural, list) or len(natural) != 2
            or not all(isinstance(v, (int, float))
                       and not isinstance(v, bool) for v in natural)):
        errors.append({
            "code": _MISSING, "field": "clock.natural_range_hz",
            "detail": "clock.natural_range_hz must be [lo, hi] in Hz"})
    interpretation = clock.get("interpretation")
    if (interpretation is not None
            and interpretation not in ("step", "stride")):
        errors.append({
            "code": _MISSING, "field": "clock.interpretation",
            "detail": "clock.interpretation: must be step or stride"})
    return errors


def _label_parts(label: str) -> list:
    """A contract label (``value.a[0].b``) as navigation parts."""
    parts = []
    for name, index in re.findall(r"([^\.\[\]]+)|\[(\d+)\]", label):
        if name:
            parts.append(name)
        else:
            parts.append(int(index))
    return parts


def _node_at(schema, parts):
    """The evidence-schema node at ``parts``, or None."""
    node = schema
    for part in parts:
        if isinstance(part, str):
            if part == "value":
                continue
            if not isinstance(node, dict):
                return None
            props = node.get("properties")
            if not isinstance(props, dict) or part not in props:
                return None
            node = props[part]
        else:
            if not isinstance(node, dict):
                return None
            items = node.get("items")
            if isinstance(items, dict):
                node = items
            elif (isinstance(items, list) and 0 <= part < len(items)):
                node = items[part]
            else:
                return None
    return node if isinstance(node, dict) else None


def _value_at(evidence, parts):
    """The evidence value at ``parts``, or None when absent."""
    node = evidence
    for part in parts:
        if isinstance(part, str):
            if part == "value":
                continue
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        else:
            if not isinstance(node, list) or not 0 <= part < len(node):
                return None
            node = node[part]
    return node


def _type_name(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _type_ok(value, want) -> bool:
    names = [want] if isinstance(want, str) else list(want)
    return _type_name(value) in names or (
        _type_name(value) == "integer" and "number" in names)


def _choice_branches(schema):
    branches = schema.get("anyOf", schema.get("oneOf", []))
    return [b for b in branches if isinstance(b, dict)]


def _value_parts(value, schema, label) -> list:
    """Contract-style problems for a value under a plain schema."""
    parts = []
    if not isinstance(schema, dict):
        return parts
    if "anyOf" in schema or "oneOf" in schema:
        detail = _choice_detail(value, schema, label)
        if detail is not None:
            nested, _ = detail
            parts.append(nested)
        return parts
    want = schema.get("type")
    if want is not None and not _type_ok(value, want):
        names = [want] if isinstance(want, str) else list(want)
        parts.append(f"{label}: expected type {' or '.join(names)}, "
                     f"got {_type_name(value)}")
        return parts
    if isinstance(value, dict):
        required = schema.get("required", [])
        props = schema.get("properties", {})
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    parts.append(f"{label}.{key}: required field "
                                 f"missing")
        if isinstance(props, dict):
            for key, item in value.items():
                if key in props and isinstance(props[key], dict):
                    parts.extend(_value_parts(
                        item, props[key], f"{label}.{key}"))
    elif isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for pos, item in enumerate(value[:10]):
                parts.extend(_value_parts(
                    item, items, f"{label}[{pos}]"))
    return parts


def _branch_score(value, branch) -> int:
    """Fewest problems wins: rank one choice branch for a value."""
    if not isinstance(branch, dict):
        return 1 << 30
    want = branch.get("type")
    if want is not None and not _type_ok(value, want):
        return 1 << 30
    if isinstance(value, dict) and want in (None, "object"):
        missing = sum(
            1 for key in branch.get("required", []) or []
            if key not in value)
        props = branch.get("properties", {}) or {}
        extra = sum(
            1 for key in value
            if (branch.get("additionalProperties") is False
                and key not in props))
        return missing + extra
    if isinstance(value, list) and want in (None, "array"):
        return 0
    return 0


def _discriminant_values(subschema):
    """``const``/``enum`` values of one branch property, or None.

    None means the branch puts no fixed choice on the field, so any
    value accepts it.
    """
    if not isinstance(subschema, dict):
        return None
    if "const" in subschema:
        return [subschema["const"]]
    enum = subschema.get("enum")
    if isinstance(enum, list):
        return list(enum)
    return None


def _discriminant_detail(value, branches, label):
    """Errors by the branch the value's choice field names (§45).

    When the branches share a field with ``const`` or ``enum``
    (the overview candidates' ``decision``), the value's entry for
    that field picks the branch: the detail shows the errors of the
    branch whose ``const``/``enum`` accepts the value. When no
    branch accepts it, the detail is ``"<field>: got <value>;
    allowed: <values of all branches>"``. Returns ``(detail,
    field)`` or None when no choice field applies.
    """
    if not isinstance(value, dict):
        return None
    keys = []
    for branch in branches:
        props = branch.get("properties", {}) if isinstance(
            branch, dict) else {}
        if not isinstance(props, dict):
            continue
        for key, subschema in props.items():
            if (_discriminant_values(subschema) is not None
                    and key in value and key not in keys):
                keys.append(key)
    for key in keys:
        entry = value[key]
        allowed: list = []
        accepting = []
        for branch in branches:
            props = branch.get("properties", {}) if isinstance(
                branch, dict) else {}
            fixed = _discriminant_values(
                props.get(key) if isinstance(props, dict) else None)
            if fixed is None:
                accepting.append(branch)
                continue
            for option in fixed:
                if option not in allowed:
                    allowed.append(option)
            if entry in fixed:
                accepting.append(branch)
        if not accepting:
            shown = ", ".join(str(option) for option in allowed)
            return (f"{label}.{key}: got {entry!r}; allowed: {shown}",
                    strip_prefix(label) + f".{key}")
        branches = accepting
    if len(branches) == 1:
        return ("__single__", branches[0])
    return None


def _choice_detail(value, schema, label):
    """One error for a failed ``anyOf``/``oneOf`` (brief §34).

    When the value is an object (or array) and the choice allows an
    object (or array), the error reports that branch's own
    problems: the missing required keys, the keys the branch does
    not allow, and each wrong type with its path. Returns
    ``(detail, field)`` or None when no branch matches the value.
    """
    branches = _choice_branches(schema)
    if not branches:
        return None
    picked = None
    if isinstance(value, dict):
        # A value that names its branch by a const/enum field (the
        # overview candidates' ``decision``) is judged against that
        # branch, not the fewest-problems one (brief §45).
        made = _discriminant_detail(value, list(branches), label)
        if made is not None:
            detail, field = made
            if detail != "__single__":
                return made
            picked = field
    if picked is not None:
        options = [picked]
    else:
        options = None
    if isinstance(value, dict):
        if options is None:
            options = [b for b in branches
                       if b.get("type", "object") == "object"]
        if not options:
            return None
        branch = min(options, key=lambda b: _branch_score(value, b))
        parts = []
        required = branch.get("required", []) or []
        props = branch.get("properties", {}) or {}
        for key in required:
            if key not in value:
                parts.append(f"missing key '{key}'")
        if branch.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    parts.append(f"key '{key}' is not allowed")
        for key, item in value.items():
            if key in props and isinstance(props[key], dict):
                parts.extend(_value_parts(
                    item, props[key], f"{label}.{key}"))
        if not parts:
            return None
        keys = [k for k in required
                if isinstance(k, str)] or sorted(props)
        return (f"{label}: " + "; ".join(parts) +
                f" (expected {{{', '.join(keys)}}})",
                strip_prefix(label))
    if isinstance(value, list):
        options = [b for b in branches
                   if b.get("type", "array") == "array"]
        if not options:
            return None
        branch = min(options, key=lambda b: _branch_score(value, b))
        parts = []
        if ("minItems" in branch and len(value) < branch["minItems"]):
            parts.append(f"need at least {branch['minItems']} items")
        if ("maxItems" in branch and len(value) > branch["maxItems"]):
            parts.append(f"at most {branch['maxItems']} items "
                         f"allowed")
        items = branch.get("items")
        if isinstance(items, dict):
            for pos, item in enumerate(value[:10]):
                parts.extend(_value_parts(
                    item, items, f"{label}[{pos}]"))
        if not parts:
            return None
        return (f"{label}: " + "; ".join(parts) + " (expected array)",
                strip_prefix(label))
    return None


def _join_label(node_path) -> str:
    """Parts back to a contract label (``value.a[0].b``)."""
    out = ""
    for part in node_path:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += ("." if out else "") + str(part)
    return out


def _is_under(node_path, parts) -> bool:
    """Raw label ``parts`` sits at or under the detailed node."""
    if len(parts) < len(node_path):
        return False
    return list(parts[:len(node_path)]) == list(node_path)


def check_v1(evidence) -> list:
    """Schema errors as ``MISSING_FIELD`` records with exact paths."""
    if not isinstance(evidence, dict):
        return [{"code": _MISSING, "field": "evidence",
                 "detail": "evidence: must be a JSON object"}]
    raw = validate_evidence(evidence)
    errors = []
    suffix = " " + allowed_camera_shapes()
    try:
        schema = load_evidence_schema()
    except (OSError, ValueError):
        schema = {}
    detailed: set = set()
    for message in raw:
        field = _field_of(message)
        if field == "camera" or field.startswith("camera."):
            continue
        if field == "clock" or field.startswith("clock."):
            continue
        label = message.split(":", 1)[0].strip()
        parts = _label_parts(label)
        node_path = None
        # The nearest choice the label sits under, if any: an
        # object (or array) value failing an ``anyOf``/``oneOf``
        # names that branch's keys, not the bare "expected type"
        # line (brief §34). One error per choice.
        for cut in range(len(parts), 0, -1):
            candidate = _node_at(schema, parts[:cut])
            if candidate is not None and (
                    "anyOf" in candidate or "oneOf" in candidate):
                node_path = tuple(parts[:cut])
                break
        if node_path is not None and node_path not in detailed:
            value = _value_at(evidence, list(node_path))
            node = _node_at(schema, list(node_path))
            if isinstance(value, (dict, list)) and isinstance(
                    node, dict):
                made = _choice_detail(value, node,
                                      _join_label(node_path))
                if made is not None:
                    detailed.add(node_path)
                    errors.append({"code": _MISSING, "field": made[1],
                                   "detail": made[0]})
                    continue
        if (node_path is not None and node_path in detailed
                and _is_under(node_path, parts)):
            continue
        errors.append({"code": _MISSING, "field": field,
                       "detail": message + (
                           suffix if field.startswith("camera") else "")})
    if "camera" not in evidence:
        errors.append({"code": _MISSING, "field": "camera",
                       "detail": ("camera: required field missing "
                                  + allowed_camera_shapes())})
    else:
        errors.extend(_camera_errors(evidence["camera"]))
    if "clock" in evidence:
        errors.extend(_clock_errors(evidence["clock"]))
    return errors

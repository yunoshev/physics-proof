# generated from brief/06 · part 06 owns this file
"""Tool dispatch: argument validation and exception policy.

A tool call with bad arguments is the agent's mistake, not our crash
(part 06 addendum 2026-10-28, second live run): missing or extra
arguments, or arguments of the wrong type, get a structured
``bad_arguments`` error naming the expected parameters from the tool
schema, and the loop goes on. Only an exception that is not about the
arguments still goes to synthesis (:class:`CatastrophicToolError`).

``EXPECTED_PARAMS`` and the schemas are re-exported from part 07's
single source (never copied); the pinned cross-part test checks the
equality.
"""

from __future__ import annotations

import json

from src.tools.result import err_result
from src.tools.schemas import EXPECTED_PARAMS, TOOL_SCHEMAS

__all__ = [
    "EXPECTED_PARAMS",
    "TOOL_SCHEMAS",
    "TRANSIENT_EXCEPTIONS",
    "CatastrophicToolError",
    "check_arg_types",
    "validate_args",
]

#: Transport deaths retried with backoff (part 14 §4). :class:`OSError`
#: covers :class:`ConnectionError` and its subclass the accounting
#: ``NetworkError``; the accounting ``FailedCallError`` is a plain
#: ``Exception`` and never takes this path.
TRANSIENT_EXCEPTIONS = (OSError,)

#: JSON-schema type names to Python checks (``bool`` is never an
#: ``integer``/``number``).
_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float))
    and not isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def _type_names(spec) -> list:
    kind = spec.get("type", "object") if isinstance(spec, dict) else "object"
    return [kind] if isinstance(kind, str) else [str(k) for k in kind]


def check_arg_types(tool: str, arguments: dict) -> str:
    """Why ``arguments`` mistypes ``tool``'s schema (``""`` when clean).

    Absent (``None``) values are never mistyped: every part-07 tool
    takes ``None`` defaults and reports a missing domain argument as
    its own structured error. ``submit``'s ``evidence`` additionally
    accepts a JSON string (part 07 §7).
    """
    schema = next((e for e in TOOL_SCHEMAS if e.get("name") == tool), None)
    if schema is None:
        return f"unknown tool {tool!r}"
    props = (schema.get("parameters", {}) or {}).get("properties", {}) or {}
    for name, value in arguments.items():
        if value is None:
            continue
        if tool == "submit" and name == "evidence" \
                and isinstance(value, str):
            continue
        spec = props.get(name)
        if spec is None:
            continue
        names = _type_names(spec)
        if any(_TYPE_CHECKS.get(kind, lambda v: True)(value)
               for kind in names):
            continue
        return (f"{tool}.{name} must be "
                f"{'/'.join(names)}, got {type(value).__name__}")
    return ""


def _coerce_arguments(arguments):
    """Accept a dict or a JSON string of one; else ``(None, reason)``."""
    if isinstance(arguments, dict):
        return dict(arguments), ""
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments) if arguments.strip() else {}
        except ValueError as exc:
            return None, f"arguments are not valid JSON: {exc}"
        if not isinstance(parsed, dict):
            return None, ("arguments must be a JSON object, got "
                           f"{type(parsed).__name__}")
        return parsed, ""
    return None, ("arguments must be a JSON object, got "
                  f"{type(arguments).__name__}")


def validate_args(tool: str, arguments) -> tuple:
    """``(clean, fault)``: exactly the schema's params, or a fault.

    ``fault`` is a ready-made ``bad_arguments`` result naming the
    expected parameters; ``clean`` holds every expected key (absent
    ones as ``None``, which the tools default). Only unknown tools,
    unparsable arguments, extra keys and mistyped present values
    fault here; a missing domain argument is reported by the tool
    itself as its own structured error, and the loop goes on.
    """
    expected = EXPECTED_PARAMS.get(tool)
    if expected is None:
        known = sorted(EXPECTED_PARAMS)
        return None, err_result(
            "bad_arguments",
            f"unknown tool {tool!r}; expected one of {', '.join(known)}")
    parsed, reason = _coerce_arguments(arguments)
    if parsed is None:
        return None, err_result(
            "bad_arguments",
            f"{tool}: {reason}; expected parameters "
            f"{', '.join(expected)}")
    extra = [k for k in parsed if k not in expected]
    if extra:
        return None, err_result(
            "bad_arguments",
            f"{tool}: unexpected argument(s) {', '.join(extra)}; "
            f"expected parameters {', '.join(expected)}")
    clean = {k: parsed.get(k) for k in expected}
    mistyped = check_arg_types(tool, clean)
    if mistyped:
        return None, err_result(
            "bad_arguments",
            f"{mistyped}; expected parameters {', '.join(expected)}")
    return clean, None


class CatastrophicToolError(Exception):
    """Our bug inside a tool handler: the run must synthesise, not hang."""

    def __init__(self, tool: str, exc: BaseException) -> None:
        super().__init__(f"tool {tool} failed: "
                         f"{type(exc).__name__}: {exc}")
        self.tool = str(tool)
        self.exc = exc

# generated from brief/04 · part 04 owns this file
"""Blind mask-check and search-blindness classifier clients (§6).

Single context-free calls: no tools, ``effort:
BLIND_REASONING_EFFORT`` (``high``, addendum 2026-11-01),
``max_output_tokens: BLIND_MAX_OUTPUT_TOKENS`` (16384 — thinking
counts toward the limit), strict JSON schema, contributor model
(``skills/meta-api.md``). An ``incomplete`` answer is an error, and a
4xx raises :class:`FailedCallError` (the tools map it to a structured
error result — never retried as network).

The blind client also answers part 07 §§19/22 line checks
(addenda 2026-10-31 and 2026-11-01): the request takes a ``kind``.
Without one it is a mask check as before; ``"line_look"`` returns
per-line objects (``description`` plus ``view`` — the side the
object is seen from — and ``dimension`` — the object's own
dimension the line runs along) from the overlay image, and
``"line_match"`` returns per-line ``results`` from descriptions
plus claims with no image. No claim ever goes with the image.

Gap (named per part 04 §6): the classifier's interface —
``(query) -> "yes" | "no" | "uncertain"`` as
:func:`src.tools.web_search.web_search` defines it — carries no usage
channel, so its token cost never reaches the ledger. The blind-check
interface does carry ``usage`` and is priced exactly like an agent
call.
"""

from __future__ import annotations

import base64
import json
import re

from src import config as _config
from src.accounting import FailedCallError
from src.tools.web_search import CLASSIFIER_QUESTION

from ._http import auth_headers, request_with_retries
from .spark import _extract_usage

__all__ = [
    "BLIND_ANSWER_SCHEMA",
    "CLASSIFIER_ANSWER_SCHEMA",
    "CLASSIFIER_QUESTION",
    "extract_json_object",
    "line_look_schema",
    "line_match_schema",
    "make_blind_client",
    "make_classifier",
]


#: Strict answer shape for the blind coverage call.
BLIND_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "alternatives": {"type": "array",
                         "items": {"type": "string"}},
    },
    "required": ["description", "alternatives"],
    "additionalProperties": False,
}

#: Strict answer shape for the classifier call.
CLASSIFIER_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string"},
    },
    "required": ["verdict"],
    "additionalProperties": False,
}

#: What the classifier is asked (it sees only the query text): the single
#: wording pinned as part 07's interface
#: (:data:`src.tools.web_search.CLASSIFIER_QUESTION`, part 04 §7),
#: imported here, never copied or paraphrased.


def line_look_schema(n_lines: int) -> dict:
    """Strict answer schema for a ``line_look`` call (part 04 §2026-10-31,
    extended by part 07 §22 on 2026-11-01).

    An object with ``descriptions``: an array of per-line objects —
    each ``{"description", "view", "dimension"}`` (all strings) — with
    ``minItems`` = ``maxItems`` = ``n_lines``.
    """
    count = int(n_lines)
    return {
        "type": "object",
        "properties": {
            "descriptions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "view": {"type": "string"},
                        "dimension": {"type": "string"},
                    },
                    "required": ["description", "view", "dimension"],
                    "additionalProperties": False,
                },
                "minItems": count,
                "maxItems": count,
            },
        },
        "required": ["descriptions"],
        "additionalProperties": False,
    }


def line_match_schema(n_claims: int) -> dict:
    """Strict answer schema for a ``line_match`` call (part 04 §2026-10-31).

    An object with ``results`` (``[{agrees, why}]``): an array with
    ``minItems`` = ``maxItems`` = the number of claims.
    """
    count = int(n_claims)
    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "agrees": {"type": "boolean"},
                        "why": {"type": "string"},
                    },
                    "required": ["agrees", "why"],
                    "additionalProperties": False,
                },
                "minItems": count,
                "maxItems": count,
            },
        },
        "required": ["results"],
        "additionalProperties": False,
    }


def extract_json_object(text: str, required_keys=()) -> dict | None:
    """First JSON object in ``text`` holding ``required_keys``.

    A strict-schema answer can still arrive wrapped in prose or a
    fence (``skills/meta-api.md``), so the parse scans balanced
    braces instead of demanding a bare object.
    """
    if not isinstance(text, str) or "{" not in text:
        return None
    start = text.find("{")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    candidate = json.loads(text[start:index + 1])
                except ValueError:
                    return None
                if isinstance(candidate, dict) and all(
                        k in candidate for k in required_keys):
                    return candidate
                return None
    return None


def _terminal_text(terminal: dict) -> str:
    """Concatenated message text of a terminal event's output."""
    inner = terminal.get("response") if isinstance(terminal, dict) else None
    output = (inner.get("output") if isinstance(inner, dict)
              else (terminal or {}).get("output")) or []
    texts = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if (isinstance(part, dict)
                    and part.get("type") == "output_text"
                    and part.get("text")):
                texts.append(str(part["text"]))
    return "".join(texts)


def _strict_format(name: str, schema: dict) -> dict:
    return {
        "type": "json_schema",
        "name": name,
        "schema": schema,
        "strict": True,
    }


def _post_answer(api_key: str, base: str, body: dict, timeout: float,
                 sleep, kind: str):
    """One context-free call; return ``(terminal, usage)``.

    ``response.failed`` and ``response.incomplete`` raise
    :class:`FailedCallError` (an incomplete answer is an error here);
    transport deaths raise through the retry policy as network.
    """
    terminal, _ = request_with_retries(
        f"{base}/responses", auth_headers(api_key), body,
        timeout=timeout, sleep=sleep)
    kind_name = (terminal or {}).get("type")
    usage = _extract_usage(terminal or {})
    if kind_name == "response.completed":
        return terminal, usage
    if kind_name == "response.incomplete":
        raise FailedCallError(f"{kind} ended response.incomplete")
    inner = ((terminal or {}).get("response") or {})
    error = inner.get("error") or "response.failed"
    raise FailedCallError(f"{kind} ended response.failed: {error}")


def _request_image_bytes(blind_request: dict) -> bytes:
    """Raw image bytes of a blind request (or raise)."""
    image = blind_request.get("image")
    if isinstance(image, (bytearray, memoryview)):
        image = bytes(image)
    if not isinstance(image, bytes) or not image:
        raise FailedCallError("blind request carries no image bytes")
    return image


def _request_question(blind_request: dict) -> str:
    """The non-empty question of a blind request (or raise)."""
    question = str(blind_request.get("question") or "").strip()
    if not question:
        raise FailedCallError("blind request carries no question")
    return question


def make_blind_client(api_key, *, base_url=None,
                      model=None, timeout=None, sleep=None):
    """The ``check_mask`` / ``check_line`` backend (part 04 §6).

    ``blind_request`` takes a ``kind`` (addendum 2026-10-31). Without
    one it is a mask check: ``{"image", "extents", "question"}``
    returns ``{"description", "alternatives", "usage"}``. With
    ``"line_look"`` (``{"kind", "image", "question", "n_lines"}``) it
    returns ``{"descriptions", "usage"}`` where each entry of
    ``descriptions`` is ``{"description", "view", "dimension"}``
    (part 07 §22; a bare string passes through for an older look
    that predates §22); with ``"line_match"``
    (``{"kind", "descriptions", "claims", "question"}``, no image) it
    returns ``{"results", "usage"}``. Usage rides along so the tool
    prices the call like an agent call. Every request carries no
    history, no phrase, no hypothesis — and no claim ever goes with
    the image.
    """
    key = str(api_key)
    base = str(base_url or _config.API_BASE_URL)
    limit = float(timeout if timeout is not None
                  else _config.API_TIMEOUT_S)

    def blind_client(blind_request) -> dict:
        if not isinstance(blind_request, dict):
            raise FailedCallError("blind request must be a dict")
        kind = blind_request.get("kind", None)
        if kind is None:
            return _mask_check(blind_request, key, base,
                               model, limit, sleep)
        if kind == "line_look":
            return _line_look(blind_request, key, base,
                              model, limit, sleep)
        if kind == "line_match":
            return _line_match(blind_request, key, base,
                               model, limit, sleep)
        raise FailedCallError(f"unknown blind kind {kind!r}")

    return blind_client


def _mask_check(blind_request, key, base, model, limit, sleep) -> dict:
    """The mask check: image plus extents, coverage answer."""
    image = _request_image_bytes(blind_request)
    question = _request_question(blind_request)
    extents = blind_request.get("extents")
    enquiry = question
    if isinstance(extents, dict) and extents:
        enquiry += ("\nMask pixel extents: "
                    + json.dumps(extents, sort_keys=True,
                                 default=str))
    body = {
        "model": model or _config.SPARK_MODEL,
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_image",
                 "image_url": ("data:image/png;base64,"
                               + base64.b64encode(image).decode())},
                {"type": "input_text", "text": enquiry},
            ],
        }],
        "stream": True,
        "store": False,
        "max_output_tokens": int(_config.BLIND_MAX_OUTPUT_TOKENS),
        "reasoning": {"effort": _config.BLIND_REASONING_EFFORT},
        "text": {"format": _strict_format(
            "blind_check", BLIND_ANSWER_SCHEMA)},
    }
    terminal, usage = _post_answer(key, base, body, limit, sleep,
                                   "blind check")
    parsed = extract_json_object(
        _terminal_text(terminal), ("description",))
    if parsed is None:
        raise FailedCallError(
            "blind check returned no structured answer")
    description = parsed.get("description")
    if not isinstance(description, str) or not description.strip():
        raise FailedCallError(
            "blind check returned an empty description")
    alternatives = parsed.get("alternatives") or []
    if not isinstance(alternatives, list):
        alternatives = [str(alternatives)]
    return {
        "description": description.strip(),
        "alternatives": [str(a) for a in alternatives],
        "usage": usage,
    }


def _clean_look_entry(entry, position: int):
    """One per-line look answer, validated (or raise).

    Part 07 §22: each per-line answer carries ``description`` (where
    the line starts and ends), ``view`` (the side the object is seen
    from) and ``dimension`` (the object's own dimension the line runs
    along). An empty string anywhere raises, as for a mask check.

    A bare non-empty string is tolerated for an older look that
    predates §22 (the schema we send still requires the object
    shape, so a compliant model returns objects): it passes through
    unchanged so callers written against the string shape keep
    working. Anything else raises.
    """
    if isinstance(entry, str):
        if not entry.strip():
            raise FailedCallError(
                f"line look returned an empty description "
                f"for line {position}")
        return entry.strip()
    if not isinstance(entry, dict):
        raise FailedCallError(
            f"line look returned a malformed entry for line {position}: "
            f"{entry!r}")
    clean = {}
    for name in ("description", "view", "dimension"):
        value = entry.get(name)
        if not isinstance(value, str) or not value.strip():
            raise FailedCallError(
                f"line look returned an empty {name} for line {position}")
        clean[name] = value.strip()
    return clean


def _line_look(blind_request, key, base, model, limit, sleep) -> dict:
    """The line-look call: the overlay image only, ``n`` per-line looks."""
    image = _request_image_bytes(blind_request)
    question = _request_question(blind_request)
    n_lines = blind_request.get("n_lines")
    if (isinstance(n_lines, bool) or not isinstance(n_lines, int)
            or int(n_lines) < 1):
        raise FailedCallError(
            f"line_look needs a positive n_lines, got {n_lines!r}")
    count = int(n_lines)
    body = {
        "model": model or _config.SPARK_MODEL,
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_image",
                 "image_url": ("data:image/png;base64,"
                               + base64.b64encode(image).decode())},
                {"type": "input_text", "text": question},
            ],
        }],
        "stream": True,
        "store": False,
        "max_output_tokens": int(_config.BLIND_MAX_OUTPUT_TOKENS),
        "reasoning": {"effort": _config.BLIND_REASONING_EFFORT},
        "text": {"format": _strict_format(
            "line_look", line_look_schema(count))},
    }
    terminal, usage = _post_answer(key, base, body, limit, sleep,
                                   "line look")
    parsed = extract_json_object(
        _terminal_text(terminal), ("descriptions",))
    if parsed is None:
        raise FailedCallError(
            "line look returned no structured answer")
    descriptions = parsed.get("descriptions")
    if (not isinstance(descriptions, list)
            or len(descriptions) != count):
        raise FailedCallError(
            "line look returned "
            f"{len(descriptions) if isinstance(descriptions, list) else '?'}"
            f" descriptions for {count} lines")
    clean = [_clean_look_entry(entry, position)
             for position, entry
             in enumerate(descriptions, start=1)]
    return {"descriptions": clean, "usage": usage}


def _clean_lines(values, name: str) -> list:
    """Non-empty strings of a line-match side (or raise).

    A mapping carrying the side's text (a post-§22 look object with
    ``description`` passed straight into the match, or a ``claim``
    mapping) is read through its text field; anything else must be a
    non-empty string.
    """
    if not isinstance(values, (list, tuple)) or not values:
        raise FailedCallError(
            f"line_match needs a non-empty list of non-empty {name}, "
            f"got {values!r}")
    key = "description" if name == "descriptions" else "claim"
    clean = []
    for value in values:
        if isinstance(value, dict):
            value = value.get(key, value.get("description",
                                             value.get("claim")))
        if not isinstance(value, str) or not value.strip():
            raise FailedCallError(
                f"line_match needs a non-empty list of non-empty "
                f"{name}, got {values!r}")
        clean.append(value.strip())
    return clean


def _line_match(blind_request, key, base, model, limit, sleep) -> dict:
    """The line-match call: descriptions plus claims, text only."""
    descriptions = _clean_lines(
        blind_request.get("descriptions"), "descriptions")
    claims = _clean_lines(blind_request.get("claims"), "claims")
    if len(descriptions) != len(claims):
        raise FailedCallError(
            f"line_match needs one description per claim, got "
            f"{len(descriptions)} descriptions for "
            f"{len(claims)} claims")
    question = _request_question(blind_request)
    pairs = "\n".join(
        f"Line {position} \u2014 description: {text}; claim: {claim}"
        for position, (text, claim)
        in enumerate(zip(descriptions, claims), start=1))
    body = {
        "model": model or _config.SPARK_MODEL,
        "input": [{
            "role": "user",
            "content": [{
                "type": "input_text",
                "text": question + "\n" + pairs,
            }],
        }],
        "stream": True,
        "store": False,
        "max_output_tokens": int(_config.BLIND_MAX_OUTPUT_TOKENS),
        "reasoning": {"effort": _config.BLIND_REASONING_EFFORT},
        "text": {"format": _strict_format(
            "line_match", line_match_schema(len(claims)))},
    }
    terminal, usage = _post_answer(key, base, body, limit, sleep,
                                   "line match")
    parsed = extract_json_object(
        _terminal_text(terminal), ("results",))
    if parsed is None:
        raise FailedCallError(
            "line match returned no structured answer")
    results = parsed.get("results")
    if (not isinstance(results, list)
            or len(results) != len(claims)):
        raise FailedCallError(
            "line match returned "
            f"{len(results) if isinstance(results, list) else '?'}"
            f" results for {len(claims)} claims")
    clean = []
    for entry in results:
        if not isinstance(entry, dict):
            raise FailedCallError(
                f"line match returned a malformed result {entry!r}")
        agrees = entry.get("agrees")
        why = entry.get("why")
        if not isinstance(agrees, bool):
            raise FailedCallError(
                f"line match returned a non-boolean agrees {entry!r}")
        if not isinstance(why, str) or not why.strip():
            raise FailedCallError(
                "line match returned an empty why")
        clean.append({"agrees": agrees, "why": why.strip()})
    return {"results": clean, "usage": usage}


def make_classifier(api_key, *, base_url=None, model=None,
                    timeout=None, sleep=None):
    """The ``web_search`` blindness classifier (part 04 §6).

    Sees only the query text. Returns exactly ``"yes"``, ``"no"`` or
    ``"uncertain"`` — doubt fails closed. Any transport or answer
    failure raises (the tool then fails closed too).
    """
    key = str(api_key)
    base = str(base_url or _config.API_BASE_URL)
    limit = float(timeout if timeout is not None
                  else _config.API_TIMEOUT_S)

    def classifier(query) -> str:
        if not isinstance(query, str) or not query.strip():
            return "uncertain"
        body = {
            "model": model or _config.SPARK_MODEL,
            "input": [{
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": (CLASSIFIER_QUESTION + "\n\nQuery: "
                             + query.strip()),
                }],
            }],
            "stream": True,
            "store": False,
            "max_output_tokens": int(_config.BLIND_MAX_OUTPUT_TOKENS),
            "reasoning": {"effort": _config.BLIND_REASONING_EFFORT},
            "text": {"format": _strict_format(
                "blindness_verdict", CLASSIFIER_ANSWER_SCHEMA)},
        }
        terminal, _ = _post_answer(key, base, body, limit, sleep,
                                   "classifier")
        parsed = extract_json_object(_terminal_text(terminal),
                                     ("verdict",))
        raw = (parsed.get("verdict") if isinstance(parsed, dict)
               else _terminal_text(terminal))
        word = re.sub(r"[^a-z]", "", str(raw or "").strip().lower())
        if word in ("yes", "no", "uncertain"):
            return word
        return "uncertain"

    return classifier

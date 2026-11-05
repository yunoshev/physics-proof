# generated from brief/04 · part 04 owns this file
"""Blind line-check kinds (part 04 addenda 2026-10-31 and 2026-11-01,
offline).

The blind client answers part 07 §§19/22 line checks: ``kind:
"line_look"`` returns per-line objects (``description`` plus ``view``
and ``dimension``) from the overlay image, and ``kind:
"line_match"`` returns per-line ``results`` from descriptions plus
claims with no image. A wrong count or an empty string raises
:class:`FailedCallError`, as for a mask check.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.accounting import FailedCallError

from tests.clients.conftest import sse_completed_text


def _completed_json(payload: dict, **usage_kwargs) -> bytes:
    return sse_completed_text(json.dumps(payload), **usage_kwargs)


def _look_object(description="a span", view="side", dimension="depth"):
    return {"description": description, "view": view,
            "dimension": dimension}


def test_line_look_sends_schema_and_returns_descriptions(
        stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"descriptions": [
            _look_object("lower edge of the dark bar", "front", "width"),
            _look_object("tip of the long finger", "side", "height")]},
        input_tokens=200, cached_tokens=0, output_tokens=60,
        reasoning_tokens=10))
    clients = make_clients(stub_server)
    answer = clients["blind_spark_client"]({
        "kind": "line_look",
        "image": b"\x89PNG overlay bytes",
        "question": "Where does each numbered line start and end?",
        "n_lines": 2})
    assert answer["descriptions"] == [
        {"description": "lower edge of the dark bar",
         "view": "front", "dimension": "width"},
        {"description": "tip of the long finger",
         "view": "side", "dimension": "height"}]
    assert answer["usage"]["input_tokens"] == 200
    body = stub_server.log[-1]
    from src import config as _config

    assert body["reasoning"] == {"effort": _config.BLIND_REASONING_EFFORT}
    assert body["max_output_tokens"] == _config.BLIND_MAX_OUTPUT_TOKENS
    assert "tools" not in body, "blind calls carry no tools"
    assert len(body["input"]) == 1, "no history on a blind call"
    content = body["input"][0]["content"]
    assert {p["type"] for p in content} == {"input_image", "input_text"}
    image_part = next(p for p in content if p["type"] == "input_image")
    assert base64.b64decode(
        image_part["image_url"].split(",", 1)[1]) == b"\x89PNG overlay bytes"
    text_part = next(p for p in content if p["type"] == "input_text")
    assert text_part["text"] == "Where does each numbered line start and end?"
    schema = body["text"]["format"]["schema"]
    array = schema["properties"]["descriptions"]
    assert array["minItems"] == 2 and array["maxItems"] == 2
    assert array["items"]["required"] == ["description", "view",
                                          "dimension"]
    assert array["items"]["additionalProperties"] is False
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["descriptions"]


def test_line_look_returns_view_and_dimension(stub_server, make_clients):
    """Part 07 §22: a stub line-look answer carrying ``view`` and
    ``dimension`` comes back from the client with both.

    Fails without the fix: the old client reads each per-line answer
    as a bare string, so the side the object is seen from and the
    dimension the line runs along are dropped on the floor.
    """
    stub_server.enqueue(_completed_json(
        {"descriptions": [
            _look_object("a horizontal line across the torso",
                         "side", "depth")]}))
    clients = make_clients(stub_server)
    answer = clients["blind_spark_client"]({
        "kind": "line_look", "image": b"bytes",
        "question": "q", "n_lines": 1})
    (entry,) = answer["descriptions"]
    assert entry["description"] == "a horizontal line across the torso"
    assert entry["view"] == "side"
    assert entry["dimension"] == "depth"


def test_line_look_carries_no_claims_or_extents(stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"descriptions": [_look_object()]}))
    clients = make_clients(stub_server)
    clients["blind_spark_client"]({
        "kind": "line_look",
        "image": b"bytes",
        "question": "neutral question",
        "n_lines": 1})
    body = stub_server.log[-1]
    raw = json.dumps(body)
    assert "claim" not in raw.lower(), "no claim goes with the image"
    assert "extents" not in raw.lower(), "no extents on a line look"


def test_line_look_count_mismatch_raises(stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"descriptions": [_look_object("only one")]}))
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({
            "kind": "line_look", "image": b"bytes",
            "question": "q", "n_lines": 2})


def test_line_look_empty_description_raises(stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"descriptions": [_look_object("  "),
                          _look_object("b")]}))
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({
            "kind": "line_look", "image": b"bytes",
            "question": "q", "n_lines": 2})


def test_line_look_empty_view_or_dimension_raises(
        stub_server, make_clients):
    """Part 07 §22: an empty ``view`` or ``dimension`` raises, like an
    empty description — the match cannot check the dimension
    otherwise."""
    stub_server.enqueue(_completed_json(
        {"descriptions": [_look_object("a span", "  ", "depth")]}))
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({
            "kind": "line_look", "image": b"bytes",
            "question": "q", "n_lines": 1})
    stub_server.enqueue(_completed_json(
        {"descriptions": [_look_object("a span", "side", "")]}))
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({
            "kind": "line_look", "image": b"bytes",
            "question": "q", "n_lines": 1})


def test_line_look_bare_string_passes_through_for_older_looks(
        stub_server, make_clients):
    """A bare-string per-line answer passes through (part 07 §22
    compat).

    The schema we send requires per-line objects, so a compliant
    model returns them; but an older look (or stub) that predates
    §22 answers bare strings, and the client must not turn those
    into ``FailedCallError`` — part 07's tool written against the
    string shape reads them back. An empty string still raises, as
    for a mask check, and anything neither string nor object
    raises.
    """
    stub_server.enqueue(_completed_json(
        {"descriptions": ["a bare string from an older look"]}))
    clients = make_clients(stub_server)
    answer = clients["blind_spark_client"]({
        "kind": "line_look", "image": b"bytes",
        "question": "q", "n_lines": 1})
    assert answer["descriptions"] == ["a bare string from an older look"]
    stub_server.enqueue(_completed_json({"descriptions": ["   "]}))
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({
            "kind": "line_look", "image": b"bytes",
            "question": "q", "n_lines": 1})
    stub_server.enqueue(_completed_json({"descriptions": [42]}))
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({
            "kind": "line_look", "image": b"bytes",
            "question": "q", "n_lines": 1})


def test_line_match_accepts_look_objects_as_descriptions(
        stub_server, make_clients):
    """Post-§22 look objects passed straight into the match read
    through their ``description`` field."""
    stub_server.enqueue(_completed_json(
        {"results": [{"agrees": True, "why": "match"}]}))
    clients = make_clients(stub_server)
    answer = clients["blind_spark_client"]({
        "kind": "line_match",
        "descriptions": [_look_object("a span", "side", "depth")],
        "claims": ["a claim"],
        "question": "q"})
    assert answer["results"] == [{"agrees": True, "why": "match"}]
    body = stub_server.log[-1]
    text = body["input"][0]["content"][0]["text"]
    assert "a span" in text


def test_line_look_missing_image_is_an_error(stub_server, make_clients):
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({
            "kind": "line_look", "question": "q", "n_lines": 1})
    assert stub_server.hits == 0


def test_line_match_sends_schema_and_returns_results(
        stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"results": [{"agrees": True, "why": "both name the bar edge"},
                     {"agrees": False, "why": "description names a finger"}]},
        input_tokens=120, cached_tokens=0, output_tokens=40,
        reasoning_tokens=4))
    clients = make_clients(stub_server)
    answer = clients["blind_spark_client"]({
        "kind": "line_match",
        "descriptions": ["the lower edge of the dark bar",
                         "the tip of the long finger"],
        "claims": ["spans the bar edge", "spans the cuff"],
        "question": "Does each description match its claim?"})
    assert answer["results"] == [
        {"agrees": True, "why": "both name the bar edge"},
        {"agrees": False, "why": "description names a finger"}]
    assert answer["usage"]["input_tokens"] == 120
    body = stub_server.log[-1]
    from src import config as _config

    assert body["reasoning"] == {"effort": _config.BLIND_REASONING_EFFORT}
    assert body["max_output_tokens"] == _config.BLIND_MAX_OUTPUT_TOKENS
    assert "tools" not in body, "blind calls carry no tools"
    assert len(body["input"]) == 1, "no history on a blind call"
    content = body["input"][0]["content"]
    assert all(p["type"] == "input_text" for p in content), (
        "a line match is text only: no image travels with claims")
    text = content[0]["text"]
    assert "Line 1" in text and "Line 2" in text
    assert "the lower edge of the dark bar" in text
    assert "spans the cuff" in text
    schema = body["text"]["format"]["schema"]
    array = schema["properties"]["results"]
    assert array["minItems"] == 2 and array["maxItems"] == 2
    assert array["items"]["required"] == ["agrees", "why"]
    assert array["items"]["additionalProperties"] is False


def test_line_match_missing_image_is_not_an_error(
        stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"results": [{"agrees": True, "why": "match"}]}))
    clients = make_clients(stub_server)
    answer = clients["blind_spark_client"]({
        "kind": "line_match",
        "descriptions": ["a span"], "claims": ["a claim"],
        "question": "q"})
    assert answer["results"] == [{"agrees": True, "why": "match"}]


def test_line_match_count_mismatch_raises(stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"results": [{"agrees": True, "why": "match"}]}))
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({
            "kind": "line_match",
            "descriptions": ["one", "two"], "claims": ["a", "b"],
            "question": "q"})


def test_line_match_empty_why_raises(stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"results": [{"agrees": True, "why": "   "}]}))
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({
            "kind": "line_match",
            "descriptions": ["a span"], "claims": ["a claim"],
            "question": "q"})


def test_line_match_non_boolean_agrees_raises(stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"results": [{"agrees": "yes", "why": "match"}]}))
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({
            "kind": "line_match",
            "descriptions": ["a span"], "claims": ["a claim"],
            "question": "q"})


def test_unknown_kind_raises_without_a_call(stub_server, make_clients):
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({"kind": "line_sniff",
                                       "question": "q"})
    assert stub_server.hits == 0

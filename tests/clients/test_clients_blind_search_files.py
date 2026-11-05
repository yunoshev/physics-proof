# generated from brief/04 · part 04 owns this file
"""Blind-check, classifier, web-search and Files tests (offline)."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.accounting import FailedCallError

from tests.clients.conftest import (
    sse_completed_text,
    sse_failed,
    sse_incomplete,
    sse_truncated,
)


def _completed_json(payload: dict, **usage_kwargs) -> bytes:
    return sse_completed_text(json.dumps(payload), **usage_kwargs)


def test_blind_check_answer_and_usage(stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"description": "covers the pack plus the top unit",
         "alternatives": ["pack alone"]},
        input_tokens=200, cached_tokens=0, output_tokens=60,
        reasoning_tokens=10))
    clients = make_clients(stub_server)
    answer = clients["blind_spark_client"]({
        "image": b"\x89PNG fake bytes",
        "extents": {"frame": 3, "bbox": [1, 2, 3, 4]},
        "question": "What does the mask cover?"})
    assert answer["description"] == "covers the pack plus the top unit"
    assert answer["alternatives"] == ["pack alone"]
    assert answer["usage"]["input_tokens"] == 200
    body = stub_server.log[-1]
    # Blind calls think at high effort with room for thinking
    # (part 04 addendum 2026-11-01), read from config, not spelled out.
    from src import config as _config

    assert body["reasoning"] == {"effort": _config.BLIND_REASONING_EFFORT}
    assert body["max_output_tokens"] == _config.BLIND_MAX_OUTPUT_TOKENS
    assert "tools" not in body, "blind calls carry no tools"
    content = body["input"][0]["content"]
    kinds = {p["type"] for p in content}
    assert kinds == {"input_image", "input_text"}
    image_part = next(p for p in content if p["type"] == "input_image")
    assert base64.b64decode(
        image_part["image_url"].split(",", 1)[1]) == b"\x89PNG fake bytes"


def test_blind_check_sends_no_history(stub_server, make_clients):
    stub_server.enqueue(_completed_json(
        {"description": "d", "alternatives": []}))
    clients = make_clients(stub_server)
    clients["blind_spark_client"]({"image": b"x", "extents": {},
                                   "question": "q"})
    body = stub_server.log[-1]
    assert len(body["input"]) == 1


def test_blind_incomplete_is_error(stub_server, make_clients):
    stub_server.enqueue(sse_incomplete())
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({"image": b"x", "extents": {},
                                       "question": "q"})


def test_blind_402_not_retried(stub_server, make_clients):
    payload = json.dumps({"error": {
        "code": "billing_not_configured", "message": "no payment",
        "type": "auth_error"}}).encode()
    stub_server.enqueue(payload, status=402)
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["blind_spark_client"]({"image": b"x", "extents": {},
                                       "question": "q"})
    assert stub_server.hits == 1


def test_classifier_verdicts(stub_server, make_clients):
    for verdict in ("yes", "no", "uncertain"):
        stub_server.enqueue(_completed_json({"verdict": verdict}))
    clients = make_clients(stub_server)
    assert clients["classifier"]("who filmed this clip?") == "yes"
    assert clients["classifier"]("average adult step rate") == "no"
    assert clients["classifier"]("???") == "uncertain"


def test_classifier_sends_part07_question(stub_server, make_clients):
    """One wording (part 04 §7): the live classifier asks part 07's
    pinned question, imported — never copied or paraphrased."""
    from src.clients import blind as blind_module
    from src.tools import web_search

    assert (blind_module.CLASSIFIER_QUESTION
            is web_search.CLASSIFIER_QUESTION)
    stub_server.enqueue(_completed_json({"verdict": "no"}))
    clients = make_clients(stub_server)
    assert clients["classifier"]("suited astronaut height metres") == "no"
    body = stub_server.log[-1]
    text = body["input"][0]["content"][0]["text"]
    assert text.startswith(web_search.CLASSIFIER_QUESTION), text[:120]
    assert "Query: suited astronaut height metres" in text
    # The classifier is a blind call too: high effort, blind tokens
    # (part 04 addendum 2026-11-01). Fails without the fix: the old
    # body asked for low effort with 4096 tokens.
    from src import config as _config

    assert body["reasoning"] == {"effort": _config.BLIND_REASONING_EFFORT}
    assert body["max_output_tokens"] == _config.BLIND_MAX_OUTPUT_TOKENS


def test_no_legacy_classifier_wording_in_clients():
    """The pre-§7 wording ("identify a specific video, event, or
    source") flagged missions/people/places; it must be gone from
    every client module. The probe strips quotes and whitespace so a
    wording split across string-literal lines still matches (a plain
    ``in`` check passes vacuously on the old blind.py, which wrapped
    the line after "or"). Fails on the old blind.py, passes now."""
    import re

    root = Path(__file__).resolve().parents[2]
    hits = []
    for module in sorted((root / "src" / "clients").glob("*.py")):
        compact = re.sub(r'["\s]+', "",
                         module.read_text(encoding="utf-8"))
        if "event,orsource" in compact:
            hits.append(module.name)
    assert hits == []


def test_classifier_fails_closed_on_prose(stub_server, make_clients):
    stub_server.enqueue(sse_completed_text("I cannot decide."))
    clients = make_clients(stub_server)
    assert clients["classifier"]("anything") == "uncertain"


def test_classifier_truncated_is_retried(stub_server, make_clients):
    stub_server.enqueue(sse_truncated())
    stub_server.enqueue(_completed_json({"verdict": "no"}))
    clients = make_clients(stub_server)
    assert clients["classifier"]("beam widths") == "no"
    assert stub_server.hits == 2


def test_search_facts_pass_through(stub_server, make_clients):
    facts = [
        {"text": "A generic mast is 8 m tall",
         "source_url": "https://example.com/mast",
         "quote": "masts are 8 m"},
        {"text": "Step rates cluster near 2 Hz",
         "source_url": "https://example.com/gait",
         "quote": "2 Hz typical"},
    ]
    stub_server.enqueue(_completed_json({"facts": facts}))
    clients = make_clients(stub_server)
    answer = clients["search_client"]("generic mast height")
    assert answer["answer"] == facts
    assert answer["sources"] == ["https://example.com/mast",
                                 "https://example.com/gait"]
    body = stub_server.log[-1]
    assert {"type": "web_search"} in body["tools"]
    assert body["tool_choice"] == "auto"


def test_search_failed_is_terminal(stub_server, make_clients):
    stub_server.enqueue(sse_failed("search down"))
    clients = make_clients(stub_server)
    with pytest.raises(FailedCallError):
        clients["search_client"]("beam sizes")


def test_files_upload_and_delete(stub_server, make_clients, tmp_path):
    target = tmp_path / "cut.mp4"
    target.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)
    clients = make_clients(stub_server)
    record = clients["files"].upload(str(target))
    assert record["id"] == "file_1"
    assert record["status"] == "uploaded"
    assert stub_server.uploads and stub_server.uploads[0]["size"] > 100
    assert clients["files"].delete(record["id"]) is True
    assert stub_server.deletes == ["/files/file_1"]

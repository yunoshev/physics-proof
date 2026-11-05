# generated from brief/06 · part 06 owns this file
"""Failed agent calls: logged, retried without images, then synthesis.

Part 06 addendum 2026-11-03 (sped-up run 20261102T222230Z): the
loop logs the API's error payload as ``spark_error``, retries once
with the newest turn's image inputs replaced after two consecutive
``response.failed`` calls, and ends the run after the third with
``the model service refused the request``.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.loop.run import (
    IMAGE_REFUSED_PLACEHOLDER,
    SPARK_REFUSED_REASON,
    _spark_error,
    _spark_error_code,
)


def _failed(message="boom", code="model_refused"):
    """A ``response.failed`` agent reply carrying an error payload."""
    return {"terminal": "response.failed", "text": "",
            "tool_calls": [], "usage": None,
            "error": {"code": code, "message": message}}


def _image_blocks(request):
    """Image content blocks of the request's tool messages."""
    blocks = []
    for message in request.get("messages", []) or []:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "tool":
            continue
        for block in message.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "image":
                blocks.append(block)
    return blocks


def _text_blocks(request):
    """Text of the request's tool messages, joined."""
    texts = []
    for message in request.get("messages", []) or []:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "tool":
            continue
        for block in message.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(str(block.get("text", "")))
    return "\n".join(texts)


def _loop_rows(run_dir):
    path = Path(str(run_dir)) / "logs" / "loop.jsonl"
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_loop_three_failed_calls_end_run_with_refused_reason(
        drive_loop, make_run):
    """Three ``response.failed`` calls end the run; every row carries
    ``spark_error``."""
    run_dir = make_run()
    requests: list = []

    def _spark(request):
        requests.append(request)
        return _failed()

    out = drive_loop(run_dir, _spark)
    assert len(requests) == 3
    assert out["status"] == "undetermined"
    assert SPARK_REFUSED_REASON in out["reason"]
    assert "model_refused" in out["reason"]
    rows = _loop_rows(run_dir)
    assert len(rows) == 3
    for row in rows:
        assert row["spark_terminal"] == "response.failed"
        assert "model_refused" in row["spark_error"]
        assert "boom" in row["spark_error"]
    assert (Path(str(run_dir)) / "result.json").is_file()


def test_loop_two_failures_strip_newest_images_then_run_goes_on(
        drive_loop, make_run, monkeypatch, stub_responses,
        accepting_validator):
    """After two failures the third request drops the newest turn's
    images and the run continues."""
    import src.tools.view_frames as view_frames_mod
    from src.loop import run as run_mod

    def _fake_view(run_dir, turn, **kwargs):
        return {"ok": True, "summary": "sheet",
                "files": ["artifacts/t0_view_sheet.png"], "metrics": {}}

    monkeypatch.setattr(view_frames_mod, "view_frames", _fake_view)
    donated = {"terminal": "response.completed", "text": "starting",
               "tool_calls": [{"call_id": "call-0", "name": "view_frames",
                               "arguments": {}}],
               "usage": {"input_tokens": 10, "cached_tokens": 0,
                         "output_tokens": 5, "reasoning_tokens": 0}}
    monkeypatch.setattr(run_mod, "run_preplan",
                        lambda *args, **kwargs: (None, donated, None))

    run_dir = make_run()
    requests: list = []
    failures = {"count": 0}

    def _spark(request):
        requests.append(request)
        if failures["count"] < 2:
            failures["count"] += 1
            return _failed("nope", "try_again")
        if len(requests) == 3:
            return stub_responses["completed"](
                "go", [stub_responses["call"](
                    "submit",
                    {"evidence": {"segments": [
                        {"frames": {"start": 1, "apex": 5, "end": 9}}]},
                     "dry_run": False},
                    "call-submit")])
        return stub_responses["completed"]("out of script")

    out = drive_loop(run_dir, _spark,
                     validator=accepting_validator(run_dir))
    assert out["status"] == "submitted"
    # The first request still rode the newest turn's image in.
    assert _image_blocks(requests[0])
    # The third request — after two consecutive failures — carries no
    # image from the newest turn, only the placeholder text.
    assert _image_blocks(requests[2]) == []
    assert IMAGE_REFUSED_PLACEHOLDER in _text_blocks(requests[2])


def test_loop_spark_error_cut_and_coded():
    """The logged payload is cut to the cap and keeps its code."""
    from src.loop.run import SPARK_ERROR_CAP

    long_message = "x" * (SPARK_ERROR_CAP + 500)
    response = {"terminal": "response.failed",
                "error": {"code": "E", "message": long_message}}
    text = _spark_error(response)
    assert len(text) <= SPARK_ERROR_CAP
    assert _spark_error_code(response, text) == "E"
    assert _spark_error({"terminal": "response.failed",
                         "error": "http 500 body"}) == "http 500 body"
    assert "response.failed" in _spark_error(
        {"terminal": "response.failed"})

"""Offline probes 4-5: the recorded fixtures parse (Spark text/tool, SAM)."""

from __future__ import annotations

import json

import numpy as np

from physics_proof.meta_client import (
    _function_calls,
    _message_text,
    _usage_of,
    decode_sam_text,
    parse_response_body,
    video_dimensions,
)


def test_spark_text_fixture_parses(fixtures_dir):
    raw = (fixtures_dir / "spark_text.sse").read_bytes()
    _deltas, completed = parse_response_body(raw)
    assert completed["status"] == "completed"
    text = _message_text(completed["output"])
    assert text.strip() != ""
    usage = _usage_of(completed)
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0


def test_spark_tool_fixture_yields_one_function_call(fixtures_dir):
    raw = (fixtures_dir / "spark_tool.sse").read_bytes()
    _deltas, completed = parse_response_body(raw)
    calls = _function_calls(completed["output"])
    assert len(calls) == 1
    call = calls[0]
    assert call.name != ""
    assert isinstance(call.arguments, dict)
    assert call.arguments != {}


def test_sam_fixture_decodes(fixtures_dir):
    manifest = json.loads((fixtures_dir / "sam_manifest.json").read_text())
    raw = (fixtures_dir / "sam_red_square.sse").read_bytes()
    _deltas, completed = parse_response_body(raw)
    width, height = video_dimensions(fixtures_dir / "sam_clip.mp4")
    assert (width, height) == (manifest["width"], manifest["height"])
    full_text = _message_text(completed.get("output", [])) or _deltas
    frames = decode_sam_text(full_text, width, height)
    assert sorted(frames) == manifest["frames_with_objects"]
    assert len(frames) == manifest["frame_count"]
    for index, objects in frames.items():
        assert objects, f"frame {index} has no objects"
        for obj in objects:
            x1, y1, x2, y2 = obj.box
            assert 0 <= x1 < x2 <= width
            assert 0 <= y1 < y2 <= height
            assert obj.mask.dtype == bool
            assert obj.mask.shape == (height, width)
            assert obj.mask.any(), f"frame {index} object {obj.id} mask is empty"
            rows, cols = np.nonzero(obj.mask)
            assert rows.min() >= y1 and rows.max() < y2
            assert cols.min() >= x1 and cols.max() < x2

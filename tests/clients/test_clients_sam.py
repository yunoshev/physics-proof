# generated from brief/04 · part 04 owns this file
"""SAM 3.1 client tests (part 04 §6, offline, stubbed)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

np = pytest.importorskip("numpy", reason="SAM masks need numpy")


def _encoder():
    try:
        from meta_sam_parser._mask_codec import _encode_raster
    except ImportError:
        pytest.skip("meta-sam-parser cannot encode test payloads; "
                    "the live smoke covers decode")
    return _encode_raster


def _sam_text(encode) -> str:
    pay1 = encode([1, 1, 1, 1], 2, 2)
    pay2 = encode([1, 0, 0, 1], 2, 2)
    line0 = (
        "<0f>1<|box;x1=0;y1=0;x2=1;y2=1;w=8;h=8;c=0.90|>"
        f"<|mask;x=0;y=0;c=0.90;data=2,2,{pay1}|>,"
        "2<|box;x1=4;y1=4;x2=5;y2=5;w=8;h=8;c=0.80|>"
        f"<|mask;x=0;y=0;c=0.80;data=2,2,{pay2}|>")
    line1 = (
        "<1f>1<|box;x1=0;y1=0;x2=1;y2=1;w=8;h=8;c=0.90|>"
        f"<|mask;x=0;y=0;c=0.90;data=2,2,{pay1}|>")
    return line0 + "\n" + line1 + "\n"


def test_sam_two_objects_two_frames_mapped_by_start(stub_server,
                                                    make_clients):
    encode = _encoder()
    from tests.clients.conftest import sse_completed_text

    stub_server.enqueue(sse_completed_text(
        _sam_text(encode), video_frames_processed=50))
    clients = make_clients(stub_server)
    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(2)]
    masks = clients["sam_client"]("the square", [10, 11], frames)
    # Two objects, each aligned with the two requested frames; the cut
    # index maps back by the cut's start frame (10, not 0).
    assert sorted(masks) == ["1", "2"]
    assert len(masks["1"]) == 2 and len(masks["2"]) == 2
    assert masks["1"][0][0:2, 0:2].all()
    assert masks["1"][1][0:2, 0:2].all()
    assert masks["2"][0][4:6, 4:6].sum() == 2  # diagonal payload
    assert not masks["2"][1].any(), "absent frame stays all-False"
    assert clients["sam_client"].last_report["frames_billed"] == 50
    assert clients["sam_client"].last_report["frame_start"] == 10
    # Upload first, delete afterwards.
    assert len(stub_server.uploads) == 1
    assert stub_server.deletes == ["/files/file_1"]


def test_sam_request_shape(stub_server, make_clients):
    encode = _encoder()
    from tests.clients.conftest import sse_completed_text

    stub_server.enqueue(sse_completed_text(
        _sam_text(encode), video_frames_processed=2))
    clients = make_clients(stub_server)
    frames = [np.zeros((8, 8, 3), dtype=np.uint8)]
    clients["sam_client"]("the square", [4], frames)
    body = stub_server.log[-1]
    assert body["model"] == "sam-3.1"
    content = body["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "the square"}
    assert content[1] == {"type": "input_video", "file_id": "file_1"}
    assert body["metadata"] == {"include_confidence": "true",
                                "mask_encoding": "lossless"}
    for absent in ("instructions", "reasoning", "max_output_tokens",
                   "tools"):
        assert absent not in body
    # Billing honours the padded usage: max(50, frames, processed).
    assert clients["sam_client"].last_report["frames_billed"] == 50
    from src.clients import sam_billed_frames

    assert sam_billed_frames(2, 50) == 50
    assert sam_billed_frames(60, 60) == 60
    assert sam_billed_frames(60, 40) == 60
    with pytest.raises(ValueError):
        sam_billed_frames(-1)


def test_sam_without_parser_is_backend_death(stub_server, make_clients,
                                             monkeypatch):
    import src.clients.sam as sam_mod

    monkeypatch.setattr(sam_mod, "decode_sam_text",
                        lambda text: (_ for _ in ()).throw(
                            RuntimeError("no parser")))
    from tests.clients.conftest import sse_completed_text

    stub_server.enqueue(sse_completed_text("<0f>", video_frames_processed=50))
    clients = make_clients(stub_server)
    frames = [np.zeros((8, 8, 3), dtype=np.uint8)]
    with pytest.raises(RuntimeError):
        clients["sam_client"]("the square", [0], frames)
    # The uploaded file is still deleted on the way out.
    assert stub_server.deletes == ["/files/file_1"]
    assert json.dumps(stub_server.log[-1])  # request was well-formed

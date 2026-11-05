# generated from brief/04 · part 04 owns this file
"""Offline end-to-end test (part 04 addendum 2026-10-28).

Runs the real :func:`src.loop.run.run_loop` with the real clients
from :mod:`src.clients` against the validating stub, for four turns:

1. a commentary message plus a ``function_call`` to the
   frame-viewing tool, whose result carries an image;
2. a second tool call (web search, through the real classifier and
   search clients);
3. a plain text reply with no tool call, which the loop must answer;
4. a final submit.

Every request the loop sends is validated by the stub — this is the
test the first live run would have failed. Turn 2's request must
carry turn 1's call (part 04 addendum 2026-10-27).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.clients.conftest import (
    sse_completed_call,
    sse_completed_text,
)


def _build_clip(run: Path, frames: int = 8) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("needs ffmpeg for the clip fixture")
    pytest.importorskip("cv2", reason="view_frames decodes with cv2")
    clip = run / "input" / "clip.mp4"
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"testsrc=size=64x64:rate=10:duration={frames / 10}",
         "-pix_fmt", "yuv420p", "-an", str(clip)],
        capture_output=True, timeout=120)
    if proc.returncode != 0 or not clip.is_file():
        pytest.skip("ffmpeg could not build the clip fixture")
    (run / "input" / "timing.json").write_text(json.dumps({
        "frame_count": frames,
        "timestamps": [i / 10 for i in range(frames)],
        "timestamps_s": [i / 10 for i in range(frames)],
        "measured_fps": 10.0,
        "confirmed_duplicates": [],
        "cuts": [],
    }), encoding="utf-8")


def test_end_to_end_four_turns_against_validating_stub(
        stub_server, tmp_path):
    from src.clients import build_clients
    from src.loop import run_loop

    run = tmp_path / "e2e"
    (run / "input").mkdir(parents=True)
    _build_clip(run)
    sleeps: list = []
    clients = build_clients("test-key", base_url=stub_server.base_url,
                            run_dir=str(run), timeout=10,
                            sleep=sleeps.append)
    # Turn 1: commentary + frame-viewing call (result carries images).
    stub_server.enqueue(sse_completed_call(
        "starting with a look", call_id="call_t1", name="view_frames",
        arguments={"frame_start": 0, "frame_end": 3}))
    # Turn 2: a second tool call (search, via classifier + search).
    stub_server.enqueue(sse_completed_call(
        "looking up a size", call_id="call_t2", name="web_search",
        arguments={"query": "generic steel beam widths"}))
    stub_server.enqueue(sse_completed_text(
        '{"verdict": "no"}'))  # classifier
    stub_server.enqueue(sse_completed_text(json.dumps({"facts": [{
        "text": "Beams are wide", "source_url": "https://example.com/b",
        "quote": "wide beams"}]})))  # search
    # Turn 3: plain text with no tool call — the loop must answer.
    stub_server.enqueue(sse_completed_text("thinking, no call yet"))
    # Turn 4: the final submit.
    submitted: list = []

    def accepting_validator(evidence, run_context=None, dry_run=False):
        submitted.append(evidence)
        result_path = run / "result.json"
        result_path.write_text(json.dumps({"accepted": True}) + "\n",
                               encoding="utf-8")
        return {"accepted": True, "errors": [],
                "result": {"accepted": True},
                "result_path": str(result_path)}

    stub_server.enqueue(sse_completed_call(
        "handing in", call_id="call_t4", name="submit",
        arguments={"evidence": json.dumps({"draft": True}),
                   "dry_run": False}))
    outcome = run_loop(str(run), "e2e-run",
                       spark_client=clients["spark_client"],
                       blind_spark_client=clients["blind_spark_client"],
                       classifier=clients["classifier"],
                       sam_client=clients["sam_client"],
                       search_client=clients["search_client"],
                       validator=accepting_validator,
                       sleep=lambda s: None)
    assert outcome["status"] == "submitted", outcome
    assert submitted and submitted[0] == {"draft": True}
    # Every request the loop sent passed live-API validation.
    assert stub_server.rejections == []
    # Agent requests carry instructions; classifier/search/SAM do not.
    spark_bodies = [b for b in stub_server.log if "instructions" in b]
    assert len(spark_bodies) == 4, (
        "turns 1, 2, 3 (tool-less) and 4 each sent one agent request")
    # Turn 2's request carries turn 1's call, paired with its output.
    turn2 = spark_bodies[1]
    call_ids = [i.get("call_id") for i in turn2["input"]
                if i.get("type") == "function_call"]
    output_ids = [i.get("call_id") for i in turn2["input"]
                  if i.get("type") == "function_call_output"]
    assert "call_t1" in call_ids, "turn 1's call must be replayed"
    assert "call_t1" in output_ids, "turn 1's output must be paired"
    # The frame-viewing result's image rode along as input_image.
    images = [p for i in turn2["input"] for p in (i.get("content") or [])
              if isinstance(p, dict) and p.get("type") == "input_image"]
    assert images, "turn 1's contact sheet must reach turn 2"
    # The loop answered the tool-less turn instead of stalling.
    assert outcome["turns"] == 4

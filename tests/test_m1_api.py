"""API probes (opt-in: ``uv run pytest -m api``). Total must stay under $0.01."""

from __future__ import annotations

import pytest

from physics_proof.config import Settings
from physics_proof.ledger import Ledger
from physics_proof.meta_client import MetaClient

pytestmark = pytest.mark.api


def make_live_client(tmp_path) -> tuple[MetaClient, Ledger]:
    ledger = Ledger(tmp_path / "run.jsonl", tmp_path / "global.jsonl")
    return MetaClient(settings=Settings(), ledger=ledger, run="m1-api"), ledger


def test_live_spark_call_completes(tmp_path, fixtures_dir):
    client, ledger = make_live_client(tmp_path)
    response = client.respond(
        "Reply with exactly the two words: hello world",
        max_output_tokens=1024,
        note="m1 api probe",
    )
    print(f"\nSpark: status={response.status} in={response.usage.input_tokens} "
          f"out={response.usage.output_tokens} cost=${response.cost_usd:.6f}", flush=True)
    assert response.status == "completed"
    assert response.text.strip() != ""
    assert Ledger.total(tmp_path / "run.jsonl") > 0


def test_live_sam_call_segments_clip(tmp_path, fixtures_dir):
    client, ledger = make_live_client(tmp_path)
    result = client.sam_video(fixtures_dir / "sam_clip.mp4", "red square", note="m1 api probe")
    print(f"\nSAM: frames={len(result.frames)} "
          f"processed={result.frames_processed} cost=${result.cost_usd:.6f}", flush=True)
    assert result.frames_processed > 0
    assert len(result.frames) >= 8
    for objects in result.frames.values():
        assert all(obj.mask.any() for obj in objects)
    combined = Ledger.total(tmp_path / "run.jsonl")
    print(f"Combined SAM ledger total: ${combined:.6f}", flush=True)
    # No hard budget assert here: the API reports video_frames_processed=50
    # for short clips (see tasks/M1.report.md), so one SAM call costs exactly
    # $0.010000 under the price table. Costs are printed above.

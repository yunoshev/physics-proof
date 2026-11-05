# generated from brief/07 · part 07 owns this file
"""``segment``: billing floor, artifacts, run-only cache."""

from __future__ import annotations

import json

import numpy as np

from src.helpers import masks_io
from src.tools import segment


def test_small_range_refused_without_confirm(make_run, fake_sam,
                                            ledger):
    run = make_run(frames=40)
    result = segment.segment(str(run), 3, phrase="the square",
                             frame_start=0, frame_end=9,
                             sam_client=fake_sam, ledger=ledger,
                             cache={})
    assert not result["ok"]
    assert (result["error"]["code"]
            == "small_range_requires_confirm")
    assert result["metrics"]["frames_billed"] == 50
    assert fake_sam.calls["n"] == 0
    assert ledger.sam_frames_billed == 0


def test_confirmed_small_range_bills_50(make_run, fake_sam, ledger):
    run = make_run(frames=40)
    result = segment.segment(str(run), 3, phrase="the square",
                             frame_start=0, frame_end=9,
                             confirm_small_range=True,
                             sam_client=fake_sam, ledger=ledger,
                             cache={})
    assert result["ok"], result
    assert result["metrics"]["frames_requested"] == 10
    assert result["metrics"]["frames_billed"] == 50
    assert ledger.sam_frames_billed == 50
    assert fake_sam.calls["n"] == 1


def test_full_range_bills_exactly(make_run, fake_sam, ledger):
    run = make_run(frames=100)
    result = segment.segment(str(run), 0, phrase="the square",
                             frame_start=0, frame_end=99,
                             sam_client=fake_sam, ledger=ledger,
                             cache={})
    assert result["ok"], result
    assert result["metrics"]["frames_billed"] == 100
    assert result["metrics"]["frames_requested"] == 100


def test_masks_previews_stats_named_and_valid(make_run, fake_sam,
                                              ledger):
    run = make_run(frames=60)
    result = segment.segment(str(run), 1, phrase="the square",
                             frame_start=0, frame_end=59,
                             sam_client=fake_sam, ledger=ledger,
                             cache={})
    assert result["ok"], result
    masks_rel = result["metrics"]["masks_artifact"]
    assert masks_rel.startswith("artifacts/t1_segment_")
    assert masks_rel.endswith(".npz")
    masks = masks_io.load_masks(run / masks_rel)
    assert set(masks) == {"obj0"}
    assert sorted(masks["obj0"]) == list(range(60))
    assert masks["obj0"][0].dtype == bool
    stats_rel = result["metrics"]["stats_artifact"]
    assert stats_rel in result["files"]
    previews = result["metrics"]["previews"]
    assert 1 <= len(previews) <= 6
    for preview in previews:
        assert (run / preview["artifact"]).is_file()
        assert preview["artifact"] in result["files"]
    row = [r for r in
           json.loads((run / stats_rel).read_text(encoding="utf-8"))
           if r["frame"] == 0][0]
    assert row["objects"]["obj0"]["area_px"] == 40 * 40
    assert row["objects"]["obj0"]["bbox"] == {"x0": 20, "y0": 30,
                                             "x1": 59, "y1": 69}


def test_cache_is_run_only(make_run, fake_sam, ledger):
    run = make_run(frames=60)
    cache = {}
    first = segment.segment(str(run), 0, phrase="the square",
                            frame_start=0, frame_end=59,
                            sam_client=fake_sam, ledger=ledger,
                            cache=cache)
    assert first["ok"], first
    assert fake_sam.calls["n"] == 1
    second = segment.segment(str(run), 2, phrase="the square",
                             frame_start=0, frame_end=59,
                             sam_client=fake_sam, ledger=ledger,
                             cache=cache)
    assert second["ok"]
    assert second["metrics"]["cache_hit"] is True
    assert fake_sam.calls["n"] == 1, "same run must reuse the cache"
    other = make_run(frames=60)
    third = segment.segment(str(other), 0, phrase="the square",
                            frame_start=0, frame_end=59,
                            sam_client=fake_sam, ledger=ledger,
                            cache={})
    assert third["ok"]
    assert fake_sam.calls["n"] == 2, "a new run must re-call SAM"


def test_out_of_range_and_missing_backend(make_run, fake_sam):
    run = make_run(frames=40)
    bad = segment.segment(str(run), 0, phrase="the square",
                          frame_start=0, frame_end=100,
                          sam_client=fake_sam, cache={})
    assert not bad["ok"]
    assert bad["error"]["code"] == "bad_range"
    none = segment.segment(str(run), 0, phrase="the square",
                           frame_start=0, frame_end=39,
                           confirm_small_range=True,
                           sam_client=None, cache={})
    assert not none["ok"]
    assert none["error"]["code"] == "sam_unavailable"


def test_sam_failure_is_a_tool_error(make_run, ledger):
    run = make_run(frames=60)

    def _boom(phrase, indices, frames):
        raise RuntimeError("uplink down")

    result = segment.segment(str(run), 0, phrase="the square",
                             frame_start=0, frame_end=59,
                             sam_client=_boom, ledger=ledger, cache={})
    assert not result["ok"]
    assert result["error"]["code"] == "sam_failed"
    assert result["metrics"]["frames_billed"] == 60
    assert ledger.sam_frames_billed == 0

# generated from brief/04 · part 04 owns this file
"""Live smoke (part 04 §6): real API, real money, tiny budget.

Runs only with ``PHYSICS_PROOF_LIVE=1`` and costs < $0.05: one
contributor text call, one SAM call on a generated 60-frame clip of
a moving white square (mask found, centroid moves), one web search.
Without the variable every test skips with a reason.
"""

from __future__ import annotations

import os

import pytest

LIVE = os.environ.get("PHYSICS_PROOF_LIVE") == "1"
NEEDS_LIVE = pytest.mark.skipif(
    not LIVE, reason="needs PHYSICS_PROOF_LIVE=1 (spends < $0.05)")


def _clients():
    from src.cli import read_api_key
    from src.clients import build_clients

    key = read_api_key()
    if not key:
        pytest.skip("no META_API_KEY/MODEL_API_KEY in the environment")
    return build_clients(key)


@NEEDS_LIVE
def test_live_contributor_text_call():
    clients = _clients()
    response = clients["spark_client"]({
        "model": "muse-spark-1.3-contributor",
        "messages": [
            {"role": "system",
             "content": [{"type": "text", "text": "Reply briefly."}]},
            {"role": "user",
             "content": [{"type": "text",
                          "text": "Say the word alive and nothing else."}]},
        ],
        "max_output_tokens": 64})
    assert response["terminal"] == "response.completed"
    assert "alive" in response["text"].lower()
    assert response["usage"]["output_tokens"] > 0


@NEEDS_LIVE
def test_live_sam_moving_square():
    np = pytest.importorskip("numpy", reason="SAM masks need numpy")
    clients = _clients()
    frames = []
    for i in range(60):
        grid = np.zeros((64, 64, 3), dtype=np.uint8)
        x = 4 + i // 2
        grid[24:40, x:x + 16] = 255
        frames.append(grid)
    masks = clients["sam_client"](
        "the white square", list(range(60)), frames)
    assert masks, "SAM found no object on a plain moving square"
    oid = sorted(masks)[0]
    assert len(masks[oid]) == 60

    def centroid(grid):
        ys, xs = np.nonzero(np.asarray(grid, dtype=bool))
        return float(xs.mean()) if len(xs) else 0.0

    first = centroid(masks[oid][0])
    last = centroid(masks[oid][-1])
    assert last > first, "the mask centroid must move with the square"
    assert clients["sam_client"].last_report["frames_billed"] >= 60


@NEEDS_LIVE
def test_live_web_search():
    clients = _clients()
    answer = clients["search_client"]("generic steel beam widths")
    assert isinstance(answer.get("facts"), list)

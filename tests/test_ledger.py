"""Offline probe 6: ledger costs match a hand-computed table; totals add up."""

from __future__ import annotations

import pytest

from physics_proof.ledger import Ledger, Usage, compute_cost_usd, load_prices

PRICES = {
    "models": {
        "muse-spark-1.3": {
            "input_per_1m": 1.25,
            "output_per_1m": 4.25,
            "cached_input_per_1m": 0.15,
        },
        "muse-spark-1.3-contributor": {
            "input_per_1m": 0.10,
            "output_per_1m": 0.20,
            "cached_input_per_1m": 0.002,
        },
    },
    "web_search_per_1k_calls": 2.50,
    "sam_per_1k_frames": 0.20,
    "sam_per_1k_images": 2.50,
}

CASES = [
    # (usage kwargs, expected usd)
    (
        {"model": "muse-spark-1.3-contributor", "kind": "spark",
         "input_tokens": 1000, "output_tokens": 500},
        (1000 * 0.10 + 500 * 0.20) / 1_000_000,
    ),
    (
        {"model": "muse-spark-1.3", "kind": "spark",
         "input_tokens": 1_000_000, "output_tokens": 1_000_000},
        1.25 + 4.25,
    ),
    (
        {"model": "muse-spark-1.3", "kind": "spark",
         "input_tokens": 10, "output_tokens": 10, "searches": 2000},
        (10 * 1.25 + 10 * 4.25) / 1_000_000 + 2000 * 2.50 / 1000,
    ),
    # Cached tokens are a subset of input tokens: the cached part is
    # billed at the discounted cached price, the rest at the input price.
    (
        {"model": "muse-spark-1.3-contributor", "kind": "spark",
         "input_tokens": 1000, "cached_tokens": 600, "output_tokens": 0},
        (400 * 0.10 + 600 * 0.002) / 1_000_000,
    ),
    # Task probe: 1M input of which 900k cached, 10k output, contributor.
    (
        {"model": "muse-spark-1.3-contributor", "kind": "spark",
         "input_tokens": 1_000_000, "cached_tokens": 900_000,
         "output_tokens": 10_000},
        0.1 * 0.1 + 0.9 * 0.002 + 0.01 * 0.2,
    ),
    # Task probe: standard tier cached discount.
    (
        {"model": "muse-spark-1.3", "kind": "spark",
         "input_tokens": 1_000_000, "cached_tokens": 500_000,
         "output_tokens": 0},
        (500_000 * 1.25 + 500_000 * 0.15) / 1_000_000,
    ),
    (
        {"model": "sam-3.1", "kind": "sam", "frames": 1500},
        1500 * 0.20 / 1000,
    ),
    (
        {"model": "sam-3.1", "kind": "sam-image", "frames": 4},
        4 * 2.50 / 1000,
    ),
    ({"model": "files", "kind": "upload"}, 0.0),
    ({"model": "files", "kind": "delete"}, 0.0),
]


@pytest.mark.parametrize("kwargs,expected", CASES)
def test_hand_computed_costs(kwargs, expected):
    usage = Usage(run="probe", **kwargs)
    assert compute_cost_usd(usage, PRICES) == pytest.approx(expected)


def test_missing_cached_price_falls_back_to_input_price():
    prices = {
        "models": {
            "legacy-model": {"input_per_1m": 1.00, "output_per_1m": 2.00},
        },
        "web_search_per_1k_calls": 2.50,
        "sam_per_1k_frames": 0.20,
        "sam_per_1k_images": 2.50,
    }
    usage = Usage(
        run="probe", model="legacy-model", kind="spark",
        input_tokens=1000, cached_tokens=600, output_tokens=100,
    )
    assert compute_cost_usd(usage, prices) == pytest.approx(
        (1000 * 1.00 + 100 * 2.00) / 1_000_000
    )


def test_unknown_model_raises():
    usage = Usage(run="probe", model="nope-9", kind="spark", input_tokens=5)
    with pytest.raises(ValueError):
        compute_cost_usd(usage, PRICES)


def test_ledger_appends_to_both_files_and_totals_add_up(tmp_path):
    run_path = tmp_path / "run.jsonl"
    global_path = tmp_path / "global.jsonl"
    ledger = Ledger(run_path, global_path)
    # Point the ledger at the same table the cases above use.
    ledger.prices = PRICES
    expected_total = 0.0
    for kwargs, expected in CASES:
        record = ledger.add(Usage(run="probe", **kwargs))
        assert record["usd"] == pytest.approx(expected)
        assert set(record) >= {
            "ts", "run", "model", "kind", "input_tokens", "cached_tokens",
            "output_tokens", "reasoning_tokens", "frames", "searches",
            "usd", "note",
        }
        expected_total += expected
    assert Ledger.total(run_path) == pytest.approx(expected_total)
    assert Ledger.total(global_path) == pytest.approx(expected_total)
    assert Ledger.total(tmp_path / "missing.jsonl") == 0.0


def test_repo_price_table_loads():
    from physics_proof.config import REPO_ROOT

    prices = load_prices(REPO_ROOT / "config" / "prices.json")
    assert prices["models"]["muse-spark-1.3-contributor"]["input_per_1m"] == 0.10
    assert prices["models"]["muse-spark-1.3-contributor"]["cached_input_per_1m"] == 0.002
    assert prices["models"]["muse-spark-1.3"]["cached_input_per_1m"] == 0.15
    assert prices["sam_per_1k_frames"] == 0.20

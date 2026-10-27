"""Cost ledger (SPEC.md M1, prices in section 7).

Every Meta API call appends one JSON line to both the run ledger and the
global ledger. Cost is computed here from the price table, never in the
client, so hand-checking the arithmetic needs only this file plus
``config/prices.json``.

Cached input tokens are a subset of input tokens (that is how the API
reports them), so charging input tokens at the input price already charges
cached tokens at the input price: there is no discount and no double count.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Usage:
    """One billable API call."""

    run: str
    model: str
    kind: str  # "spark" | "sam" | "sam-image" | "upload" | "delete"
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    frames: int = 0
    searches: int = 0
    note: str = ""


def load_prices(path: str | Path) -> dict[str, Any]:
    """Load the price table from JSON."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compute_cost_usd(usage: Usage, prices: Mapping[str, Any]) -> float:
    """Price one usage record in dollars."""
    kind = usage.kind
    if kind in ("upload", "delete"):
        return 0.0
    if kind == "sam":
        per_1k = float(prices["sam_per_1k_frames"])
        return usage.frames * per_1k / 1000.0
    if kind == "sam-image":
        per_1k = float(prices["sam_per_1k_images"])
        return usage.frames * per_1k / 1000.0
    if kind == "spark":
        models = prices["models"]
        if usage.model not in models:
            raise ValueError(f"unknown model in price table: {usage.model!r}")
        entry = models[usage.model]
        tokens_usd = (
            usage.input_tokens * float(entry["input_per_1m"])
            + usage.output_tokens * float(entry["output_per_1m"])
        ) / 1_000_000.0
        searches_usd = usage.searches * float(prices["web_search_per_1k_calls"]) / 1000.0
        return tokens_usd + searches_usd
    raise ValueError(f"unknown usage kind: {kind!r}")


class Ledger:
    """Appends one JSON line per call to the run ledger and global ledger."""

    def __init__(
        self,
        run_path: str | Path,
        global_path: str | Path,
        prices_path: str | Path | None = None,
    ) -> None:
        self.run_path = Path(run_path)
        self.global_path = Path(global_path)
        if prices_path is None:
            from .config import REPO_ROOT

            prices_path = REPO_ROOT / "config" / "prices.json"
        self.prices = load_prices(prices_path)

    def add(self, usage: Usage | Mapping[str, Any]) -> dict[str, Any]:
        """Price a usage, append the record line to both files, return it."""
        if not isinstance(usage, Usage):
            usage = Usage(**dict(usage))
        record = asdict(usage)
        record["ts"] = datetime.now(timezone.utc).isoformat()
        record["usd"] = compute_cost_usd(usage, self.prices)
        line = json.dumps(record, sort_keys=True) + "\n"
        for path in (self.run_path, self.global_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line)
        return record

    @staticmethod
    def total(path: str | Path) -> float:
        """Sum the ``usd`` column of a ledger file (missing file is 0)."""
        path = Path(path)
        if not path.exists():
            return 0.0
        total_usd = 0.0
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    total_usd += float(json.loads(line)["usd"])
        return total_usd

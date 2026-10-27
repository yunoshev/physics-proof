"""Settings for the Meta API client (SPEC.md section 2 and M1).

Everything comes from code defaults, overridable by environment variables.
The API key is deliberately NOT part of Settings: ``MetaClient`` reads
``META_API_KEY`` itself and never logs it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3-contributor"
DEFAULT_EFFORT = "low"
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_TIMEOUT_S = 300.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE_S = 1.0

#: Files of this size or less are inlined as data URLs; larger uploads
#: go through the Files API first (measured 2026-10-27: 50 MB limit).
MAX_DATA_URL_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    """Client settings with environment overrides."""

    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    prices_path: Path = REPO_ROOT / "config" / "prices.json"
    global_ledger_path: Path = Path.home() / ".physics-proof" / "ledger.jsonl"
    run_ledger_path: Path | None = None
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    backoff_base_s: float = DEFAULT_BACKOFF_BASE_S

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings, letting documented env vars override defaults."""
        get = os.environ.get
        max_tokens = get("META_MAX_OUTPUT_TOKENS")
        timeout = get("META_TIMEOUT_S")
        prices = get("META_PRICES_PATH")
        run_ledger = get("META_RUN_LEDGER")
        global_ledger = get("META_GLOBAL_LEDGER")
        return cls(
            base_url=get("META_BASE_URL", DEFAULT_BASE_URL),
            model=get("META_MODEL", DEFAULT_MODEL),
            effort=get("META_EFFORT", DEFAULT_EFFORT),
            max_output_tokens=int(max_tokens) if max_tokens else DEFAULT_MAX_OUTPUT_TOKENS,
            prices_path=Path(prices) if prices else REPO_ROOT / "config" / "prices.json",
            global_ledger_path=Path(global_ledger)
            if global_ledger
            else Path.home() / ".physics-proof" / "ledger.jsonl",
            run_ledger_path=Path(run_ledger) if run_ledger else None,
            timeout_s=float(timeout) if timeout else DEFAULT_TIMEOUT_S,
        )

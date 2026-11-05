# generated from brief/04 · part 04 owns this file
"""Config tests (part 04 §3, PLAN.md): the single source of limits."""

from __future__ import annotations

import datetime
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_price_table_versioned():
    from src import config

    assert isinstance(config.PRICE_TABLE_VERSION, int)
    assert config.PRICE_TABLE_VERSION >= 1
    # Spark contributor tier (skills/meta-api.md): $0.10 / $0.002 / $0.20.
    assert config.PRICE_SPARK_INPUT_PER_1M == pytest.approx(0.10)
    assert config.PRICE_SPARK_CACHED_PER_1M == pytest.approx(0.002)
    assert config.PRICE_SPARK_OUTPUT_PER_1M == pytest.approx(0.20)
    # SAM 3.1 (skills/sam-3-1.md): $0.20 per 1000 frames, min 50/call.
    assert config.PRICE_SAM_PER_1000_FRAMES == pytest.approx(0.20)
    assert config.SAM_MIN_BILLED_FRAMES == 50
    # The ledger prices exactly this table (subset, not addends).
    from src.accounting import price_call

    got = price_call(1000, 200, 500)
    assert got == pytest.approx(
        (800 * 0.10 + 200 * 0.002 + 500 * 0.20) / 1_000_000)


def test_caps_match_part03():
    from src import config

    # Hard acceptance ceilings (part 03 + owner addendums of early
    # November: from four runs at once on a third clip both limits
    # rise while the dollar cap stays put, and from the full suite
    # after the two-hundred-twenty-turn change turns rise to a
    # multiple of 2, 3 and 5, so one third, one half and 80 % of the
    # turn budget are whole turns; from street-jump run 80 the wall
    # cap rises to six hours (a run alone dry-runs at turn 89 after
    # one hundred fifty minutes and the loop self-submits at 80 % of
    # the old cap with fixable errors left); from street-jump run 81
    # the wall cap rises to eight hours (with six hours a run again
    # dry-runs near turn 96 after about one hundred fifty minutes
    # with fixable errors left, and ninety-second turns need the
    # extra room). Fails without the fix: the previous values pin a
    # smaller wall cap that ends runs before they can fix their
    # dry-run errors. The assertions read the constants themselves,
    # never a stale minute, turn or second count spelled as a
    # literal.
    assert config.HARD_CAP_COST_USD == pytest.approx(2.00)
    assert config.WARN_RATIO == pytest.approx(0.80)
    assert config.HARD_CAP_WALL_S == pytest.approx(
        datetime.timedelta(hours=8).total_seconds())
    assert config.MAX_TURNS == 48 * 5
    assert config.MAX_TURNS % 2 == 0
    assert config.MAX_TURNS % 3 == 0
    assert config.MAX_TURNS % 5 == 0
    assert config.MAX_TURNS // 3 * 3 == config.MAX_TURNS
    assert config.MAX_TURNS // 2 * 2 == config.MAX_TURNS
    assert config.WARN_RATIO * config.MAX_TURNS % 1 == pytest.approx(0.0)
    assert config.MAX_TURNS * 60 < config.HARD_CAP_WALL_S
    assert config.MAX_OUTPUT_TOKENS == 32768
    assert 0.0 < config.WARN_RATIO < 1.0


def test_max_mask_checks_eight():
    """Part 04 addendum 2026-11-03 (street-jump run): twenty mask checks
    per run, so line checks cannot starve mask checks.

    Fails without the fix: the old cap spends itself on early line
    checks (six line checks at two debits each) plus replaced masks,
    leaving reference mask checks with no budget left, and part 11
    returns MASK_CHECK_MISSING. Twenty holds eight for check_mask
    plus twelve for the most check_line can use. The assertion reads
    the constant — the expected value is spelled as a product, never
    as a bare digit.
    """
    from src import config

    assert config.MAX_MASK_CHECKS == 2 * 10
    assert config.load_config()["MAX_MASK_CHECKS"] is config.MAX_MASK_CHECKS
    # The loop enforces this same constant, not a copy of it.
    loop_text = (ROOT / "src" / "loop" / "run.py").read_text(
        encoding="utf-8")
    assert "MAX_MASK_CHECKS" in loop_text


def test_reasoning_efforts_and_blind_tokens():
    """Part 04 addendum 2026-11-01: the agent thinks at max effort,
    the blind calls at high, and the blind token limit fits thinking.

    Fails without the fix: the old config has no effort constants
    and the blind limit is 4096, which cut replies at high effort.
    The assertions read the constants, never their spellings.
    """
    from src import config

    assert config.SPARK_REASONING_EFFORT != config.BLIND_REASONING_EFFORT
    assert config.BLIND_MAX_OUTPUT_TOKENS == 16384
    assert config.MAX_OUTPUT_TOKENS == 32768
    table = config.load_config()
    assert table["SPARK_REASONING_EFFORT"] is config.SPARK_REASONING_EFFORT
    assert table["BLIND_REASONING_EFFORT"] is config.BLIND_REASONING_EFFORT
    assert table["BLIND_MAX_OUTPUT_TOKENS"] == config.BLIND_MAX_OUTPUT_TOKENS


def test_no_hardcoded_limits_elsewhere():
    """Spot scan: runtime code reads limits from config (PLAN.md)."""
    from src import config

    checked = {
        "src/loop/run.py": ["MAX_OUTPUT_TOKENS"],
        "src/accounting/__init__.py": ["PRICE_SPARK_INPUT_PER_1M"],
    }
    for rel, names in checked.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for name in names:
            assert name in text, f"{rel} must read {name} from config"
            # No literal redefinition of the value beside the import.
            assert f"{name} =" not in text, (
                f"{rel} hard-codes {name}")
    assert config.SPARK_MODEL == "muse-spark-1.3-contributor"


def test_python_pinned_313():
    """One Python, 3.13 (part 04 addendum 2026-10-28).

    Fails without the fix: with ``>=3.13`` a bare ``uv run`` builds
    .venv on 3.14 and the pinned test command fails on the non-empty
    directory. The pin must be ==, not >=.
    """
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(
        encoding="utf-8"))
    pinned = data["project"]["requires-python"]
    assert pinned == "==3.13.*", pinned
    assert re.fullmatch(r"==3\.13\.\*", pinned), pinned


def test_blindness_patterns_answer_seeking_only():
    """Part 04 §7 (part 07 §17): the screen blocks the clip and its
    answer, never missions, people or places the agent may look up.

    Fails without the fix: the old tuple carried ``apollo``, ``alsj``,
    astronaut names and ``lunar surface journal``.
    """
    from src import config

    lowered = [str(p).lower() for p in config.BLINDNESS_PATTERNS]
    for dropped in ("apollo", "alsj", "armstrong", "aldrin", "conrad",
                    "bean", "shepard", "mitchell",
                    "lunar surface journal"):
        assert dropped not in lowered, dropped
    assert "a16salute" in lowered
    assert "moon landing hoax" in lowered


def test_load_config_covers_table():
    from src import config

    table = config.load_config()
    assert table["SPARK_MODEL"] == config.SPARK_MODEL
    assert table["HARD_CAP_COST_USD"] == pytest.approx(2.00)
    assert table["CONTRACT_VERSION"] == 2

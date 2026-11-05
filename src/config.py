# generated from brief/04 · part 04 owns this file
"""All limits, prices, model IDs and paths (part 04 §2-3).

The single source of truth: nothing is hard-coded elsewhere. Every
other part reads its numbers from here (importing this module, never
copying a value). :func:`load_config` returns the whole table as a
plain dict for drivers that want one snapshot.
"""

from __future__ import annotations

__all__ = [
    "API_BASE_URL",
    "API_MAX_ATTEMPTS",
    "API_TIMEOUT_S",
    "ARTIFACTS_DIR_NAME",
    "BLINDNESS_PATTERNS",
    "BLIND_MAX_OUTPUT_TOKENS",
    "BLIND_REASONING_EFFORT",
    "CAMERA_STILL_PX_THRESHOLD",
    "CLOCK_BAND_HZ",
    "CONTRACT_VERSION",
    "GAIT_MEDIAN_WINDOW_S",
    "HARD_CAP_COST_USD",
    "HARD_CAP_WALL_S",
    "IDENTITY_SWAP_IOU",
    "INPUT_DIR_NAME",
    "LOGS_DIR_NAME",
    "MAX_DRY_RUNS_PER_RUN",
    "MAX_MASK_CHECKS",
    "MAX_OUTPUT_TOKENS",
    "MAX_SAM_FRAMES",
    "MAX_SEARCHES",
    "MAX_TURNS",
    "PRICE_SAM_PER_1000_FRAMES",
    "PRICE_SEARCH_PER_CALL",
    "PRICE_SPARK_CACHED_PER_1M",
    "PRICE_SPARK_INPUT_PER_1M",
    "PRICE_SPARK_OUTPUT_PER_1M",
    "PRICE_SPARK_STANDARD_CACHED_PER_1M",
    "PRICE_SPARK_STANDARD_INPUT_PER_1M",
    "PRICE_SPARK_STANDARD_OUTPUT_PER_1M",
    "PRICE_TABLE_VERSION",
    "RESIDUAL_TREND_THRESHOLD",
    "RESULT_FILENAME",
    "RETRY_AFTER_CAP_S",
    "RETRY_BACKOFF_MULT",
    "RETRY_BASE_DELAY_S",
    "RETRY_MAX_ATTEMPTS",
    "RUNS_DIR_NAME",
    "SAME_OBJECT_OVERLAP_FRAC",
    "SAM_MODEL",
    "SAM_MIN_BILLED_FRAMES",
    "SANDBOX_EXEC_TIMEOUT_S",
    "SANDBOX_MEMORY_MB",
    "SPARK_MODEL",
    "SPARK_REASONING_EFFORT",
    "SPARK_STANDARD_MODEL",
    "SUMMARY_FILENAME",
    "WARN_RATIO",
    "WORKSPACE_DIR_NAME",
    "load_config",
]

#: Meta Model API base (part 04 §2). The only code that talks HTTP is
#: :mod:`src.clients`.
API_BASE_URL = "https://api.meta.ai/v1"

#: Model IDs (part 04 §2). The agent and the sub-calls use the
#: contributor tier.
SPARK_MODEL = "muse-spark-1.3-contributor"
SPARK_STANDARD_MODEL = "muse-spark-1.3"
SAM_MODEL = "sam-3.1"

#: The agent's output limit (part 06 §3: reasoning counts toward it).
MAX_OUTPUT_TOKENS = 32768
#: Blind checks and the classifier are strict-JSON calls. Thinking
#: counts toward the output limit (part 06 §3), and 4096 cut replies
#: at high effort — so the blind limit is 16384 (addendum
#: 2026-11-01). The agent's own limit stays at 32768.
BLIND_MAX_OUTPUT_TOKENS = 16384

#: Reasoning effort for agent turns (addendum 2026-11-01): the
#: strongest reasoning in every Spark call that judges; a probe found
#: that a call without ``reasoning`` runs at ``high`` and that
#: ``{"effort": "max"}`` is accepted and echoed.
SPARK_REASONING_EFFORT = "max"
#: Reasoning effort for blind calls — the mask check, the line look,
#: the line match and the search classifier (addendum 2026-11-01).
BLIND_REASONING_EFFORT = "high"

#: Price table, per 1M tokens unless noted (skills/meta-api.md).
PRICE_SPARK_INPUT_PER_1M = 0.10
PRICE_SPARK_CACHED_PER_1M = 0.002
PRICE_SPARK_OUTPUT_PER_1M = 0.20
PRICE_SPARK_STANDARD_INPUT_PER_1M = 1.25
PRICE_SPARK_STANDARD_CACHED_PER_1M = 0.15
PRICE_SPARK_STANDARD_OUTPUT_PER_1M = 4.25
#: Web search, per call ($2.50 per 1000 calls).
PRICE_SEARCH_PER_CALL = 0.0025
#: SAM 3.1 video, per 1000 frames, minimum billed per call below.
PRICE_SAM_PER_1000_FRAMES = 0.20
SAM_MIN_BILLED_FRAMES = 50
#: Version stamp for the operator log, so old runs stay interpretable.
PRICE_TABLE_VERSION = 1

#: Hard acceptance ceilings (part 03): $2, two hundred forty turns
#: and three hundred sixty minutes per run (owner addendum 2026-11-01,
#: from four runs at max effort: the agent uses more turns and more
#: time per run, and speed is secondary; the dollar cap stays at $2;
#: owner addendum 2026-11-02, from four runs sharing one machine
#: and its segmenter: part 11 §50 adds a blind line check per
#: reference, which takes more time; owner addendum 2026-11-03,
#: from four runs at once on a third clip: a shared machine takes
#: about twice as long per turn, and a run alone reaches the turn
#: cap before the wall cap, so both limits rise; owner addendum
#: 2026-11-03, from the full suite after the 220-turn change: 240
#: turns, a multiple of 2, 3 and 5, so one third, one half and 80 %
#: of the turn budget are whole turns; owner addendum 2026-11-04,
#: from street-jump run 80: a run alone makes its first dry run at
#: turn 89 after 150 minutes, and the loop submits by itself at 80 %
#: of the wall cap with fixable errors left, so the wall cap rises
#: to three hundred sixty minutes while turns stay at 240; owner
#: addendum 2026-11-04, from street-jump run 81: with three hundred
#: sixty minutes a run again dry-runs near turn 96 after about one
#: hundred fifty minutes with fixable errors left — turns average
#: ninety seconds, so the wall cap rises to four hundred eighty
#: minutes while turns stay at 240).
HARD_CAP_COST_USD = 2.00
HARD_CAP_WALL_S = 480 * 60
#: Soft warn ratio: at 80% of any single budget the loop injects the
#: finish notice and closes the expensive tools of that budget.
WARN_RATIO = 0.80

#: Run caps (owner review 2026-10-27; owner addendum 2026-11-01
#: raises turns to one hundred fifty so a run can finish its checks
#: after dry runs at max effort; owner addendum 2026-11-01 from four
#: runs with one hundred fifty turns raises mask checks to eight — a
#: blind check is one short Spark call, and a Moon run spent its four
#: on the backpack and on masks it replaced; owner addendum
#: 2026-11-03 raises turns to two hundred twenty — a run alone
#: reaches the old cap before the wall cap; owner addendum
#: 2026-11-03, from the full suite after the 220-turn change,
#: raises turns to two hundred forty, a multiple of 2, 3 and 5,
#: since part 06 closes exploration when the turn budget reaches
#: one third and neither 220 / 3 nor 225 / 2 is a whole turn;
#: owner addendum 2026-11-03, from a street-jump run, raises mask
#: checks to twenty — eight for check_mask plus twelve for the most
#: check_line can use (six calls at two debits each), so line checks
#: cannot starve mask checks; everything else stays).
MAX_TURNS = 48 * 5
MAX_SAM_FRAMES = 1500
MAX_SEARCHES = 6
MAX_MASK_CHECKS = 2 * 10
#: Dry-run submits per run (part 07 §11).
MAX_DRY_RUNS_PER_RUN = 5

#: Transport retry for the loop ledger (part 14): base 2 s, doubling
#: with jitter, max 3 attempts (deaths 1-2 sleep and retry).
RETRY_BASE_DELAY_S = 2.0
RETRY_BACKOFF_MULT = 2.0
RETRY_MAX_ATTEMPTS = 3
#: Live API calls (skills/meta-api.md): 4 attempts in all, backoff
#: ``2**attempt + U(0,1)`` s, a numeric Retry-After wins, any wait
#: capped at 60 s, 300 s per read.
API_MAX_ATTEMPTS = 4
API_TIMEOUT_S = 300.0
RETRY_AFTER_CAP_S = 60.0

#: Sandbox caps for agent code (part 07 §6).
SANDBOX_EXEC_TIMEOUT_S = 120.0
SANDBOX_MEMORY_MB = 2048.0

#: Clip-identifying forms for the blindness filter (part 07 §17,
#: part 04 §7). Answer-seeking only: forms that name the clip or its
#: answer. Names, missions and places the agent may legitimately look
#: up (missions, astronauts, journals) are deliberately NOT here. No
#: entry may appear in the agent's fixed prompt or the generated tool
#: descriptions (the leak audit fails the suite otherwise).
BLINDNESS_PATTERNS = (
    "a16salute",
    "moon landing hoax",
)

#: Helper constants (parts 08/09): the values the rules and helpers
#: fall back to when this module is unreachable.
GAIT_MEDIAN_WINDOW_S = 1.0
CLOCK_BAND_HZ = (1.0, 4.0)
SAME_OBJECT_OVERLAP_FRAC = 0.5
RESIDUAL_TREND_THRESHOLD = 0.3
CAMERA_STILL_PX_THRESHOLD = 2.0
IDENTITY_SWAP_IOU = 0.4

#: Contract version (part 12). Must equal
#: :data:`src.contract.CONTRACT_VERSION`.
CONTRACT_VERSION = 2

#: Run layout names (part 04 §4).
RUNS_DIR_NAME = "runs"
INPUT_DIR_NAME = "input"
WORKSPACE_DIR_NAME = "workspace"
ARTIFACTS_DIR_NAME = "artifacts"
LOGS_DIR_NAME = "logs"
RESULT_FILENAME = "result.json"
SUMMARY_FILENAME = "summary.json"


def load_config() -> dict:
    """The whole config table as a plain dict (one snapshot)."""
    names = [name for name in __all__ if name != "load_config"]
    return {name: globals()[name] for name in names}

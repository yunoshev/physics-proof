# 14 — Cost, Runtime and Failures

**Owns:** `src/accounting/` (the run ledger) and the retry/termination policies parts 06/07 call into. Prices and API behaviour are in `skills/meta-api.md`; this part says how they are counted and what happens at the limits. **Small-code principle:** one ledger object, one price table in config, three error classes. Nothing else.

## 1. Prices (config, `src/config.py` — the only place they live)

| Item | Price |
|---|---|
| Spark `muse-spark-1.3-contributor`, input | $0.10 / 1M tokens |
| Spark `muse-spark-1.3-contributor`, cached input | $0.002 / 1M tokens |
| Spark `muse-spark-1.3-contributor`, output (incl. reasoning) | $0.20 / 1M tokens |
| Spark `muse-spark-1.3` (standard tier, if ever used) | $1.25 / $0.15 cached / $4.25 per 1M |
| Web search | $2.50 / 1000 calls ($0.0025 each) |
| SAM 3.1 video | $0.20 / 1000 frames, **minimum 50 billed per call** |

A price change is a config edit, not a code change; the ledger stamps the price-table version into the run log so old runs stay interpretable.

## 2. The ledger

One ledger per run, owned by the loop (part 06), written by every model/tool call through this module:

- **Counting rule: cost is counted from the usage in the terminal event** (`response.completed`) — input, cached input, output, and reasoning tokens are only reported there (skill: meta-api). Streaming deltas are never used for accounting (they carry no usage).
- **The usage fields are subsets, not addends: `cached` is part of `input`, and `reasoning` is part of `output`.** A call's token cost is therefore exactly `(input − cached) × input-price + cached × cached-price + output × output-price` (per 1M). Reasoning tokens are recorded for diagnostics and are already paid for inside `output` — adding them again double-counts, and the ledger code must not. (This is the pricing error this rule exists to prevent; `tests/accounting/` covers it.)
- A call that ends `response.incomplete` still consumed tokens: if its terminal event carries usage, it's counted by the same formula; the loop's handling (discard + re-prompt) is part 06's business.
- A call that ends `response.failed` or dies in transport has no trustworthy usage: the ledger records `cost_unknown: true` with the request's input-token estimate, and the run's total is marked *estimated*. Estimates never silently pass as exact in `summary.json`.
- SAM frames are debited as `max(50, frames_requested)` at call time (part 07 §3); web searches at call time; both are reconciled in the final summary from the ledger, not re-derived.
- Ledger entries: `{turn, kind, model, usage, cost_usd, artifact}` appended to `logs/` (operator-only) and aggregated into `summary.json` (part 12 §9): total + breakdown (spark input/cached/output, SAM, search), turns, SAM frames billed, searches, mask checks, wall time, model, budget outcome.

## 3. Caps and enforcement (with part 06)

- **Hard caps (acceptance, part 03):** $2.00 and 30 min per run. The loop checks the ledger before every model/tool call; a call that would start after a hard cap is never made.
- **Soft warning:** at 80% of any single budget (dollars, wall time, turns, SAM frames, searches, mask checks — defaults in config), part 06's near-limit behaviour triggers (finish-and-submit notice; expensive tool classes closed).
- **At a hard cap:** the loop stops and part 11 synthesises *undetermined: budget* with a valid result file. Budget-stopped runs count as completed runs (§5).
- The typical target ($0.10–0.20, 7–11 min) is a **design target, not a cap**: the dashboard for it is the iteration log (part 15), not a runtime abort. Only the hard caps abort.

## 4. Retries — three error classes, never confused

| Class | Recognition | Policy |
|---|---|---|
| **Network/transport** | No terminal event; connection error, 5xx, stream dies mid-way | Retry with exponential backoff (config: base 2 s, ×2, jitter, **max 3 attempts**). Then the call fails as a tool error to the agent (or aborts the run if it was the agent call itself, §5). |
| **Incomplete** | Terminal `response.incomplete` (e.g. output limit; reasoning counts toward it) | **Not a network failure — never retried as one.** Part 06 §3: discard partial turn, re-prompt once to continue concisely/submit; counts as a turn. |
| **`response.failed`** | Terminal `response.failed` with API error payload | No blind retry of an identical request. Returned as a structured tool/agent error; if the agent call itself fails twice consecutively, the run degrades per §5. |

Tool calls (SAM, search, mask-check) follow the same classes; a SAM call's retries do not double-bill the ledger — only calls that reach a terminal/billing event are debited, and the ledger records attempts separately so double-billing would be visible.

## 5. Failure degradation (every path ends in a valid file)

- Tool failure → structured error to the agent; the agent adapts (part 06 §6).
- Repeated agent-call failure, catastrophic tool bug, unreadable video (part 05 §6), exhausted submit attempts, hard-cap hit → **synthesised undetermined result** via part 11 §4, with the reason recorded (`budget`, `video unreadable`, last validator error codes, or the exception class). A traceback is logged for the operator; the result file contains the plain-words reason only.
- A run that produces no `result.json` at all is a **system bug**, never an acceptable outcome — part 15's harness asserts `result.json` exists and validates for every run, including killed ones.
- Wall-clock guard: one watchdog in the loop checks elapsed time per turn (a single hung tool/SAM call must not eat the 30 min silently); per-call timeouts are config values, and a timeout is a tool error, not a hang.

## 6. Logging (operator side)

`logs/` holds: the full API event log (prompts hashed, tool traffic, terminal usages — the raw material of part 03's prompt-leak test), the ledger, and the run's error history. Logs never enter the workspace, the sandbox, or the agent's context (parts 04–07). Retention is the maintainer's choice; nothing in a later run may read an earlier run's logs.

## 7. Owner addendum (2026-10-28, from the eighth live run): no local paths in run outputs

`summary.json` carried `"result_path": "/Users/<name>/Projects/…/result.json"`. Part 13 inlines `summary.json` into the page, so a published page would carry the operator's home path. Every path written into `summary.json` (and every other file a page may inline) is relative to the run directory: `"result_path": "result.json"`. Test: after a stubbed run, `summary.json` contains no absolute path and no string starting with `/`.

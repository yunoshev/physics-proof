# M1 fix 2 report — retry transient Spark/SAM stream failures

## What was built
- [physics_proof/meta_client.py](/Users/ayunoshev/Projects/Personal/physics-proof-wt/m1fix2/physics_proof/meta_client.py): `_post_responses_stream` now retries transient failures — HTTP 429/500/502/503/504, cut streams, connection resets, timeouts (`httpx.TransportError`, which covers timeouts) — up to 3 retries (4 attempts). New `TruncatedStreamError(StreamError)` marks only the cut-stream case retryable; malformed/empty streams and 4xx other than 429 raise at once (402 billing unchanged, exactly one request). Backoff is 1 s, 2 s, 4 s plus uniform jitter, capped at 60 s; `Retry-After` is honoured exactly. Each failed attempt that retries logs one zero-cost ledger line (`spark` with zero tokens / `sam` with zero frames) with the reason in the note. `respond`/`sam_video` take `budget_check`, run before every attempt.
- [physics_proof/config.py](/Users/ayunoshev/Projects/Personal/physics-proof-wt/m1fix2/physics_proof/config.py): `DEFAULT_MAX_ATTEMPTS` 3 → 4 (first try + 3 retries).
- [physics_proof/agent.py](/Users/ayunoshev/Projects/Personal/physics-proof-wt/m1fix2/physics_proof/agent.py): `GuardClient.respond`/`sam_video` pass `budget_check=self._budget.check`, so the dollar cap is enforced before each retry, not just the first attempt.
- [tests/test_meta_client.py](/Users/ayunoshev/Projects/Personal/physics-proof-wt/m1fix2/tests/test_meta_client.py): `test_500s_raise_after_3_retries` (was 3 attempts); new `test_cut_stream_once_then_complete_logs_one_retry`, `test_cut_stream_four_times_raises_after_3_retries`, `test_400_never_retried`, `test_retry_after_wait_is_honoured` (patches sleep, asserts ≥ 2 s), `test_budget_check_runs_before_each_attempt`, `test_sam_stream_cut_once_then_complete` (SAM shares the retry path).

## Probe coverage
- Cut once then complete → one result, one `$0` retry line noting the truncation.
- Cut four times → `StreamError: truncated SSE stream` after 4 requests / 3 retry lines.
- 400 → `ApiError`, exactly 1 request, no ledger lines. 429 + `Retry-After: 2` → slept 2.0 s.

## Test output
- `uv run pytest tests/test_meta_client.py -q`: 16 passed.
- Full offline `uv run pytest -q`: 197 passed, 23 skipped (api/slow).

## Not done / open questions
- Retryable 5xx narrowed from "any 5xx" to 500/502/503/504 per the task (501/505+ now fail fast); saying so in case the maintainer wants all 5xx.
- A cut stream carries no usage, so retry lines are all-zero as the task expects; if a future failure mode yields partial usage, `_log_retry` takes only the reason today — counts would need adding.

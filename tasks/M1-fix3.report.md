# Task M1 fix 3 report — `response.incomplete` is not a truncated stream

## What was built
- [physics_proof/meta_client.py](physics_proof/meta_client.py): `parse_response_body` now treats every terminal event correctly — `response.completed` as before; `response.incomplete` is returned (not raised) with the response object, readable via new `incomplete_reason_of()`; `response.failed` and bare `error` events raise new `ResponseFailedError(ApiError, StreamError)` carrying the server's message and code. Only a stream with no terminal event raises `TruncatedStreamError`, so the fix-2 retry still fires only for real cuts. `SparkResponse` gained `incomplete_reason`; `respond` fills it and ledgers usage as usual (incomplete tokens are billed). New `IncompleteResponseError` + `raise_if_incomplete()` helper for callers that need a complete answer.
- [physics_proof/config.py](physics_proof/config.py): `DEFAULT_AGENT_MAX_OUTPUT_TOKENS = 32768` plus `Settings.agent_max_output_tokens`, env `META_AGENT_MAX_OUTPUT_TOKENS`. 32768 is safely under the published model maxima (catalogues of the 1M-context model report 131072 and 943718 output tokens; promptfoo defaults `max_tokens` to 131072), and double (65536) still fits. Sub-callers keep the 4096 default.
- [physics_proof/agent.py](physics_proof/agent.py): `run_analysis(..., agent_max_output_tokens=None)` sends the large limit on every agent turn. A turn cut by `max_output_tokens` retries once with double the limit; if still cut, the run continues with a short reply ("Your last answer was cut off at N output tokens … do the work in smaller steps") instead of ending. Other incomplete reasons end the run with a clear error.
- [physics_proof/search_tool.py](physics_proof/search_tool.py), [physics_proof/mask_check.py](physics_proof/mask_check.py): classifier, web search and mask check keep small limits and call `raise_if_incomplete`, so a cut-off turn becomes a clear refused/cut reason (fail-closed) or tool error. Classifier keeps the billed cost on the error path.
- [tests/test_m1_fix3.py](tests/test_m1_fix3.py): 13 tests covering every probe.

## Probe coverage
- Incomplete body → returned with reason `max_output_tokens`, usage (4096 out / 3000 reasoning), one billed ledger line.
- `response.failed` body → `ResponseFailedError` with the server message and code, exactly 1 request (no retry); bare `error` event likewise.
- Body with no terminal event → `TruncatedStreamError` (fix-2 retry path unchanged; its tests still pass).
- Agent fake-client runs: cut → one retry at 65536 then continues; cut twice → short "cut off / smaller steps" reply and `undetermined: budget`, not an error; limit configurable per-call and via env; `content_filter` cut → clear error, no retry.

## Test output
- `uv run pytest tests/test_m1_fix3.py -q`: 13 passed.
- Full offline `uv run pytest -q`: 210 passed, 23 skipped (api/slow opt-ins).

## Not done / open questions
- Nothing outstanding. If Meta's docs later pin a different output maximum, only `DEFAULT_AGENT_MAX_OUTPUT_TOKENS` needs changing; the doubled retry (65536) stays under every published maximum.

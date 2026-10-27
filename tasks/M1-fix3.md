# Task M1 fix 3 — `response.incomplete` is not a truncated stream

Two real runs (`runs/2026-10-27-moona-r2`, `runs/2026-10-27-wallrun-r2`) ended with
`truncated SSE stream: no response.completed event` exactly when the agent was writing its long final script with
`reasoning.effort = "high"`; resuming failed again on the next call. Root cause (verified by the maintainer with a raw
request, `max_output_tokens: 60`, effort high): the stream ends with a **`response.incomplete`** event carrying
`"incomplete_details": {"reason": "max_output_tokens"}` — not with `response.completed`. `parse_response_body` ignores
that event and reports a truncated stream. The client default is `DEFAULT_MAX_OUTPUT_TOKENS = 4096`, and reasoning tokens
count toward it.

## Do
1. `parse_response_body` handles every terminal event: `response.completed` (as now); `response.incomplete` → return the
   response with an `incomplete` reason (usage is recorded in the ledger as usual — those tokens are billed);
   `response.failed` and `error` events → raise with the server's message and code. "Truncated" only when the stream
   really ends without any terminal event (this case keeps the retry from fix 2).
2. Agent turns use a much larger `max_output_tokens` (find the model's maximum in Meta's docs or by a cheap probe; at
   least 32 000), configurable. When a turn still comes back incomplete for `max_output_tokens`: retry once with double
   the limit; if it is still incomplete, give Spark a short reply ("your last answer was cut off at N tokens; do the
   work in smaller steps") instead of ending the run.
3. Other callers (search, classifier, mask check) keep small limits but must surface `incomplete` as a clear error.

## Probes (offline, recorded SSE bodies)
A body ending in `response.incomplete` → returned with reason `max_output_tokens` and usage; a `response.failed` body →
error with the server message; a body with no terminal event → truncated (retried by fix 2); the agent retries once with
a doubled limit and then replies to Spark (fake client).

## Done when
Offline tests pass; `tasks/M1-fix3.report.md` written.

# Task M1 fix 2 — retry transient Spark stream failures

A real agent run (`runs/2026-10-27-moona-r2`) died at turn 23 with
`error: spark call failed: truncated SSE stream: no response.completed event`. Nothing was wrong with the request; the
stream was cut. One flaky call should not end a 10-minute run.

## Do
In `MetaClient.respond` (and the SAM stream, if it has the same failure mode): retry transient failures — a stream that
ends without its completion event, connection resets, timeouts, HTTP 429/500/502/503/504 — up to 3 times with
exponential backoff (1 s, 2 s, 4 s, plus jitter), honouring `Retry-After`. Never retry 4xx other than 429. Log every
retry to the ledger as a zero-cost line with the reason (a cut stream has no usage; if a partial usage arrived, record
it once). The dollar budget check still runs before each attempt.

## Probes (offline, fake transport)
A stream cut once then complete → one result, one retry logged; cut four times → the original error after 3 retries;
a 400 → no retry; a 429 with `Retry-After: 2` → waits ≥ 2 s (patch the sleep).

## Done when
Offline tests pass; `tasks/M1-fix2.report.md` written.

# M1 fix 1 report — price cached input tokens

## What was built
- [config/prices.json](/Users/ayunoshev/Projects/Personal/physics-proof-wt/m1fix/config/prices.json): added `cached_input_per_1m` to both models — contributor `0.002`, standard `0.15` — plus a `comment` field noting the source.
- [physics_proof/ledger.py](/Users/ayunoshev/Projects/Personal/physics-proof-wt/m1fix/physics_proof/ledger.py): `compute_cost_usd` now bills `(input − cached) × input_per_1m + cached × cached_input_per_1m + output × output_per_1m`; a model entry without `cached_input_per_1m` falls back to the input price. Module docstring fixed (previously claimed no discount).
- [tests/test_ledger.py](/Users/ayunoshev/Projects/Personal/physics-proof-wt/m1fix/tests/test_ledger.py): updated table/cases to the discounted formula; added the task's $0.0138 probe, a standard-tier cached case, a no-cached-price fallback test, and repo-table assertions for both cached prices.

## Standard-tier cached price
No direct access to Meta's pricing docs from here; used public sources that cite them: standard cached input **$0.15/1M** is reported consistently (promptfoo Meta provider docs state their table follows Meta's published pricing; musecodes.io, datacamp.com, techpilot.ai citing dev.meta.ai, truefoundry.com all agree; contributor $0.002 confirmed by the same sources and the task). Recorded in the JSON `comment` field per the task.

## Probe coverage
- 1M input / 900k cached / 10k output on contributor = $0.0138: covered by a parametrized case (`0.1 × 0.1 + 0.9 × 0.002 + 0.01 × 0.2`).
- Fallback without a cached price: `test_missing_cached_price_falls_back_to_input_price` (600 cached of 1000 input billed fully at input price).

## Test output
- `uv run pytest tests/test_ledger.py -q`: 14 passed.
- Full offline suite `uv run pytest -q`: 133 passed, 17 skipped (API-marked, need `-m api`).

## Not done / open questions
- Nothing outstanding. If Meta's pricing page later shows a different standard cached rate, only the JSON value needs changing (fallback keeps old tables working).

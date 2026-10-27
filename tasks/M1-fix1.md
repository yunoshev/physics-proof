# Task M1 fix 1 — price cached input tokens

`physics_proof/ledger.py` prices cached input tokens at the full input price (its docstring says so). Meta Model API
bills them much lower: for `muse-spark-1.3-contributor` cached input is **$0.002 per 1M** (vs $0.10 for new input).
Checked against the invoice on 2026-10-27: list prices with the cached discount reproduce the billed amount; full price
overstates it about 5×.

## Do
1. Add `cached_input_per_1m` to each model in `config/prices.json`: contributor `0.002`. For `muse-spark-1.3`
   (standard) look the cached price up in Meta's pricing documentation; if you cannot find it, keep the full input price
   for that model and say so in the report and in a comment field in the JSON.
2. Ledger cost = (input − cached) × input price + cached × cached price + output × output price (+ SAM, searches as
   before). Fix the docstring.
3. Tests: a ledger line with 1 000 000 input of which 900 000 cached and 10 000 output on the contributor tier costs
   0.1 × 0.1 + 0.9 × 0.002 + 0.01 × 0.2 = $0.0138; a model without a cached price falls back to the input price.

## Done when
Offline tests pass; `tasks/M1-fix1.report.md` written.

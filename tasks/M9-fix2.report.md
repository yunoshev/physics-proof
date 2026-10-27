# M9 fix 2 report — `combine` tests the retime explanation against the clock

## Files changed
- [physics_proof/schema.py](/Users/ayunoshev/Projects/Personal/physics-proof/physics_proof/schema.py): new `_clock_numbers()` helper; `combine()` tests `none_fits` with a numeric timescale from the numbers (true rate `value × k` ± `err × k`): inside `[lo, hi]` within 2σ → `retimed`, outside → `impossible`, 2σ band reaching zero → `none_fits` as today; `timescale.verdict` kept as the agent's reading (fallback when numbers are missing); `schema_doc()` now says `expected_range` is the natural range of the clock rhythm in the same unit, sourced in `method`/notes.
- [tests/test_schema_m9.py](/Users/ayunoshev/Projects/Personal/physics-proof/tests/test_schema_m9.py): 4 new tests (impossible / retimed-overriding-a-`normal`-mark / too-large-error / sped-up `k < 1`).
- [tests/fixtures/analysis_ramp.json](/Users/ayunoshev/Projects/Personal/physics-proof/tests/fixtures/analysis_ramp.json): `overall` updated, see below.

## Probe coverage
- (k=2.3, 2.6±0.2, 2.5–4.5) → `impossible` (true 5.98±0.46, outside); text states k, true rate, range.
- (k=1.5, 2.2±0.2, 2.5–4.5) → `retimed` (true 3.30±0.30, natural); numbers override the verdict mark.
- (k=1.5, 2.2±2.0) → `none_fits` (band reaches zero); null timescale → `none_fits`.
- `fits:` / `undetermined` paths untouched; old verdict-only tests (`normal` → impossible, slow+consistent → retimed) still pass.
- Both fixtures validate. Ramp fixture label changed `impossible` → `retimed`: its numbers (3.2±0.3 × k=1.57 = 5.01±0.47 vs range 2.5–5.0) are consistent within 2σ, so the new rule says retimed even though the agent's `timescale.verdict` still reads `normal`. Timescale section left as-is per the task.

## Test output
- `uv run pytest -q`: 223 passed, 23 skipped (API-gated), 0 failed.

## Not done / open questions
- The ramp fixture is now self-tensioned (agent says `normal`, overall says `retimed`); maintainer may want fixture numbers that tell one story.
- "Too large" is defined as the 2σ band reaching zero (err/value ≥ 0.5); a moderate error straddling one range edge still decides by overlap.

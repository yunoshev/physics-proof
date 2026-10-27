# M8 fix 2 report — worlds come from the scene; a wall segment is a wall

## Built
- `config/prompts/agent_system.md`: new rule — before `decide`, write which
  worlds the scene rules out and the visible cue for each (moving
  hair/cloth/dust/plants/clouds/birds, people walking, buildings, traffic),
  then pass only the remaining worlds to `decide`. Names no clip, place,
  world, or expected answer.
- `physics_proof/schema.py`: `verdict.worlds_tested` (non-empty name list)
  and `verdict.worlds_ruled_out` (`{world, by}` list), both required when
  `verdict.state` is `none_fits`; the decide recomputation now uses exactly
  the `worlds_tested` subset of `worlds`. `schema_doc()` documents both
  fields and the `wall` (body on a vertical surface: normal force ~0, so
  vertical motion must follow g) vs `flight` (no contact) distinction.
- `physics_proof/agent.py`: `finish` recomputes `decide` with exactly
  `worlds_tested` (unknown names leave the table empty so the validator
  rejects with a path); `tools_doc` tells the agent to supply both fields.
- `config/analysis.schema.json`: both fields as optional properties (never
  in `required`, so old fits/undetermined analyses still parse).
- `scripts/make_m9_fixtures.py` + regenerated `tests/fixtures/`: ramp
  (none_fits) gains `worlds_tested`/`worlds_ruled_out`; its timescale is now
  5.10 ± 0.17 steps/s over 2.5–4.5 so overall stays `impossible`.
- Tests: 3 in `tests/test_schema_m9.py` (missing `worlds_tested`,
  missing `worlds_ruled_out`, unknown tested name — each names its path);
  1 in `tests/test_agent_m8.py` (`finish` with `worlds_tested: ["Earth"]`
  on 3.75 ± 0.72 → `none_fits`, k ≈ 1.62, `overall` impossible).

## Probe coverage
1. `finish` + r3 numbers → `none_fits`, k 1.617 ≈ 1.62, `overall`
   `impossible` (true rate ≈ 8.3 steps/s outside 2.5–4.5). Covered.
2. `none_fits` without `worlds_tested` → `/verdict/worlds_tested` issue
   (and likewise for `worlds_ruled_out`). Covered.
3. Blindness tests (`test_agent_prompt_has_no_answers`,
   `test_blind_prompt_and_clip_name`, `test_package_reads_no_eval_data`)
   pass; old tests pass. Covered.

## Test output
- `uv run pytest`: 227 passed, 23 skipped (api/sandbox/slow).

## Could not do / open questions
- `runs/2026-10-27-wallrun-r3` is not in this checkout, so the r3 numbers
  come from the task text; old run files under `runs/` were not edited.
- The ramp fixture script's `impossible` assert was already stale (fixture
  said `retimed` after the M9-fix2 clock logic); fixed by giving the
  fixture a clock that is genuinely off at the measured rate.
- SPEC §4 rule 9 already existed verbatim in the prompt via evidence
  rules; the new paragraph turns it into an action (write down, then pass
  only the rest). SPEC itself untouched per ground rules.

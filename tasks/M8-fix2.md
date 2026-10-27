# Task M8 fix 2 — worlds come from the scene; a wall segment is called a wall

SPEC §4 rule 9 (new) and rule 8. Look at the run `runs/2026-10-27-wallrun-r3` (`analysis.json`, `turns/`).

What happened: a person runs up a vertical wall in a city street (trees, buildings, other people walking). The agent
measured the climb at 3.75 ± 0.72 m/s² and the run-up step rate at 5.1 steps/s, and called `decide` with Earth and
Moon. The Moon was the nearest world, so `k` was computed against the Moon and `combine` answered "consistent with a
clip sped up by ×1.52" — a Moon-gravity explanation for a street on Earth. Against Earth alone the same numbers give
k = 1.62, a true step rate of ~8 steps/s, so "impossible". Also, the climb was logged with `kind: "flight"` although
the body was in contact with the wall the whole time, and the eval looks for a `wall` segment.

## Do
1. **Prompt** (`config/prompts/agent_system.md`): before `decide`, the agent writes which worlds the scene rules out and
   what in the frames shows it (the cues in SPEC §4 rule 9), and passes only the remaining worlds to `decide`. Do not
   name any clip, place or expected answer; keep the blindness test passing.
2. **Schema** (`schema.py`, `schema_doc()`): `verdict.worlds_tested` (list of names) and `verdict.worlds_ruled_out`
   (list of `{world, by}`), both required when `verdict.state` is `none_fits`; `finish` recomputes `decide` with exactly
   `worlds_tested`. Document when a segment is `kind: "wall"` (the body touches a vertical surface — normal force ~0,
   so friction cannot hold it up and the vertical motion must follow g) versus `kind: "flight"` (no contact at all).
3. Update the fixtures; the three real analyses under `runs/` may fail the new required fields — that is expected,
   `build` (M10) will handle old runs; do not edit run files.

## Probes (tests, offline)
- `finish` with `worlds_tested: ["Earth"]` on the r3 numbers (3.75 ± 0.72, clock 5.10 ± 0.17, range 2.5–4.5) →
  `none_fits`, k ≈ 1.62, `overall` = impossible.
- `none_fits` without `worlds_tested` → a schema issue with its path.
- Blindness test still passes; old tests pass.

## Done when
Offline tests pass; `tasks/M8-fix2.report.md` written.

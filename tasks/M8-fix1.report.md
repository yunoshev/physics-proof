# M8 fix 1 report — what the first three real runs showed

## Built
- `physics_proof/agent.py`: `finish` coerces harmless slips (`_coerce_analysis`:
  int `mask.object`, bool/list `duplicates_found`, list `accel`/`accel_err`,
  `[x]`/`[]` `scale.second`, int-like frames) and reports each in the reply;
  then computes and writes `flights[i].decide`, `verdict`, `overall`
  (`_fill_computed` from `blocks.decide`/`combine`) before validating, so only
  real data inconsistencies are rejected, all with paths at once.
- Same file: ask-once second-reference gate (`scale.second` or written reason
  in `scale.notes`; next `finish` passes), full `blocks` signatures+docstrings
  via `inspect` (`blocks_doc`), workspace layout + `pathlib` note in the prompt,
  relative file paths in every tool result (`sheets/…`, `sam/…npz`+sheet,
  `mask_checks/…`, `scripts/…`), `max_turns` 60, `effort="high"` for agent
  turns (param/CLI flag, logged in `summary.json`).
- `physics_proof/sandbox.py`: profile carves out workspace, `physics_proof/`
  package, `blocks.py` shim, venv/interpreter — never the repo root; runner
  preloads package+shim from explicit paths, repo root stays off `sys.path`.
- `physics_proof/__main__.py`: `--turns` default 60, new `--effort` (high).
- Tests: 6 new in `tests/test_agent_m8.py` (fill, coercions, ask-once gate,
  file names, signatures, effort/turns defaults); 5 new in
  `tests/test_sandbox.py` (profile carve-outs offline; list/read-denied +
  working `import blocks` for the Mac).

## Probe coverage
1. finish fills verdict: scripted run with measurements only (no decide, no
   computed keys, guessed overall) ends `ok`; saved file matches
   `blocks.decide`/`combine`. Covered.
2. Tool results name `sheets/turn02.png`, `sam/red_square.0-10.npz`/`.png`,
   `mask_checks/…`, `scripts/…`. Covered.
3. `blocks_doc` holds every public name with signature + docstring; prompt has
   layout and `finish computes`. Covered.
4. Simulated unlistable root: `import blocks` + `fit_parabola` work, `iterdir`
   fails. Offline profile test green; Mac sandbox tests await the maintainer.
5. First `finish` without `scale.second` asks (names `scale.notes`); next
   passes. Covered.
6. Slips coerce with `Coercions:` in the reply; validator sees the rest.
   Covered. Defaults 60/high asserted; summary logs `effort`.

## Test output
- `uv run pytest`: 191 passed, 23 skipped (api/sandbox/slow; sandbox-exec is
  denied in this shell). `test_e1.py` needed one docstring reword (its
  blindness scan forbids the literal `eval/` path in package code).

## Could not do / open questions
- Mac sandbox tests and the three real reruns are the maintainer's (this
  shell cannot apply Seatbelt profiles).
- SPEC M8/§7 still say 40 turns, low effort; task says 60/high — SPEC
  untouched per ground rules; maintainer to reconcile.
- `finish` still builds no page (M10/M11 own that).

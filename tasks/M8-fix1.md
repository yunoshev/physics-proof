# Task M8 fix 1 — what the first three real runs showed

The maintainer ran the agent on three clips (contributor tier, 40 turns, cap $1). All three reached `finish` and all
three ended "undetermined: budget" at turn 40 without an analysis, costing $0.05–0.09 each. Run directories are in
`runs/2026-10-27-*` (read the turn files: `turns/turnNN.json`, fields `tool_call`, `arguments`, `result_text`).
Symptoms, in order of cost:

1. **`finish` demands texts the agent cannot know.** Every run burned its last 4–9 turns on
   `/overall/text: text does not match combine for this verdict` (and `/overall/label …`). The agent has no access to
   `combine` and tried to guess its sentence. SPEC Principle 6 says the verdict is computed by a verified block, never
   written by hand.
2. **Tool results do not say where their files are.** After `sam(...)` the agent guessed `masks.npz`, `sam.npz`, …;
   in one run it gave up on SAM masks and thresholded colours by hand instead. `os` and `glob` are (rightly) banned,
   so it could not list the workspace either.
3. **~10 turns per run on `help(blocks.x)`**, `print(dir(blocks))`, `inspect` — the blocks documentation in the prompt
   is not enough to call them.
4. **Blindness hole in the sandbox.** In one run the agent printed `blocks.__file__` and listed
   `Path(blocks.__file__).parent.iterdir()` — the repo root with `SPEC.md`, `COSTS.md`, `eval/`, `examples/`, `runs/`,
   `tasks/`. It could have read `eval/expected.json` or the spec. The analysis code must be able to read only its
   workspace and what `import blocks` needs.
5. Two runs had no second reference (`scale.second: null`) and nothing asked for one (SPEC §4 rule 2).
6. Small: `duplicates_found` written as a list, `mask.object` as an int, `accel` as a list — each cost a finish round.

## Do
- `finish` computes and **writes** `flights[i].decide`, `verdict` (from the agent's `g`, `g_err`, `worlds`) and
  `overall` (`combine`) itself; the agent supplies only measurements and its own prose (`page_texts`, notes). Reject
  only real inconsistencies in the agent's data. Coerce harmless type slips (an int id where a string is expected) and
  say so in the reply; reject the rest with paths, all at once.
- Every tool result names the files it produced, relative to the workspace (`sam/…npz`, its sheet, mask-check sheets,
  frame sheets, images from `python`). The system prompt describes the workspace layout and says to use `pathlib` to
  list it.
- The prompt carries the full signature and docstring of every public `blocks` function (generated, not hand-copied).
- Close the hole: the sandbox may read the workspace, the `physics_proof` package, the `blocks.py` shim, the venv and
  the interpreter — not the rest of the repo. Add offline tests on the generated profile, and add sandbox-layer tests
  (they run on the maintainer's Mac) that from inside `python`: listing `Path(blocks.__file__).parent` fails, reading
  `SPEC.md` and `eval/expected.json` fails, `import blocks` still works.
- On the first `finish` without `scale.second`, reply once asking for a second reference or a written reason in
  `scale.notes`; accept on the next call.
- Default `max_turns` 60. Use `reasoning.effort = "high"` for the agent's turns (configurable); log it in the summary.

## Done when
Offline tests pass; the fake-Spark full run passes with `finish` filling the verdict; `tasks/M8-fix1.report.md`
written. The maintainer reruns the sandbox tests on the Mac and the three real runs.

# 06 — Spark Agent Loop

**Owns:** `src/loop/`. Spark is the orchestrator; this part is the frame it thinks inside. **Lesson sources:** "The agent loop" — exact-sentence checks looped the agent to death; thinking tokens count toward output limits; old images bloat context and break caching.

## 1. Loop shape

A turn = one Spark call followed by zero or more tool calls, executed by our code, whose results are appended for the next turn. The loop runs until one of:

1. **Submit accepted** — the agent calls `submit` (part 07) and part 11's checks pass.
2. **Budget exhaustion** — §5.
3. **Unrecoverable error** — §6.

Spark decides the plan turn by turn: view frames, segment, measure, check, code, submit — in any order, revisiting earlier steps. The loop must not hint at a preferred sequence beyond the tool descriptions and the measuring rules (part 08). Prompts, tool descriptions, and helper docs are assembled from a **stable prefix** (system prompt + tool schemas + rules) that never changes mid-run, so API prompt caching works.

## 2. Who computes the verdict — not the agent

**Enforced in code (lesson: an exact-sentence check once looped the agent until it ran out of turns).** The agent submits *structured evidence* (measurements, segments, references, world exclusions, clock readings, provenance pointers). **Our code computes the verdict and the overall display sentence** deterministically from that evidence (part 11, applying part 02). Therefore:

- No check may ever compare model-produced prose to a required string.
- Validation feedback to the agent is a list of **structured error codes with the offending field names** (e.g. `SECOND_REFERENCE_SAME_OBJECT: references[1] overlaps references[0] by 0.83`), never "rephrase this".
- Validation rejections are capped (default 3 submit attempts); after that the run ends as *undetermined* with the last error list recorded — the loop can never be spent entirely on arguing with the checker.

## 3. Output limits and incomplete replies (lesson)

With high reasoning, Spark's thinking counts toward the output token limit: at 4096 tokens, replies were cut mid-stream. Therefore:

- Every agent call requests **`max_output_tokens = 32768`** (a named config value, part 04).
- A response ending with status `incomplete` (reason: output limit) is a **recognised outcome, not a stream error**: the partial turn is discarded, and the model is re-prompted once with its own last tool state plus an instruction to continue concisely or submit with what it has. Repeated incompletes count against the turn budget like any turn.
- Genuine network/transport failures are a different class: retried with backoff (part 14's policy), never mistaken for incompleteness, and vice versa.

## 4. Context management (lesson)

Images are the context killer. The loop keeps **only the last two tool results' images** in the conversation. Older images are replaced in-place by a text placeholder that **names the artifact file** (e.g. `[image omitted; see artifacts/turn_012_contact_sheet.jpg]`), so the agent can re-request the file if it actually needs it — files persist on disk even when they leave the context. Non-image tool results are kept as text, subject to a per-result size cap with truncation that names the full artifact on disk. Tool results must always name the files they produced (part 07 enforces this at the tool layer); the loop relies on it here.

## 5. Budgets — enforced by the loop, in code (lesson: budgets live in the frame, not the prompt)

The loop maintains a **budget ledger** counting, at minimum: turns, wall-clock seconds, Spark tokens (input/cached/output separately), SAM billed frames, web searches, blind mask checks, sandboxed executions, and estimated dollars (part 14 prices). Limits are config values; defaults sized for the part-03 envelope (hard caps $2.00 and 30 min; the ledger warns far earlier — see part 14).

- **Near a limit** (default: 80% of any single budget): the loop injects one system notice — "budget nearly exhausted: finish and submit with what you have" — and refuses to start new *expensive* tool classes (config-defined; e.g. no new SAM calls), steering to submission.
- **At a limit:** the loop stops calling Spark and **synthesises a valid `undetermined: budget` result file itself** (part 11's synthesis path), preserving whatever evidence artifacts exist. A budget-stopped run is a completed run.
- The agent is never asked to watch the budget itself; any budget numbers in prompts are informational copies of ledger state.

## 6. Errors and isolation

- A tool call that fails returns a structured error to the agent (it may adapt); a tool that fails *catastrophically* (our bug) aborts the run into the synthesis path with the error logged — never a raw traceback into the conversation, never a hung loop.
- The loop passes the agent **no state from any other run**: fresh conversation, fresh workspace (part 04 §4). The only carry-over in the whole system is the human-promoted helper library (part 10).
- Every turn (prompt hash, tool calls, results, ledger snapshot) is appended to `logs/` (operator-only), sufficient to replay *why* a run did what it did, and to feed part 03's prompt-leak test.

## 7. Model-call hygiene

- Agent, blind-check, and classifier calls are **separate conversations**; blind calls receive no run context by construction (part 07), not by instruction.
- Temperature/seed: whatever the API supports is pinned in config for maximal reproducibility; variance is absorbed by part 03's 2-of-3 protocol, not hidden.

## Owner addendum (2026-10-28, from the second live run)

- **A tool call with bad arguments is the agent's mistake, not our crash.** Missing or extra arguments, or arguments of the wrong type, get a structured error result (`bad_arguments`, naming the expected parameters from the tool schema) and the loop goes on. Seen: `run_python` called with `{}` raised `TypeError` inside the handler, and the loop ended the whole run as "tool run_python failed". Only an exception that is not about the arguments still goes to synthesis.
- **Repeated identical failures are stopped.** When the same tool returns the same error class three times in a row, its next result carries a plain notice: the tool is failing in this run, stop calling it, and use the other tools or submit what you have (an undetermined answer is acceptable). After five, the tool is closed for the run, like the near-limit closing of expensive tools. Seen: 31 consecutive `run_python` calls with `print("hello")`, all exit 71.
- **Tests:**
  - a stubbed agent that sends `{}` to `run_python` gets `bad_arguments` and the run continues;
  - a stubbed tool that always fails produces the notice on the 3rd failure and closes the tool on the 5th.

## Owner addendum (2026-10-27, from the third live run)

Run 3 ended `undetermined: budget` after 60 turns: 52 `run_python`, 5 `view_frames`, no `segment`. The agent hunted for the evidence format (fixed in part 07 §10) and repeated itself. It read the same file 13 times and made the same `view_frames` call four times. It never saw its own earlier calls, because the history did not replay them.

- **The agent sees its own past calls.** History follows `skills/meta-api.md` (stateless turns). The previous response's output items, `function_call` items included, are replayed verbatim, and each is paired with its `function_call_output` by `call_id`. Older image results are still pruned per §4, but calls and text results stay.
- **Informational budget line.** Every tool result ends with one line copied from the ledger, for example `turn 14/60 · $0.004 of $2.00 · SAM 0/1500 frames · searches 0/6 · mask checks 0/4`. This is the "informational copy" §5 allows. It does not hint at an order of steps.
- **The near-limit closing is per budget.** When turns or wall time near their limit, the loop injects the notice but closes nothing. Expensive tools close only when their own budget, or dollars, is near its limit. Run 3 closed `segment` at turn 48 although SAM had used 0 of 1500 frames.
- **Identical calls are flagged.** A call identical to an earlier one in this run (same tool, same arguments) still runs. Its result starts with "same call as turn N", and the third identical call gets the §6-addendum notice.
- **Tests (stub agent):**
  - the second request contains the first response's `function_call` and its paired `function_call_output`;
  - every tool result ends with the budget line;
  - at 80 % of turns with SAM unused, `segment` stays open;
  - a repeated identical call is marked with the earlier turn.

## Owner addendum (2026-10-28, from the fourth live run)

- **The agent sees everything a tool returns**, except image bytes. The rendered tool result includes the tool's `errors` list and any other structured fields, not only `summary` and `files`. Seen: the submit error list was in `metrics.errors` and never shown, and the agent spent about 12 turns probing for the format.
- **Tests:**
  - a rejected `submit` stub with 3 errors renders all 3 codes and fields in the text the agent receives;
  - a `dry_run` submit does not count against the 3 attempts.

## Owner addendum (2026-10-28, from the fifth live run)

The feedback worked: across five dry runs the agent cut its errors from 5 to 3 to 2, and only the `camera` shape was left. Two loop rules then ended the run.

- **`submit` rejections are not "repeated failures".** The rule "same error class three times → notice, five → close" (addendum from the second run) closed `submit` after five dry-run rejections whose error lists kept shrinking. The agent then called the closed tool nine times. `submit` is exempt from that rule: it has its own limits (3 real attempts, the dry-run cap). For every other tool the rule counts a failure as repeated only when the code **and** the detail text are identical.
- **Only run-level budgets end the run.** These are turns, wall time and dollars. A per-tool budget, such as SAM frames, web searches, blind mask checks or dry runs, closes that tool when exhausted, with a one-line notice, and the run goes on. Seen: `mask_checks 4>=4` ended run 5 as `undetermined: budget` at turn 56 of 60, with $0.10 spent of $2.
- **Tests (stub agent):**
  - five rejected dry runs with different error lists leave `submit` open, and the next call is a real attempt;
  - exhausting mask checks closes `check_mask` and the run continues to its next turn.

## Owner addendum (2026-10-28, from the sixth live run)

The sixth run spent 54 turns before its first submit, a dry run on turn 55, and hit the 60-turn limit. Its budget line showed turns used ("turn 54/60"), and the prompt said "never watch the budget yourself".

- **The budget line shows what is left:** `turn N/60 · M turns left · $spent of $cap`.
- **The prompt plans the finish.** Replace "never watch the budget yourself, just finish and submit with what you have when asked" with: as soon as you have a track and a scale, write your evidence file and run `submit` with `dry_run` (aim for half the turns); dry-run again after each fix; make the real submit after a clean dry run. Mention `evidence_path` (part 07 §13) as the way to submit.
- **A half-way notice.** At 50 % of turns with no `submit` call yet, append once: "Half the turns are used and nothing has been submitted: write workspace/evidence.json and submit it with dry_run now." The 80 % notice adds: "Submit for real now if your last dry run was clean."
- **Tests (stub agent):** the budget line contains "turns left"; a stub that never submits gets the half-way notice exactly once, at turn 30 of 60; the prompt text no longer contains "never watch the budget".

## Owner addendum (2026-10-28, from live run 10 and the first wall run)

Both runs ended `undetermined: budget wall_time ≥ 1800` without one `submit` call:
- the Moon clip at turn 36 of 60, about 51 s a turn;
- the wall clip at turn 28 of 60, about 67 s a turn.

The half-way notice counts turns only. It came at turn 30 (minute 24), together with the 80 % wall-time notice, so the agent had six turns left and no dry run behind it. Wall time, not turns, is now the budget that runs out first.

- **Notices follow the first run-level budget to cross the ratio**, whichever it is: turns, wall time or dollars, not turns alone.
  - The half-way notice fires once, when any of them reaches 50 % with no `submit` call yet. It names that budget: "Half the time is used and nothing has been submitted: write workspace/evidence.json and submit it with dry_run now." (or "Half the turns…", "Half the budget…").
  - The 80 % notice works the same way.
- **The budget line shows time left:** `turn N/60 · M turns left · K min left · $spent of $cap`.
- **At a run-level cap, a clean dry run beats nothing.** When a run-level budget ends the run, and the last dry run passed validation with no errors, the loop submits that same evidence for real (one attempt) before it closes. The result's provenance notes "submitted at the budget limit from the last clean dry run". Without a clean dry run the run ends as now.
- **Tests (stub agent, fake clock):**
  - a stub that never submits gets the half-way notice once, when the clock passes 15 of 30 minutes, even at turn 10;
  - the budget line contains "min left";
  - a stub whose last dry run was clean and that then hits the wall-time cap ends with that evidence's result, not `undetermined: budget`;
  - a stub with a rejected last dry run still ends `undetermined: budget`.
- **Push codes count as clean at the cap** (part 11 §16). A dry run whose only errors are in `src.validate.PUSH_CODES` counts as clean for the rule above, so a run with a measured g but one reference still ends with that measured, undetermined result. *Test:* a stub whose last dry run failed only with `SECOND_REFERENCE_REQUIRED` and that then hits the wall-time cap ends with that evidence's result.

## Owner addendum (2026-10-28, from Moon run 12 and wall run 3)

Both runs ended `undetermined: budget turns ≥ 60` at about 25–30 s a turn, with good measurements already in hand.
- **Moon run.** Turns 10–20 went to finding and reading the helper library inside the sandbox. The half-way notice (turn 30) and the 80 % notice (turn 48) were ignored. The first evidence write came at turn 58 and failed on a Python syntax error, so there was no dry run at all.
- **Wall run.** Turns 1–23 went to reading the helper sources and `HELPERS_DOCS.md` in 12 000-character chunks. The first dry run came at turn 36 and the fixed one at turn 59.

- **The helper library is in the prefix.**
  - `build_prefix` appends `src/helpers/HELPERS_DOCS.md` verbatim after the measuring rules, under the heading `HELPER LIBRARY (import as helpers.<module> inside run_python):`.
  - The prefix stays byte-identical across turns. It is cached, so this costs cached tokens only.
  - In the initial task, "read inputs and helper docs as needed" becomes "the helper library is documented above; do not read its source".
- **No dry run by the half-way point closes exploration.**
  - If three turns pass after the half-way notice with no `submit` call, the loop closes `segment`, `view_frames`, `web_search` and `check_mask`.
  - Each closed tool answers with one line: "closed until your first dry run: write workspace/evidence.json and submit it with dry_run".
  - They reopen after the first `submit` call in this run, dry or real. `run_python` and `submit` stay open.
  - This closing is separate from the budget-exhaustion closing and does not count as a tool failure.
- **Tests (stub agent, fake clock):**
  - the prefix contains the first heading of `HELPERS_DOCS.md` and the name of every public helper module, and two consecutive requests carry the identical prefix;
  - the initial task no longer contains "helper docs as needed";
  - a stub that never submits gets the half-way notice, and three turns later `segment` returns the closed line while `run_python` still runs;
  - after that stub's first `dry_run` submit, `segment` runs again.

## Owner addendum (2026-10-29, from Moon run 13 and wall run 4): the last fifth is for finishing

Seen: both runs made a first dry run (turns 39 and 30) with fixable errors.
- **Moon:** two blind-check alternatives were left unanswered, and sigma was 0.4 % short.
- **Wall:** the fit window mixed phases, and the fit curve had three points.

Neither run dry-ran again. The Moon run spent turns 40–55 on new references (`segment`, `check_mask`, `web_search`), and both runs hit 30 minutes.

- **The finishing phase.**
  - When the first run-level budget (turns, wall time or dollars) reaches 80 %, the loop closes `segment`, `view_frames`, `web_search` and `check_mask` for the rest of the run.
  - Each closed tool answers with one line: "finishing phase: fix the errors of your last dry run with run_python and submit; dry-run first if you have not".
  - `run_python` and `submit` stay open.
  - This replaces the text of the 80 % notice.
- **The last dry run stays in view.** After a rejected dry run, every budget line ends with `last dry run: N errors (turn T)`. After a clean one, it ends with `last dry run: clean (turn T)`.
- **Caps come from config.** Tests read `MAX_TURNS` and `HARD_CAP_WALL_S` from `src.config` instead of writing 60 or 1800. Part 04 now sets 90 turns and 45 minutes.
- **Tests (stub agent, fake clock):**
  - at 80 % of wall time, `segment` returns the finishing line and `run_python` still runs;
  - after a rejected dry run with 2 errors, the next budget line ends with "last dry run: 2 errors (turn T)";
  - no test file in `tests/loop/` contains the literal "1800" or "/60".

## Owner addendum (2026-10-29, from Moon run 15): the first dry run by one third

Seen: Moon run 15 (part 07 fixed, so push codes reached the agent) made its first dry run at turn 48 of 90, 37 of 45 minutes, already inside the finishing phase. Its dry runs at turns 50 and 52 returned `SECOND_REFERENCE_REQUIRED` and `CLOCK_REQUIRED`, but `segment`, `web_search` and `check_mask` were closed, so it could not act on them. It submitted one reference and ended undetermined (g = 1.17 ± 0.08 from a 0.66 m backpack; run 14 got 1.91 ± 0.40 from a 1.04 m reading of the same backpack). Exploration had closed only at turn 41 (half-way plus three turns).

- **Exploration closes at one third.** When the first run-level budget (turns, wall time or dollars) reaches one third with no `submit` call in the run, the loop closes `segment`, `view_frames`, `web_search` and `check_mask` with the existing line "closed until your first dry run: write workspace/evidence.json and submit it with dry_run". This replaces "three turns after the half-way notice"; everything else in the 2026-10-28 addendum stays (they reopen after the first `submit`, dry or real).
- **The initial task says it.** The initial task ends with: "Dry-run early: submit a first evidence with dry_run by one third of the budget, even incomplete; its errors and push codes tell you what is still missing, and you need the remaining time to add it."
- **Tests (stub agent, fake clock):** a stub that never submits finds `segment` closed once one third of `HARD_CAP_WALL_S` has passed, and open just before; the initial task contains "by one third of the budget".

## Owner addendum (2026-10-29): Describe, then Wonder, then measure

The owner's direction: before anything is measured, one model call describes the clip and a second one asks what in it is worth proving and how. Only then does the measuring loop start, with that plan as its task. Today the loop finds its question inside a long tool conversation; runs 13–15 spent 15–30 turns before they knew what to measure.

- **Describe (one Spark call, no tools, before turn 1).** Input: contact sheets of the whole clip at a spacing of at most 0.5 s, built by the same code the loop runs for `view_frames`, plus the clip facts (duration, fps, size). Output, JSON, saved to `artifacts/describe.json`:
  - `what_happens`: 3–6 sentences in time order, with clip times;
  - `scene`: where it is and which world the frames show, with the frame that shows it;
  - `things`: the people, animals and objects visible, with what can be identified about them (model, event, place);
  - `on_screen_text`: any text in the frames, verbatim.
- **Wonder (one Spark call, no tools, after Describe).** Input: Describe's JSON and the same sheets. Output, JSON, saved to `artifacts/wonder.json`:
  - `claim`: what the clip shows or says that a viewer might doubt;
  - `question`: the viewer's question, in plain words (part 08 R-Q1);
  - `world`: the scene's world (part 02 §8);
  - `checks`: one to three items, each `what` (the quantity to measure), `why` (how it answers the question), `how` (what to measure in which frames, against which object of known size) and `compare_with` (the real-world value or range to look up: the world's gravity, records, body norms, a product's published size);
  - `realistic_if` and `not_realistic_if`: one sentence each.
- **The loop starts from the plan.** The initial task quotes `wonder.json` and says: "This is your plan. Measure these checks; you may change a check, but say why in first_look.summary." `first_look.question` is Wonder's question.
- **Cost and failure.** Both calls are on the run's ledger and count against the dollar and wall-time budgets, not against turns. A call that fails or returns invalid JSON is retried once; if it fails again, the loop starts as before, without a plan, and `logs/` records why.
- **Blindness:** both calls see only frames and clip facts, never the file name; Wonder names what to look up, never the clip or its answer (part 07's filter still guards `web_search`).
- **Tests (stub Spark):** both calls happen before turn 1 and write their artifacts; the initial task contains Wonder's `question` and each check's `what`; a malformed reply is retried once and then skipped with the loop still starting; both calls appear on the ledger.

## Owner addendum (2026-10-30, from wall run 7): each check has a kind, the example is not the clip, the finish is the loop's

Wall run 7 (`20261030T094352Z-8be844c9`) was the first run with a plan. Describe placed the scene on Earth, and Wonder asked "Could a person really run straight up a wall that tall?" with two checks: the wall's height against people's height, and the ascent speed against records. The run then ended "undetermined: budget" after 50 turns, for three reasons:
- Its only evidence (dry run at turn 26) was the example evidence with a few values changed. Its one reference was still "backpack height", and `range_checks` was empty, so neither check of the plan reached the evidence.
- Wonder missed the check that settles the clip. On a vertical face nothing presses the body to the wall, so its vertical motion is free and must accelerate downward at the world's g. The owner's manual probe measured 3.2 ± 0.3 m/s² against 9.81.
- After the finishing notice the agent ran `run_python` for eight more turns and never submitted.

1. **Wonder knows the three kinds of check the loop can measure.** Each item of `checks` gains `kind`, one of the following:
   - `gravity`: a body moving with nothing holding it up must accelerate downward at the world's g. That body may be in the air, falling, or on a surface that cannot push it upward, such as a vertical face. The check is a segment, a parabola fit against g.
   - `range`: a measured size, ratio, speed, height or duration is compared with a sourced real-world range. The range may be body norms, records or a product's published size. The check is a `range_checks` item (part 02 §9).
   - `clock`: a periodic motion with a known natural rate shows whether the clip plays at real speed. Steps, a swing and a bounce are examples. The check is the evidence `clock`.

   The Wonder prompt states these three kinds in one sentence each, with no example from any clip. It asks for at least one check of the kind that would settle the question. `kind` stays in `artifacts/wonder.json` and the initial task. Part 11 copies to the result only the fields part 12 §23 defines.
2. **The initial task maps the plan to the evidence.** After the plan it says:
   - every `gravity` check becomes a segment;
   - every `range` check becomes one `range_checks` item with its value, σ, extents and a sourced range;
   - a `clock` check becomes `clock`;
   - an evidence that has range checks and no segment is valid.

   The task's opening sentence no longer says "When you have a track and a scale". It says "When you have measured the plan's checks".
3. **The example is not the clip.** The prefix shows two examples, labelled as examples of the shape only: the Moon example (a gravity segment) and the still-range fixture's evidence (part 12 §22, range checks only). It adds this line: "Every name, value and source in your evidence comes from your own clip and your own searches; an evidence that still carries an example's reference name or value is rejected." The rejection happens in part 11 as `EXAMPLE_VALUE_COPIED`, matched on the reference names and source URLs of both examples. A dry run reports it as an error.
4. **The loop finishes the run.**
   - In the finishing phase the agent has at most four more turns.
   - At the first of these, the loop's notice lists the last dry run's errors in plain words. When there was no dry run yet, it says to write `workspace/evidence.json` now.
   - After the fourth turn, or when the run-level budget is spent, whichever comes first, the loop submits `workspace/evidence.json` itself, for real, if the file exists and parses. The run's result is then the validator's answer, accepted or rejected. If the validator rejects it, the loop ends the run through part 11's synthesis with the kind `not finished` and the rejection's errors. The result then says "Undetermined: not finished" and names the first two errors in plain words (part 11 §23).
   - Only a run with no evidence file at all ends "Undetermined: budget".
5. **Tests (stub Spark):**
   - Wonder's checks carry `kind`, and the initial task contains each check's kind and the evidence field it maps to.
   - The prefix contains both examples and the "comes from your own clip" line.
   - A stub agent that keeps calling `run_python` in the finishing phase is stopped after four turns. Its `workspace/evidence.json` is submitted by the loop, and the result's reason names the validator's first errors.
   - A run with no evidence file still ends "Undetermined: budget".

## Owner addendum (2026-10-30): build range checks and the clock with the library

Part 09 §7 adds `helpers.ranges` (`mask_extent`, `range_value`, `print_check`) and `helpers.clock.clock_evidence`. After the plan, the initial task gains these lines:
- "Build every range check with the library: load the measured thing's mask, take each extent with `ranges.mask_extent`, the value and σ with `ranges.range_value`, and print the whole item with `ranges.print_check` in one run_python. That run_python is the check's `measurement_artifact`. Copy the printed item into the evidence unchanged, then add `range` from your search."
- "Build `clock` with `clock.clock_evidence` and copy it unchanged."
- A range bound's `quote` is copied character for character from the `web_search` fact that gave it.
- **Test:** the initial task, with and without a plan, contains `ranges.mask_extent`, `ranges.print_check` and `clock.clock_evidence`.

## Owner addendum (2026-10-31, from hand run 5): no placeholder evidence; keep the evidence current; check lines

Seen: hand run 5's first dry run (turn 24) was a placeholder, with empty `references` and `range_checks` and a dummy scale. Its single schema error hid everything else. The agent then measured the hand correctly, 18.3 cm against the author's 19 cm, but never put the measurement into `workspace/evidence.json`. The loop's own submit at turn 50 therefore sent the placeholder.

- **The first dry run carries a real measurement:** at least one range check built with `helpers.ranges`, or one segment, and its scale reference. The initial task says: "Never dry-run a placeholder; dry-run what you have measured, even if it is only one check."
- **The evidence stays current.** After each measurement that belongs in the evidence, the agent writes it into `workspace/evidence.json` at once. The initial task says: "From your first measured check on, keep workspace/evidence.json current after every measurement; the loop submits that file when time runs out."
- **Lines are checked before they are submitted.** The initial task adds: "Before a range check goes into a dry run, check its lines with check_line(frame, lines) on the frame you measured; re-measure any line the second look does not confirm."
- **The loop offers `check_line`** (part 07 §19). It uses the schema part 07 publishes and dispatches the call like `check_mask`, with the blind Spark client and the ledger. It is not an exploration tool, so it stays open in the finishing phase and after one third of the budget.
- **Test:** the initial task contains the three quoted sentences, with and without a plan, and a stub agent's `check_line` call reaches the tool with the blind client and the ledger.

## Owner addendum (2026-10-31, from hand run 7 and wall run 12): the loop refuses a placeholder and shows the plan's progress

Seen:
- Hand run 7 dry-ran a placeholder at turn 37 (its code says "create dummy ref track"), although the initial task forbids it.
- It then spent 33 turns on 19 frame views, 29 code runs and 9 segmentations, but never wrote a measurement into `workspace/evidence.json`. At turn 70 the loop submitted the placeholder.
- Wall run 12 did the same: placeholder at turn 32, and again at turn 65.

- **The loop refuses a placeholder dry run,** without calling the validator and without counting it as a dry run. A placeholder has no reference with an `extent_px`, no range check with an extent, and no segment with frames. The tool result says: "This evidence has no measurement yet. Measure one check of the plan with helpers.ranges or a segment fit, write it into workspace/evidence.json, then dry-run."
- **Every turn's status line shows the plan's progress.** One entry per Wonder check: its `kind` and a few words, and whether `workspace/evidence.json` holds it now. A gravity check counts once it has a segment with frames, a range check once it has a range check with extents, and a clock check once it has a clock. An example: "plan: 1 gravity: wall-run ascent — not in evidence.json; 2 range: wall height vs runner — in evidence.json". The loop reads the file each turn and never edits it.
- **Tests:**
  - a placeholder dry run returns the message above, does not call the validator stub, and does not advance the dry-run count;
  - the status line shows "not in evidence.json" for every check until the file holds the matching item, then "in evidence.json".

## Owner addendum (2026-10-31, from part 07's regeneration): loop tests do not pin another part's request shape

Seen: part 07 §20 was regenerated to send the blind client `kind: "line_look"` / `"line_match"`, as its brief says. The generation was refused only because a loop test asserted the exact key set `{"image", "question"}` of the blind request. That shape belongs to parts 04 and 07, and their joint test (07 §20) covers it.

- **The loop's tests check only what the loop owns:** the call reaches the tool with the blind client and the ledger, the ledger counts, the rendered result, the phases. They never assert the exact keys of a request that a part 07 tool builds for the blind client.
- A stub blind client answers by what the request carries: a request with an image gets `descriptions`, one without an image gets `results`. It accepts any extra keys, such as `kind` or `n_lines`.
- **Test:** the `check_line` test from the addendum above passes with a stub that receives extra keys (for example `kind`) in each request.

## Owner addendum (2026-11-01, from the Moon and sped-up Moon runs): the loop offers `motion_overview`

- **The loop dispatches `motion_overview`** (part 07 §21) like the other tools: its schema is in the tool list Spark receives, its result is logged and its files are named. Its chart and strip images go back to Spark as images, the same way `view_frames` sheets do.
- **The prefix says when to use it** (part 08 R-M6, R-M7, R-S11, R-S12), in one short paragraph: segment the moving body over the whole clip in one call, run `motion_overview` on it, look at the chart and strips, decide every candidate, measure the free flights (one first, the others as confirmations), measure references close before the first flight on short segments.
- **The plan's progress line** counts a motion check as done only when `first_look.overview` gives every candidate a decision and every `measured` candidate has a segment with frames.
- **Test:** a scripted run (fake client) that calls `motion_overview` on the `fixtures/source/fake-1/` masks gets a result naming the chart and the strips, and the next request to the client carries the chart as an image.

## Owner addendum (2026-11-02, from four runs after part 11 §47): no early real submit while pushes remain

Seen: sped-up run `20261102T024430Z-0cfab426` dry-ran at turn 60 and got one push, `SECOND_REFERENCE_REQUIRED`. At turn 61 it made the real submit, with 89 of 150 turns and 93 of 150 minutes left. The result was "Undetermined: scale rests on one reference". Its mask check had listed the parts it would need.

- **The loop holds back an early real submit.** When a real submit (`dry_run: false`) gets push codes and no errors from the validator, and every run-level budget (turns, wall time, dollars) is under 50 % used, the loop does not accept it. It returns the validator's reply as a dry-run reply (it counts as a dry run) with this first line: "Time remains (61 of 150 turns, 57 of 150 min used): the pushes below can still change the result. Work on them, then submit again."
- From 50 % of any run-level budget, a real submit with pushes is accepted as before. The 80 % notice and the loop's own submit at the end (§ near a limit) are unchanged.
- A real submit with no pushes and no errors is accepted at any time.
- **Tests:**
  - with a stub validator that returns one push and no errors, a real submit at turn 20 of 150 (wall and dollars low) is not accepted: the reply starts "Time remains", the dry-run count goes up by one, and the run goes on;
  - the same submit at turn 80 of 150 is accepted;
  - a real submit at turn 20 with no pushes and no errors is accepted.

## Owner addendum (2026-11-02, from four runs after the addendum above): the early hold uses a dry run of the same evidence

Seen: sped-up run `20261102T071022Z-986bae28` dry-ran at turn 58 and got one push, `SECOND_REFERENCE_REQUIRED`. At turn 59 (39 % of turns, 43 % of wall time) it made the real submit and it was accepted, "Undetermined: scale rests on one reference". The hold above never fired: in a real submit the validator does not return push codes (part 11 turns them into an undetermined verdict), so the loop saw no pushes.

- **Before it accepts a real submit while every run-level budget is under 50 % used, the loop validates the same evidence as a dry run.** When that dry run gives push codes and no errors, the loop holds the submit back as described above: the reply is that dry run's reply with the "Time remains" first line, and it counts as a dry run. When the dry run gives no pushes, the real submit goes on as usual.
- From 50 % of any run-level budget, the loop does not run this extra dry run.
- **Tests (the stub validator behaves like part 11: a dry run returns pushes, a real submit of the same evidence is accepted with no errors):**
  - a real submit at turn 20 of 150 is not accepted: the reply starts "Time remains" and lists the push, and the dry-run count goes up by one;
  - the same real submit at turn 80 of 150 is accepted, and the stub sees no extra dry run;
  - a real submit at turn 20 whose dry run gives no pushes is accepted.

## Owner addendum (2026-11-03, from sped-up run `20261102T222230Z-6bab6921`): a failed agent call is logged and stops the run after the second

Seen: from turn 14 every agent call ended `response.failed`, 110 times in a row, until the turn cap. The log rows say only `response.failed`; the ledger says `cost_unknown`. Part 14 §4 says the run degrades after two consecutive failures.

- **The loop logs the API's error payload** (the `error` object of the terminal event, or the HTTP status and body; never a header or key) in the turn's `loop.jsonl` row as `spark_error`, cut to 2000 characters.
- **After two consecutive failed agent calls,** the loop retries once with the image inputs of the newest turn's tool outputs replaced by the text "(image omitted: the model service refused the request with this image)". A third consecutive failure ends the run as part 14 §5 says, with the reason "the model service refused the request" and the last `spark_error` code.
- **Tests:** a fake client that fails twice and then accepts a request without images: the run goes on, and the third request has no image from the newest turn; a fake client that always fails: the run ends after 3 failed calls with that reason, and each row carries `spark_error`.

## Owner addendum (2026-11-04, from street-jump run 82): max effort where judgment is made, high for routine turns

Seen: in street-jump run 82, 97 % of Spark's output was reasoning: about 8 500 tokens a turn at about 96 tokens a second. A turn took about 100 s, and the 134 turns took 244 minutes; the tools took a small share. Most turns answer a routine tool result (a frame view, a script's output). The judgment the owner asked max effort for (part 04, 2026-11-01) is made in the first look, and when the validator or the loop speaks.

- Every agent request the loop sends carries `"reasoning_effort"` (part 04 sends it to Spark):
  - `"max"` (part 04's `SPARK_REASONING_EFFORT`) on the first `MAX_EFFORT_FIRST_TURNS = 20` turns; on a turn whose new input holds a `submit` result (a dry run's errors, a refusal or an early hold); and on a turn whose new input holds a loop notice (half-way, 80 %, exploration closed, finishing, a closed tool);
  - `ROUTINE_EFFORT = "high"` on every other turn.
  - Both constants live in `src/loop/` next to the other loop budgets.
- `logs/loop.jsonl` records each turn's `reasoning_effort`.
- **Tests (stub agent; tests read the constants, never 20, "high" or "max"):**
  - turns 0 to `MAX_EFFORT_FIRST_TURNS` − 1 carry `SPARK_REASONING_EFFORT`;
  - a turn after `MAX_EFFORT_FIRST_TURNS` that answers a `run_python` result carries `ROUTINE_EFFORT`;
  - the turn that answers a dry-run `submit` carries `SPARK_REASONING_EFFORT`, and the next routine turn carries `ROUTINE_EFFORT`;
  - the turn after the half-way notice carries `SPARK_REASONING_EFFORT`;
  - each `loop.jsonl` line holds `reasoning_effort`.

## Owner addendum (2026-11-04, from street-jump run 83): the clip card is built from masks before the plan; a closing line is sent once

Seen: in run 83 the first look read the jump over the car from small contact sheets as "vaults over moving car with hand support". The agent built the jumper's and the car's masks later (turns 6 and 28) but never checked that reading against them: in its own masks the two never touch (no overlap in frames 60–110, smallest gap 54 px at frame 80). It then refused to measure the flight as "not a free flight". The owner's direction: before deciding what to prove, the run must know from masks which things move, how they move, where they touch, and how the camera moves. Run 83 also repeated one closing line ("web_search is closed … nearly spent") on every turn from turn 55, and each repeat counted as a loop notice, so every turn ran at max effort.

- **Describe names the moving things.** Describe's JSON gains `moving_things`: up to 4 short noun phrases SAM can segment (a person, an animal, a vehicle, a ball), each a thing that moves in the clip, the most important first.
- **The clip card (after Describe, before Wonder; no Spark call):**
  - for each phrase, part 07's `segment` over the whole clip (first to last frame); the SAM frames go on the ledger and count against the SAM budget, as a tool call does;
  - part 07's `motion_overview` on each result;
  - contacts: for each pair of segmented objects, the frame ranges where their masks overlap or come within 3 px, and the smallest gap in pixels over the clip;
  - camera: part 09's `find_still_patches` over the whole clip with every segmented mask as `avoid`, then `still_track` on its first box; the card records the box's largest displacement in pixels, or "no still patch";
  - output `artifacts/card.json` (the phrase, artifact and object id of each object; its candidates with frames, airtime and peak rise; the contacts; the camera) and the overview charts. Card artifacts are named with the prefix `card_`.
  - The card adds objects in Describe's order and stops before one that would take the card past half of the run's SAM frame budget; a phrase left out is listed with that reason.
  - A phrase that SAM returns empty or fails on is listed with its reason, and the card goes on without it. If every phrase fails, the loop starts as before and `logs/` records why.
- **Wonder plans from the card.** Wonder's input adds the card JSON and the overview charts. A check whose `how` relies on a contact names a contact range the card lists.
- **The initial task quotes the card**: each object with its masks artifact and object id ("these masks exist; reuse them"), each candidate flight, the contacts (or "no contact between any two objects"), and the camera's movement.
- **A closing line for a tool is sent once.** The loop records each tool it has sent a closing line for and does not send it again. Only the first send counts as a loop notice for the reasoning effort.
- **Tests (stub Spark and stub SAM; no model calls):**
  - a Describe reply with two moving things: the card step calls `segment` once per phrase over the whole clip, then `motion_overview` on each; `artifacts/card.json` lists both objects;
  - two stub masks that never come within 3 px: the card says no contact; two that overlap in frames 10–14: the card lists that range;
  - Wonder's request and the initial task contain the card's objects and contacts;
  - a stub SAM that fails on one phrase: the card lists it with the reason, and the loop still starts;
  - with web searches at 5 of 6 for 10 turns, the closing line appears in the history once, and only the turn after it carries `SPARK_REASONING_EFFORT` for that reason.

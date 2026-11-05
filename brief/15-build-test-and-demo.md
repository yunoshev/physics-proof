# 15 — Build, Test and Demo

**Owns:** `PLAN.md` process, `tools/dev_loop` (the regeneration tool, with `tests/dev_loop/`), the acceptance harness (`tests/acceptance/`), `scripts/demo/`, and the iteration log. This part describes **how the owner and the coding agent work together**; it is part of what the judges are shown, not backstage scaffolding. It does **not** own the other parts' tests: each part owns the tests of its own modules, per the fixed rule in part 04 §3.

## 1. Step zero: PLAN.md

Before any product code: **Muse** (`skills/muse-code-headless.md`) — model `muse-spark-1.3`, `--reasoning-effort max` — reads this entire spec (`brief/` + `skills/`) and writes `PLAN.md` containing:

- the module list (from part 04 §3) with the interface each module exposes to the others,
- the generation order (README build order, made concrete with dependencies),
- the test list per part (from §§3–5 below, named before the code exists, each test assigned to its owning part's test path per part 04 §3),
- risks and open questions, each either resolved from the spec or raised to the owner — never silently decided.

`PLAN.md` is reviewed by the owner once. After that, parts are generated **one at a time with Muse**, model `muse-spark-1.3-contributor`, `--reasoning-effort medium` by default and `high` for the hard parts — `06` (agent loop), `11` (result validation), `13` (player) — each invocation fed exactly its spec part + `PLAN.md` + the relevant skills, and producing that part's owned test files (per part 04 §3) in the same invocation. If generation reveals a spec gap, the fix goes into the spec part first, then the code is regenerated — the spec is the only thing humans and agents negotiate in.

## 2. The development loop tool (`tools/dev_loop`)

The **first thing generated** after `PLAN.md` is the tool that makes every later step safe. For a named part it:

1. **Refuses to continue if a generated file was edited by hand.** The manifest (`tools/manifest.json`) records, right after each green generation, the SHA-256 and owning part of every file under that part's owned paths; **a hash mismatch, or a file under owned paths that the manifest doesn't list, aborts the run and names the file.** That is the whole check. Files whose format allows comments (Python, JS, CSS, HTML, shell, TOML, Markdown) also carry a reader-facing header (`generated from brief/NN`); a missing header is never a violation — JSON, images and other data files can't carry one. (Spec files, `PLAN.md`, and the iteration log are human/agent-negotiated and are not generated files.)
2. Deletes that part's owned files (per part 04 §3) — **including that part's owned test files, and no other part's**: regenerating part 06 deletes `tests/loop/` and nothing else under `tests/`; regenerating part 15 deletes only `tests/dev_loop/` and `tests/acceptance/`. It then regenerates them by invoking Muse exactly as specified in `skills/muse-code-headless.md` (model/effort per §1), capturing the `run_usage` event for cost.
3. Runs that part's tests (§3, at the paths listed in part 04 §3). A red test stops the loop; the failure output goes back to the coding agent with the spec part, and regeneration repeats — the owner is not asked to read stack traces. **Deletion happens once, before the first attempt; a retry continues from the previous attempt's files** with the failing output as feedback — it never restarts from an empty tree or from an older commit, so fixes and tests written in one attempt survive into the next. (Seen 2026-10-27: each retry restarted from the last commit, the third attempt dropped the review tests written by the first, and the part went green without the review fixes.) **Every attempt leaves a record** in `.dev_loop/<part>/<timestamp>-<attempt>/` (git-ignored): the Muse JSONL event log, the agent's final message, and the full test output. When a part ends red, the tool prints the last attempt's failing test names with their first error lines and the path of that record, so the owner can change the spec without re-running anything.
4. On request (`--pages`), rebuilds the affected player pages (§5) and runs the screenshot review (§6).
5. **Appends one line to `ITERATIONS.md`**: date, spec part changed, generation cost (from the `run_usage` event of the Muse run, converted per `skills/muse-code-headless.md`), tests result, acceptance result (if run), page link/path. One line, always appended, never edited — this file is the project's honest lab notebook and is shown to judges as-is.

Acceptance runs (`--acceptance`) invoke the part-03 protocol via the harness in `tests/acceptance/`: three fresh runs per clip via the normal one-command entrypoint, the 2-of-3 evaluation, the universal criteria, and the prompt-leak test (§4). The harness is owned by this part but implements part 03's criteria; if part 03 changes, the harness is regenerated under this part in the same step (part 04 §3).

## 3. Tests, by layer

**Ownership:** every test file is owned by the part that owns the module under test (part 04 §3's fixed rule), is generated with that part, and is deleted/regenerated only with that part. Part 15 owns only `tests/dev_loop/` and the integration-level `tests/acceptance/`. All tests are written from the spec, before or with the code.

- **Helper tests** (owner: part 09, `tests/helpers/`): synthetic data, known answers — parabola recovery, scale, gait/clock incl. the band-edge refusal, ghost landing, masks round-trip. These gate the helpers' importability.
- **Rule/violation tests** (owners: part 08 in `tests/rules/` for the pure check functions; part 11 in `tests/validate/` for submit-time enforcement): deliberately violating submissions that part 11 must reject — same-object second reference (overlap > 50%), fitted contact frames, no mask check on the reference, a retimed verdict with no clock, σ smaller than its own components, a Moon fit for an excluded world. Each maps to one validator code (part 11 V1–V12).
- **Contract tests** (owners: part 12 in `tests/contract/` for schema/fixture validation — both fixtures validate, removing any required field fails; part 13 in `tests/player/` for the player opening both fixtures with zero JS errors, headless check).
- **Sandbox tests** (owner: part 07, `tests/tools/`): from inside the sandbox, the repo, `brief/`, `tests/`, and the original input path are unreadable; network is unreachable; writes outside the workspace fail. **The coding agent itself runs inside a sandbox where nested `sandbox-exec` is blocked** (skill: macos-sandbox) — these tests are marked `maintainer` and run by the owner outside the agent; a skipped-marked test is reported as such, never as a pass.
- **Ingest tests** (owner: part 05, `tests/ingest/`; clip generation: part 03, `tests/test_make_clips.py`): a CFR-forced encode with duplicated frames is caught; clips A and B after `make_clips.py` show 0 confirmed duplicates and equal measured fps.
- **Loop and accounting tests** (owners: part 06 in `tests/loop/`, part 14 in `tests/accounting/`): a stubbed API that ends `incomplete` is handled as incomplete (not retried as network); a dying stream is retried as network; cost is computed without double-counting cached/reasoning tokens (part 14 §2); a hard-cap ledger triggers the synthesised *undetermined: budget* file; a submission rejected 3 times ends the run with a valid file.

## 4. Acceptance (part 03, wired)

`dev_loop --acceptance` runs the acceptance harness (`tests/acceptance/`, owned by this part) over §3's suite plus, per clip: 3 fresh runs, 2-of-3 verdict/tolerance evaluation against the harness-only constants, cost < $2, wall time < 30 min, ≥1 blind mask check recorded, valid result file. **The prompt-leak test is part of acceptance, not an extra:** everything sent to Spark in every run is captured (part 14 logs) and scanned for clip identities, expected verdicts, and tolerance values; the runtime-must-not-import-tests boundary is checked structurally (import graph) as well as textually. A leak failure fails the whole suite even if every verdict is right.

Cross-clip note (part 08 R-E3): the harness *may* report the A/B acceleration ratio (expected ≈1.5) as a cross-check line **in the acceptance report and in demo narration only** — never on a per-clip player page, whose result file cannot contain another clip's numbers (part 12 §1). It is never fed back into any run and never changes a verdict.

## 5. Building pages

`dev_loop --pages` takes completed runs and produces, per clip: `pages/<clip-slug>/index.html` (part 13 template with data inlined, hash recorded), the H.264 video copy (transcoded per skill: video-ffmpeg — presentation only), poster frame, mask-check image(s), chronophotograph composite where the segment outlines allow it (part 12 §11); and rebuilds the gallery `pages/index.html`. Page weight without video < 1 MB is asserted; the frozen-template hash in each page must match `player/`'s recorded hash.

## 6. Screenshot review (no page reaches the owner unreviewed)

Before any page is shown to the owner:

1. Headless Chrome screenshots the page at **each key moment** using part 13's URL parameters (`event=<id>`, plus `frame=` spot checks), at desktop and phone widths.
2. **Spark looks at the screenshots** (vision, a fresh call seeing only the screenshot + the result file's numbers) and returns a structured defect list. It checks at minimum the named historical defects: black video, missing/thin overlay (dot-only), unreadable or dark-on-dark text, numbers with absurd decimals, wrong numbers vs. the result file, chart/cursor desync with the video frame, ghost labels missing or swapped.
3. Any defect → back into §2's loop (fix the **spec part** if the spec allowed it, regenerate, re-screenshot). Only a **clean** review is presented to the owner.
4. **The owner is the final acceptance.** Pages are published to **GitHub Pages only after the owner's explicit approval** of the reviewed build; the approval (date + template hash + run IDs) is recorded in `ITERATIONS.md`. No auto-publish on green tests — green tests plus screenshots earn a *request* for approval, nothing more.

## 7. Demo (Nov 4)

- **Demo video:** recorded from owner-approved published pages — the analysis playing in the player for the three clips — not from a live run. Text and graphics only, matching the product.
- **Repo:** `brief/`, `skills/`, `PLAN.md`, `ITERATIONS.md`, all source, `scripts/make_clips.py`, and the two Apollo clips. The wall-run clip is referenced by path only (part 03).
- **Live pages:** the approved GitHub Pages gallery + per-clip players.
- **Fallbacks, rehearsed:** if Pages is unreachable, the same pages run from a local folder (`file://` by design, part 13); if asked for a fresh analysis live, one command runs it (7–11 min typical) — but the demo never depends on it.
- A fresh clone must reproduce the demo: `make_clips` → one-command analysis per clip → `dev_loop --pages` → local pages identical in behaviour to the published ones (template hash equality is the check).

## 8. Owner notes (2026-10-27): tests never spend money

- **The test command of this part is offline.** `tests/dev_loop/` and `tests/acceptance/` check the harness with stubbed Muse runs, stubbed analysis runs and stubbed Spark replies. No Meta API, Muse, SAM or network call happens when this part's tests run, and nothing they do costs money.
- **Real runs go behind one gate.** `dev_loop --acceptance`, `dev_loop --pages` and the screenshot review (§6, a Spark vision call) start paid work only when `PHYSICS_PROOF_LIVE=1` is set. Without it they print what they would run and the cost cap, then exit non-zero. The owner sets the variable by hand for a real run.
- **Screenshots** follow part 13 §16.2: the installed Google Chrome (Playwright `channel="chrome"`), host-only behind `PHYSICS_PROOF_BROWSER=1`. The review takes 1440×900 and 390×844 shots of the first screen and of every event (`?event=…`). It checks them against the player spec's named defect lists (part 13 §§15–17) and returns a defect list per shot.
- **Regenerating `tools/dev_loop` keeps §2 behaviour,** and `tests/dev_loop/` covers each item:
  - the hash-only hand-edit guard;
  - deletion once, before the first attempt, with retries continuing from the previous attempt's files;
  - a record per attempt in `.dev_loop/<part>/…`;
  - one `ITERATIONS.md` line per run;
  - cost from `run_usage`.
- **The cost in the `ITERATIONS.md` line is the whole run's cost**, summed over every attempt. Each attempt's `run_usage` is priced on its own and then added up. The line also gives the attempt count and each attempt's cost, e.g. `cost $3.27 over 2 attempts ($1.61 + $1.66)`, and every attempt's record keeps its own cost. Seen: only the last attempt was counted (player: $1.66 shown, $3.27 spent).
- **Parts that build a screen get a browser.** A registry entry may set `"browser": true`; today that is part 13 (player and page build) and this part (screenshot review). For such a part, `dev_loop`:
  - runs Muse with `--disable-sandbox`: Chrome cannot start inside the shell sandbox, and outside it does;
  - sets `PHYSICS_PROOF_BROWSER=1` both in Muse's environment and in its own test run;
  - tells the agent in the prompt that it can and must run the browser tests itself, take screenshots of its pages and open them to look before it finishes.

  Every other part keeps the sandbox. The workspace is still the part's own worktree or checkout.

**Owner note (2026-10-28): a regeneration must implement what changed.** The coding agent has git, so after `dev_loop` deletes a part's files it restores them from history, runs the old tests, sees them pass and stops. It never meets the new requirements. Seen: part 04 "regenerated" in 10 model calls with no change but an `ITERATIONS.md` line. Its new addendum (one source for tool schemas, replay of `function_call` items) was not implemented. Part 07 kept `from conftest import …` against the brief-04 rule, which part 07 never saw. Therefore the prompt `dev_loop` builds contains, after the part's own spec:

- **Shared constraints.** `brief/04-architecture-and-constraints.md` goes into every part's prompt, not only part 04's. Module ownership, the test rules and the platform constraints bind every part.
- **What changed since this part was last generated.** A section titled `SPEC CHANGES SINCE THE LAST GENERATION OF THIS PART`. It holds the `git diff` of the part's spec file, `brief/04-…` and the part's skills, from the last commit that changed any of the part's owned files to `HEAD`. If there is no such commit, or the diff is empty, the section says so in one line. The instruction comes with it: implement every change in this diff, and back each one with a test that would fail without it. Restored code that passes the old tests is not done. In the final message, list each change with the file and the test that implement it.
- **Tests:**
  - with a fixture repo where a part's spec gained a paragraph after the part's last generation commit, the built prompt contains that paragraph in the changes section and contains `brief/04`;
  - with no spec change, the section says "no changes".

**Owner note (2026-10-28): a part must not break the suite's collection.** A part's own test command passes even when its new file collides with another part's. Seen: part 07's `tests/tools/test_contract.py` duplicated part 12's basename, and the full suite stopped with a collection error. After the part's tests pass, `dev_loop` therefore runs `pytest --collect-only -q` over the whole `tests/` tree. A collection error fails the attempt, and its text goes back as feedback like a test failure. Test: in a fixture repo with two same-named test modules in different directories, the attempt fails and the feedback names both paths.

## 9. Owner addendum (2026-10-28): a regeneration must not break other parts

Three chains in one day passed every part's own tests and still broke other parts. Each break showed only in the full suite after the chain, and fixing it cost another regeneration.
- Part 11 dropped `write_result` and changed `synthesize_undetermined`; 14 failures in parts 04 and 06.
- Part 11 renamed `logs/validator_last_errors.json`; 1 failure in part 06.
- Part 07 deleted `src/tools/timing.py`, which part 05's tests import, and changed tool behaviour that part 06's tests rely on: the refusal of the 5th call, `run_python`'s bad-argument message, transport retries, the blind-call payload. 10 failures in parts 05 and 06; the owner reverted the generation.

Pinning names one by one (part 11 §10) does not scale. `dev_loop` checks the whole suite itself:

1. **Baseline.** Before the first attempt, `dev_loop` runs the full suite (`tests/`) on the base commit, with `PHYSICS_PROOF_BROWSER=1` when the part has `"browser": true`, and records which tests pass.
2. **Guard.** After the part's own tests and the collection check pass, it runs the full suite again. A test outside the part's owned paths that passed in the baseline and fails now fails the attempt. That test is rerun once alone first: if it passes alone, it is reported as flaky and does not fail the attempt.
3. **Feedback.** The next attempt's prompt lists each such failure (test id, the error line, the test's file) under `OTHER PARTS' TESTS YOU BROKE`, with the instruction: other parts use these names, files and behaviours; keep them unless your spec says otherwise. Retries continue from the previous attempt's files (§8).
4. **Breaks on purpose.** A spec section may say that some other part's tests must change because of it, in a line starting `Breaks on purpose:` followed by test paths and the part that will update them. Failures of those tests are listed in the summary and the `ITERATIONS.md` line and do not fail the attempt.
5. **Cost.** The full suite takes about 3 minutes; it runs locally and costs nothing.
6. **Tests** (offline, stubbed Muse):
   - a fake part whose stubbed generation deletes a module that another part's test imports fails the attempt, and the next prompt names that test;
   - with a `Breaks on purpose:` line naming that test, the attempt passes and the summary lists it;
   - a foreign test that fails in the full run and passes alone is reported as flaky and does not fail the attempt;
   - a test that already failed in the baseline never fails the attempt.

## 10. Owner addendum (2026-10-28): the leak scan's scope

The acceptance harness (`tests/acceptance/`) implements part 03's addendum of 2026-10-28. The leak scan checks what the system and the operator send for clip identities and per-clip expectations. It checks the agent's own turn texts and its own search results only for acceptance constants and expected verdicts, because the agent may now name what it identifies in the frames (part 01). Test: as in part 03's addendum.

## 11. Owner addendum (2026-10-28): a `Breaks on purpose:` path survives punctuation

Seen: brief 09 §6 wrote "Breaks on purpose: `tests/validate/test_validate_fixture.py`. The run-7 fixture …". The parser strips backticks, quotes, brackets, commas, semicolons and colons, but not the full stop. It kept "tests/validate/test_validate_fixture.py`.", matched nothing, and part 09 failed its guard twice.

- **Clean each token completely.** Strip every leading and trailing character that cannot end a path: `` ` `` `'` `"` `(` `)` `,` `;` `:` `.` `!` `?` `—`. A trailing `/` is kept, then dropped as now.
- **Show what was parsed.** The excused paths are printed once before the baseline, so a typo shows up at once.
- **Tests:**
  - `` `tests/a/test_x.py`. ``, `` (`tests/a/`), `` and `tests/a/test_x.py;` each parse to their bare path;
  - a line naming two paths yields both.

## 12. Owner addendum (2026-10-29): a regeneration keeps its own tests

Seen:
- Regenerating part 11 for a short addendum (§17) rewrote the whole part and dropped 24 of its 85 tests. Among them were all the behaviour tests for §16's push codes (`test_single_reference_push_dry_only`, `test_clock_required_dry_only`, `test_motions_scan_gap`, `test_motions_scan_covered`).
- Part 15 lost 5 of its 15 acceptance tests the same way.

The §9 guard checks the other parts' tests, not the part's own, so nothing stopped either loss.

- **The part's own tests do not shrink.**
  - Before a regeneration, dev_loop records the test functions in the part's own test paths, as node ids without parametrize suffixes, from `pytest --collect-only`.
  - After each attempt, every recorded function must still be collected under the same file and name, unless a brief line `Removes test:` names it (parsed like `Breaks on purpose:`, §11).
  - A missing function fails the attempt the same way a failing test does.
  - Function bodies may change. The names stay.
- **The generator is told up front.** The attempt prompt lists the recorded test functions and says they must all remain: edit them as the brief requires, and add new ones beside them. The retry prompt names the ones that went missing.
- **Tests (fake part, no model calls):**
  - a regeneration stub that deletes one test function fails, and the missing node id is printed;
  - the same stub passes when the brief has `Removes test:` naming that function;
  - a stub that changes a parametrize list but keeps the function passes;
  - the attempt prompt contains every recorded function name.

## 13. Owner addendum (2026-10-29): the guard always runs the browser tests

Seen: part 11 is not a `"browser": true` part, so its baseline and guard ran without `PHYSICS_PROOF_BROWSER=1`, and all 46 player browser tests were skipped. Its regeneration rebuilt `fixtures/run-7`, and five player tests then failed in the full suite after the chain: NaN stage boxes, missing scale chips, a stamp that never appeared.

- **The baseline and the guard always set `PHYSICS_PROOF_BROWSER=1`**, whatever the part's own flag. The part's own tests keep their flag as now.
- **A skipped test is not a protected test.** The baseline line prints how many tests were skipped (`baseline: N passed, K skipped of M collected`). When a guard run skips a test that passed in the baseline, the attempt fails the same way as when that test fails.
- **Tests (fake part, no model calls):**
  - a non-browser part whose stub breaks a browser-marked test of another part fails the attempt;
  - the baseline line contains "skipped".

## 14. Owner addendum (2026-10-29): the repository is ready to publish

The repository is published as one snapshot at `github.com/yunoshev/physics-proof` and submitted to the hackathon. Part 15 owns the files a visitor reads first: `README.md`, `LICENSE`, `.gitignore`, `results/` and `tools/make_readme`.

- **`results/<clip>/`** holds copies of live runs, placed by the owner: `result.json`, `summary.json` and `source.txt`. `source.txt` has one line `title | source URL | rights note`. A clip's video is never in `results/`; only the NASA Moon clip is in the repository, under `fixtures/`.
- **`README.md`** is written by `tools/make_readme` from the repository itself, so its numbers cannot drift. It is in English and at most 160 lines, with these sections in order:
  1. **What it is.** A video goes in, and a player page with a physics verdict comes out. One sentence on the three verdict states. Then one short paragraph: it is one general system, not a script for one clip; nothing in the code is tuned to a particular video; for each clip Muse Spark works out from the frames what a viewer would doubt, finds objects of known size and their sourced sizes, and plans the checks (a free flight against the world's gravity, a size or speed against a sourced human range, a step rate against a natural clock); during the hackathon it was verified end to end on a limited set of clips, listed under Results.
  2. **How it was built.** Built during the Meta hackathon, from 2026-10-27. The briefs in `brief/` are the only human-written part (the owner's requests, turned into briefs by Muse Wonder). All code, tests and the player are generated by Muse Spark through Muse Code (`tools/dev_loop`). Every analysis run is done by Muse Spark with SAM 3.1 through the Meta Model API.
  3. **Run one video.**
     - The exact command `uv run python -m src.cli <video> --runs-dir runs`.
     - The environment variable it needs (`META_API_KEY`) and what the run writes.
     - The command that builds the player page with `src.pagebuild.build_page`.
  4. **Regenerate the code.**
     - The command `tools/dev_loop --part NN`.
     - A table with one row per part in `tools/parts.json`: number, title (the brief's first heading), and the cost of the part's last generation (the last `ITERATIONS.md` line for that part), plus a total row.
     - One line giving the sum of all `ITERATIONS.md` costs as "all generations so far".
  5. **Results.** One row per `results/<clip>/`: title, verdict sentence, measured value with sigma when there is one, cost, turns and wall time. The source URL is a link.
  6. **Meta tools used.** Muse Wonder (wrote the briefs from the owner's requests), Muse Spark (the agent loop, blind checks and code generation), SAM 3.1 (segmentation on the agent's request), and web search with sources.
  7. **Clips and rights.** The Moon clip is NASA footage in the public domain. Every other clip is only linked, with its author.
  8. **License.** MIT.
- **`LICENSE`:** MIT, "Copyright (c) 2026 Andrey Yunoshev".
- **`.gitignore`** also ignores `runs/`, `.dev_loop/` and `.venv/`.
- **Tests (offline):**
  - every part in `tools/parts.json` appears with a cost, and the total equals the sum of the rows;
  - every `results/<clip>/` with a `summary.json` appears with its cost;
  - running `make_readme` twice gives byte-identical output;
  - `README.md` in the repository equals a fresh `make_readme` output;
  - `results/` contains no video files.

## 15. Owner addendum (2026-10-29): the README follows every generation

Seen: right after part 15's own regeneration, `dev_loop` appended its `ITERATIONS.md` line. `README.md` then no longer matched `make_readme`, and `test_readme_matches_make_readme_output` failed in the full suite.

- **`dev_loop` refreshes the README.** After it appends its `ITERATIONS.md` line, it runs `tools/make_readme`, so both files change together.
- **Test (fake part, no model calls):** after a stubbed generation, `README.md` equals a fresh `make_readme` output and contains that generation's cost.

## 16. Owner addendum (2026-10-29): a generation writes only its own paths

Seen: part 09's generation of 2026-10-28 rewrote `fixtures/clip-a/result.json`, which part 12 owns; nothing stopped it, and part 12's next regeneration was refused as "edited by hand".

- **After each attempt, `dev_loop` lists the files the attempt changed.** A changed file outside the part's `owned_paths` (other than `ITERATIONS.md`, `README.md` and `tools/manifest.json`, which `dev_loop` itself writes) is restored to its state before the attempt, and the attempt fails with "wrote outside its paths: <files>". If the part's tests need that file changed, the owner of that file must change it.
- **Tests:** a fake attempt that writes a file under another part's paths fails with that message and leaves the file as it was; one that writes only its own paths passes this check.

## 17. Self-review (2026-10-30): the changes section starts at the last generation, not at the last touch

Seen: the owner reverted one file of part 11's fixture, which a test of another part's suite had rewritten (commit `1db441a`). The changes section then measured "since the last generation" from that revert, because it was the newest commit touching part 11's paths. So the diff held only the newest paragraph (§22). The generation implemented §22 and silently skipped §20 and §21, which had been added between the real last generation and the revert. The hand run then found that the validator ignores `range_checks` entirely.

- **The base of the changes section** is the newest commit that adds a line for this part to `ITERATIONS.md`, which is the commit holding the part's last generation. It is not the newest commit touching the part's owned paths. A revert, a fixture fix or a README refresh by the owner does not move it. With no such commit, the section says so in one line, as now.
- **Test:** in a fixture repo, a part is generated (an `ITERATIONS.md` line is added), its spec gains paragraph A, one of its owned files is then changed by another commit, and its spec gains paragraph B. The built prompt's changes section contains both A and B.

## Owner addendum (2026-11-03, from the published repository): the README opens with the two ideas

Seen: a judge opens the repository, and the README is the first thing they read. The two ideas that set this project apart sat in the middle of section 1 and section 2, without numbers, and the live pages had no link at the top.

- **Above section 1**, `tools/make_readme` writes, in this order: the title; the tagline in bold ("Drop in any video; it asks what is worth proving, measures it, and shows every step on the footage."); a **Live** line with the GitHub Pages address (`https://yunoshev.github.io/physics-proof/`) and one clause on what Play does; a **See it work** line with one link per clip in `results/` to its page (`https://yunoshev.github.io/physics-proof/<slug>/`, the slug in `results/<clip>/page.txt`, placed by the owner), each link text the clip title and its verdict with the number; a **Demo video** line with the link in `results/demo.txt` when that file exists; then two short blocks.
- **"One system for any clip — $X per clip"**: the paragraph that section 1 used to carry (one general system, nothing tuned to a clip, what Muse Spark works out per clip, verified end to end on a limited set of clips listed under Results), then one line "Average cost per clip: **$X** = Muse Spark $a + SAM 3.1 $b + web search $c (average of N live runs, <dates>)". The numbers come from `results/costs.json`, placed by the owner like the run copies: `{"runs": N, "dates": "...", "spark_usd": a, "sam_usd": b, "search_usd": c, "total_usd": X}`. Without that file the line is left out.
- **"Rebuilt from text — $Y for a full rebuild"**: no hand-written code; the 15 briefs are the only human-written part (the owner's requests, turned into briefs by Muse Wonder); Muse Spark generates every part through Muse Code, one part at a time (`tools/dev_loop --part NN`); the full test suite checks each generation; a live run that went wrong changed the brief, not the code. Then "A full rebuild of all 13 parts by Muse Spark: **$Y** (the last generation of each part, section 4)", where $Y is section 4's total.
- Section 1 keeps only the three-state sentence. The 160-line limit still holds.
- Tests: on a fixture tree with `results/costs.json`, the README starts with the title, the bold tagline, the Live line and both blocks in this order, and the two dollar figures equal the file's `total_usd` and section 4's total; without the file the per-clip line is absent.

## Owner addendum (2026-11-04, before the submission): the README states the limits the owner places

Seen: the system reached right verdicts end to end on the Apollo clip and its sped-up copy. On a handheld street-jump clip, four runs ended without a correct verdict. The owner wants the README to say so plainly, in the owner's words, and to change the words when a run on a new clip succeeds.

- `results/limits.md`, placed by the owner like `results/costs.json`, holds one short paragraph of plain text.
- When the file exists, `tools/make_readme` writes right after the "One system for any clip" block a line "**Limits.** " followed by the file's text, unchanged. Without the file nothing is written.
- Tests: on a fixture tree with `results/limits.md`, the README holds "**Limits.** " and the file's text right after the "One system for any clip" block, before "Rebuilt from text"; without the file, no "Limits." line.

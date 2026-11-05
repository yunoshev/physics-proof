# Project Spec — Index

**Working title:** *In Which World Is This True?*
**Deadline:** Nov 4 (Meta hackathon)
**How this spec is used:** The code is written from scratch by a coding agent (Muse, Spark). No hand-editing of code. If output is wrong, we change the relevant spec part and regenerate only the code owned by that part. Each part below lives in its own file for exactly that reason.

## What the product is (one paragraph)

The user supplies one viral video. The system answers not "real or fake" but **"in which world is this motion physically true"** — e.g. consistent with Earth gravity, only consistent with Moon gravity, only consistent if playback was slowed/sped by a factor, consistent with no playback speed at all, or *undetermined*. The result is shown in a **player, not a report**: the same video replays with the body outline, tracked point and trail, fitted curve, and a "ghost" of where real gravity would have put the body drawn on top. The video auto-pauses at key moments (takeoff, apex, landing) with a short caption; the calculation appears step by step beside the video; a big verdict ends the playback. Text and graphics only, no voice. There is **one frozen player template** — per video, only the video file and its data file change.

## The central correction: Spark is the orchestrator

There is **no fixed pipeline** (planner → segmentation → trajectory → scale → physics). Clips differ too much: on the wall run the camera moves and the track must be measured relative to the wall; on the Moon the camera is still. What worked in the first attempt is an **agent loop**:

- **Spark owns the reasoning.** Given the clip and a toolset, Spark decides turn by turn what to do: look at frames (contact sheets, crops), ask SAM 3.1 to segment a phrase over a frame range, look up a real size on the web, ask for a second blind check of what a mask actually covers, run Python in a sandbox, and finally submit the result file.
- **Our code owns the frame:** the loop itself, the tools, a small verified library of physics helpers Spark may import, the budgets, and the checks on the submitted result.
- **Measuring rules** (parts 08–09) are rules the agent must follow, enforced in code wherever they can be, not stages it is marched through.
- **Spark may build itself a missing tool:** it writes a small module plus a test on synthetic data with a known answer; the module becomes importable only if the test passes. Good self-built tools are promoted into the verified helper library later, by a human only.

## Global invariants

1. **Video-only input.** The system receives only the video, under an anonymous file name. No title, no caption, no source, no hints about which test clip it is.
2. **Meta models only.** Every model call goes through Meta models: Spark (`muse-spark-1.3-contributor`) for reasoning/vision/code, SAM 3.1 for segmentation, both via the Meta Model API.
3. **Numbers only from code.** No number in the result may come from a model's head. Every reported quantity is produced by executed Python and carries provenance.
4. **Honest abstention.** If something cannot be measured, the verdict is *undetermined*, with a stated reason. Never guess.
5. **Blind discrimination.** The Apollo 16 jump-salute original and our 1.5× slowed copy must be told apart with no information about which is which. Acceptance numbers (part 03) must never reach the analysis agent.
6. **Worlds come from the scene.** Which worlds are candidates is decided from what is visible in the frames, with the ruling-out evidence stated. See part 02.
7. **Budgets enforced in code.** Turns, SAM frames, searches, mask checks, dollars. Near a limit Spark is told to finish with what it has; at the limit the run ends as "undetermined: budget" with a valid result file.
8. **Runs on the owner's Mac** (M3 Max, 36 GB, macOS 26). Typical analysis 7–11 min; hard limits $2 and 30 min per run for acceptance (part 03).
9. **Keep the code small.** One week. Every enforced rule is code that can be wrong, so each check is the simplest version that catches a failure actually observed (parts 08, 11).

## Parts

| File | Covers (one line) |
|---|---|
| `01-product-and-scope.md` | Who it's for (hackathon judges), the demo surfaces, the user experience end to end, in-scope vs. explicitly out-of-scope. |
| `02-verdicts-and-worlds.md` | Verdict taxonomy, the candidate-worlds-from-the-scene rule, the independent-clock rule for "retimed" vs. "impossible", decision and fit criteria, verdict wording. |
| `03-test-clips-and-acceptance.md` | The three test clips, how blindness is enforced, tolerances, the 3-runs/2-must-pass protocol, and the prompt-leak test. |
| `04-architecture-and-constraints.md` | System shape around the agent loop, spec-part → code-module ownership map, Meta-only model access, Mac runtime, directory layout. |
| `05-ingest-and-anonymisation.md` | Video intake: anonymous renaming, metadata stripping, probing, *measured* fps (not the container's claim), artifact storage. |
| `06-spark-agent-loop.md` | The loop our code owns: turns, context management, tool-call dispatch, budget enforcement, near-limit/at-limit behaviour, result submission. |
| `07-agent-tools.md` | The tool surface: frame/contact-sheet/crop viewing, SAM 3.1 segmentation by phrase over a frame range, web search behind the blindness filter, blind mask check, sandboxed Python, submit. |
| `08-measuring-rules.md` | Rules Spark must follow when measuring: scale, tracked point, camera-relative tracks, unsupported vs. wall-supported motion, independent clocks, uncertainty — enforced in code where possible. |
| `09-verified-helper-library.md` | The small verified physics/geometry helper library Spark may import: contents, accuracy requirements, how helpers are tested. |
| `10-self-built-tools.md` | Spark writing its own module + synthetic-data test; importable only on a pass, scoped to the run; human-only promotion into part 09's library. |
| `11-result-validation.md` | Code-enforced checks on the submitted result: provenance, mask-check gate, world-exclusion evidence, clock logic, internal consistency; our code computes the verdict and sentence. |
| `12-result-data-contract.md` | The single versioned data file per video that the player consumes: trajectory, fit, ghosts, key moments, calculation steps, verdict, provenance; plus the run summary. |
| `13-player-template.md` | The frozen player: first screen, overlay rendering, auto-pause captions, step-by-step calculation panel, verdict screen, gallery. Data-in only. |
| `14-cost-runtime-and-failures.md` | Cost accounting against the Meta API pricing, budget caps and enforcement, runtime limits, retries, logging, failure degradation to *undetermined*. |
| `15-build-test-and-demo.md` | The build loop: PLAN.md, per-part regeneration tool, acceptance runs, screenshot review, iteration log, GitHub Pages publishing after owner approval. |

## Skills (technical notes for the coding agent)

Read alongside the parts. Short, factual, no product decisions in them.

| File | Covers (one line) |
|---|---|
| `skills/meta-api.md` | `/responses` streaming, terminal events, where usage appears, pricing, video input limits. |
| `skills/sam-3-1.md` | One phrase per call, object-id instability, compressed masks, trimming ranges, per-run caching. |
| `skills/macos-sandbox.md` | `sandbox-exec`/Seatbelt facts learned the hard way; nested-sandbox test marking. |
| `skills/video-ffmpeg.md` | Measured fps, duplicate detection, one-frame-in/one-frame-out generation, metadata stripping, HEVC → H.264 for pages. |
| `skills/muse-code-headless.md` | Driving Muse non-interactively: the `muse exec` invocation, JSONL `run_usage`/`run_terminal`, model/effort tiers, no hand edits. |

## Dependencies between parts

- `02` depends on `01`. `03` depends on `01`, `02`.
- `04` depends on `01`–`03`.
- `12` (data contract) depends on `02`, `08`, `11` — it freezes what the agent must submit and what `13` may consume.
- `05` depends on `04`. `06` depends on `04`, `05`. `07` depends on `06`. `08` depends on `06`, `07`; `09` and `10` provide the code `08`'s rules are executed with. `11` depends on `02`, `06`, `08`, `12`.
- `13` depends **only** on `12`. This is deliberate: the player can be built and frozen against fixture data before the agent works.
- `14` depends on `04`, `06`, `07`. `15` depends on all parts and all skills.

```
01 → 02 → 03 → 04 → 05 → 06 → 07 ─┐
                    │         ├→ 08 (rules) ── uses 09 (verified lib)
                    │         │        └────── uses 10 (self-built tools)
                    └→ 14     └→ 11 (result checks) → 12 → 13
                         15 = everything, last
```

## Build order for the coding agent

Defined in detail in part 15. In outline:

0. **Tooling first:** `PLAN.md` (Muse, `muse-spark-1.3`, max effort), then `tools/dev_loop` itself (part 15) — every later step runs through it.
1. **Foundations:** `01`, `02`, `03`, `04` — verdicts, scene/clock rules, and acceptance criteria before any code.
2. **Contract skeleton:** `12` — define the result data file early, with hand-made fixture data.
3. **Player first against fixtures:** `13` — frozen template, testable without any agent.
4. **The frame our code owns:** `05`, `06`, `07`, `09`, `14` — ingest/anonymisation, the agent loop, the tools, the verified helpers, budget/cost scaffolding.
5. **Rules, self-building, checks:** `08`, `10`, `11` — measuring rules, synthetic-test-gated self-built tools, result validation.
6. **End to end:** `15` — golden tests on the three blind test clips, demo rehearsal.

## Regeneration rule

Each part file lists the code modules it owns and the contracts it guarantees. A fix = edit one part, regenerate only its owned modules, re-run the tests named in `15`. If a change would break `12`, the contract version is bumped and both sides (producer checks in `11`, player in `13`) are regenerated in the same step. Generated files are never edited by hand; the build tool in part 15 refuses to continue if one was.

## Status

- `01`–`15`: written.
- `skills/`: written from the owner's API notes and first-attempt lessons.
- Remaining owner inputs: any API-note updates go into `skills/meta-api.md` or `skills/sam-3-1.md` first, then into the owning part.

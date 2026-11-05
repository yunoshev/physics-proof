# 04 — Architecture and Constraints

**Owns:** the overall system shape, the code-module ownership map, and the hard platform constraints. Every other part builds inside this frame; if a part seems to require breaking this file, this file is changed first.

## 1. System shape

There is **no fixed measurement pipeline**. The system is an agent loop (part 06) in which Spark orchestrates tools (part 07) under measuring rules (part 08), using a verified helper library (part 09) and optionally self-built tools (part 10). Our code owns the loop, the tools, the budgets, the sandbox, and the validation of the submitted result (part 11). Spark owns the reasoning: what to look at, what to segment, what to measure, in what order.

```
one command (path to video)
        │
        ▼
┌──────────────────┐   anonymous input, timing report   ┌────────────────────┐
│ 05  Ingest       │ ─────────────────────────────────▶ │ 06  Agent loop     │
└──────────────────┘                                    │  (Spark, tools,    │
                                                        │   budgets, checks) │
┌──────────────────┐   masks, measurements, evidence    └─────────┬──────────┘
│ 07  Tools        │ ◀───────────────────────────────────────────┘ tool calls
│ 08  Rules        │        rules enforced in code (checked at submit, part 11)
│ 09  Helpers      │        imported by sandboxed code, never re-implemented
│ 10  Self-built   │        synthetic-test-gated, run-scoped
└──────────────────┘
        │ submit
        ▼
┌──────────────────┐   valid result file (part 12)      ┌────────────────────┐
│ 11  Validation   │ ─────────────────────────────────▶ │ 13  Player (frozen)│
└──────────────────┘                                    └────────────────────┘
```

## 2. Platform constraints (hard)

- **Machine:** Apple M3 Max, 36 GB RAM, macOS 26. Everything runs locally except model calls. No cloud compute, no Docker assumption (macOS sandboxing, part 07).
- **Models — Meta only.** Every model call goes to the Meta Model API at `https://api.meta.ai/v1` (OpenAI-compatible `/responses`, streaming).
  - Spark: `muse-spark-1.3-contributor`, priced $0.10 input / $0.002 cached / $0.20 output per 1M tokens. Used for: the agent loop, blind mask checks, the search-blindness classifier, helper calls.
  - SAM 3.1: remote, through the same API. $0.20 per 1000 frames, **minimum 50 frames billed per call**.
  - Detailed API quirks (from the owner's technical notes) are normative once pasted in and are recorded in parts 06/07/14 as applicable.
  - (Build-time code generation uses Muse with its own model tiers — `skills/muse-code-headless.md`. That is the workshop, not the product, and never ships in the runtime.)
- **Non-model tooling is unrestricted plain code:** ffmpeg/ffprobe, numpy, OpenCV, scipy and similar local libraries are fine. They are code, not models.
- **Web access** exists only through the API's `web_search` tool, behind the blindness filter (part 07). Sandboxed Python has no network (part 07).
- **Cost/time envelope:** typical analysis 7–11 min, target ≈ $0.10–0.20; hard acceptance ceilings $2 and 30 min per run (part 03). Budget mechanics in part 14, enforcement in part 06.

## 3. Module ownership map

Each module is regenerated from exactly one part. A module may import another part's *contracts*, never its internals across a boundary marked ✗.

**Test ownership (fixed rule):** tests mirror the code they test, and belong to the same part as that code. A package `src/<name>/` owns `tests/<name>/`; a top-level file `src/<name>.py` owns `tests/test_<name>.py`; non-`src` modules own the test path listed in the table. No part may create test files outside its listed paths, and regenerating a part deletes and recreates **only its own** test files. Parts 01 and 02 own no code and no test files — their rules are tested through the parts that implement them (02 through part 11, in `tests/validate/`). Part 15 owns only the dev-loop's tests and the acceptance harness — **not** the other parts' tests.

**Tests pass together, not only alone (owner note 2026-10-27).** The whole suite runs in one pytest process from the repo root, and it must pass there as well as under each part's own test command. A test module **never imports `conftest` by name** (`from conftest import make_blind`). With several `conftest.py` files in one process, that name resolves to whichever was loaded first. On int, `tests/tools/test_submit.py` failed this way inside the full suite while passing alone. Helpers shared by a part's tests are pytest fixtures in that part's own `conftest.py`, factory fixtures where a test needs to call them with arguments. **Test module basenames are unique across `tests/`.** Test directories are not packages, and pytest's default import mode needs unique basenames. Name a file after its own subject with the package prefix where needed (`test_tools_contract.py`, not a second `test_contract.py`). Seen: part 07 added `tests/tools/test_contract.py` beside part 12's `tests/contract/test_contract.py`, and the whole suite stopped at collection.

| Module | Owned by | Responsibility (one line) | Owned test files |
|---|---|---|---|
| `pyproject.toml` | 04 | The Python 3.13 project: the only place libraries are declared — runtime `numpy`, `scipy`, `opencv-python-headless`; tests `pytest` and `playwright` (browser tests, run against the installed Google Chrome) in the `dev` dependency group. Every part's tests run in this environment, from the repo root, as `uv run python -m pytest <paths>`; tests import runtime code as `src.<module>` and never edit `sys.path`. A part that needs another library changes this row first. `uv.lock` is local, not committed. | (checked by every part's tests) |
| `src/cli.py` | 04 | The one command: path in → run → player-ready output. | `tests/test_cli.py` |
| `src/config.py` | 04 | All limits, prices, model IDs, paths. Nothing hard-coded elsewhere. | `tests/test_config.py` |
| `src/ingest/` | 05 | Anonymisation, probing, measured fps, timing report. | `tests/ingest/` |
| `src/loop/` | 06 | Agent loop, context management, budget ledger, termination. | `tests/loop/` |
| `src/tools/` | 07 | Frame viewing, SAM 3.1, blind mask check, filtered search, sandbox, submit. | `tests/tools/` |
| `src/clients/` | 04 | Live adapters to the Meta Model API (Spark agent turns, blind checks and classifier, SAM 3.1, web search, Files API) behind the injection interfaces of parts 06 and 07; the only code that talks HTTP. | `tests/clients/` |
| `src/rules/` | 08 | Measuring-rule check functions (pure, testable) invoked by tools and by part 11. | `tests/rules/` |
| `prompts/measuring_rules.md` | 08 | The agent-facing statement of the rules (code checks are authoritative). | (with `src/rules/`) |
| `src/helpers/` | 09 | Verified physics/geometry library Spark may import. | `tests/helpers/` |
| `src/selfbuilt/` | 10 | Self-built tool gating, synthetic tests, run-scoped registry. | `tests/selfbuilt/` |
| `src/validate/` | 11 | Submit-time result checks; deterministic verdict computation. | `tests/validate/` |
| `src/contract/` | 12 | Result-file schema, versioning, fixture data. | `tests/contract/` |
| `player/` | 13 | The frozen static player template. | `tests/player/` |
| `src/pagebuild/` | 13 | Per-clip page assembly (inline data, H.264 copy, small images) and gallery build; invoked by part 15. | `tests/pagebuild/` |
| `src/accounting/` | 14 | Cost/runtime accounting, logging, retry policy. | `tests/accounting/` |
| `tools/dev_loop` | 15 | Regeneration/acceptance/page-build driver; refuses hand-edited generated files. | `tests/dev_loop/` |
| `tests/acceptance/`, `scripts/demo/` | 15 | Acceptance harness (incl. prompt-leak test), demo build. | (the harness itself) |
| `fixtures/source/` | owner | Owner input, never generated or edited by a part: the clip-A test-run output used to build the real-data fixture (part 12 §11). | — |
| `fixtures/clip-a/` | 12 | The converted real-data fixture (`result.json`, `summary.json`), regenerated by part 12's converter. | `tests/contract/` |
| `scripts/make_clips.py` | 03 | Downloads Apollo source and produces clips A and B. | `tests/test_make_clips.py` |

Two apparent exceptions, both deliberate:

- **Promotion (part 10):** when a human promotes a self-built tool, its module moves into the helper library and its test moves to `tests/helpers/` — ownership transfers to part 09 with the code.
- **Acceptance (part 03):** the harness in `tests/acceptance/` is owned by part 15 but *implements* part 03's criteria; if part 03's criteria change, the harness is regenerated under part 15 in the same step.

`PLAN.md` and `ITERATIONS.md` are process artefacts owned by part 15's workflow, not code modules; they are never generated files in the hash-manifest sense of part 15 §2.

Boundary rules:

- `src/loop` may call `src/tools` only through the tool schemas of part 07, and `src/validate` only through part 11's submit interface.
- `src/tools` (sandbox) may expose to agent code only: the run workspace and `src/helpers` (plus run-gated `src/selfbuilt` modules, part 10). ✗ Never the repo, the tests, or `brief/`.
- Test code may import runtime code to *check* it (`tests/acceptance/` may import anything in the runtime); ✗ no runtime module may import any `tests/` path or read `scripts/make_clips.py` ground truth.
- `player/` and `src/pagebuild/` read only part 12's result file plus the artifacts it names in `provenance`. ✗ No other coupling.

## 4. Run directory layout

```
runs/<run-id>/                  # one per analysis, self-contained, disposable
  input/clip.<ext>              # the anonymised video (part 05) — all the agent ever sees
  input/timing.json             # measured fps, duplicates, cuts (part 05)
  workspace/                    # agent scratch: frames, masks, code, intermediate results
  artifacts/                    # named outputs of every tool call (part 07)
  logs/                         # operator-only: original filename, hashes, full API log
  result.json                   # final, validated, part-12 contract file
```

`logs/` is never visible to the agent or the sandbox. Run IDs carry no clip identity (timestamp + random suffix). A run can be deleted wholesale with no effect on any other run; the only cross-run artefact is the human-promoted helper library (part 10).

## 5. Determinism of the frame, freedom of the agent

Our code must behave identically for identical *tool traffic*; the agent's choices may vary run to run. Acceptance (part 03: 2 of 3 runs) is written for exactly this split. Anything that must *always* hold — budgets, provenance, blindness, anonymity, rule checks marked "enforced in code" — lives in our code, not in the prompt. The prompt may *state* a rule, but no invariant may depend on the model obeying prose.

## 6. Owner addendum (2026-10-27): live clients and the one command

Every external call is injected: `run_loop(spark_client=…, blind_spark_client=…, classifier=…, sam_client=…, search_client=…)` (part 06) and the tools (part 07) take callables. No part wrote the real ones, so `cli` ran every clip into "undetermined: no model configured". This part owns them.

- **`src/clients/`** implements each callable against the real API, exactly to the interface its consumer already defines: read the docstrings in `src/loop/` and `src/tools/` and conform to them. Never edit another part's files. When an interface cannot carry something the API needs, adapt inside the client and name the gap in your final message.
- **Protocol facts** are in `skills/meta-api.md` and `skills/sam-3-1.md` (Protocol sections). Follow them literally:
  - streaming `/responses`, flat strict tools, stateless turns with `store:false`;
  - the SSE parsing and terminal-event rules, and the retry policy;
  - Files API upload and delete;
  - SAM via the `sam-3.1` model, decoded with `meta-sam-parser` (never a hand-written decoder);
  - web search as the built-in `web_search` tool.
- **Models and limits** come from `src/config.py`: the agent and the sub-calls use the contributor tier, and the agent's `max_output_tokens` is 32768.
- **Usage goes to the ledger** from the terminal event only (part 14). SAM is billed `max(50, frames, video_frames_processed)`, web search per call.
- **`cli`** builds the clients from `META_API_KEY` (fallback `MODEL_API_KEY`) and passes them to `run_analysis` → `run_loop`. No key → the existing synthesis path with reason "no model configured". The key never reaches logs, exceptions, results, prompts or the run folder.
- **One command:** `uv run python -m src.cli <video>` analyses a clip end to end and prints the run folder.
- **`pyproject.toml`** adds `meta-sam-parser` (Meta's SAM output parser; note its licence in the README) and one HTTP library (`httpx`).
- **Tests (`tests/clients/`) are offline.** They run against a local stub HTTP server on 127.0.0.1 that serves synthetic SSE streams built from the skills' grammar:
  - `completed`, `incomplete` (max_output_tokens), `failed`, a stream with no terminal event (retried), 429 with `Retry-After` (honoured), 402 (not retried);
  - a function-call round trip (`function_call` → `function_call_output`);
  - usage extraction without double counting;
  - Files upload and delete;
  - a SAM text with two objects on two frames, mapped back by the cut's start frame. Its mask payload comes from `meta-sam-parser` itself if the package can encode; otherwise the decode assertion is skipped with a reason and the live smoke covers it.
- **Live smoke** (`tests/clients/test_live.py`) runs only with `PHYSICS_PROOF_LIVE=1` and costs < $0.05: one contributor text call, one SAM call on a generated 60-frame clip of a moving white square (mask found, centroid moves), one web search. Without the variable it is skipped with a reason.

**Addendum (2026-10-28, from the first live run).** The first live run died on turn 2 with `HTTP 400: content type input_text is not valid on assistant messages`: the Spark client converted the loop's assistant history into `input_text`. The offline tests passed because the stub accepted anything. Now required:

- **The stub validates like the live API.** It rejects, with the live API's 400 messages:
  - role/part-type mismatches (skill: "Part types by role");
  - a `function_call_output` whose `call_id` was never issued;
  - strict tools lacking `additionalProperties:false` or a complete `required`;
  - any `tool_choice` other than `"auto"`;
  - a missing `stream:true`.
- **An offline end-to-end test** runs the real `run_loop` (part 06) with the real clients from `src/clients/` against that stub, for at least four turns:
  1. a commentary message plus a `function_call` to a frame-viewing tool, whose result carries an image;
  2. a second tool call;
  3. a plain text reply with no tool call, which the loop must answer;
  4. a final submit.

  Every request the loop sends is validated by the stub. This is the test the first live run would have failed.
- **A 4xx other than 429 is not a transport failure.** The client raises it in a way the loop does not retry as network: use the error class the loop already distinguishes, or the loop's documented hook. A 400 is a bug in our request; retrying it three times hides it.

**Addendum (2026-10-27, from the third live run).**
- The Spark client sends the tool definitions it is given, which come from part 07's export. It keeps no copy of its own; run 3 had two diverging copies.
- It builds the history as `skills/meta-api.md` says for stateless turns, replaying `function_call` items and pairing each with its `function_call_output`. The local stub rejects a `function_call_output` whose `call_id` has no matching `function_call` earlier in the input (the pairing the skill describes).
- The offline end-to-end test asserts that turn 2's request carries turn 1's call.

**Addendum (2026-10-28): one Python, 3.13.** `pyproject.toml` pins `requires-python = "==3.13.*"`. A bare `uv run` (as coding agents type it) must pick 3.13 too. Seen: with `>=3.13`, an agent's `uv run pytest` built `.venv` on Python 3.14. The test command, `uv run --python 3.13`, then had to rebuild it, failed on a non-empty directory, and three attempts of part 07 ended without one test running.

## 7. Owner addendum (2026-10-28): the live classifier asks part 07's question

Seen after part 07 §17 was generated: part 07 moved its pattern screen into its own answer-seeking list and pinned a new classifier question as `src.tools.web_search.CLASSIFIER_QUESTION`. The live classifier in `src/clients/blind.py` still sends its own older wording ("identify a specific video, event, or source"). That wording flags any query that names what the agent identified in the frames (a mission, a person, a place), so the agent still cannot look up a suited height or an equipment size, which part 01's decision of 2026-10-28 allows.

- **One wording.** `make_classifier` sends `src.tools.web_search.CLASSIFIER_QUESTION`, imported from part 07's interface, never copied or paraphrased. It keeps everything else: the query text only, strict JSON verdict, `"yes"`, `"no"` or `"uncertain"`, doubt and failures fail closed.
- **`BLINDNESS_PATTERNS` in `src/config.py`** follows part 07 §17. It drops names, missions and places: `apollo`, `alsj`, the astronaut names, `lunar surface journal`. It keeps forms that name the clip or its answer: the source's file name `a16salute` and `moon landing hoax`.
- **Tests (`tests/clients/`, `tests/test_config.py`):**
  - the stub sees a classifier request whose text starts with `src.tools.web_search.CLASSIFIER_QUESTION`;
  - the old wording "event, or source" appears nowhere in `src/clients/`;
  - `"apollo"` and the astronaut names are absent from `BLINDNESS_PATTERNS`, while `a16salute` and `moon landing hoax` are present.

## Owner addendum (2026-10-28): cross-part interfaces are pinned in briefs

A part imports another part's code only through the names that part's brief pins as its interface (for example part 11 §10), never through private names (`_x`) or module internals. When a brief pins an interface, regenerating that part keeps it exactly. Seen: part 11 regenerated without `write_result`, and part 06's synthesis path broke.

## 8. Owner addendum (2026-10-29): room to finish a run

Seen: Moon run 13 and wall run 4 both ended `undetermined: budget wall_time ≥ 1800`, at 33–42 s a turn (55 and 44 turns). Each had made a dry run whose errors could be fixed in a few turns.

- `HARD_CAP_WALL_S = 45 * 60` and `MAX_TURNS = 90`. The dollar cap stays at $2.
- The cost and time line in §2 now reads: hard ceilings of $2 and 45 min per run.
- **Test:** `tests/test_config.py` pins the new values.

Breaks on purpose: `tests/loop/` — its tests pin "turn 1/60" and "wall_time ≥ 1800", and part 06 updates them next (part 06 addendum of 2026-10-29)

## Owner addendum (2026-10-30, from runs on a loaded machine): 60 minutes per run

On a machine shared with other work, one agent turn takes about 55 s, and the Describe and Wonder calls take the first minutes. That leaves about 44 turns in 45 minutes, and wall runs 8–10 and hand runs 2–4 ended with errors still to fix after their second dry run.
- `HARD_CAP_WALL_S = 60 * 60`. `MAX_TURNS` stays 90 and the dollar cap stays $2.
- The cost and time line in §2 now reads: hard ceilings of $2 and 60 min per run.
- Tests read the constant, never 45 or 2700.

## Owner addendum (2026-10-31, from wall runs 12–13 and hand runs 6–7): the blind client answers line checks too

Seen: all six live `check_line` calls (part 07 §19) failed with `blind_malformed`. The blind client returns the mask-check shape `{description, alternatives}` under its fixed `blind_check` schema, while `check_line` expects `{descriptions: [...]}` for its look and `{results: [...]}` for its match. The tests passed because each part stubbed the other.

The blind client takes a `kind` in the request. Without one, it is a mask check as now.
- **`kind: "line_look"`**: `{kind, image, question, n_lines}` → `{descriptions: [n strings], usage}`. The strict schema is an object with `descriptions`, an array of strings with `minItems` = `maxItems` = `n_lines`. The image goes in as for a mask check. No extents are sent.
- **`kind: "line_match"`**: `{kind, descriptions, claims, question}`, with no image → `{results: [{agrees: bool, why: string}], usage}`. The strict schema has `minItems` = `maxItems` = the number of claims. The text sent numbers the pairs: "Line 1 — description: …; claim: …". Without an image, the request is text only, and a missing image is not an error for this kind.
- **Errors:** a wrong count or an empty string raises `FailedCallError` with the reason, as for a mask check. The blindness rules hold: no history, and no claim ever goes with the image.
- **Tests (stub server):**
  - each kind sends its schema and returns the documented shape;
  - a `line_look` request carries the image and no claims, and a `line_match` request carries no image;
  - a count mismatch raises.

## Owner addendum (2026-11-01, from four runs on the Moon and sped-up Moon clips): the agent thinks at max effort, the blind checks at high, 90 minutes per run

Seen: of four runs on one clip, one was right. The errors were judgment errors, for example a reference measured and then left out because it disagreed. The owner asked for the strongest reasoning in every Spark call that judges; speed is secondary. A probe on 2026-11-01 found that a `/v1/responses` call without `reasoning` runs at `high` (the response echoes `{"effort": "high"}`), and that `{"effort": "max"}` is accepted and echoed.

- `src/config.py` gains `SPARK_REASONING_EFFORT = "max"` and `BLIND_REASONING_EFFORT = "high"`.
- **Agent turns** (`src/clients/spark.py`): every request body carries `"reasoning": {"effort": SPARK_REASONING_EFFORT}`.
- **Blind calls** (`src/clients/blind.py`: the mask check, the line look, the line match and the search classifier): `"reasoning": {"effort": BLIND_REASONING_EFFORT}` in place of `low`.
- `BLIND_MAX_OUTPUT_TOKENS = 16384`: thinking counts toward the output limit (part 06 §3), and 4096 cut replies at high effort. `MAX_OUTPUT_TOKENS` stays 32768.
- `HARD_CAP_WALL_S = 90 * 60`: thinking makes each turn longer. `MAX_TURNS` stays 90 and the dollar cap stays $2. The cost and time line in §2 now reads: hard ceilings of $2 and 90 min per run.
- Web search calls (`src/clients/search.py`) stay as they are.
- **Tests:** the agent-turn request body has `reasoning.effort` equal to `SPARK_REASONING_EFFORT`; each of the four blind request bodies has `reasoning.effort` equal to `BLIND_REASONING_EFFORT` and `max_output_tokens` equal to `BLIND_MAX_OUTPUT_TOKENS`; no request body in `src/clients/` contains `"low"` as an effort. Tests read the constants, never "max", "high", 90 or 5400.

## Owner addendum (2026-11-01, from four runs at max effort after §46): room for the checks, 150 turns and 150 minutes per run

Seen: in the last four runs no verdict was wrong, but three of four ended undetermined. Each reached the 80 % warning (72 of 90 turns, or 72 of 90 minutes) after only one or two dry runs, and the loop submitted for it while the remaining errors were simple to fix: a reference measured on its push-off frame (`REFERENCE_SHAPE_UNSTABLE`), two reference masks without a common frame, a search file cited as a mask check. At max effort the agent uses more turns and more time per run, and speed is secondary.

- `MAX_TURNS = 150` and `HARD_CAP_WALL_S = 150 * 60`. `WARN_RATIO` stays 0.80 and the dollar cap stays $2. The cost and time line in §2 now reads: hard ceilings of $2, 150 turns and 150 min per run.
- Tests read the constants, never 90, 150 or 9000.

## Owner addendum (2026-11-01, from four runs with 150 turns): eight mask checks per run

Seen: a Moon run ended on one reference. Its absence reason said the suited figure's whole-body mask "has no blind check left in budget": `MAX_MASK_CHECKS = 4` was spent on the backpack and on masks it replaced. A blind check is one short Spark call.

- `MAX_MASK_CHECKS = 8`. Tests read the constant, never 4 or 8.
- **The line-look schema carries the view and the dimension** (part 07 §22): each per-line object of the `line_look` answer gains `view` and `dimension` (strings), and the blind client returns them with `description`. Test: a stub line-look answer with `view` and `dimension` comes back from the client with both.

## Owner addendum (2026-11-02, from four runs after part 11 §49): 210 minutes of wall time

Seen: four runs share one machine and its segmenter. Two of them reached the 80 % wall-time point (120 of 150 minutes) at turns 68 and 84 of 150, and the loop submitted for them. One had only `RANGE_SOURCE_MISSING` left, the other two line and two alternative errors. Each was a few turns of work. Part 11 §50 adds a blind line check per reference, which takes more time.

- `HARD_CAP_WALL_S = 210 * 60`. `MAX_TURNS` stays 150, `WARN_RATIO` stays 0.80 and the dollar cap stays $2.
- Tests read the constants, never 150, 210 or 12600.

## Owner addendum (2026-11-03, from four runs at once on a third clip): 300 minutes and 220 turns

Seen: four runs shared one machine and its segmenter. A turn took about 106 s, against about 50 s for a run alone. Both runs on a street-jump clip reached the 80 % wall-time point at turns 93 and 98, and the loop submitted for them with work left. One had already fitted the flight (g about 10.2 m/s²) but still had a reference measured in a crouch and range bounds without sources. The other had a camera reference that moves. From now on the owner runs one clip at a time. A run alone reaches 150 turns before it reaches the wall cap, so both limits rise.

- `HARD_CAP_WALL_S = 300 * 60` and `MAX_TURNS = 220`. `WARN_RATIO` stays 0.80 and the dollar cap stays $2.
- Tests read the constants, never 150, 210, 220, 300 or 18000.

## Owner addendum (2026-11-03, from the full suite after the 220-turn change): 240 turns

Seen: with `MAX_TURNS = 220` one loop test failed. Part 06 closes exploration when the turn budget reaches one third, and 220 / 3 is not a whole turn, so the loop closed it one turn after the test expected. A try with 225 broke the half-way notice test the same way (225 / 2 is not a whole turn).

- `MAX_TURNS = 240`, a multiple of 2, 3 and 5, so one third, one half and 80 % of the turn budget are whole turns. Everything else in the addendum above stays (300 minutes, `WARN_RATIO` 0.80, $2).
- Tests read the constants, never 150, 210, 220, 225, 240, 300 or 18000.

## Owner addendum (2026-11-03, from a street-jump run): twenty mask checks, so line checks cannot starve mask checks

Seen: `check_line` (part 07 §19) debits the same mask-check counter as `check_mask`, two per call, and allows up to 6 calls. A street-jump run checked its lines first: 6 line checks used 12 of the 8 mask checks, `check_mask` closed, and the run could never record the reference mask checks that part 11 requires. Three dry runs in a row returned the same `MASK_CHECK_MISSING` errors.

- `MAX_MASK_CHECKS = 20`: 8 for `check_mask` plus 12 for the most `check_line` can use. Everything else stays.
- Tests read the constant, never 4, 8 or 20.

## Owner addendum (2026-11-04, from street-jump run 80): 360 minutes

Seen: a street-jump run alone made its first dry run at turn 89, after 150 minutes, and got four fixable errors. The loop submits by itself at 80 % of the wall cap, 240 minutes, which left about 30 turns to fix them.

- `HARD_CAP_WALL_S = 360 * 60`. `MAX_TURNS` stays 240, `WARN_RATIO` stays 0.80, the dollar cap stays $2, `MAX_MASK_CHECKS` stays 20.
- Tests read the constants, never 300, 360, 18000 or 21600.

## Owner addendum (2026-11-04, from street-jump run 81): 480 minutes

Seen: with 360 minutes, a street-jump run again made its first dry run near turn 96, after about 150 minutes, and got six fixable errors. Turns took 90 seconds on average, so 288 minutes leave about 90 turns to fix them, and the run before needed more.

- `HARD_CAP_WALL_S = 480 * 60`. `MAX_TURNS` stays 240, `WARN_RATIO` stays 0.80, the dollar cap stays $2, `MAX_MASK_CHECKS` stays 20.
- Tests read the constants, never 300, 360, 480, 18000, 21600 or 28800.

## Owner addendum (2026-11-04, from street-jump run 82): an agent request may name its reasoning effort

Seen: in run 82, 97 % of Spark's output was reasoning, about 8 500 tokens a turn at about 96 tokens a second, so a turn took about 100 s and 134 turns took 244 minutes. Part 06 now asks for max effort only on the turns where judgment is made.

- `src/clients/spark.py`: the body's `reasoning.effort` is `request["reasoning_effort"]` when that value is one of "low", "medium", "high", "max"; otherwise it is `SPARK_REASONING_EFFORT`. `SPARK_REASONING_EFFORT` stays "max". Blind calls keep `BLIND_REASONING_EFFORT`. Nothing else changes.
- Tests: a request with `"reasoning_effort": "high"` sends `"effort": "high"`; a request without the field, or with "fast", sends `SPARK_REASONING_EFFORT`. Tests read the constant, never "max".

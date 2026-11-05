# 07 — Agent Tools

**Owns:** `src/tools/`. The complete tool surface Spark orchestrates with. A tool is a contract: typed inputs, typed outputs, named artifact files, a budget price debited by the loop (part 06). **Lesson sources:** "tool results must name their files"; "the sandbox could read the whole repo — including the expected answers"; scale lessons requiring a blind second look (part 08 enforces the *use*, this part builds the *means*).

## 1. Rules for every tool

1. **Every result names its files.** A tool result is JSON: `{ok, summary, files: [...], metrics: {...}, error?: {...}}`. Any image, mask, table, or plot lives in `artifacts/` under a deterministic name (`t<turn>_<tool>_<n>.<ext>`); the result references it. A result that produces data but names no file is a bug in the tool.
2. **Tools measure and fetch; they do not decide.** No tool returns a verdict, a world, or a fitted `g` presented as fact. (Helpers, part 09, compute what agent-written code asks them to compute.)
3. **Tools validate their inputs in code** (ranges, file existence, frame bounds) and fail with structured errors — the agent should never be able to crash a tool or escape the workspace through a path.
4. All paths in inputs/outputs are **run-relative** and start with `input/`, `workspace/` or `artifacts/` (§10). Absolute paths and `..` are rejected.

## 2. `view_frames` — looking at the clip

Inputs: frame range and stride *or* explicit frame indices; optional crop (normalised coordinates); layout (contact sheet grid or sequence). Outputs: JPEG contact sheet(s)/crops in `artifacts/`, plus a text index mapping each cell to frame number and measured timestamp (from `timing.json` — never `index/claimed_fps`). Frame indices out of range and ranges spanning a confirmed cut are reported, not silently served. This is the agent's only eyes; crops are how it inspects mask quality, scene evidence for world exclusion (part 08), and reference candidates.

## 3. `segment` — SAM 3.1 by phrase over a frame range

Inputs: a text phrase (e.g. "the astronaut", "the wall"), a frame range. Behaviour:

- Calls remote SAM 3.1 via the Meta API. **Billing reality enforced in code:** every call bills ≥50 frames; the tool (a) refuses or warns on ranges < 50 frames unless the agent explicitly confirms, (b) debits `max(50, frames)` to the ledger, (c) returns billed vs. requested counts.
- Outputs: `masks.npz` (per-frame mask arrays + frame indices + timestamps), preview overlays (a sparse set of frames with the mask drawn) as images, per-frame mask area/bbox/centroid table (CSV/JSON) — all named in the result.
- No interpretation: the tool reports *what pixels*, never *what object*. Whether the mask covers what the phrase meant is established by §4, not assumed here.

## 4. `check_mask` — the blind second look

**Purpose (scale lesson):** a reference size is only as good as knowing what its mask actually covers. This is a **separate Spark call with no run context** — a fresh conversation receiving only: one overlay image (mask drawn on its frame), the mask's pixel extents, and a neutral question. It returns a structured description of **what the mask covers** (which part of the visible object, which edges it includes/excludes — e.g. "covers the pack and the box mounted above it", "misses the spoiler at the rear"), plus alternative readings where the covering is ambiguous.

- It is deliberately **not** asked what the object *is*: it reports coverage, not identity. (Lesson: the same Apollo mask was read as "backpack alone, 0.66 m" vs. "backpack plus top unit, 0.91 m" — a 1.4× swing in `g`. Coverage ambiguity like this must surface here so part 08 can price it into σ.)
- Blindness is by construction: the call is built from the mask artifact alone; the loop (part 06) gives this tool's conversation no history, no phrase, no hypothesis, no clip name.
- The tool debits the mask-check budget; part 03 requires ≥1 per run and part 11 verifies the record exists.

## 5. `web_search` — size lookup behind the blindness filter

The only web access, via the API's `web_search`. Every query passes the **blindness filter** before execution, in code:

1. **Pattern screen:** reject queries containing the run's anonymous filename, hashes, or known clip-identifying forms (titles, "Apollo", astronaut names, the specific viral-clip phrasing — the pattern list lives in config owned by this part and is itself tested by part 15; it must be *generic in structure* — blocking identifying-the-clip, not blocking physics).
2. **Context-free classifier:** a separate Spark call that sees **only the query text** (no conversation, no clip, no run state) and answers one question: "is this query trying to identify a specific video/event/source or its known answer, rather than look up generic facts (object dimensions, natural step rates, material sizes)?" Reject on yes/uncertain.

Allowed and expected: real-world sizes of generic objects, natural human step-rate ranges, standard dimensions. Rejected queries return a structured refusal (the agent may rephrase generically). All queries and filter decisions are logged for the prompt-leak audit (part 03 §5).

## 6. `run_python` — sandboxed execution

Agent-written Python, executed under macOS `sandbox-exec`:

- **Read:** only `workspace/`, `artifacts/`, `input/` (read-only), and `src/helpers/` (read-only; part 10 may add run-gated modules). **Write:** `workspace/` and `artifacts/` only. **Network: none.** Environment scrubbed (no API keys, no home directory). CPU/wall timeout and memory cap from config.
- This directly closes the first-attempt hole where the sandbox could read the whole repo, including expected answers: the profile is deny-by-default with explicit allows, and part 15 tests that `../brief`, `../tests`, and the original input path are unreadable from inside.
- Stdout/stderr are returned truncated, **plus** a list of files created/modified (names + sizes) — the "name your files" rule applied to agent code too. The agent imports helpers (part 09) rather than re-deriving fits; nothing it prints is a "result" until submitted and validated (part 11).

## 7. `submit` — handing in evidence

Inputs: the structured evidence object defined by part 12 (segments with fit outputs and artifact pointers, references with mask-check pointers, world exclusions with frame evidence, clock readings, error budget, provenance). The tool writes it to `workspace/submission.json`, invokes part 11's validator, and returns either acceptance (loop ends; part 11 computes verdict + sentence, part 06) or the structured error list (bounded retries, part 06 §2). The agent cannot write `result.json` directly — `submit` is the only path, so no run can bypass validation.

## 8. What is *not* a tool

No "fit gravity" tool, no "decide world" tool, no "generate ghost" tool with baked choices: those compositions are the agent's reasoning, executed through `run_python` + helpers, checked by rules (part 08) and validation (part 11). Keeping them out of the tool layer is what keeps Spark the orchestrator rather than a form-filler.

## 9. Owner addendum (2026-10-28, from the second live run)

The second live run had the agent call `run_python` 33 times; every call ended `sandbox-exec: execvp() of '<repo>/.venv/bin/python3' failed: Operation not permitted` (exit 71). The profile correctly hides the repository, but the interpreter and its libraries live inside it, so sandboxed Python never started. The sandbox tests still passed: they only assert that "READABLE:" is *not* printed, and a dead interpreter prints nothing.

- **The sandboxed interpreter lives outside the repository.** On first use, create a dedicated environment under the user cache (`~/Library/Caches/physics-proof/sandbox-env-<hash>`; the hash covers the runtime dependency list and the Python version). It holds the runtime libraries (`numpy`, `scipy`, `opencv-python-headless`) and is reused across runs. The profile allows read and exec for that environment and for the real paths of the base interpreter and its standard library (resolve symlinks). The repository stays unreadable, except `src/helpers/` read-only as §6 says, and the agent's code imports the helpers from there.
- **Every live sandbox test has a positive control.** The probe first prints `ALIVE`, imports `numpy`, `scipy`, `cv2` and the helpers package, and prints their versions; the test fails unless those lines are present, and only then checks the denials. Add a probe that writes a file to `workspace/` and reads `input/timing.json`, both of which must succeed.
- **These tests run for real during generation.** This part is generated outside the coding agent's own shell sandbox (registry flag, part 15 §8), so `sandbox-exec` works and the agent runs the live probes itself. A skipped live probe is reported as skipped, never as passed.

## 10. Owner addendum (2026-10-27, from the third live run)

The third live run spent all 60 turns without one `segment` call. 46 of them went to hunting through the disk for the evidence format, and the sandbox let the hunt succeed. The agent's code listed and read sibling runs' `result.json`, the parent directory of the runs, `/private/tmp`, and a log of another program. By the profile it could also have read `~/.config/…`, where the API key lives. The cause is one line in the profile, `(allow file-read* (subpath "/"))`, while §6 says the opposite. The live probe checked only the repository paths, so it passed.

- **Reads are an explicit allow-list.** File data may be read only from:
  - the run's `input/`, `workspace/`, `artifacts/` (not `logs/`);
  - `src/helpers/` (read-only);
  - the sandbox environment (§9);
  - the real paths of the base interpreter and its standard library;
  - a short named list of system paths Python needs on macOS: `/System/Library`, `/usr/lib`, `/usr/share`, `/private/var/db/timezone`, `/dev/null`, `/dev/urandom`.
  
  `file-read-metadata` (stat) may stay global, so path resolution works. Listing a directory needs read permission on it, so outside the list nothing can be listed. Everything else is denied: the runs directory and sibling runs, `$TMPDIR` and `/private/tmp`, `$HOME` and `~/.config`, the repository.
- **The live probe has negatives that would have failed run 3.** The test creates decoy files in:
  - the parent of the run directory;
  - a sibling run directory;
  - a fresh directory under `$TMPDIR`.
  
  From inside the sandbox, reading each decoy and listing each of those directories must fail. So must listing `~` and `~/.config` (no content is read; nothing is written to the real home). The §9 positive controls still run first.
- **One path model.** `run_python` runs with the **run directory as its working directory**, so `input/clip.mp4`, `input/timing.json`, `workspace/` and `artifacts/` mean the same thing in the prompt, the tool descriptions, the results and the agent's code. Writes are still allowed only in `workspace/` and `artifacts/`. The `run_python` description states this and gives the exact helper import line, the one that works in the sandbox (e.g. `from helpers import masks_io`). Absolute host paths in returned stdout/stderr (tracebacks included) are replaced by the run-relative form.
- **Honest `run_python` feedback.**
  - Elapsed time is measured, not the timeout. Run 3 said "ran clean in 300s" for 6-s runs.
  - No environment noise on stderr: `ulimit -v` is rejected on macOS and printed an error on every call. Enforce memory from the parent by watching the child's resident size and killing it over the cap, or declare no cap; either way stderr carries only the agent code's own output.
  - The result shows stdout before stderr and before the metrics.
  - Full stdout is saved to `artifacts/t<turn>_run_python_<n>.stdout.txt`. A truncated result names that file, not the code file.
- **The tool schemas have one source.** This part exports the definitions of all tools: name, description and strict JSON parameters, with `submit`'s description carrying the **evidence field list from part 12 and a minimal skeleton**. The loop's prompt prefix (part 06) and the Spark client (part 04) both use this export; neither keeps its own copy. Run 3's agent was told only `evidence: string`.
- **Tests:**
  - the decoy probe above;
  - `run_python` from the run directory reads `input/timing.json` by that path;
  - a 1-s sleep reports ≈ 1 s, not the timeout;
  - stderr of a clean run is empty;
  - truncation names the stdout file;
  - the exported `submit` description contains every top-level evidence field of part 12's schema.
- **Tests pass in the full suite** (brief 04, test ownership): no test module imports `conftest` by name; shared helpers such as `make_blind` and `make_frames` are fixtures. `tests/tools/test_submit.py` failed this way in the full suite on int.

## 11. Owner addendum (2026-10-28, from the fourth live run): `submit` that can be satisfied

The agent submitted three times and saw only "submission rejected with 124 error(s)". The `{code, field, detail}` list was in the tool result's metrics, which the loop does not show (part 06 addendum). The skeleton in `submit`'s description failed the schema itself: `contract_version: 1`, `worlds: []`, `clock: {}`, string artifacts.

- **The description is generated from `evidence.schema.json`** (part 12 §14), never hand-written. It gives:
  - every field path with its type, whether it is required, and its schema description;
  - the shipped `evidence.example.json`.

  Test: the example embedded in the description validates against the evidence schema, and every required path of the schema appears in the description.
- **Rejections are readable.**
  - The result's `summary` lists every error as `CODE field: detail`, V1 errors first and grouped by code, up to 40 lines, then "+N more of CODE".
  - The full list is saved to `artifacts/t<turn>_submit_errors.json`, and the result names that file.
  - Test: a rejected submit's summary contains each error's code and field.
- **Dry run.** `submit` takes `dry_run: bool`. A dry run validates fully and returns the same error list, but is not an attempt and writes no result. There are at most 5 dry runs per run (config).
- **`web_search` passes the facts through.** The client returns `answer` items `{text, source_url, quote}` (part 04). The tool must return them, so that `references[].sources` can quote them. Seen: the tool read `facts`/`results`/`sources`, found nothing and returned URLs only, so the agent fell back on an uncited 1.8 m height. Test: with the client's real answer shape, the tool result contains the text, URL and quote of every item.

## 12. Owner addendum (2026-10-28, from the fifth live run)

- **Each `submit` call saves its full error list** to `artifacts/t<turn>_submit_errors.json` (dry runs included), as §11 already said, and the result names that file. In run 5 no such file existed.

## 13. Owner addendum (2026-10-28, from the sixth live run)

The sixth run made its first submit, a dry run, on turn 55 of 60 and was rejected. Its fit curve in the call did not match its own file: the agent had written `workspace/evidence.json`, but `submit` takes only an inline object, so it retyped a 31-sample curve it had never seen in full and invented the middle samples. It also read the operator's files.

- **`submit` takes a file.** Besides inline `evidence`, `submit` accepts `evidence_path`: a run-relative path to a JSON file under `workspace/` that the agent wrote with `run_python`. Exactly one of the two is given; both or neither is a readable rejection. Dry runs work the same way. The tool description says to prefer the file whenever the evidence holds arrays (tracks, fit curves, outlines). The validator receives the parsed object; the file's content as submitted is copied to `artifacts/t<turn>_evidence.json`.
- **The run root is not readable.** §10 already lists the readable places: the run's `input/`, `workspace/`, `artifacts/`. Today the profile allows the whole run directory, so `logs/` (the loop's own records) and files at the run root such as `probe.json` (which names the source path) were readable. Allow exactly those three subtrees, `workspace/` read-write; nothing else under the run directory. The working directory may stay the run directory; listing it is denied.
- **The submit description names the required parts of the error budget,** generated from the evidence schema (part 12 §15): the always-required components and the conditions that require `reading_spread` and `repetition_spread`.
- **Tests:** a `submit` with `evidence_path` pointing at a valid file passes a dry run; with both `evidence` and `evidence_path` it is a readable rejection; the live sandbox probe adds decoys in the run's `logs/` and at the run root and must fail to read both, while `input/`, `artifacts/` and `workspace/` stay readable.

## 14. Owner addendum (2026-10-28, from the seventh live run)

- **The blind check asks about parts.** The question `check_mask` sends asks, besides what the tinted region covers, to list as alternatives any separable or stacked parts inside it (for example a unit mounted on top of another) and any part of the same object left outside. Seen: the mask covered a backpack with its top unit; the two alternatives returned were about margins only, and the agent read the pack as the bare backpack.
- **The submit description** carries the new evidence fields and rules of part 12 §16 and part 11 §9 (generated from the schema): `segments[].subject`, the person-as-second-reference rule, reference agreement, answering every blind-check alternative, no `takeoff_level_y_px`.
- **Test:** the blind question text contains "stacked" and "separable"; the generated submit description mentions `subject` and `REFERENCES_DISAGREE`.

## 15. Owner addendum (2026-10-28, from the eighth live run): the blind check names the kind

The eighth run was accepted with verdict Moon, g = 1.27 ± 0.22 m/s². The jumper is an astronaut, but the agent declared `subject: {kind: "object", description: "foreground suited figure"}`, and the person-as-second-reference rule (part 11 §9) never fired. A label that switches a rule on must not come from the party the rule constrains.

- **One more blind question.** `check_mask` also asks, in its own line: "In one word, is the covered thing a person (any human, including one in a suit, costume or uniform), an animal, or an object?" The question names no experiment and no world, so the check stays blind. The tool records the answer, normalised to `person`, `animal` or `object`, as `kind_answer` in the check artifact `artifacts/t<turn>_check_mask_<n>.json` and returns it in the tool result.
- **Test:** the blind question text contains "person", "animal" and "object"; with a stubbed vision reply "A person." the artifact carries `kind_answer: "person"`.

## 16. Owner addendum (2026-10-28): the kind question is withdrawn

§15's one-word kind question served a rule tied to a person in the clip; the owner replaced that rule with a general one (part 08 R-S6, part 11 §13: two or three references for every clip). `check_mask` no longer asks it, and the check artifact has no `kind_answer`. The submit description carries R-S6 in the validator's terms. Test: the blind question text does not contain "person"; the submit description mentions "two" references and `REFERENCES_DISAGREE`.

## 17. Owner addendum (2026-10-28): the blindness filter blocks the answer, not the identity

The ninth run's queries "Apollo life support backpack PLSS height dimensions metres" and "Apollo spacesuit astronaut height metres suited" were rejected by the pattern screen (`"apollo"` in `BLINDNESS_PATTERNS`). The agent fell back to "adult male standing height average" and measured a suited astronaut as an average man. Part 01's decision of 2026-10-28 moves the line:

- **Allowed:** queries that name what the agent identified in the frames (places, missions, people, models, eras) to look up facts about those things: heights, dimensions, equipment sizes, boot sole thickness, standard rates.
- **Rejected:** queries that look for the clip or its answer: the clip itself ("video of …", "viral …"), an analysis of it, "real or fake", "hoax", "faked", or a measured gravity, jump height or hang time of the event in the clip.
- **Pattern screen** (`BLINDNESS_PATTERNS`): keeps the run's anonymous filename, hashes and the answer-seeking forms ("hoax", "fake", "faked", "real or fake", "debunk", "gravity in the video", "slowed down footage"). It drops names, missions and places (`apollo`, `alsj`, astronaut names, `lunar surface journal`).
- **Classifier question:** "Is this query trying to find a specific video, an analysis of it, or the answer to whether its motion is real or what gravity it shows, rather than facts about objects, people or places (sizes, dimensions, rates)?" Reject on yes or uncertain. The wording lives in `src.tools.web_search.CLASSIFIER_QUESTION`; that name is part 07's interface, and part 04 §7 imports it for the live classifier.
- **Tests:** "Apollo spacesuit astronaut height metres suited" and "John Young astronaut height" pass the pattern screen; "Apollo 16 jump salute gravity measured" and "moon landing hoax jump" are rejected; a stubbed classifier's "yes" still rejects.

## 18. Owner addendum (2026-10-29, from Moon run 14): a dry run reaches the validator as a dry run

Seen: Moon run 14 submitted one reference and ended undetermined ("scale rests on one reference"), although part 11 §16 makes a one-reference dry run not clean (`SECOND_REFERENCE_REQUIRED`). None of its three dry runs (turns 49, 51, 55) carried a push code. Cause: `submit` falls back to `_default_validator(evidence, run_context)`, which calls `validate(evidence, run_context)` without `dry_run`. Every live dry run was therefore judged as a real submit: push codes never fired, and an accepted dry run wrote `result.json`.

- **The default validator forwards `dry_run`.** `_default_validator(evidence, run_context, dry_run=False)` calls part 11's `validate(evidence, run_context, dry_run=dry_run)`. A dry run never writes `result.json`, whichever validator is used.
- **Tests (default validator, no fake):**
  - `submit` with `dry_run: true` on a valid one-reference evidence returns `SECOND_REFERENCE_REQUIRED` among its errors, is not clean, and leaves no `result.json` in the run dir;
  - the same evidence with `dry_run: false` is accepted as an undetermined result and writes `result.json`;
  - a dry run on an evidence that passes every check, push codes included, is accepted and still leaves no `result.json`.

## 19. Owner addendum (2026-10-31, from hand runs 2–5 and wall run 11): `check_line`, a blind look at a measured line

Seen:
- In hand run 5 every endpoint lay on the hand's mask, so it passed part 11's `RANGE_EXTENT_NOT_ON_MASK`, yet the "palm length" line was a short sliver along the mask's edge, and the palm/hand ratio came out 0.27 instead of about 0.6.
- In wall run 11 a "crowd barrier height" line gave a scale five times off the person's.

A mask check says what a mask covers. Nothing yet says what a measured line spans. A seventh tool does:

- **`check_line(frame, lines)`**: `lines` holds one to three items `{x1, y1, x2, y2, claim}`. `claim` is what the line is said to measure, in plain words, such as "hand length: wrist crease to the tip of the middle finger".
- **The tool draws each line itself** on that frame of the run's own clip: numbered, 3 px, a contrasting colour, small end caps. It saves the overlay as an artifact. The agent never supplies the image.
- **Call 1, blind.** A fresh Spark conversation receives only the overlay and this question: "For each numbered line drawn on this video frame, say where it starts and where it ends, naming the visible part at each end (for example 'the lower edge of the dark rectangle', 'the tip of the longest finger'). Do not guess what the video is or what is being measured."
- **Call 2, text only.** A fresh conversation receives call 1's descriptions and the claims, with no image: "Does each description match its claim? For each line answer yes or no, with one sentence." This keeps the claim from steering the look.
- **Record:**
  - `artifacts/t<turn>_check_line_<k>.json` holds the frame, each line's endpoints, claim, blind description, `agrees` (bool) and `why`;
  - the same record is appended to `artifacts/line_checks.jsonl` (read by part 11);
  - the tool's result returns the descriptions and `agrees` to the agent.
- **Budget and filters.** The cap is 6 calls per run, a constant in the tool's module. Both Spark calls go on the ledger like `check_mask`, and the blindness filter of §17 applies to both. `check_line` stays open in the finishing phase, because it checks, it does not explore.
- **Tests (stub Spark):**
  - the overlay is drawn by the tool on the given frame, and an agent-supplied image path is rejected;
  - call 1's request carries the image and no claim, and call 2's carries the claims and no image;
  - the record has the fields above;
  - the seventh call in a run is refused with the cap message.

## 20. Owner addendum (2026-10-31): `check_line` speaks the blind client's line kinds, proven against the real client

Seen: all six live `check_line` calls failed with `blind_malformed`, because the tool and the real blind client disagreed on the reply's shape. Part 04's addendum of 2026-10-31 adds the kinds `line_look` and `line_match`.

- **Call 1** sends `{kind: "line_look", image, question: BLIND_LOOK_QUESTION, n_lines}` and reads `descriptions`.
- **Call 2** sends `{kind: "line_match", descriptions, claims, question: MATCH_QUESTION}` and reads `results`.
- **A failure stays visible.** A `FailedCallError` from the client becomes `blind_failed` with its message. The tool's error result tells the agent whether to retry once: yes for a transport error, no for a malformed reply. Neither failure counts against the cap of six.
- **Joint test:** `tests/tools/` builds the real `make_blind_client` against a local stub HTTP server, like part 04's client tests (a minimal server in the test file is fine). The server answers the two kinds with schema-shaped JSON. `check_line` then succeeds end to end: the record is written to `line_checks.jsonl`, and `agrees` is taken from the stub. A stub that returns the mask-check shape yields `blind_failed`, not a crash.

## 21. Owner addendum (2026-11-01, from the Moon and sped-up Moon runs): `motion_overview`, the trajectories of what SAM found

The Apollo clip has two jumps of the same astronaut (frames ≈ 243–274 and ≈ 328–369). The Moon run measured the first and called the second "standing after landing". The sped-up run measured the second and never listed the first. Both had looked at contact sheets by eye. The sped-up run had even segmented the astronaut over all 192 frames: in its own masks the lowest point of the figure rises clear off its support at frames 101–113 and 136–150. The agent had no tool that showed it the trajectories. R-M4 (part 08) asked for every repetition; the agent could not see them.

`motion_overview` turns a `segment` result into trajectories the agent can look at. It is local computation: no API call, no price.

- **Inputs:** a masks artifact from `segment` (`artifacts/…npz`), optional object ids (default: every object in it).
- **Per object and frame** (from part 09 `largest_component` and `mask_stats`): bottom, top and centroid y, centroid x, height and area, on measured timestamps (`timing.json`).
- **Support level and rise.** The support level at a frame is the lowest bottom position (largest y) within ±1 s. Rise = support level − bottom, in pixels.
- **Candidate flights.** A candidate is a maximal run of at least 4 frames where the rise is at least max(3 px, 4 % of the object's median mask height). For each candidate the tool reports:
  - `id` (F1, F2, … in frame order), first and last frame, start and end time, airtime;
  - peak rise in pixels and in median mask heights;
  - the curvature of a parabola fitted to the centroid y over the run, its sign and R²;
  - mask flags inside the run ±3 frames: area jumps (a frame whose area differs by more than 25 % from the median of its ±3 neighbours), frame-edge contact, splits (part 09 `track_quality`).
  A candidate is a pixel fact, not a decision: the tool never says "jump".
- **Outputs, all named in the result** (§1):
  - a JSON table of the per-frame values and the candidates;
  - a chart image: one row per object; time on x; the bottom and the centroid drawn with up as up; the support level dashed; the area as a thin line on its own scale; each candidate shaded and labelled with its id and airtime;
  - one strip image per candidate: 6 frames (takeoff − 3, takeoff, the frame of peak rise, landing, landing + 3, and the frame halfway between) with the object's outline drawn, each cell labelled with its frame number and time.
  The images are returned to Spark as images, the same way `view_frames` returns its sheets.
- **Tests:**
  - synthetic masks of a rectangle that walks at a steady height, then makes two parabolic hops at planted frames: exactly two candidates, each within ±1 frame of the planted takeoff and landing, curvature positive (down in the world), R² ≥ 0.95;
  - the same masks with planted area jumps on 3 walking frames: no candidate there, or the candidate carries the area-jump flag;
  - on `fixtures/source/fake-1/` (`artifacts/t9_segment_0.npz`, object `1`, all 192 frames): candidates cover frames 101–113 and 136–150 (±2 frames);
  - the chart and the strips are written, are non-empty images, and are named in `files`.

### 21.1 Owner addendum (2026-11-01, from the first generated `motion_overview` on fake-1): the chart shows a flight as a hump, ids are unique, the strip is in time order

The first generated tool found both flights on fake-1 (F2 101–113, F3 136–150, R² 0.98 and 0.99). Three things in its output still mislead the agent:

- **The chart draws a flight as a dip.** The vertical axis runs in image y, so the larger y (lower in the image) is at the top and a body that rises off its support goes down on the chart. Fix: the vertical axis is height in the picture — a smaller image y is drawn higher. A flight is a hump above the dashed support line, never a dip. The axis labels say "higher in frame" at the top and "lower in frame" at the bottom, with the pixel values.
- **Ids collide between objects.** With two objects, each got its own F1, and the map of strips kept only one of them. Fix: ids are unique over the whole result — F1, F2, … in order of first frame over all objects, ties by object id. Every candidate has exactly one strip, and the result maps each id to its strip.
- **The strip is out of time order.** The "halfway" frame came last, after landing + 3. Fix: the 6 cells go in time order: takeoff − 3, takeoff, peak, the frame halfway between peak and landing, landing, landing + 3. The result lists each strip's frames in `metrics.strip_frames[<id>]`.

Tests:
- on the synthetic two-hop masks: the test finds the bottom line's colour in the chart column of each peak frame and in the column of a walking frame 1 s before the first takeoff; at both peaks the line is higher in the image (smaller row) than at the walking frame;
- a synthetic file with two objects that each hop once: the ids are F1 and F2, the strip map has 2 entries, and `files` names 2 strips;
- `metrics.strip_frames` for every candidate is 6 frames in increasing order (equal neighbours allowed only where the run is shorter than 6 frames);
- on fake-1 object 1 the old range tests still hold.

## 22. Owner addendum (2026-11-01, from four runs with 150 turns): `check_line` says the view and the dimension

Seen: a Moon run measured "suited figure width 0.82 m" with a horizontal line across the figure. The figure is seen from the side, so the line spans its depth with the backpack, not the suit's width. `check_line` confirmed it, because the look described the endpoints and the match compared only the endpoints with the claim.

- **The look question adds:** "For each line, also say from which side the object is seen in this frame (front, back, side, top, or unclear), and along which of its own dimensions the line runs (height, width, depth, or unclear)."
- **The match question adds:** "When a claim names a dimension (height, tall, width, wide, depth, deep, length, long), answer yes only if the description says the line runs along that same dimension of the object."
- The look's per-line answer gains `view` and `dimension` (strings), written to the result JSON next to `description`; the blind client's line-look schema (part 04) carries them.
- **Tests:** a stub look that returns `dimension: "depth"` for a claim "suited figure width" makes the stub match receive a question containing "along that same dimension"; the result JSON of every line holds `view` and `dimension`.

## 23. Owner addendum (2026-11-02, from part 11 §50's generation): accepted test evidence carries line checks

Seen: part 11 §50 makes the validator refuse a reference whose line has no agreeing `check_line` record (`REFERENCE_LINE_NOT_CONFIRMED`). Part 11's generation failed only on two tests of this part, `test_default_validator_real_submit_single_reference_accepted` and `test_default_validator_dry_run_clean_writes_nothing`: their helper `_make_default_valid_run` builds evidence that passes every real check but writes no line checks.

- **`_make_default_valid_run` writes one agreeing line check per measured line:** for each reference's `extent_px` and for a `check_scale` extent, a file `artifacts/t<n>_check_line_0.json` in the run dir, in the shape `check_line` writes (§20, §22): `frame`, and one line with `x1`, `y1`, `x2`, `y2` equal to the extent's, a `claim` that names the dimension ("height of the …"), `description`, `view`, `dimension: "height"`, `agrees: true`, `why`.
- Any other test of this part that expects the default validator to accept evidence does the same.
- **Test:** the two tests above pass with a validator that applies part 11 §50, and still pass with one that does not.

## 24. Owner addendum (2026-11-04, from street-jump run 83): a flight ends where the body lands, at whatever level

Seen: in run 83 the jumper took off at frame ≈ 63 and landed at frame ≈ 112, farther from the camera, about 60 px higher in the frame than he took off. `motion_overview` took the support level as the lowest bottom within ±1 s, so after landing the rise stayed above threshold, and it reported one candidate over frames 40–166: "airtime" 2.1 s, centroid R² 0.39. The real flight (≈ 0.8 s, R² 0.997 on the centroid) sat inside it, and the agent judged the whole candidate not a flight.

- **A candidate is cut to its own takeoff and landing**, found from the bottom's motion inside the candidate:
  - the bottom's vertical speed per frame: central difference on measured timestamps, over 3 frames;
  - landing: the first frame after the peak where the downward speed falls below 25 % of the largest downward speed after the peak and stays below for 3 frames;
  - takeoff: the last frame before the peak where the upward speed is still below 25 % of the largest upward speed before the peak;
  - frames outside [takeoff, landing] leave the candidate; the frames after the landing form a new support level, and a later candidate needs a new rise from that level.
- Airtime, peak rise, curvature, R² and the flags are computed on the cut range. The JSON table records the uncut range as `raw_frames` beside the cut one.
- Part 11 §43's recomputed overview uses the same computation, so the agent's and the validator's candidates agree.
- **Tests:**
  - synthetic masks: a rectangle stands, makes one parabolic hop, and lands 60 px higher in the frame than it took off, then stands: exactly one candidate within ±2 frames of the planted takeoff and landing, centroid R² ≥ 0.95;
  - the existing tests keep their results (the two-hop rectangle; `fixtures/source/fake-1/` candidates 101–113 and 136–150 within ±2 frames).

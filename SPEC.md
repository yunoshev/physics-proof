# physics-proof — specification

Status: spec stage, written 2026-10-27 (day 2 of the Meta Global AI Developer Hackathon). This document is the contract
the code is written against. It contains no code on purpose: the code is written by Spark through Muse Code, module by
module, and every module is accepted by the probes listed here.

Contents: 1 Goal · 2 Principles · 3 Architecture and modules · 4 Rules of evidence (lessons) · 5 Acceptance ·
6 Process · 7 Budget and credits · 8 Submission and prizes · 9 Open questions.

---

## 1. Goal

**Video in, proof out.** A person gives a short video and asks one question: *is this physically real?* The tool answers
with a proof, not an opinion. It finds a physical claim that can be tested from the picture alone, measures it, compares
it with what physics predicts, states a verdict with an honest error bar, and publishes the work step by step.

- **Input:** one video file (mp4/mov). Nothing else: no title, caption, source or hints.
- **Output:** one interactive HTML page = a frozen player template + the analysis JSON. The video sits next to the page
  as a file (or behind a URL); it is not embedded. Libraries (fonts, KaTeX) load from a CDN with pinned versions.
- **What the page shows:** the video playing frame by frame, pausing on key moments (scale, takeoff, apex, landing,
  verdict), with the measurement drawn over it — mask outlines, the tracked point, the fitted parabola, a scale bar,
  "ghost" trajectories of the same jump on Earth and on the Moon, a live h(t) chart, the math step by step, the error
  budget and the verdict.
- **First case:** the Apollo 16 "jump salute" (NASA, public domain) and a slowed copy we make ourselves. The page must say
  "Moon" for the original and "too slow for any world; slowed about ×1.5" for the copy.
- **Second case: a viral wall run** (an AI-generated clip, Singapore, a runner sprints up a tall vertical wall to the top).
  The general claim behind both cases: **wherever a body is unsupported, it must move under g.** On a vertical wall
  nothing presses the runner against it, so there is no normal force, hence no friction to push on, and the vertical
  motion is free flight: `a_y = −g`. A steady climb (`a_y ≈ 0`) is physically impossible at any playback speed. A second,
  independent measurement — the step rate on the flat run-up (people run at 2.5–5 steps/s) — shows whether time in the
  clip runs normally. The page must say "physically impossible: the climb ignores gravity" with both numbers.
- **Hackathon theme:** Push the Frontier — "understand a physical system… when these models meet the real world".
- **Language:** all page text and UI in English.

Non-goals for the hackathon: a hosted web service (the site is static, on GitHub Pages — see M13), user accounts,
audio-based evidence, scene types other than unsupported motion under g (ballistic flight, a body on a vertical surface;
a collision type may follow if time allows), any clip we have no rights to.

## 2. Principles

1. **Only the video goes in.** The analysis agent knows nothing about the clip. File names are anonymised (`clip.mp4`).
2. **Spark is the orchestrator.** Spark watches the video, decides what can be proven, asks for segmentation, looks at
   frames, looks up reference sizes, writes and runs the measurement code, and assembles the page. There are no
   hardcoded scene types: if nothing measurable is in the clip, the honest answer is "cannot be determined".
3. **Meta stack only for every model call.** Muse Spark 1.3 (standard or contributor tier) through Meta Model API,
   SAM 3.1 through Meta Model API, Spark's built-in `web_search`. Optional: Muse Voice Transcribe. No OpenRouter, no
   local SAM, no non-Meta model in the product. Optional open-weights path: Muse Spark Open on a partner (§7).
4. **We own the frame, Spark owns the reasoning.** Ours: the agent loop, the tools, the verified physics blocks, the
   frozen player, the schema and the validators. Spark's: everything specific to the clip.
5. **Numbers come from code.** Every number on the page comes from code Spark ran, or from a cited source (reference
   sizes). Each number is traceable to a turn in the run log.
6. **Honest verdicts.** Three verdict states: a world fits; no world fits (with the time-scale factor it would take);
   undetermined (error too large). "Undetermined" is a valid, valued result. The verdict is computed by a verified block,
   never written by hand; the orchestrator recomputes it and rejects a mismatch.
7. **Blindness.** The analysis agent never sees answers: no ground truth in prompts, no hand-measured numbers, no clip
   names. Web search refuses queries about the event's own measured quantities (how high, how long, how fast, how far)
   and about the clip's authenticity (slowed, sped up, edited, fake); such sentences are also cut from search results.
   Every query is logged.
8. **Budgets are enforced in code**, not in the prompt: turns, SAM frames, searches, dollars per run, dollars in total.
9. **Reproducible runs.** A run directory keeps every turn (request, action, tool result, images shown, cost), the
   workspace, the final page and screenshots. A run can resume from its saved turns.

## 3. Architecture and modules

```
video ─► agent loop (Spark) ─► tools: video_info · frames · sam · mask_check · search · python · finish
                                   │         │       │        │          │        │         │
                                   └─ Meta API client (Spark, SAM 3.1, files, cost ledger)  │
                                                                     sandbox + physics blocks
                                                                                           ▼
                                                     analysis.json ─► validator ─► frozen player ─► page.html + video
                                                                                                          ▼
                                                                          publish ─► GitHub Pages: one page per analysis
```

Each module below lists: **does** (responsibility), **in / out**, **probes** (invariants checked at the junction before
the module is accepted). Probes run offline wherever possible; the ones that need the API are marked *(API)* and cost
cents. A module is done when all its probes pass and the probe commands are in the repo.

### M1. Meta API client
- **Does:** one place for all calls to `https://api.meta.ai/v1`: Responses API for Spark (text, images, video input,
  strict JSON schema output, tool calling, `web_search`, reasoning effort), Files API (upload with expiry, delete),
  SAM 3.1 streaming responses. Retries with backoff on 429/5xx. Model and tier come from config, not from code.
- **Out:** parsed responses plus a usage record per call (model, input/output tokens, frames, searches, dollars) appended
  to a cost ledger (one JSONL per run plus one global ledger).
- **Errors:** HTTP 402 `billing_not_configured` becomes a clear, single-line error that names the Billing page; it is never
  retried. Keys are read from the environment (`META_API_KEY`) and never logged.
- **Probes:** a fake server returns 402, 429-then-200, and a malformed stream — the client gives the right error, retries
  once, and fails clearly; the ledger sums match a hand-computed price table; no key appears in any log *(offline)*.
  One real 16-token Spark call and one 5-frame SAM call return usage that lands in the ledger *(API, < $0.01)*.

### M2. Video
- **Does:** probe the file (width, height, fps as an exact rational, frame count, pixel aspect ratio, duration); read
  exact frames by index; build contact sheets (≤ 30 tiles, each labelled `f<index>`, labels drawn after the final resize
  so they stay readable); zoom and crop in original pixel coordinates; normalise the input to H.264 with identical frame
  count and timestamps for the player.
- **Probes:** a synthetic clip with a burned-in frame counter: frame N read back shows N, for every 10th frame; labels
  on a 30-tile sheet are legible (OCR or pixel check); normalised video has the same frame count and pts as the source;
  non-square pixel input reports the right aspect.

### M3. SAM 3.1 tool
- **Does:** `sam(phrase, start, stop)`: send the clip (Files API) and one short noun phrase to SAM 3.1, decode the per-frame
  masks with Meta's `meta-sam-parser` (do not write our own decoder), keep frames start..stop-1, save
  `sam/<phrase>.<start>-<stop>.npz` in the run workspace. Returns per-object statistics (area, bbox, centroid per frame),
  track-quality flags (gaps, area jumps, splits/merges, identity swaps) and an overlay sheet with each object tinted.
- **Cache:** key (clip hash, phrase, start, stop); an identical call is free; a sub-range of a cached longer call is cut
  from it.
- **Budget:** frames per clip (default 1500, counted as stop − start); refuses beyond it with a clear message.
- **Probes:** decoder on the example from Meta's docs gives the documented mask *(offline)*; a 5-frame call on the test
  clip returns 5 frames of masks whose bbox matches the overlay *(API)*; cache hit makes no API call; budget refusal
  triggers at the limit.

### M4. Search tool
- **Does:** `search(query)`: a separate Spark call with `web_search` that returns `{facts: [{text, source_url, quote}]}`
  under a strict schema. Allowed: sizes and masses of manufactured objects, equipment specifications, physical constants,
  what a piece of equipment is. Refused: the event's own results and the clip's authenticity (Principle 7).
- **Blindness filter:** two layers. (1) A word list plus patterns on the query (refuse before calling) and on the answer
  (cut sentences, log the cut). (2) Added 2026-10-27 after the patterns kept leaking on paraphrases: a separate,
  context-free Spark call classifies every query that passed the patterns, and every returned fact, as a reference fact
  or as being about the filmed event / its authenticity / whether the filmed action is possible; anything but a
  reference fact is refused or cut. The classifier fails closed (an error means refuse). Per-clip limit (default 6). Every query, refusal and cut goes to the run log.
- **Probes:** a fixed list of 20 queries (10 must pass, 10 must be refused) is classified exactly; an answer with a
  planted forbidden sentence comes back with it removed and logged *(offline)*; one real query returns at least one fact
  with a source URL and a verbatim quote *(API)*.

### M5. Python sandbox
- **Does:** `python(code)` runs Spark's code in the run workspace: Python 3.13 with numpy, scipy, Pillow, matplotlib and
  `import blocks`. Before running: a static review (no file-system paths outside the workspace, no subprocess except
  ffmpeg/ffprobe, no eval/exec/dynamic import, no network modules). URLs inside strings are data and are allowed.
  Running: macOS `sandbox-exec` profile — no network, writes only inside the workspace, reads of the home directory denied;
  60 s timeout; isolated interpreter mode. Returns stdout/stderr (truncated) and up to two PNG/JPG files the code wrote.
- **Probes:** code that opens a socket, writes outside the workspace, reads the home directory, or runs `sh` is refused
  by the review or fails in the sandbox — both layers tested separately; a 61 s loop is killed; a plot written by the
  code is returned as an image.

### M6. Physics blocks (verified library)
- **Does:** small, documented, unit-tested functions available as `import blocks`:
  - `load_masks` (npz → per-frame masks per object), `video_info`, `read_frames`;
  - `spans_of` (compact mask encoding for the page), `mask_stats`, `largest_component`;
  - `track_quality` (flags per object: gaps, area jumps > threshold, splits, merges);
  - `fit_parabola` (pixel row vs frame number over a window → acceleration in px/s², standard error, rms, residuals);
  - `decide(g, g_err, worlds)` → verdict dict: per-world sigma, which worlds are consistent within 2σ, label,
    slowdown factor `k = sqrt(g_world / g_measured)` for the nearest claimed world, text; Earth 9.81, Moon 1.62
    (Mars 3.71 optional). States: `fits:<world>`, `none_fits` (with k), `undetermined` (error too large to separate
    the worlds).
- **Probes:** synthetic parabolas with known g and Gaussian pixel noise: recovered g within 1σ in ≥ 66 % of 200 trials and
  the reported error matches the scatter within 20 %; `decide` table of 12 hand cases (fits, none fits, undetermined at
  the boundary) matches exactly; `track_quality` flags a planted gap, jump and split; docstrings state argument shapes
  (a single-object mask array vs a dict of objects must give a clear TypeError, not a numpy error).

### M6b. Blocks for moving cameras and time scale (added 2026-10-27 for the wall run)
- **Does:** more verified functions in `blocks`:
  - `relative_track(target, reference, *, anchor, size)` — the camera pans and zooms, so positions are expressed in a
    frame attached to a static object: per frame, (target point − reference anchor) / reference size in px. Units are
    "reference sizes"; the reference's real size converts them to metres.
  - `step_rate(series, fps)` — the dominant frequency of a periodic signal (e.g. the runner's mask top bobbing on the
    run-up) with its error: steps/s.
  - `ghost(y0, v0, a, frames, fps)` — the trajectory a body would follow from the measured start under a given
    acceleration (for the page: "where he would be if gravity acted").
  - `decide` accepts hypotheses as well as worlds (e.g. `{"unsupported on Earth": 9.81}`); when the measured downward
    acceleration is ≤ 0 or far below every hypothesis, the text says that no playback speed explains it.
- **Probes:** a synthetic panning-and-zooming camera over a parabola gives back the true acceleration in reference units;
  a synthetic bob at 3.2 Hz with noise gives 3.2 ± its error; `ghost` matches the analytic formula; `decide` texts for
  the new cases match a table.

### M7. Mask check
- **Does:** `mask_check(file, object, frames, claim)`: a separate Spark call with no context of the run. It sees only crops
  of up to 4 frames, each as "plain | mask highlighted", and must answer under a schema: what is inside the mask, what is
  outside, **which part of the object the mask covers** (e.g. "the main box and the upper module", "the whole person
  including the helmet"), and a judgement of the claim (agrees / mask covers more / covers less / different object /
  cannot tell). The crop sheet is saved for the page.
- **Rule:** `finish` refuses to run until at least one mask check was made on the mask used as the size reference.
- **Probes:** two fixtures with a known answer (mask covers the whole object; mask covers object + attachment) — the
  checker describes the attachment in the second *(API, < $0.01)*; the gate in `finish` blocks a run without a check.

### M8. Agent loop
- **Does:** runs one analysis. Message 0: the system prompt (role, tools, rules of evidence §4, blocks documentation,
  analysis schema, player documentation) and the video. Each turn Spark makes exactly one tool call — native tool calling
  if the Responses API supports it for all our tools, otherwise a strict flat JSON schema (one `action` field plus
  nullable argument fields; no top-level `anyOf`). Parse defensively (text before the JSON is ignored).
- **Context:** images older than the last two tool results are pruned; tool results are truncated with a note.
- **Limits:** max turns (default 40), SAM frames, searches, mask checks (4), dollars per run (default cap in §7); the
  dollar cap is checked before every call, including sub-calls. Hitting a limit asks Spark for a final `finish` with what
  it has, or ends with "undetermined: budget".
- **Logs:** `runs/<tag>/turns/NN.json` (Spark's note, action, arguments, full tool result, images, cost), `conversation`,
  `summary.json` (status, turns, SAM calls/frames, searches, cost, wall time, page path).
- **Resume:** `--resume` restarts from saved turns; the last action is asked again.
- **Probes:** a scripted fake Spark (replays a fixed list of actions) drives a full run on the test clip offline (SAM and
  search served from fixtures) and produces a page; a malformed action is rejected with a readable message and the run
  continues; the dollar cap stops a run mid-way; resume after a kill reproduces the same turn files.

### M9. Analysis schema and validator
- **Does:** the JSON contract between Spark and the player. Sections: `context` (scene, claim, expected values, sources),
  `first_look` (what/where/when/source/confidence and a by-eye estimate before measuring — shown on the intro), `reference`
  (name, which extent, value, tolerance, source URL, verbatim quote, source type primary/secondary/estimate; mask check
  result), `scale` (frame, pixel extent, metres per pixel and error, second independent reference and their agreement),
  `track` (what point, method, one entry per frame), `masks` (only frames the page draws, compact spans), `flights`
  (per unsupported segment: `kind` = `flight` | `wall`, start, apex/end frames, rise in px and m, duration, parabola fit,
  measured acceleration, the hypothesis it is tested against, the ghost trajectory, cross-checks), `timescale` (optional:
  how the clip's time rate was checked, e.g. step rate, and its result),
  `error_budget` (term → relative error), `verdict` (exactly the dict from `blocks.decide` plus g, g_err).
- **Validator:** required fields with paths in error messages; types; ranges (frames inside the clip, positive errors);
  internal consistency (rise = (base − apex) × m/px within rounding; t_air = frames/fps; verdict recomputed by `decide`).
  Fields the player does not know are ignored, not rejected.
- **Probes:** the validator accepts a complete fixture; removing each required field in turn gives an error naming that
  path; a tampered verdict is rejected.

### M10. Frozen player
- **Does:** one HTML template, written once and frozen (hash recorded); per analysis only the JSON and the video change.
  The renderer is chosen by a `type` field (`world-g` first); no per-clip branches.
- **Steps on the page:** intro (Spark's first look and by-eye estimate) → reference card with the quote and the mask
  check → scale bracket on the frame → for each flight: takeoff → apex → landing with the live parabola and the h(t) chart
  → error budget bars → verdict scale (g with error bar against Earth and Moon; three states including undetermined) →
  optional side-by-side ghosts (the same rise on Earth and on the Moon) → optional reveal (the truth about the clip, shown
  only after the verdict, for demos).
- **Overlays:** mask outline, tracked point and trail, fitted parabola, scale bar, ghosts, chronophotograph of the
  landing from real crops.
- **Controls:** play/pause, frame step, auto-pause on events, jump to event, URL parameters (`frame=`, `clip=`, `reveal=`).
- **Size:** page without video ≤ 1 MB for a 15 s clip (masks only for drawn frames, compact encoding).
- **Probes:** headless Chrome renders a fixture page with no console errors; seeking lands on the requested frame
  (check 10 frames); a screenshot set of the 5 key moments is produced; each text string can be overridden from the JSON;
  the template hash does not change between analyses.

### M11. Finish
- **Does:** `finish(page_texts, analysis_file)`: validate (M9) → check the mask-check gate (M7) → recompute the verdict
  → build the page (M10) → take 5 screenshots (scale, takeoff, apex, landing, verdict) and show them to Spark once.
  Spark may fix data or texts and call `finish` again; the second successful finish ends the run.
- **Probes:** a fixture run ends after the second finish; a validator error goes back to Spark with paths; screenshots
  exist and are non-blank.

### M14. Toolsmith (added 2026-10-27)
- **Does:** an agent tool `make_tool(name, code, probe)`: the agent writes a small module for a measurement the blocks do
  not cover plus a probe on synthetic data with a known answer; the module becomes importable only if the probe passes
  in the sandbox. `finish` lists the verified tools in `analysis.tools`; the page shows them. `promote` turns a useful
  tool into a library candidate (`physics_proof/contrib/` + a test) for human review — the toolbox grows from clip to
  clip.
- **Probes:** see `tasks/M14.md`.

### M12. CLI
- `run <video> [--tag] [--turns] [--cap-usd] [--tier standard|contributor] [--resume]` → run directory and the page path.
- `build <analysis.json> <video>` → rebuild a page without the agent (for player work).
- `ledger` → spend per run and in total.
- **Probe:** `run --dry` with the fake Spark finishes offline in under a minute.

### M13. Publish (GitHub Pages)
- **Does:** `publish <run>` (and `run --publish`): copies the page, its analysis JSON, the video and the mask-check images
  into `site/<slug>/` on the `gh-pages` branch, regenerates the gallery `site/index.html` (one card per analysis:
  thumbnail, clip name, verdict, g ± error, link), commits and pushes. Each analysis gets its own address
  `https://yunoshev.github.io/physics-proof/<slug>/`: send a video in, a new page with the video and its proof appears.
  The gallery is the presentation and the "live product" for the judges.
- **Rules:** only clips we have rights to are published — the run carries `rights` (`public-domain`, `cc-by …`, `own`)
  and `publish` refuses anything else; no secrets and no local paths in published files; each video ≤ 50 MB
  (GitHub's hard limit is 100 MB per file).
- **Probes:** publishing a fixture run gives `site/<slug>/index.html` that opens from a local static server with the
  video playing; the gallery lists it; a run without `rights` is refused; a search of the published tree finds no key
  and no `/Users/` path.
- **Stretch:** a GitHub Actions workflow (`workflow_dispatch`, macOS runner, API key as a repository secret) that takes
  a video URL, runs the agent and publishes the page without a local machine. Only the maintainer can start it (spend).

## 4. Rules of evidence (lessons from research before 26.10)

Before the hackathon we ran a throw-away proof of concept (not part of this repo). These general rules came out of it and
go into the system prompt. They contain no answers about any clip.

1. **A reference size is only as good as knowing what its mask covers.** Use the real size of exactly what the mask
   covers; if a published size refers to a part of the object, find the size of the whole covered extent or measure a
   different extent. The most common silent error is a mask that covers more (or less) than the number you looked up.
   An object seen at an angle shows a mix of its width and depth: use an extent you see face-on, or one that does not
   change when the object turns (the height of an upright object).
2. **Two independent references.** Cross-check the scale with a second reference at about the same depth (another object
   of known size, a body height). If they disagree beyond their errors, find out why before measuring; report both.
   Two extents of the same object are not independent: a wrong idea of what the object is (which parts it includes)
   spoils both and they still agree. The second reference must be a different object or body.
3. **Fit only unsupported motion.** Find where support starts and ends (takeoff and landing from the lowest point of the
   moving body — feet, bottom of the body mask — not from the tracked point; for a body on a surface, where the surface
   stops pressing on it, e.g. where a curved ramp turns vertical). Frames with support flatten or bend the parabola.
   Track a point that moves rigidly with the body during the segment (the top of the head or helmet, the top of the
   mask), and check the fit residuals for a trend before trusting the curvature.
4. **Time is measured, not assumed.** The model checks the real frame rate, duplicated frames, interpolated frames and cuts
   from the frames themselves, and says what its result implies if the clip is not real-time.
5. **Look before trusting a mask.** Overlay sheets and `track_quality` flags are reviewed; each flag gets a written
   decision. Ask SAM again with a better phrase or range when a mask breaks mid-motion.
6. **Honest error budget.** Reference size, pixel scale, fit, tracked point vs centre of mass, spread between repetitions —
   all propagated into g_err. Claiming more than the error bar supports is a failure; "undetermined" is not.
7. **Relative time survives a wrong scale.** Two clips of the same event share the scale error; their ratio of g still
   recovers a relative slowdown. The page may show this as a cross-check, never as the verdict.
8. **Check the time rate independently of the physics under test.** A rhythm whose natural rate is known (steps of a
   walking or running person, a pendulum, wing beats, a bouncing object, falling debris) shows whether the clip plays at
   normal speed. "No world fits" means "retimed" only if the clock check agrees; if the clock is normal, the motion
   itself is impossible. Report the clock check with its error either way.
9. **Test only the worlds the scene allows.** Before deciding, say which worlds the scene rules out and by what (air:
   moving hair, cloth, dust clouds, plants, clouds, birds; ordinary people walking in the background; buildings,
   traffic). A world the scene rules out is not a hypothesis: a retime is computed only against worlds that remain.

## 5. Acceptance (the Moon)

**Clips** (NASA, public domain; committed under `examples/moon/` with their source):
- **A — original:** Apollo 16, 21 April 1972, John Young's jump salute, from the Apollo Lunar Surface Journal
  (`https://www.apollojournals.org/alsj/a16/video16.html`, file `a16salute.mpg`). Re-encoded to H.264 without audio or
  metadata.
- **B — our fake:** the same clip slowed ×1.5 with motion interpolation back to the original frame rate, same encoding.
  Made by a script in the repo from A, so anyone can rebuild it.

**Pass criteria** (checked by `eval/`, which holds the expected answers; nothing in `eval/` is ever put into a prompt):
- Clip A: verdict `fits:Moon`; |g − 1.62| ≤ 2·g_err; g_err ≤ 0.35 m/s² (tight enough to exclude Earth by > 5σ).
- Clip B: verdict `none_fits` with k within 1.5 ± 0.25. `undetermined` is a soft fail; `fits:Moon` is a hard fail.
- Both: the page renders, all five screenshots are non-blank, at least one mask check was made on the reference mask,
  every number on the page is present in a turn log.
- Cost per run ≤ the per-run cap (§7); wall time ≤ 30 min per run.
- Repeatability: 3 runs per clip; at least 2 of 3 pass.

**Second clip (chosen 2026-10-27): the wall run.** A viral AI-generated clip (TikTok, @stuntversehq, 10 s, 24 fps; a
runner sprints up a tall vertical wall in Singapore). Used as commentary: the page credits the author and links the
original; the file is not redistributed elsewhere (`rights` field, M13). Pass criteria:
- the vertical part of the climb is found as an unsupported segment (`kind: wall`) and its downward acceleration is
  measured in a frame attached to the wall (the camera pans and tilts);
- verdict `none_fits` against "unsupported on Earth" (9.81 m/s²) by more than 5σ;
- the time scale is checked independently (step rate on the run-up) and found normal, so the overall verdict is
  "physically impossible at normal speed" rather than "slowed";
- the same page requirements and repeatability as the Moon clips.

## 6. Process

- **Who writes the code:** Spark through Muse Code (`muse exec` with a task file), one module at a time, in the order
  M1 → M2 → M6 → M5 → M3 → M4 → M7 → M9 → M10 → M11 → M8 → M12. A task = the module's section of this spec + its probes +
  the interfaces of modules already done.
- **Who checks:** the maintainer writes the task files, runs the probes, reviews the diff, and sends back a fix task
  when a probe fails. If Spark stalls on a module after two fix rounds, the maintainer writes that module and the README says so.
- **Commits:** code generated by Muse Code carries `[muse-code]` in the subject; maintainer commits carry no tag. History starts on 2026-10-27;
  everything in this repo is new work made during the hackathon.
- **Tests:** probes live next to the code and run with one command; API probes are opt-in (`--api`) and print their cost.
- **Timeline (2026):**

| Date | Work |
|---|---|
| 27.10 | spec, repo; credits claimed (blocker: card and credits on the Billing page) |
| 28–29.10 | M1 client, M2 video, M6 blocks, M5 sandbox, M3 SAM, M4 search — with probes |
| 30–31.10 | M7 mask check, M9 schema, M10 player, M11 finish, M8 agent loop, M12 CLI, M13 publish to GitHub Pages |
| 01–02.11 | Moon acceptance (3 runs per clip), fixes; second clip if time allows |
| 03.11 | demo video (3 min), README, X post draft; last day for submission questions |
| 04.11 | submit by 18:00 ET (deadline 21:00 ET) |

## 7. Budget and credits

**Money (as of 27.10):**
- Meta Model API credits: **$150 per participant**, claimed through the hackathon's credit form (claim before 04.11 21:00 ET).
  Credits arrive in batches and show under "free credits" on the Billing page. **A payment card is required for any call.**
  Until the credits appear, every call is charged to the card. "Spend limits" on the Billing page is an e-mail
  notification only, not a hard stop.
- Own money: at most **$50** in total (owner's decision, 20.10). Before the credits show up only smoke probes run.
- Partner credits (pending, optional): Baseten $100 + 2M TPM (model `meta-models/muse-spark-open-1026`), Modal $100,
  Fireworks $25 — for an open-weights path with Muse Spark Open.

**Prices** (Meta Model API, read 21.10, per 1M tokens unless stated):

| Model | Input | Output | Notes |
|---|---|---|---|
| muse-spark-1.3 | $1.25 | $4.25 | 1M context; `web_search` $2.50 per 1k calls |
| muse-spark-1.3-contributor | $0.10 | $0.20 | data is shared with Meta; 150 RPM |
| sam-3.1 | — | — | $0.20 per 1k video frames |
| muse-voice-transcribe-1.0 | — | — | $0.18 per hour |
| Muse Code | — | — | pay-as-you-go on the API key, or a plan: Everyday $5, High $15, Power $50, Maximum $200 |

**Caps enforced in code:**
- Per analysis run: default **$2** (standard tier); turns 40; SAM 1500 frames; searches 6; mask checks 4.
- Total ledger stop: **$100** of API spend for analysis runs and probes. With the harness build (≤ $40) and a $10
  margin this stays inside the $150 credits.
- Harness build through Muse Code: target **≤ $40** in total; the ledger of Muse Code sessions is checked after each module.
- Clips we have rights to may use the contributor tier (data shared with Meta); third-party clips use the standard tier.

## 8. Submission and prizes

**Deliverables mapped to the rules** (submission on the Cerebral Valley portal by 04.11 21:00 ET):

| Requirement | Deliverable |
|---|---|
| Public repository | this repo, public before submission; README with setup, one-command run, "How we use Meta tools" |
| New work clearly identified | history from 27.10; README section "Built during the hackathon"; no pre-hackathon code |
| 3-minute demo video of what was built | screen recording of a full run on the Moon clips: Spark's turns, SAM masks, mask check, the page and verdicts |
| Live product | the GitHub Pages gallery: one page per analysis with the video and its proof (A, B, more), plus the command to run on any video |
| Rights to all assets | NASA public-domain footage and our own derived fakes only |
| Uses Meta models | Spark (orchestrator, mask check, search), SAM 3.1; optional Spark Open |

**Judging rubric and how we answer it:** Impact 30% (anyone can check a viral clip's physics; fact-checkers, teachers,
viewers) · Use of Meta AI tooling 25% (Spark runs a multi-step investigation with tools, SAM on demand, an independent
Spark checks its own masks, Muse Code wrote the harness) · Technical depth 20% (verified blocks, error budgets, blind
search, honest "undetermined") · Demo 25% (the page itself: overlays and ghosts on real footage).

**Bonus prizes we target:** Best Agentic Use-Case ($5k: the agent decides and coordinates the whole proof); Most Viral
($20k: a demo post on X, engagement until 08.11); Best Build on Meta Open Weight Models ($10k: only if partner credits
arrive and Spark Open can run the loop or its sub-calls).

## 9. Open questions

1. Repository name and GitHub account (provisional: `physics-proof`); when to make it public.
2. Muse Code: headless mode details, whether it can use the contributor tier, plan vs pay-as-you-go for the harness build.
3. Spark video input cost in tokens per second of video; whether SAM 3.1 streams report frame usage.
4. Native tool calling vs strict JSON schema on Meta's Responses API for all seven tools.
5. What counts as "live product" for the judges: published pages, or a running service.
6. The second clip (rights-clean, not sports).
7. Whether Mars stays in the worlds list (adds a third state for the page; not needed for the Moon acceptance).
8. Contributor tier for user-submitted clips (privacy): default to standard tier unless the clip is ours or public domain.

# 12 — Result Data Contract

**Owns:** `src/contract/` — the JSON schemas (`result.schema.json`, `summary.schema.json`), the fixtures, the source-fixture converter (§11), and contract versioning. This is the **only** interface between the analysis side (parts 05–11) and the player (part 13). The player reads exactly two data files per clip: **`result.json`** and the **run summary**, plus the page assets defined in §12. Everything on the page is either in these files, derived from them by the player template, or one of those assets.

`contract_version: 2`. (Version 2 replaces normalised coordinates with source-video pixels throughout — see §0. Anyone still producing version 1 is out of date; parts 11 and 13 regenerate together on this bump, per the README rule.) Unknown top-level fields are rejected; optional fields are explicitly marked.

## 0. Coordinates — source pixels, everywhere

**All geometry in this contract is in source-video pixels**: mask outlines, tracked points, reference extents, takeoff level, ghost paths, fit curves. Nothing is normalised to 0–1. The player maps source pixels onto the displayed picture, accounting for scaling, letterboxing, and **non-square pixels** (part 13 §5) — which is why `video` (§1) carries the sample aspect ratio. Metres are carried alongside pixels wherever both are shown.

Origin: top-left of the coded frame, `x` right, `y` down, in pixels. (Physics in metres with `y` up is the helpers' internal business, part 09; the contract is a display-and-evidence format, so it speaks pixels and metres, never screen fractions.)

## 1. `result.json` — top level

| Field | Type | Notes |
|---|---|---|
| `contract_version` | int | = 2. |
| `video` | object | `{coded_width, coded_height, sample_aspect: {num, den}, measured_fps, frame_count, duration_s}`. Display width = `coded_width × num/den` (clip A: 352×240, SAR 200:219 → display ≈ 321.5×240, 4:3-ish). From `timing.json` + probe (part 05). |
| `first_look` | object | §2. What the agent saw **before measuring**. |
| `references` | array | §3. |
| `scale` | object | §4. |
| `segments` | array | §5. Empty only in undetermined results. |
| `calculation_steps` | array | §6. The sidebar's step data: formulas with numbers already substituted. |
| `clock` | object \| null | §7. `null` + `clock_absent_reason` where relevant. |
| `worlds` | object | §8. |
| `error_budget` | object | §9. |
| `verdict` | object | §10, computed by part 11. |
| `sentence` | string | The overall sentence, computed by part 11. The player displays it verbatim. |
| `page_texts` | object (optional) | Per-run string overrides for player template chrome (headings, tab-less labels); flat key→string map, digit-free (part 11 V12), placeholders `{g}`/`{world}` substituted by the player. Key-moment captions live in §5, first-look text in §2 — not here. |
| `self_built_tools` | array | `{name, purpose, attempts, status}` from the part-10 registry (all built tools, used or not). |
| `provenance` | object | `{model, run_id, artifacts: [{name, produced_by, path}]}` — paths relative to the run directory; every artifact any number cites must appear here. The page build (part 13) may copy/derive assets only from artifacts listed here and from the page's own video (§12). |

`result.json` must never contain ground truth, expected verdicts, clip identity, or anything about another run (parts 03, 08 R-E3). The acceptance "reveal" data reaches the page by a separate harness sidecar at page-build time (part 13 §10), never through this file.

## 2. `first_look` — before measuring

`{question, summary, scene_card: {scene, place_date | null, confidence, objects: [string]}, by_eye: {jump_m | null, airborne_s | null, reasoning} | null, views: [{frame_start, frame_end, artifact}]}`

- `question` is the headline the first screen asks ("Does the physics add up to the Moon?"). `scene_card` backs the "What we see" card: scene description, place/date **as read from the frames** (may be `null` — the agent says what it can see, not what it knows), a confidence word (`low|medium|high`), and object chips.
- `by_eye` backs the "By eye, before measuring" card: the agent's naked-eye estimates and one line of reasoning. These are explicitly **pre-measurement model estimates**: every field carries `used_in_verdict: false` by construction (the validator never reads this object), they are labelled as such on the page, and they are the *only* model-estimated numbers in the file — permitted because they are displayed as a before/after contrast with the measured result, never as evidence. If the agent made no by-eye estimate, `by_eye` is `null` and the card says so.

## 3. `references[]` — the scale's evidence

`{name, extent_description, extent_type (face_on|rotation_invariant|projected), extent_px: {x1, y1, x2, y2, length_px, frame}, size_m, size_tolerance_m, size_derivation: {mode (single|sum|mean), note}, sources: [{url, domain, quote, quote_highlight, value_m | null, source_type}], mask: {artifact, object_id, frame, outline: [[x,y],…]}, mask_check: {artifact, coverage_answer, confidence | null, alternative_readings: [{description, size_m}]}}`

- `extent_px` gives the **endpoints of exactly the extent that was measured**, in source pixels on the scale frame — the player draws its ruler between these two points (part 13 §6), not around a bounding box.
- `sources` is a list: a size may rest on several sources (the prototype's reference summed two). Each source carries the **verbatim quote**, the `quote_highlight` substring (the number inside the quote, highlighted on the card), its domain, and the value it supports. `size_derivation.mode` says how the sources combine (`sum of two sources` is a displayable tag, not a secret).
- `mask.outline` is the simplified polygon (source pixels) of the reference mask at `mask.frame`.
- `mask_check.confidence` is the blind check's self-reported confidence where it gives one (e.g. "PLSS + OPS stack, confidence 0.9"); the coverage answer remains the load-bearing field (part 11 V3).
- `alternative_readings` is where the Apollo backpack ambiguity (0.66 m vs. 0.91 m) lives; part 11 V5 controls how it propagates into σ.

## 4. `scale`

`{frame, m_per_px, sigma_m_per_px, reference_index, extent_px (copied from the reference for the player's convenience), second_reference_index | null, second_reference_absent_reason | null, check_scale: {m_per_px, sigma} | null}`

The `check_scale` (independent second object, R-S3) is stored alongside, not averaged in silently; part 11 has already refused a fake one.

## 5. `segments[]` — the measured motion

`{id, label, kind (free_flight|wall), mask: {artifact, object_id}, frames: {start, apex, end}, times_s: {start, apex, end}, key_moments: [{type (takeoff|apex|landing|wall_start|wall_end), frame, t_s, caption}], overlay: [{frame, outline: [[x,y],…], point: [x,y], bbox: [x,y,w,h]}], track: [{frame, t_s, x_px, y_px, x_m, y_m}], fit: {g_app, sigma_g, a_px_s2, sigma_a_px_s2, v0, y0, residual_trend, n_points}, fit_curve_px: [{t_s, x_px, y_px}], takeoff_level_y_px, apex_info: {rise_m, sigma_m, feet_clearance_m | null}, landing_info: {airborne_s, sigma_s}, world_outcomes: [{world, landing_time_s, landing_x_px}], ghosts: [{role (earth_counterfactual|fitting_world), world, gravity_m_s2, points: [{t_s, frame, x_px, y_px}], landing: {t_s, x_px, y_px}}], repetitions: [{frames, g_app, sigma_g}]}`

- `label` ("Jump 1", "Jump 2", "Wall run") is what the timeline ranges and sidebar steps are called.
- `overlay` is per frame: the **simplified mask outline in source pixels** (code-generated from the mask; vertex count capped in the schema so files stay small), the tracked point, and the mask bbox (the page build cuts ghost/chronophotograph silhouettes from `mask.artifact` + `bbox`, §12). This replaces the first attempt's dot-only overlay.
- `takeoff_level_y_px` is the horizontal line drawn at takeoff/landing ground level. `apex_info` and `landing_info` carry exactly the numbers the Apex/Landing captions print. `world_outcomes` carries the **per-world landing times and positions** (clip, Moon, Earth…) that the chronophotograph's time axis labels ("Earth 0.40 s · Moon 0.97 s · in the clip 1.03 s") — computed by part 11 with the ghost helper, not estimated by the player.
- `fit` numbers are the validator-recomputed ones (part 11 V2), including the pixel-space acceleration (`a_px_s2`) because the sidebar's formulas show it (`a = 117.1 ± 3.4 px/s²` → `g = a·s`).
- `ghosts` are validator-computed (part 11 §3) and may be **empty** — on an Earth verdict (the fit curve is the Earth path) and for wall segments. Ghost `points` are in source pixels and include the frame each point belongs to, so silhouettes can be placed per frame.
- `key_moments[].caption` is agent-written display text: short, digit-free (part 11 V12). The numbers in event captions come from the `*_info` fields, never from the caption.

## 6. `calculation_steps[]` — the sidebar's data

One entry per sidebar step, in display order:

`{id, title, frame, frame_end | null, segment_id | null, short: [block], full: [block], caveats: [{text, artifact | null}]}`

A **block** is one of:

- `{type: "formula", latex, fallback, chip: {text, tone (final|intermediate)} | null}` — a typeset formula **with the real numbers already substituted** (`s = L/ℓ = 0.874 m / 67 px`), where `latex` is the KaTeX source and `fallback` is the same formula as readable plain text for when KaTeX is unavailable (part 13 §3). `chip` is the result chip rendered after it (amber-filled = final, cyan-outlined = intermediate).
- `{type: "text", text}` — one short line of explanation.
- `{type: "bars", source: "error_budget"}` — the uncertainty step's horizontal bars; the player renders them from §9 (percentages are σᵢ²/σ² shares, computed by the player from the components — pure display arithmetic).

Rules: every number appearing in a `latex`/`fallback`/`chip` string was produced by executed code and cites its artifacts through the step's provenance (the validator spot-recomputes the headline values as in part 11 V2); agent-authored prose (`text`, `caveats[].text`) remains digit-free (part 11 V12). `short` is the default view; `full` adds the longer derivations and cross-checks behind the "Full calculation" toggle. A step that a run cannot support carries a single `text` block saying what is missing — the player never has to invent a step (part 13 §13).

Step ids are a controlled vocabulary so the player can icon/order them: `time_from_frames, mask_check, scale, segment, fit, measured_g, clock, uncertainty, verdict` (segment-specific steps repeat per segment via `segment_id`).

## 7. `clock`

`{signal_description, measured_rate_hz, measured_rate_sigma_hz, interpretation (step|stride), band_hz: [lo, hi], natural_range_hz: [lo, hi], natural_range_source: {url, quote}, implied_stretch, implied_stretch_sigma, reads_normal: bool}`

The stretch arrives **with its σ** (part 11 V11's agreement test is computed from these), and the natural range arrives with its source — or the clock does not exist as far as the verdict is concerned.

## 8. `worlds`

`{candidates: [{world, g_m_s2, fits_native: bool, delta_sigma, retime_factor | null}], excluded: [{world, evidence_text, evidence_frames: [int], evidence_artifact}]}`

`candidates` are the worlds actually tested (the verdict card's g-axis shows exactly these, no others); `excluded` are the scene-ruled-out worlds with their visual evidence. `delta_sigma` = |ḡ − g_world| / σ_g is what the per-world chips print ("Moon 0.9σ ✓").

## 9. `error_budget`

`{components: [{name, sigma_contribution, basis}], sigma_total, sigma_relative}`

Component names from the controlled list (`reference_size`, `pixel_scale`, `fit`, `point_vs_com`, `repetition_spread`, `reading_spread`, `projection`) so the player can label bars without parsing free text. `sigma_relative` (σ_g/g) feeds the "√Σεᵢ²" line.

## 10. `verdict`

`{kind (world|retimed|impossible|undetermined), world | null, direction (slowed|sped) | null, factor | null, g_measured, sigma_g, reason | null, clock_note | null}`

Display wording, the stamp (§13.7 of part 13), and colours are derived from this object by the player; `reason` is mandatory iff `kind = undetermined`, from part 11's controlled vocabulary.

## 11. Fixtures, including the real-data source fixture

- **Synthetic fixtures** (kept): a hand-made Moon-verdict result and an undetermined-by-budget result, now in contract v2 — for edge cases and degradation tests.
- **The real-data fixture.** The owner has placed the output of an earlier test run on clip A in the repo as **owner input**: `fixtures/source/clip-a-run/` — `analysis.json` (older format: track points in px per frame, masks as row spans, scale, references with quotes, flights, verdict), `sam/*.npz`, `mask_checks/`, `search.jsonl`, `summary.json`, `clip.mp4`. Part 12 owns a small converter, `src/contract/convert_source_fixture.py`, that translates this **once** into a contract-v2 fixture (`fixtures/clip-a/`: `result.json`, `summary.json`) against the real clip. The converter:
  - maps only what the source actually contains; derives only geometrically-defined values (outlines from row-span masks, extent endpoints, takeoff level, per-world landing times from the recorded fit/takeoff state) using part 09's helpers; **never invents a measurement the source doesn't support** — an unsupportable field is left `null`/absent and the player's degradation path (part 13 §13) is what the preview then shows;
  - records in the fixture's `provenance` that it is a conversion, with the source paths;
  - is deterministic: re-running it regenerates the fixture byte-identically (modulo its recorded hash), and it is rerun by part 12's tests, not by hand.
- Part 13's tests and previews use the clip-A fixture **with the real clip** (overlays on the actual astronaut); the synthetic fixtures cover undetermined/impossible shapes. Validation tests assert both synthetic fixtures validate, reject with any required field removed, and that the converted fixture validates.

## 12. `summary.json` and page assets

`summary.json`: `{contract_version, run_id, cost_usd: {total, spark_input, spark_cached, spark_output, sam, search}, turns, model, sam_frames_billed, searches, mask_checks, wall_time_s, budget_outcome (completed|budget_undetermined), result_path}` — written by loop/accounting (part 14), never the agent. (Subset rule of part 14 §2 applies to its cost breakdown.)

**Page assets** (built by part 13's page build, not part of the result): poster frame; mask-check overlay image(s) copied from `provenance` artifacts; **object cut-outs** — the page build extracts, from the page video + the segment's mask artifact (or the fixture's `sam/*.npz`), transparent cut-out images of the tracked object at the frames the ghosts and chronophotograph need, each with its bbox and anchor (tracked point) recorded in the page's asset manifest. Assets are presentation copies only; nothing is ever analysed from them.

## 13. Owner review of the clip-A fixture (2026-10-27) — must not recur

The first converted fixture faked what it should have measured. These are now binding, each with a test in `tests/contract/`:

1. **Outlines come from the masks.** For every frame of a segment that has a mask in the source `sam/*.npz`, `overlay[].outline` is the contour of that mask object (largest external contour, simplified to ≤ 80 vertices, source px). A synthetic box around the tracked point is a defect. Test: at the clip-A takeoff, apex and landing frames the outline has ≥ 20 vertices and its bbox height is ≥ 50 px (the astronaut is ~126 px tall).
2. **Ghosts are real trajectories.** Each ghost starts at the measured takeoff point and frame, rises to the measured apex height, and falls under its world's `g` (converted to px/s² with `scale`), with one point per frame until it reaches the takeoff level; `landing.t_s` is that time. Test: for clip A the Earth ghost lands earlier than the measured landing and has ≥ 5 points; the Moon ghost lands within 0.15 s of the measured landing.
3. **Every event the player freezes on is in the data** with its frame: scale (the reference frame), takeoff, apex, landing, verdict (a frame after the last landing). Test: the clip-A fixture lists all five.

## 14. Evidence: what the agent submits (owner addendum 2026-10-28, from the fourth live run)

In the fourth live run the agent measured well: g = 1.73 ± 0.12 from a clean parabola, the Moon 0.9σ away and Earth excluded. Still, all three submits were rejected, with 124, 106 and 105 errors, 112 of the first 124 being `MISSING_FIELD`. `submit` was checked against **this whole result schema**, which asks the agent for fields that code computes: per-frame overlay polygons, the recomputed fit, ghosts, calculation steps. Therefore:

- **A separate evidence schema,** `src/contract/evidence.schema.json`, describes exactly what the agent submits. It is the result schema **minus the computed fields**, plus the few agent-side pointers listed below. Computed fields, which the evidence never carries:
  - `contract_version`, `video` (from `timing.json` and the probe);
  - in each segment: `overlay` (from the mask artifact), `fit`, `ghosts`, `world_outcomes`, `apex_info`, `landing_info`, `times_s`, and each key moment's `t_s` (from frames + timing);
  - `track` in metres and seconds (from the track artifact, the scale and the timing);
  - `calculation_steps`, `verdict`, `sentence`;
  - in worlds: `candidates[].g_m_s2`, `fits_native`, `delta_sigma`, `retime_factor` (the agent names candidate worlds only);
  - `error_budget.sigma_total` (recomputed);
  - `provenance.model`, `provenance.run_id`, and `produced_by` of each artifact (from the ledger; the agent cites paths only);
  - `self_built_tools` (from the part-10 registry).
- **Agent-side pointers:**
  - `segments[].track_artifact`: a path under `workspace/` or `artifacts/`, created in this run by `run_python` or a tool. It holds a JSON list of `{frame, x_px, y_px}` rows, the tracked point per frame in source pixels. This is the input of the fit recompute (part 11 V2), and the only one.
  - `segments[].tracked_point`: short words, e.g. "top of the helmet".
  - `camera`: either `{still: {reference_phrase, reference_track_artifact}}` (a static scene object tracked over the fit window, same row format) or `{relative_track_artifact}`.
  - `clock`: `null` when the evidence makes no clock claim. An empty object is invalid.
- **Every property in the evidence schema has a `description`.** One line each: what it means, its unit, and how to obtain it with the tools. `submit`'s description is generated from this schema (part 07 §11).
- **Assembly.** On acceptance, part 11 builds `result.json` from the evidence plus the run's records, filling every computed field above. The assembled result must pass `result.schema.json` (existing test).
- **Tests:**
  - the evidence example shipped with the schema (`src/contract/evidence.example.json`) validates against it;
  - every computed field above is absent from the evidence schema;
  - every evidence property has a non-empty description.

## 15. Owner addendum (2026-10-28, from the sixth live run): the error budget's rules are in the schema

The agent learns the evidence format only from the schema's descriptions (part 07 §11 generates the submit description from them). The sixth run learned the error-budget rules only from a rejection.

- **The `error_budget.components` description states the rules** of R-E1 (`prompts/measuring_rules.md`), in the validator's terms: always required `reference_size`, `pixel_scale`, `fit`, `point_vs_com`; `reading_spread` required when an alternative reading's size differs from the headline; `repetition_spread` required when a segment has repetitions; σ_total is recomputed as the quadrature sum plus the reading spread, and a σ smaller than any component is rejected.
- **`references[].mask_check.alternative_readings` says when it is needed** (R-S2: the blind check's coverage admits another reading, e.g. backpack with or without its top unit) and that each alternative with a different size must be priced by `reading_spread`.
- **The example evidence (`evidence.example.json`) carries every always-required component.**
- **Test:** the example validates; the description text of `error_budget.components` names all four required components; a test keeps that list equal to the validator's.

## 16. Owner addendum (2026-10-28, from the seventh live run): one frame of reference, real-run shapes

The seventh run was the first accepted one. Built into a page, its result broke the player that had been tuned on the clip-A fixture: the two disagree on time origin, takeoff level and artifact paths. The contract fixes one convention, and a real run joins the fixtures.

- **One time base: video seconds.** Every `t_s` and every time field in `result.json` (`track`, `fit_curve_px`, `key_moments`, `times_s`, `ghosts[].points`, `ghosts[].landing`, `world_outcomes[].landing_time_s`) is the frame's time in the video, from `input/timing.json`. Durations (`landing_info.airborne_s`) are differences. The player derives "time after takeoff" as `t_s − times_s.start`. Seen: the run used video time, the clip-A fixture used time since takeoff.
- **Takeoff level is the tracked point at takeoff,** not the ground: `takeoff_level_y_px` = the tracked point's `y_px` at the takeoff frame, computed by code from the track. It leaves the evidence (computed field, §14). `track[].y_m` = (`takeoff_level_y_px` − `y_px`) × `m_per_px`, the tracked point's height above its takeoff position; `apex_info.rise_m` = the fitted parabola's apex above that level; ghosts start at the takeoff point and land when they return to that level. The player's "takeoff level" line passes through the tracked point, as in the approved player. Seen: the agent gave the ground under the feet (186 px) while tracking the backpack (61 px): `y_m` was 1.23 m at takeoff, `rise_m` 1.27 m, and the Earth ghost "landed" 0.07 s after takeoff.
- **Artifact paths are relative to the run directory,** the folder that holds `result.json` (already §2, `provenance`). The clip-A fixture follows it too: the converter copies every file the result cites into `fixtures/clip-a/` (`artifacts/…`, `input/timing.json`) and cites them run-relatively.
- **The jumper is described:** each segment carries `subject: {kind: person | animal | object, description}` (evidence field). Part 11 uses `kind` for the scale cross-check.
- **The real-run fixture.** `fixtures/source/run-7/` is owner input: the seventh run's directory without logs (`input/`, `artifacts/`, `workspace/`, `summary.json`); its accepted evidence is `artifacts/t34_evidence.json`. Part 11 builds `fixtures/run-7/` from it (part 11 §9).
- **Tests:** in both fixtures every time field lies within the video's duration and `track[0].t_s` equals `times_s.start`; `track` row at the takeoff frame has `y_m` = 0; `rise_m` is below 1 m; every cited artifact path resolves inside the fixture folder.

## 17. Owner addendum (2026-10-28, from the v12 player review): a fixture carries everything it points to

Building the page from `fixtures/clip-a/` logged `mask sheet missing: …/artifacts/flag_pole.240-270.0.2.png`. The converter copied the files `result.json` cites, but not the files those copies cite in turn: `artifacts/mask_checks.jsonl` names a `sheet` and an `npz` for each row, and only the astronaut's sheet came along. The source has the flagpole's sheet (`fixtures/source/clip-a-run/mask_checks/flag_pole.240-270.0.2.png`).

- **The copy is closed.** The converter follows references transitively: every path inside a copied JSON or JSONL file (`sheet`, `npz`, `overlay_artifact`, and any other string field naming a file of the source run) is copied too and rewritten run-relatively (`artifacts/<basename>`). A reference whose file is absent from the source fails the conversion with the path; it is never dropped silently.
- **Test:** walk every JSON and JSONL file in `fixtures/clip-a/`; every string value ending in `.png`, `.jpg`, `.npz`, `.json`, `.jsonl` or `.mp4` resolves to an existing file inside the fixture folder.

## 18. Owner addendum (2026-10-28): several references

The scale is always cross-checked by two or three references (part 08 R-S6, part 11 §13).

- `scale` gains `reference_indices: [int]`, every reference used, computed. `reference_index` stays the headline reference: the one the player draws the ruler on. `second_reference_index` stays and equals `reference_indices[1]`, or null. `m_per_px` and `sigma_m_per_px` are computed by code from all references (part 11 §13.3).
- The schema descriptions of `references` and `scale` state the rule: at least two references of different things, every pair within 2σ, one reference gives an undetermined verdict. They no longer mention a person rule. `segments[].subject.kind` is descriptive only.
- **Test:** the schema accepts `reference_indices` of length 1 to 5; the `references` description mentions "two" and contains no person rule.

## 19. Owner addendum (2026-10-28): every motion in the clip is listed

- `first_look.motions: [{frame_start, frame_end, description, segment_id | null, skip_reason | null}]` (evidence field, required, at least one entry): every interval of the motion under test the agent found while viewing the whole clip (part 08 R-M4). Each entry names its segment, or says why it was not measured. The schema description states the rule.
- The player's timeline shows one mark per segment, labelled with the segment's label ("Jump 1", "Jump 2"). Listed but unmeasured motions show as a grey tick with the skip reason as its tooltip.
- **Test:** the clip-A fixture's `first_look.motions` has two entries, the first naming the fixture's segment; the schema rejects an entry with neither `segment_id` nor `skip_reason`.

Breaks on purpose: `tests/validate/` (its baseline evidence in `tests/validate/conftest.py` lacks `first_look.motions`); part 11 updates it next (part 11 §14).

## 20. Owner addendum (2026-10-28): `state_match`

- `references[].size_derivation.state_match: {shown_and_covered: string, shown_not_covered: string}` (evidence, required): what the mask shows that the size source also covers, and what it shows that the source does not (part 08 R-S7). The schema description states R-S7 and R-S8.
- **Test:** the schema rejects a reference without `state_match`; the clip-A fixture carries it (the converter writes it from the fixture's known sizes). Real-run fixtures (run 7, run 8) predate it and are assembled without that check, like §16's other rejecting checks.

Breaks on purpose: `tests/validate/` (its baseline evidence lacks `state_match`); part 11 updates it next (part 11 §15).

## 21. Owner addendum (2026-10-29): the example asks the viewer's question, in one world

Part 01's addendum of 2026-10-29: the clip's own question, in the scene's world. The agent copies the evidence example, so the example shows the new shape:

- `src/contract/evidence.example.json`: `first_look.question` is "Is this hop realistic on the Moon?"; `worlds.candidates` is `[{"world": "Moon"}]` and `worlds.excluded` is `[]`.
- Schema descriptions: `first_look.question` — "The viewer's question about what the clip shows or claims, in plain words; the result answers it (part 01, 2026-10-29)"; `worlds.candidates` — "The scene's world only; a second one only when the question names it"; `worlds.excluded` — "Empty unless an earlier contract version listed exclusions".
- No field is added or removed; `contract_version` stays.
- **Tests:** the example validates; it has one candidate, an empty `excluded`, and a question that does not contain "gravity" or "physics".

## 22. Owner addendum (2026-10-29): `range_checks`

Parts 01 and 02 (second addenda of 2026-10-29) add range checks. The contract carries them; `contract_version` goes up by one, and a result of the previous version still loads in the player.

- **Evidence, new optional top-level array `range_checks`** (absent or empty when the clip needs none). Each item:
  - `id` (short slug), `label` (plain words, e.g. "palm / hand length"), `answers` (which part of the question it settles, one sentence);
  - `unit`: one of `ratio`, `m`, `s`, `m/s`;
  - `frame` (the frame the extents are on) and `extents`: one or two objects shaped like `references[].extent_px` (`x1, y1, x2, y2, length_px, frame`) plus `name` ("hand length", "palm length");
  - `value`, `sigma` (same unit), `formula` (plain text, e.g. "palm_px / hand_px" or "length_px × m_per_px"), `uses_scale` (bool), `measurement_artifact` (the `run_python` artifact that printed the value, σ and extents);
  - `range`: `min`, `max`, `typical` (number or null), `what` (whose range: "adult hands, US Army survey ANSUR II, 2012"), `bounds_kind` (`min-max` or `percentile`, with `percentiles` such as [5, 95] when percentile), and `sources`: items shaped like `references[].sources` but carrying `value` (the number quoted) and `bound` (`min`, `max` or `typical`) in place of `value_m`.
- **Segments may be empty when `range_checks` is not.** `segments` keeps its item shape; its `minItems` becomes 0, and part 11 rejects an evidence with neither (`MEASUREMENT_MISSING`). `clock`, `clock_absent_reason`, `error_budget` and `camera` stay required; with no segment, `clock` is null, `clock_absent_reason` says "no motion measured", and `error_budget` lists only what applies.
- **Result, new top-level array `range_checks`** (always present, possibly empty): the evidence item plus the validator's `outcome` (`inside`, `outside`, `not_counted`), `delta_sigma` (distance of the measured value from the nearer bound in σ, 0 when inside; part 11 §40) and `side` (`below`, `above` or null).
- **Verdict:** new field `decided_by`: `gravity`, a range check `id`, or null; `g_measured` and `sigma_g` are null when there is no gravity part.
- **Example and fixtures:** `evidence.example.json` gains `"range_checks": []` (the Moon hop is answered by g; the schema's field descriptions, which part 07 lists in the submit description, carry the item shape in full). A new fixture `fixtures/still-range/` holds a range-only evidence and its result (one still frame, two checks: a ratio inside its range and a ratio outside it) for parts 11 and 13 to test against.
- **Tests:** the example and both fixtures validate; an evidence with empty `segments` and one range check validates; one with neither fails the schema test only through part 11's check, not the schema.
- **Paths:** the new fixture lives at `fixtures/still-range/`, which part 12 owns (`tools/parts.json`).

Breaks on purpose: `tests/pagebuild/test_pagebuild.py` (it pins `contract_version` 2); part 13 updates it next and compares with `src.contract.CONTRACT_VERSION`, not a literal (part 13 §32).

## 23. Owner addendum (2026-10-29): the plan travels to the page

Part 06's addendum "Describe, then Wonder, then measure" (2026-10-29) writes `artifacts/wonder.json` before the loop.

- **Result, `first_look.wonder`** (optional object, null when the run had no plan): `claim`, `checks` (each `what`, `why`, `compare_with`), `realistic_if`, `not_realistic_if`, copied by part 11 from `artifacts/wonder.json`. The evidence does not carry it; the agent never retypes it.
- **Tests:** a result with `first_look.wonder` and one with it null both validate; the clip-A fixture carries a small plan (claim "the astronaut hops far too high for Earth", one check on g against the Moon's 1.62).

## 24. Owner addendum (2026-11-01): `first_look.overview`, the trajectories the agent decided from

- `first_look.overview` (evidence field; required when a segment exists, part 08 R-M6):
  `{artifact, object_id, tool_result, candidates: [{id, frame_start, frame_end, airtime_s, peak_rise_px, decision, segment_id | null, reason}], first_check: {segment_id, why}}`.
  - `artifact`, `object_id`: the whole-clip `segment` masks and the object the overview was made of; `tool_result`: the `motion_overview` result file.
  - `decision` ∈ {`measured`, `not_a_flight`, `not_measurable`}; `measured` names its `segment_id`; the others carry a `reason`.
  - `first_check`: the segment measured first and why (R-M7).
- Every candidate with `decision: measured` also appears in `first_look.motions` with that `segment_id`.
- **Test:** a fixture with two measured candidates and one `not_a_flight` validates; an entry `measured` without `segment_id`, or a `not_a_flight` without `reason`, is rejected.

# 11 — Result Validation

**Owns:** `src/validate/`. The agent submits **evidence**; this module checks it and, if it passes, **computes the verdict, the ghosts, and the overall sentence itself** (part 06 §2 — the agent never retypes them, and no check ever compares prose). **Small-code principle:** every check below is a comparison, a mask-overlap computation, or a recompute using an existing part-09 helper. There is no second model and no judgement call in this module; anything judgement-shaped was pushed into the evidence requirements themselves.

## 1. Interface

`validate(submission, run_context) → {accepted, errors: [{code, field, detail}], result?}`

- `run_context` gives the validator the run's own records: `timing.json`, the tool ledger (what artifacts exist, which mask checks ran), the self-built registry, and the sandbox's produced-files log. The validator trusts **artifacts and ledgers**, not the agent's narration.
- Errors are structured codes (part 06 §2). At most 3 submit attempts; then the run ends as undetermined with the last error list preserved in the result's provenance.

## 2. The checks

| # | Code | Check (simplest version that catches the seen failure) |
|---|---|---|
| V1 | `MISSING_FIELD` | Submission parses against part 12's schema. |
| V2 | `NUMBER_WITHOUT_PROVENANCE` | Every measured number cites an artifact produced by `run_python`/a tool in this run. The validator **recomputes the headline fit** from the submitted track artifact with `fit_parabola` and requires agreement within rounding — agent-typed fit numbers that don't match the track are rejected. |
| V3 | `MASK_CHECK_MISSING` | **The mask-check gate:** the mask used as the size reference has a `check_mask` artifact (part 07 §4) recorded in the ledger, and the submission quotes its coverage answer. ≥1 blind check on the reference mask is required for *any* non-undetermined verdict. |
| V4 | `SECOND_REFERENCE_SAME_OBJECT` | If two references are claimed as independent: load both masks on a common frame, reject if intersection > 50% of the smaller mask (R-S3). If no second reference: submission must carry `second_reference_absent_reason`; absence is allowed, fakery is not. |
| V5 | `REFERENCE_READING_UNPRICED` | If the blind check returned multiple readings of what the reference mask covers, the submission carries a `g` per reading or an explicit justification; the spread enters the error budget (R-S2, V9). Silent single choice → reject. |
| V6 | `FIT_INCLUDES_CONTACT_OR_DUP` | Fitted frame sets (from the track artifact) are disjoint from the submitted contact/support intervals, contain no confirmed-duplicate frames, and cross no cut (R-T2, R-M1) — set intersections against `timing.json` and the support track. |
| V7 | `RESIDUAL_TREND` | The recomputed fit's residual-trend statistic is within the library threshold, or the submission documents a re-track with a rigid point (R-M2). |
| V8 | `CAMERA_UNACCOUNTED` | Either the scene-reference track moves less than the threshold in pixels (camera still, attested by measurement), or the submitted trajectory is the `relative_track` artifact (R-M3). A screen-pixel track from a moving camera → reject. |
| V9 | `ERROR_BUDGET_INCOMPLETE` | Error budget itemises R-E1's components; validator recomputes σ_total as the quadrature sum plus any V5 reading-spread and rejects if the submitted σ is smaller than recomputed, or smaller than any single component. Repetition fits must not have identical residuals (R-E2). |
| V10 | `WORLD_NOT_FROM_SCENE` | Every world is listed `candidate` or `excluded`; exclusions carry frame-referenced evidence. Fits are computed only over candidates (R-W1); a verdict naming anything else is uncomputable here (see §3). |
| V11 | `CLOCK_LOGIC` | A retimed verdict (non-scene-pinned case) requires clock evidence: measured rate ± σ, band, stated natural range with its source, and the implied-true-rate arithmetic of R-C4 recomputed (stretch agreement uses combined σ of `s_grav` and `s_clock`, per part 02 §5). "Impossible" requires either the clock reads normal / retiming makes the clock unnatural, or an outright wall-rule violation > the submitted σ by the claimed factor. Step/stride ambiguity flagged by the clock helper and verdict-changing → forced undetermined (R-C3). |
| V12 | `UNMEASURED_NUMBER_IN_TEXT` | Any self-built tool named in provenance is in the registry, `passed`, hash-matching (part 10 §4). Agent-authored display text — key-moment captions **and `page_texts` values** (part 12) — contains **no digits**: the one simple rule that keeps agent prose from smuggling in unmeasured numbers. (Template placeholders like `{g}` contain no digits and are unaffected.) |

What is deliberately **not** checked: whether the agent's visual reading of a scene is "right". The validator cannot see; it can only refuse to let unexamined masks, same-object "second references", contact frames, or clock-free retiming claims become verdicts. That is the honest limit of code enforcement, and part 02's undetermined path is the pressure valve.

## 3. Verdict computation (deterministic, from the evidence)

In order, implementing part 02 §§4–5:

1. Recompute `g_app ± σ_total` (V2/V9) for each submitted measurable segment.
2. `worlds_fit` over **candidate** worlds only. Exactly one fit at `s = 1` → that world's verdict.
3. No native fit → clock logic: `s_grav` per candidate vs. `s_clock` (agreement → *Slowed down / Sped up ×k*; clock normal or corrected clock unnatural → *Physically impossible*). No clock + exactly one scene-pinned candidate world → retimed to that world, flagged `clock: none, scene-pinned`. No clock otherwise → *undetermined (cannot separate retiming from impossibility)*.
4. Wall segments: vertical acceleration vs. candidate `g`; a deviation confirmed under a normal clock → *Physically impossible* regardless of step 3.
5. Contradictory segments that cannot be reconciled → *undetermined (conflicting segments)*, never the more dramatic verdict.

The **ghosts** are then computed here, not submitted: for each free-flight segment, a list built from the fitted takeoff state via `ghost(takeoff_state, g, …)` (part 09):

- an entry with `role: earth_counterfactual` at Earth gravity, **whenever the verdict's world is not Earth** (on a Moon verdict, this is the "on Earth he would have landed here" path);
- an entry with `role: fitting_world` at the fitting world's gravity, whenever that world differs from Earth (it may sit close to the fit curve; it is computed from the takeoff state, not traced from the fit);
- on an **Earth verdict the list is empty** — the fitted curve already is the Earth path, and part 13 labels it as such rather than drawing the same curve twice;
- wall segments get no ghosts (there is no takeoff state); an impossible verdict's ghosts are still the two entries above where a free-flight takeoff exists, since they are display counterfactuals, not claims.

The **overall sentence** is generated from a template with the measured numbers formatted by one function (`g` and `σ` to two significant decimals in σ, matching decimals in `g` — e.g. `1.73 ± 0.23` — never raw float reprs).

## 4. The synthesis path (no valid submission)

Budget exhaustion (part 06 §5) or exhausted submit attempts produce a result anyway: the validator synthesises a minimal valid part-12 file — verdict *undetermined* with the recorded reason (`budget`, or the last error codes), whatever first-look/references were genuinely produced, empty segments, and full run provenance. A crashed or broke run must still yield a player-openable file that says, honestly, that it couldn't determine anything.

## 5. Output

On acceptance: `result.json` exactly per part 12, written by this module — the only writer of that file in the system.

## 6. Owner addendum (2026-10-28, from the fourth live run)

The agent's physics was right (g = 1.73 ± 0.12; Moon 0.9σ; Earth excluded), yet the run ended `undetermined: submit attempts exhausted`. Each failure below has a test that would have failed on that run's submissions; they are kept as fixtures in `tests/validate/`.

1. **V1 checks the evidence schema** (part 12 §14), not the result schema, and **V1 gates the rest.** If V1 fails, only V1's errors are returned, and the other checks do not run on malformed input.
2. **A crash is our bug, not the agent's attempt.** Every check is total over schema-valid input. Any exception is written with its traceback to `logs/validator_fault.txt`. The run then ends as `undetermined` with reason `validator_fault`; it is not returned to the agent as an error and not counted as an attempt. Seen: two `VALIDATOR_FAULT`s per attempt (`worlds.get` on a list, `a.get` on a string), which the agent read as its own fault.
3. **Error records name the exact place.**
   - `field` is the JSON path with indices: `segments[0].track_artifact`, never `segments.?`.
   - A missing or unreadable input is `MISSING_FIELD` naming that input, never a rule code. Seen: `FIT_INCLUDES_CONTACT_OR_DUP: no fitted frames to check` on a fit window that was fine.
   - The no-second-reference case without a reason gets its own code, `SECOND_REFERENCE_ABSENT_UNEXPLAINED`. `SECOND_REFERENCE_SAME_OBJECT` is kept for fakery.
4. **V2's input is `segments[].track_artifact` only.** The validator reads the rows, converts them with timing and scale, and recomputes the fit. The ledger must show the file was created in this run.
5. **V5 is structured:** `mask_check.alternative_readings[]` = `{reading, g_m_s2 | null, ruled_out_by: {artifact, frame} | null}`. The keyword test on free-text justifications (overlay/artifact/frame) is removed.
6. **V8 measures; it does not take the agent's word.** For `camera.still`, the validator computes the reference track's maximum displacement over the fit window and compares it with the config threshold (default 2 px).
7. **V11:** `clock: null` means no clock claim. A native-world verdict needs no clock.
8. **The last full error list** (`{code, field, detail}` records, not just codes) is kept in the undetermined result's provenance and in `logs/`.
9. **Dry run:** `validate(..., dry_run=True)` runs every check and returns the errors, but does not assemble or write anything (part 07 §11).

## 7. Owner addendum (2026-10-28, from the fifth live run)

- **Errors on a choice of shapes come from the chosen branch.** For a `oneOf`/`anyOf` property, pick the branch by its discriminating key (for `camera`: `still` or `relative_track_artifact`) and report that branch's errors with their exact paths. Report "does not match any allowed shape" only when no discriminating key is present, and then name the allowed keys. Seen: four dry runs ended with the pair "camera: does not match any allowed shape" and "camera.still: required field missing" while the agent was sending `camera.still`.
- **The track-row format is stated where it is checked.** When a `*_track_artifact` holds no rows or is not JSON, the error detail repeats the expected format: a JSON list of `{frame, x_px, y_px}`. Seen: "holds no track rows" and "invalid JSON in …stats.csv".
- **Test:** an evidence with `camera: {still: {reference_phrase: "flag"}}` gets exactly one error, `MISSING_FIELD camera.still.reference_track_artifact`.

## 8. Owner addendum (2026-10-28, from the sixth live run)

- **The fit-curve check gives numbers.** When `fit_curve_px` disagrees with the refit of the track, the detail names the curve's acceleration in px/s², the track's in px/s², `m_per_px`, the window frames and the sample count, plus the worst sample: its `t_s`, its `y_px` and the track parabola's `y_px` at that time. Seen: "fit curve implies g=0.5847 but the track recomputes to g=1.224" sent the agent hunting for a unit bug for its last four turns; the real cause was invented samples.
- **Point by point.** Besides the implied g, every curve sample must lie within max(2 px, 3 × the track fit's RMSE in px) of the track's refitted parabola; the first sample outside is reported as above. A curve with fewer than 4 samples is an error naming that minimum, not a skipped check.
- **`REFERENCE_READING_UNPRICED` fires only when a reading differs.** It requires a `reading_spread` component only if some alternative reading's size differs from the headline size. Alternatives equal to the headline need no component. Seen: two alternatives both at 0.66 m, the headline's own value, were rejected.
- **Tests:** a curve with one invented sample 6 px off the track parabola is rejected with that sample's `t_s` in the detail; a 3-sample curve is rejected; alternatives equal to the headline pass V5 without `reading_spread`.

## 9. Owner addendum (2026-10-28, from the seventh live run): scale cross-check, an honest clock, real-run fixture

The seventh run was accepted with g = 1.18 ± 0.09 and the verdict "slowed ×1.17 to Moon (clock agrees)" on real Apollo footage at normal speed (g = 1.62). Two holes let it through.

1. **The scale had no cross-check.** The agent read the masked pack as the PLSS alone (0.66 m), but the mask covers the PLSS with the oxygen purge unit on top (≈ 0.85 m; NASM lists the PLSS at 66 cm "without the OPS" and the OPS at 38 × 18 × 20 cm). The jumper standing measured 156 px, i.e. 1.54 m at that scale, short for a suited astronaut. "No second independent object visible" was accepted as the reason for one reference.
   - **A person is a second reference.** When a segment's `subject.kind` is `person`, `second_reference_absent_reason` is not accepted: the evidence must carry the jumper's standing height as a reference (a standing-frame mask, size from a sourced range for the subject's class, e.g. adult man, suited Apollo astronaut). Error `SECOND_REFERENCE_REQUIRED_PERSON`.
   - **References must agree.** With two references, compute each one's `m_per_px` ± σ (size σ and a 2 px endpoint error); if they differ by more than 2 σ_combined, reject with `REFERENCES_DISAGREE`, naming both scales, both objects and the ratio. The agent then reconciles (another reading of one object, or a corrected size), never averages it away.
   - **Every blind-check alternative is answered.** Each alternative the blind check returned (part 07 §14) appears in `alternative_readings` with a size, or with a reason it does not apply. Error `ALTERNATIVE_NOT_ADDRESSED` names the unanswered alternative.
2. **The clock was not independent.** `implied_stretch` was set from the gravity stretch (√(g_world/g)), so "clock agrees" was true by construction, and a clock that reads normal (`reads_normal: true`, 1.29 Hz inside a natural 1–2 Hz) could not veto "retimed".
   - **The clock's stretch comes from the clock only:** the interval [natural_lo / rate, natural_hi / rate] (rate ± 2σ widens it). `implied_stretch` is its centre.
   - **Retimed needs a clock that excludes normal speed:** a retimed verdict requires `reads_normal: false` (1.0 outside the clock's interval) and the gravity stretch inside it. Otherwise, when no world fits natively, the verdict is undetermined with the reason "the clock cannot separate retiming from a measurement error". (brief 02 §5: "no world fits" never by itself means retimed.)
3. **Assembly follows part 12 §16:** video-time `t_s` everywhere, `takeoff_level_y_px` computed from the track at the takeoff frame (an evidence that still carries it has it ignored), `y_m` and `rise_m` above that level, ghosts landing back at that level.
4. **The real-run fixture.** Part 11 owns `fixtures/run-7/`: `result.json` and `summary.json` assembled from `fixtures/source/run-7/` by the same code that assembles live runs (`collect_run_context` on a temporary copy, then assembly from `artifacts/t34_evidence.json`), plus copies of the artifacts the result cites. Because that evidence fails the new scale rules, the fixture is built by assembly without the rejecting checks, and its verdict comes from the verdict rules above (expected: undetermined, clock cannot separate). A test rebuilds it and compares.
5. **Tests:** run 7's evidence is rejected with `SECOND_REFERENCE_REQUIRED_PERSON`; a synthetic pair of references at 0.00985 and 0.0119 m/px with 4 % σ each is rejected with `REFERENCES_DISAGREE`; rate 1.288 Hz, natural range [1, 2] Hz and g = 1.177 never give "retimed"; a clock at 0.6 Hz with range [1.4, 2.0] Hz and g = 0.79 gives retimed ×1.43 to Moon; the rebuilt `fixtures/run-7/result.json` satisfies part 12 §16's tests.

## 10. Pinned interface (owner addendum 2026-10-28, after the run-7 regeneration)

Regenerating part 11 dropped `write_result` and changed `synthesize_undetermined`'s signature; part 06 (`src/loop/synthesis.py`) and through it part 04's CLI tests broke (10 failures in the full suite). Other parts use exactly these names from `src.validate`, and they stay as written here:

- `validate(evidence, run_context=None, dry_run=False) -> {"accepted", "errors", ["result", "result_path"]}` (part 07 `submit`);
- `synthesize_undetermined(run_dir, run_id, reason, *, ledger=None, detail="", errors=None) -> dict` — builds the undetermined result; never raises on content (part 06);
- `write_result(run_dir, result) -> str` — writes `result.json`, returns its path (part 06);
- `REQUIRED_COMPONENTS` — the tuple of always-required error-budget component names (part 12's schema test compares its description with it).

File names in `logs/` are pinned too; part 06's tests read them:

- `logs/validator_last_errors.json` — written by `synthesize_undetermined` whenever `errors` is given: a JSON array of the `{code, field, detail}` records, exactly as passed (§6.8). The regeneration of 2026-10-28 renamed it to `last_submit_errors.json`, and part 06's `test_three_rejected_submits_end_valid` failed;
- `logs/validator_fault.txt` — the traceback of a validator fault (§6.2).

Test: `tests/validate/test_validate_interface.py` imports each name from `src.validate` and calls the two functions with these signatures on a temporary run directory; with a two-record `errors` list it reads `logs/validator_last_errors.json` back and compares it with the list.

## 11. Owner addendum (2026-10-28, from the v12 player review): the run-7 fixture is closed

Building the page from `fixtures/run-7/` logged `mask check image missing (overlay_artifact=artifacts/t12_segment_preview_2.jpg)`. The fixture copied `artifacts/t15_check_mask_0.json`, which the result cites, but not the overlay image that file cites; the source has it (`fixtures/source/run-7/artifacts/t12_segment_preview_2.jpg`).

- **The copy is closed** (same rule as part 12 §17): every path inside a copied JSON or JSONL file is copied too, transitively, with run-relative paths. A reference whose file is absent from the source fails the build with the path.
- **Test:** walk every JSON and JSONL file in `fixtures/run-7/`; every string value ending in `.png`, `.jpg`, `.npz`, `.json`, `.jsonl` or `.mp4` resolves to an existing file inside the fixture folder.

## 12. Owner addendum (2026-10-28, from the eighth live run): the kind comes from the blind check; a sized alternative is priced in full

The eighth run was accepted: Moon, g = 1.27 ± 0.22 m/s², scale from the backpack at 0.66 m over 66 px (0.0100 m/px). Two holes let a wrong scale through:

- the agent declared the astronaut `subject.kind: "object"`, so §9's person rule never asked for the jumper's height;
- the blind check of the backpack offered "a smaller upper block stacked on top of a larger lower block, both inside the tinted square" and the agent sized that reading at 0.91 m, 38 % above the 0.66 m it used. It priced the difference as `reading_spread` 0.12.

With the stacked reading, 0.91 m over 66 px gives 0.0138 m/px. That matches the suited astronaut's height in the clip-A fixture (1.803 m over 132 px, 0.0137 m/px) and gives g ≈ 1.75 m/s². The second reference would have picked the reading.

1. **`subject.kind` comes from the blind check.** For each segment, the validator takes the kind from `kind_answer` (part 07 §15) of the mask check on the segment's tracked mask. If the evidence's `subject.kind` differs, the evidence is rejected with `SUBJECT_KIND_MISMATCH` (detail: the blind answer and the check artifact). If the segment's mask has no check with a `kind_answer`, it is rejected with `SUBJECT_KIND_UNCHECKED`, which asks for `check_mask` on it. §9's person rule then applies to the checked kind.
2. **A sized alternative is priced in full, unless a second reference rules it out.** For each alternative reading of a reference with a size `size_alt` that differs from the headline size `size`, the `reading_spread` component must be at least |size_alt − size| / (2 · size). The exception is a second reference that agrees within 2σ under the headline size and disagrees by more than 2σ under `size_alt`. Otherwise the evidence is rejected with `READING_SPREAD_TOO_SMALL`. The detail names the alternative, both sizes, the required spread and the given one.
3. **Owner input `fixtures/source/run-8/`:** the eighth run's directory without logs (`input/`, `artifacts/`, `workspace/`, `summary.json`). Its accepted evidence is `artifacts/t44_evidence.json`. Its check artifacts predate `kind_answer`.
4. **Tests:**
   - run 8's evidence with `kind_answer: "person"` added to the segment's check artifact (on a temporary copy) is rejected with `SUBJECT_KIND_MISMATCH`;
   - with `subject.kind` also set to `person`, it is rejected with `SECOND_REFERENCE_REQUIRED_PERSON`;
   - run 8's evidence as it is has `READING_SPREAD_TOO_SMALL` among its errors (required 0.19, given 0.12);
   - a synthetic pair where the second reference agrees only under the headline size passes without a widened spread.

## 13. Owner addendum (2026-10-28): two or three references, for every clip (supersedes §9's person rule and §12.1)

The owner's rule: scale is always cross-checked by several objects, not by a rule tied to a role in the clip. Not every clip has a jumper or a person (part 08 R-S6).

1. **At least two references.** The evidence names two or more references of different things. Fewer is accepted only with `second_reference_absent_reason`; the assembled verdict is then `undetermined` with reason "scale rests on one reference" (the measured g and σ stay in the result for the page). This replaces `SECOND_REFERENCE_REQUIRED_PERSON` (§9) and the `subject.kind` checks `SUBJECT_KIND_MISMATCH` / `SUBJECT_KIND_UNCHECKED` (§12.1). Those codes are removed; `subject.kind` is descriptive only and no rule reads it.
2. **Every pair agrees.** `REFERENCES_DISAGREE` (§9) applies to every pair of references and names the pair.
3. **The scale is computed from all references.** `scale.m_per_px` is the inverse-variance weighted mean of the references' `m_per_px`, computed by code. `sigma_m_per_px` is that mean's σ, but never below half the spread of the references' values. `scale.reference_indices` lists every reference used (part 12 §18).
4. **V4 (`SECOND_REFERENCE_SAME_OBJECT`) rejects only near-identical masks:** intersection over union above 0.8 on a common frame. A mask nested in another (a backpack inside its wearer) passes.
5. **§12.2 stands, generalised:** an alternative reading is excused from full pricing when another reference agrees within 2σ under the headline size and disagrees by more than 2σ under the alternative's size.
6. **Tests:**
   - run 8's evidence with `reading_spread` raised to 0.19 is accepted, and the result's verdict is `undetermined` with "one reference" in its reason;
   - three synthetic references at 0.0136, 0.0138 and 0.0137 m/px (3 % σ each) give `scale.m_per_px` equal to their weighted mean and `reference_indices` of length 3;
   - three references where one is at 0.0100 m/px are rejected with `REFERENCES_DISAGREE` naming that reference and each of the other two;
   - a backpack mask nested in a body mask passes V4, and the same mask passed twice fails it;
   - no code in `src/validate/` reads `subject.kind`.
   - these replace §12.4's first two tests (`SUBJECT_KIND_MISMATCH`, `SECOND_REFERENCE_REQUIRED_PERSON`) and §9.5's `SECOND_REFERENCE_REQUIRED_PERSON` test.

## 14. Owner addendum (2026-10-28): every listed motion is measured or explained

- Each `first_look.motions` entry names an existing segment or carries a non-empty `skip_reason`; every segment appears in exactly one entry. Error `MOTION_NOT_MEASURED` names the entry.
- With two or more segments, `repetition_spread` is computed by code from the segments' g values (their standard deviation over √n, relative), and is never below the per-segment fit σ.
- Run 8's evidence predates the field: its assembly in tests adds one entry for its segment. The clip-A fixture's evidence lists two motions (part 12 §19).
- **Tests:** an entry with neither a segment nor a reason is rejected with `MOTION_NOT_MEASURED`; two segments at g = 1.60 and 1.70 with 5 % σ each give `repetition_spread` from their spread and stay a world verdict.

## 15. Owner addendum (2026-10-28, from the ninth live run): a gap calls for a third reference

- With exactly two references whose `m_per_px` differ by more than 5 % of their mean, the evidence is rejected with `THIRD_REFERENCE_REQUIRED`. The detail names both scales and the gap. Three or more references pass on to the pairwise 2σ check of §13.2.
- Each reference's `size_derivation.state_match` (part 08 R-S7) is required and non-empty: `STATE_MATCH_MISSING`.
- **Tests:** run 9's references (0.66 m over 65 px; 1.71 m over 152 px; synthetic evidence) are rejected with `THIRD_REFERENCE_REQUIRED`; the same pair with a third reference within 2σ of both passes; a reference without `state_match` is rejected.

## 16. Owner addendum (2026-10-28, from live run 11 and the second wall run): checks that make the dry run push

Seen:
- **Wall run 2 fit all three phases at once.** It put frames 55–180 (run-up, turn and climb) into one parabola and got g = 0.26 ± 0.09. V7 never fired, because the residual trend it used is zero by construction (part 09 §6).
- **Both runs submitted one reference.** Each gave `second_reference_absent_reason` "only one thing of known size at the depth of the motion", copied from R-S6a. Yet the Moon run had the suited figure wearing the measured backpack, and the wall run had crowd barriers and the wall it had searched for. The dry run accepted, and the agent stopped there.
- **The wall run measured no clock.** It declared none ("no visible independent rhythm"), though the clip's first two seconds are a run-up of steps, and it ended undetermined "without a normal clock".
- **The Moon run missed a hop.** It listed one motion; the clip has two hops (R-M4).

New and changed checks:
1. **V7 uses part 09's `residual_trend_z`.** The refit imports `fit_parabola` from `src.helpers.physics`, which is part 09's interface. It rejects with `RESIDUAL_TREND` when `residual_trend_z` exceeds 3.0. The detail reads: "the window is not one stretch of constant acceleration: it mixes phases (support, a change of surface, a turn) or the point deforms; fit one phase (R-M1, R-M5)". The old threshold on the correlation (0.3) is dropped.
2. **Push codes, dry run only.** These codes appear only in a dry run, and they make the dry run not clean. `src.validate.PUSH_CODES` lists them; it is part 11's interface, and part 06 reads it. A real submit is judged as now: a single reference or a missing clock gives an accepted undetermined result.
   - **`SECOND_REFERENCE_REQUIRED`** fires on a single reference. Detail: "measure a second thing of independently known size at the depth of the motion: the moving thing itself, something it wears or carries, or a fixed thing beside it (R-S6)".
   - **`CLOCK_REQUIRED`** fires when the verdict would be undetermined only because no clock was measured, that is, the measured g fits no candidate world. Detail: "any repeating motion in the clip is a clock (steps, swings, wing beats, turning wheels): measure its rate (R-C1), or name in clock_absent_reason each repeating motion you checked and why it fails".
   - **`MOTIONS_SCAN_MISSING`** fires when the frames viewed so far leave a gap longer than 0.25 s of clip time. Viewed frames come from the `view_frames` calls in the run's turn logs (`logs/turn_NNN.json`: `frame_start`, `frame_end`, `stride`, `frame_indices`). Detail: "view the whole clip at a spacing of at most 0.25 s and list every motion in first_look.motions (R-M4)". Without turn logs (offline fixtures) the check is skipped.
3. **Tests:**
   - a three-phase wall-like track (level, then a turn, then a parabola) is rejected with `RESIDUAL_TREND`, while a clean single parabola passes;
   - a one-reference evidence gets `SECOND_REFERENCE_REQUIRED` in a dry run and is accepted as undetermined in a real submit;
   - an evidence whose g fits no world and that has no clock gets `CLOCK_REQUIRED` in a dry run only;
   - turn logs that viewed frames 0–100 of a 240-frame, 24 fps clip give `MOTIONS_SCAN_MISSING`, while logs covering 0–239 at stride 6 do not;
   - `PUSH_CODES` holds exactly these three codes.
4. **`fixtures/run-7` is rebuilt** with part 09's new fit statistics, so that `test_fixture_rebuilds_identically` holds again.

## 17. Owner addendum (2026-10-28, from the third wall run): a shape choice names its shapes

Seen: with one turn left, the agent sent `"camera": {"still": null, "relative": {...}}`. V1 picked the still branch because the `still` key was present. It answered "camera.still: expected type object, got NoneType" and "camera.relative: unknown field". The run ended without the agent learning that the relative shape is `{"relative_track_artifact": "…"}`.

1. When V1 picks a branch, a discriminating key whose value is `null` counts as absent.
2. Every V1 error under a shape choice (today `camera`) ends with the allowed shapes written out as minimal JSON on one line, for example `allowed: {"still": {"reference_phrase": "…", "reference_track_artifact": "…"}} or {"relative_track_artifact": "…"}`. The shapes are built from the schema's branches (required keys and nested required keys), not hard-coded.
3. **Tests:**
   - the wall-run camera above gives one `MISSING_FIELD` on `camera` whose detail contains `relative_track_artifact`;
   - a still camera with a missing `reference_phrase` gives an error whose detail ends with the allowed shapes;
   - valid still and relative cameras still pass.

## 18. Owner addendum (2026-10-29): rounding is not a missing component

Seen: Moon run 13's dry run was rejected with "submitted sigma 0.0733 is smaller than the recomputed quadrature total 0.0736", a gap of 0.4 % from rounding. Wall run 4 had the same error.

1. V9 compares with a 2 % relative tolerance. A submitted sigma that is below the recomputed total, or below its largest component, by at most 2 % passes, and the result uses the recomputed total. Beyond 2 %, the error stays.
2. **Tests:**
   - 0.0733 against 0.0736 passes, and the result carries 0.0736;
   - 0.070 against 0.0736 still fails.

## 19. Owner addendum (2026-10-29): the sentence answers realistic or not

Part 02 §8 (2026-10-29) sets the display wording. The result's `sentence` follows it:

- world fit: "Realistic on the Moon: measured g = 1.66 ± 0.22 m/s², 0.2σ from the Moon's 1.62." ("Realistic on Earth: …", "on Mars");
- retimed: "Not realistic at this speed: slowed down ×1.50; at real speed it fits the Moon (clock agrees). Measured g = … m/s²." (or "sped up");
- impossible: "Not realistic on Earth: <reason>. Measured g = … m/s²." (the candidate world's name);
- undetermined: "Undetermined: <reason>." plus the measured g when there is one.
- **One candidate is the normal case:** a worlds listing with one candidate and an empty `excluded` passes every check.
- **Tests:** the four sentences above from fixtures of each kind (the Moon fixture gives "Realistic on the Moon: measured g = …"); a one-candidate, empty-`excluded` evidence is accepted.

## 20. Owner addendum (2026-10-29): range checks are checked, scored and combined

Parts 01, 02 §9, 08 R-R and 12 §22 (2026-10-29) add range checks. The validator:

- **Checks each range check** (all hard rejects, in a dry run and a real submit):
  - `RANGE_NUMBER_WITHOUT_PROVENANCE`: `value`, `sigma` and every extent's endpoints appear in the cited `measurement_artifact` (as V2 does for other numbers);
  - `RANGE_FORMULA_MISMATCH`: the value recomputes from the extents within 2 % — a ratio from the two `length_px`, a metric length from `length_px × m_per_px` of the run's scale when `uses_scale`;
  - `RANGE_SOURCE_MISSING`: `min` and `max` each have a source whose quote contains that number (unit conversions allowed: mm, cm, m, in, ft; percent and fraction) and whose URL came from this run's filtered `web_search`;
  - `RANGE_SIGMA_TOO_SMALL`: σ is at least the endpoint uncertainty (1 px per endpoint, propagated) and, when `uses_scale`, the scale's relative σ;
  - `MEASUREMENT_MISSING`: neither a segment nor a range check.
- **Scores each check** (part 02 §9): `outcome` `inside` / `outside` / `not_counted`, `delta_sigma`, `side`.
- **Combines parts into the verdict** exactly as part 02 §9 says, sets `decided_by`, and writes the sentence: "Not realistic on Earth: palm / hand length 48 % ± 2 % is 2.5σ below the human minimum of 53 % (ANSUR II)." / "Realistic on Earth: hand length 19.1 ± 0.6 cm is inside the adult range 16–22 cm; palm / hand 60 % inside 53–68 %."
- **Calculation steps:** one step per range check after the scale step: title = `label`, short = the formula with numbers, full = the range with its source and the outcome.
- **A result without segments** assembles: `segments` is [], ghosts and world outcomes are absent, the error budget lists only the range checks' components.
- **Tests:** the still-range fixture (12 §22) gives `impossible` decided by the outside check with the sentence above; a gravity `world` fit plus an inside check gives `world`; a gravity fit plus an outside check gives `impossible`; each of the five codes fires on a minimal bad item; a ratio recomputed 3 % off is rejected, 1 % off passes.

## 21. Owner addendum (2026-10-29): the plan is copied, not trusted

- When assembling the result, copy `claim`, `checks` (`what`, `why`, `compare_with`), `realistic_if` and `not_realistic_if` from the run's `artifacts/wonder.json` into `first_look.wonder` (part 12 §23); null when the file is missing or unreadable. The plan is shown, never used to decide the verdict.
- **Test:** a run dir with a `wonder.json` gives a result whose `first_look.wonder.claim` equals the file's; without the file it is null.

## 22. Self-review (2026-10-30): a test never writes into `fixtures/`

Seen: `test_fixture_rebuilds_identically` calls `build_fixture()`, which rewrites `fixtures/run-7/` in place. When part 12 raised `contract_version`, part 12's full-suite guard ran this test. The test rewrote `fixtures/run-7/result.json` with the new version, failed as an excused test, and left the changed file behind. That file went into part 12's commit, and the next regeneration of part 11 refused with "generated file edited by hand".

- `build_fixture(out_dir)` builds into the directory it is given; the default stays `fixtures/run-7/` for the one deliberate rebuild part 11 does while it is generated.
- **The test builds into `tmp_path`** and compares that build file by file with the committed `fixtures/run-7/`, using the same digest as now. It never writes under `fixtures/`.
- No test in `tests/validate/` writes into the repository tree: every output goes to `tmp_path`.

## 23. Self-review (2026-10-30, hand run 1, wall run 7, Moon run 16): §20 and §21 are still to do; every result carries the plan; errors say what to do

**§20 and §21 were not implemented.** The generation of 2026-10-30 (`9b5bb0f`) received only §22 as changes (part 15 §17), so it skipped §20 and §21.
- Hand run 1 (`20261030T103000Z-cd324f8a`, a still of a hand holding a phone) submitted an accepted evidence with two range checks: hand length 0.191 ± 0.012 m against [0.171, 0.214] m, and palm length 0.115 ± 0.009 m against [0.082, 0.133] m. Its result has no `range_checks` and says "Undetermined: no measurable segment".
- Wall run 7's result has `first_look.wonder` null.

Implement §20 and §21 now, each with the tests they name:
- the range checks are checked, scored and combined, with the RANGE_* codes and `MEASUREMENT_MISSING`;
- `verdict.decided_by` is set and the sentences follow the range checks;
- the plan is copied into `first_look.wonder`;
- the result moves to the current `contract_version` together with these fields.

The hand run's two checks become a test, with no third-party data in the repository. The test builds an evidence in `tmp_path`:
- `segments` empty and one reference (the phone's long edge, 0.1646 m);
- the two range checks with the values, σ and ranges above;
- extents and measurement artifacts written by the test itself.

The test expects both checks `inside` and a sentence beginning "Realistic on Earth".

**Every result carries the plan, including the synthesised ones.**
- A result that part 11 synthesises, such as budget, not finished or a dead end, takes `first_look.question` from `artifacts/wonder.json` when present and copies the plan into `first_look.wonder` as §21 does.
- Only without a plan does it fall back to the generic question.
- Seen: wall run 7 ended "Does the physics add up?" although its plan asked "Could a person really run straight up a wall that tall?".

**`EXAMPLE_VALUE_COPIED` (hard reject, dry run included).**
- It fires when a reference's `name` or any source URL in the evidence equals one in `src/contract/evidence.example.json` or in the still-range fixture's evidence, and the clip's own records do not contain it. A clip's own records are its `web_search` results and its run_python artifacts.
- `detail` names the copied value and says: "this comes from the example, not from your clip; measure your own object and search its size".
- Seen: wall run 7 submitted a reference "backpack height" from the Moon example on a clip with no backpack.

**The loop's own submit (part 06, 2026-10-30).**
- The loop submits for an agent that ran out of turns. When that submit is rejected, the loop ends the run through this part's synthesis, passing the kind `not finished` and the rejection's errors. The synthesised verdict reason is "not finished: " followed by the first two errors in plain words, for example "not finished: the two reference masks share no frame; no second reference size". The sentence is "Undetermined: not finished — …".
- "budget" stays for a run with no evidence file.

**Errors say what to do.** An error that compares two artifacts names both artifacts and the frames each covers, then says what would satisfy it. Example: "references[0].mask covers frames 230–280, references[1].mask covers 120–160; segment one of them again on frames that overlap the other". Seen: Moon run 16 repeated "the two masks cannot be loaded on a common frame" in two dry runs and ran out of budget with it.

- **Tests:**
  - the hand-run test gives two `inside` checks and "Realistic on Earth";
  - a synthesised budget result for a run dir with `wonder.json` carries its question and plan;
  - evidence with the example's "backpack height" reference on a run whose records lack it fails with `EXAMPLE_VALUE_COPIED`;
  - a rejected loop submit gives "not finished: …" with two plain errors;
  - the common-frame error names both frame ranges.

## 24. Self-review (2026-10-30, hand run 1 re-validated): a table's unit counts; a quote must be in the search

The hand run's evidence was re-validated with the §20 checks. Two of its errors were the evidence's own faults: it gave no extent endpoints in its measurement artifacts. Two more came from the rule:
- **The unit can come from the quote's own label.** The source quote "Hand length (mm) 182.50 ± 6.60 … 213.90–171.10" names its unit once, in the label, as tables do. The bound 0.1711 m was rejected because no unit follows 171.10. A number in a quote converts with the unit that follows it or, failing that, with the single unit the quote names in a label ("(mm)", "in cm", "mm:"). When the quote names no unit, the number converts with the unit that follows the same number in the text of that `web_search` fact. When the quote names two different units, there is no fallback.
- **A quote must be one the search returned.** Today a source's `quote` is checked only against its own bound and URL. A source passes `RANGE_SOURCE_MISSING`, and the reference-source check that already exists, only when its quote appears in that URL's fact of this run's `web_search` records, in the fact's `quote` or `text`. Spaces and dash variants are normalised, and the quote may be shortened at either end. A quote not found gets its own detail: "this quote is not in what web_search returned for <url>; copy it from the search result".
- **Tests:**
  - the quote "Hand length (mm) 182.50 ± 6.60 199.50 ± 9.40 188.10 ± 11.10 213.90–171.10" supports a `min` of 0.1711 m and a `max` of 0.2139 m;
  - a quote with "(mm)" and "cm" in it does not use the label fallback;
  - a source whose quote is absent from the run's search records fails with the new detail, and the same quote present passes.

## 25. Self-review (2026-10-30, wall run 8, Moon run 17, hand run 2): masks read the helpers' way, extents lie on what they measure, errors before pushes

**Masks are read only through part 09's reader.**
- Moon runs 16 and 17 failed twice with "references[0].mask … (unreadable or empty)", although both files load. `mask_frames_for_object` looks for a `__manifest__` or `manifest` key, but the files written by the `segment` tool keep their index under `__helpers_index__` (`oid`, `frame`, `key`). So every reference mask looks empty, and the common-frame check can never pass.
- The validator reads every mask artifact with `src.helpers.masks_io.load_masks`, the same reader the agent uses (as `helpers.masks_io`), and never parses the `.npz` layout itself.
- **Test:** a mask written by the `segment` tool's own writer for frames 200–260 is found on frame 210, and two references masked on overlapping frames pass the common-frame check.

**A range check's extents lie on what they measure.** Hand run 2 was accepted with "Not realistic on Earth: hand length 29.9 ± 0.6 cm". Its "hand length" extent ran from (350, 350) to (350, 750) on a 576 × 1024 frame. That line starts below the photo of the hand, crosses the empty band and ends on the presenter, so it measures no hand at all. The endpoints had been typed in and printed, and that was enough to pass `RANGE_NUMBER_WITHOUT_PROVENANCE`. The verdict was wrong. Two hard rejects close this (dry run included):
- `RANGE_EXTENT_OFF_FRAME`: each endpoint lies inside the frame (0 ≤ x < width, 0 ≤ y < height of the run's clip).
- `RANGE_EXTENT_NOT_ON_MASK`: both endpoints of an extent lie on one object mask from this run's `segment` artifacts on the extent's frame. "On" means inside it or within 2 % of the frame diagonal of its edge. The detail says: "segment <extent name> on frame <N>; both ends of the line must lie on its mask". When the extent's frame has no mask at all, the detail says so.
- A wrong verdict is worse than none. These two checks run before any range check is scored.

**Errors come before pushes in a dry run's reply.**
- After wall run 8's second dry run (turn 23), the agent spent its last 24 turns looking for a second reference, which is a push code. It never fixed its four hard errors, which were provenance, sources and a formula mismatch, and the run ended "not finished".
- The reply lists hard errors first, under the line "Fix these first; the run cannot be accepted until they are gone". Push codes come after, under "Then, only if time allows". Each push item carries `"push": true`.
- **Test:** a dry run with one hard error and one push code returns them in that order, under those two lines.

**Tests:**
- the extent from hand run 2, (350, 350) → (750, 350) on a 576 × 1024 frame, fails `RANGE_EXTENT_OFF_FRAME`;
- an extent inside the frame but away from every mask fails `RANGE_EXTENT_NOT_ON_MASK` with the detail above;
- an extent whose ends lie on a test mask passes.

## 26. Self-review (2026-10-30, wall run 9, Moon run 18): every accepted shape assembles; a dropped reference still counts

**No evidence that passes the checks may crash assembly.**
- Wall run 9's final submit passed every check with 0 errors, then failed in `_clock_result` with `KeyError: 0`. The run ended "Undetermined: validator_fault".
- The cause: its `clock.natural_range_hz` was `{"min": 4.6, "max": 5.0, "typical": 4.8}` instead of the schema's `[lo, hi]`. The schema check let it through, because clock fields were only checked one by one and their shapes were not.
- The schema check covers the whole evidence, `clock` included, whether or not there are segments. A wrong shape is an ordinary error that the agent sees in its dry run: "clock.natural_range_hz must be [lo, hi] in Hz".
- `assemble_result` never raises on evidence that passed the checks. Every reader of a field the schema checked trusts the schema, and the rest default safely.
- **Test:** wall run 9's clock shape fails the dry run with that detail, and an evidence with `segments` empty and a full, correct `clock` assembles.

**A reference the run measured and then dropped still counts.**
- Moon run 18 dry-ran two references at turn 29: the backpack at 0.66 m over 68 px, and the suited figure at 1.7 m over 144 px. They disagreed by 22 % and got `THIRD_REFERENCE_REQUIRED`.
- The final submit kept only the backpack, gave a reason for "no second reference", and was accepted as "slowed ×1.18" on that one scale.
- A reference that appears in any of this run's earlier evidences (`artifacts/t*_evidence.json`) and is missing from the final one still counts in the agreement check (part 02 R-S6), with its measured `m_per_px` and tolerance. It stops counting only when the final evidence's `scale.second_reference_absent_reason` names it and the blind mask check of that reference recorded a reading that it covers something else. That is a field the contract already has, so no schema change is needed.
- When such a reference disagrees with the kept scale beyond 2σ, the verdict is "Undetermined: the references disagree", naming both scales. A real submit is not rejected for this: the result is honest and undetermined, and the dry run says so as a push before.
- **Test:** a run whose earlier evidence has two disagreeing references and whose final evidence has one gives "Undetermined: the references disagree" with both scales named. The same run, where the second reference is named in `second_reference_absent_reason` and its mask check records that it covers something else, gives the one-reference verdict.

## 27. Self-review (2026-10-31, Moon run 20): an alternative can be answered with a reason, in a field that exists

Moon run 20 (`20261030T171631Z-1c1fa284`) came closest to a Moon verdict on the current code.
- Its two references agreed: the backpack with its top unit gave 0.914 m over 78.6 px = 0.0116 m/px, and the suited figure gave 1.7 m over 149.5 px = 0.0114 m/px.
- Its last two dry runs failed only on `ALTERNATIVE_NOT_ADDRESSED`, seven times over, because the blind check listed seven alternatives. Two were real readings of the reference's size: "the upper smaller cap-like section", and "the larger main rectangular volume below that cap". The other five name things the size does not depend on: the figure's legs, its arm outside the box, and a thin margin of background.
- The rule asks for "a reading with a size or a reason it does not apply". The contract has no field for a reason, since `mask_check.alternative_readings` items are `{description, size_m > 0}`. So an alternative that has no size could never be answered.

Without a contract change:
- **An alternative is answered** either by a reading in `alternative_readings`, which has a size and is priced by `reading_spread` as now, or by a sentence in the reference's `size_derivation`. That sentence quotes the alternative (at least three of its content words) and says why it does not change the size, for example "the figure's legs below the box are outside the measured extent".
- **The error detail shows both forms** with the alternative's own text filled in:
  - `add {"description": "<alternative>", "size_m": <size>} to mask_check.alternative_readings if it is another size of this reference`;
  - `or add to size_derivation: "<alternative>: does not apply because …"`.
- Matching uses the alternative's own words, which the agent can copy, so wording such as "cap-like" versus "cap" never blocks.
- **Tests:**
  - Moon run 20's seven alternatives, two answered by sized readings and five by `size_derivation` sentences, pass;
  - one alternative left unanswered fails with the two-form detail;
  - a sized reading still adds `reading_spread`.

## 28. Owner addendum (2026-10-31): a range check's lines are confirmed by `check_line`

Part 07 §19 adds `check_line`. A new hard reject applies, dry run included:
- **`RANGE_LINE_NOT_CONFIRMED`**: every extent of every range check must have a record in this run's `artifacts/line_checks.jsonl` on the same frame, with both endpoints within 2 px of the extent's and `agrees: true`.
  - With no record, the detail says: "check this line with check_line(frame=<N>, lines=[{x1…, y1…, x2…, y2…, claim: '<extent name>'}])".
  - With `agrees: false`, it says: "the second look sees '<blind description>'; re-measure the line so that it runs <claim>, then check it again".
- References are not line-checked (their mask checks and the agreement check stand). This keeps the Moon flow unchanged.
- The page shows each confirmed line's blind description under its range bar (part 13 may add this later; the record carries it).
- **Tests:**
  - a range check whose extents have agreeing records passes;
  - one with a disagreeing record fails with the blind description in the detail;
  - one with no record fails with the `check_line` call to make, endpoints filled in.

## 29. Owner addendum (2026-10-31, from Moon run 22): the result carries the whole calculation, step by step

Seen: Moon run 22 was accepted ("Realistic on the Moon: g = 1.59 ± 0.25 m/s², 0.1σ"). Its page's rail, however, shows only two calculation steps, "Measured gravity" and "Verdict", plus the clip's motions. The scale, the fit and the error budget are missing. This has been the case since the regeneration of 29.10 22:14; before it, the result carried nine steps. A viewer cannot follow the proof.

- **`calculation_steps` lists every step the evidence supports,** in this order, with the ids of part 12 §6:
  1. `time_from_frames`: measured fps over the frame count, and the video length as a chip.
  2. `mask_check`: one step per reference, whose chip is the blind check's description.
  3. `scale`: one step per reference, `s = L/ℓ = <size> m / <extent> px`, with the m/px as a chip. When two references are used, the scale step shows both and their agreement.
  4. For each measured segment:
     - `segment`, titled "Segment <label>": `N = <frames>` and the tracked point as a chip;
     - `fit`, titled "Fit <label>": `a = <a> ± <σa> px/s²` with that segment's g as a chip.
  5. `measured_g`: `g = <g> ± <σ> m/s²`.
  6. `clock`: the clock's implied stretch, or "No independent clock: <clock_absent_reason>".
  7. `uncertainty`: `σ = <total>`, plus the bars block.
  8. `verdict`: the verdict sentence's numbers as a formula, with the world or answer as a chip.
- **A range check** adds one step before `verdict`, with id `scale` and title "Range check <name>": `<measured> = <length_px> px × <s> m/px` against the quoted range `[lo, hi]`, with in or out as a chip. The vocabulary stays that of part 12.
- **The look follows `fixtures/clip-a/result.json`:** its `calculation_steps` are the reference for titles, order, `short` blocks (a text line, then a formula with substituted numbers and a chip), `frame` and `segment_id`. Every number in a formula equals the result's own value at the printed precision.
- **Motions that were not measured are not calculation steps.** They stay in `first_look.motions` only.
- **Tests:**
  - for the clip-a evidence (rebuilt into `tmp_path`), the step ids, in order, are `time_from_frames, mask_check, mask_check, scale, segment, fit, measured_g, clock, uncertainty, verdict` (two references), and the scale, a and g in the formulas equal the result's values;
  - a synthetic range-only evidence yields `time_from_frames, mask_check, scale, scale(range), uncertainty, verdict`;
  - no step's title equals a motion's description.

## 30. Owner addendum (2026-10-31, from Moon run 21): one dry run reports every error at once

Seen: Moon run 21's first dry run (turn 33) had one reference. Its `mask_check` was written by the agent itself: it pointed at a segment preview instead of a `check_mask` artifact, and its coverage_answer read "covers the whole backpack". The dry run answered only with the push `SECOND_REFERENCE_REQUIRED`. The fabricated mask check and the unanswered alternatives surfaced only at turns 57–61, after the second reference was added, and the run ended "not finished" with five `ALTERNATIVE_NOT_ADDRESSED` errors left. Moon run 20 ended the same way.

- **Every check that can run, runs.** The per-reference checks run on each reference present, whatever pushes also apply: mask check present and real, alternatives answered, extents on the mask, source quote in the search. The same holds for segments, range checks and the clock. A push such as `SECOND_REFERENCE_REQUIRED` or a missing clock is added to the list. It never replaces the list.
- **The order stays:** errors first, then pushes (§25).
- **Test:** evidence with one reference whose `mask_check.artifact` is a segment preview yields, in one dry run, both `MASK_CHECK_MISSING` for `references[0]` and `SECOND_REFERENCE_REQUIRED`, in that order. The same evidence with a real mask check, whose blind alternatives are unanswered, yields `ALTERNATIVE_NOT_ADDRESSED` together with the push.

## 31. Owner addendum (2026-10-31, from Moon run 22): ghosts and world outcomes land at the clip's landing level

Seen: Moon run 22's leap lands 0.19 m below its takeoff point: the track's `y_m` at the landing frame is −0.19. The Moon ghost and `world_outcomes` end where the Moon path returns to takeoff height, 0.75 s after takeoff, while the clip's flight lasts 1.03 s. The chart therefore reads "Moon 0.75 s · in the clip 1.03 s", although g = 1.59 ± 0.25 m/s² fits the Moon.

- **The landing level** of a free-flight segment is the track's `y_m` at the segment's landing (end) frame, relative to takeoff. Every ghost of the segment is built with `ghost(..., land_y_m=<landing level>)` (part 09 §8).
- `world_outcomes[].landing_time_s` and `landing_x_px` use the same landing: `t_land = (vy + sqrt(vy² − 2·g·land_y_m)) / g`, with the same fallback. The time base of `landing_time_s` stays as it is now.
- Each world then answers the viewer's question: "in that world, when would this body touch the same ground?"
- **Tests:**
  - a synthetic free flight with fitted g = 1.59 m/s² that lands 0.19 m below takeoff: the Moon ghost lands within 0.05 s of the measured airtime, and its last point is at the landing level;
  - the Earth ghost of the same segment lands at `(vy + sqrt(vy² + 2·9.81·0.19)) / 9.81` after takeoff;
  - a segment that lands at its takeoff height gives the same ghosts and outcomes as before.

## 32. Owner addendum (2026-10-31, from wall run 15): the clock is a calculation step

Seen: wall run 15 measured a step rate of 4.0 ± 0.3 Hz on the approach run, against a sourced natural range of 4–5 Hz (`clock.reads_normal = true`). This is what shows that the clip plays at real speed. The result carries the `clock`, but its calculation steps have no `clock` step, so the page never shows it.

- When the result has a `clock`, the calculation steps include a step with id `clock`, in the order of part 12 §6. It is titled "Clock: <interpretation> rate". It shows:
  - the measured rate with its σ, the natural range and its source;
  - the implied stretch with its σ;
  - the reading: "plays at real speed" when `reads_normal`, otherwise the retime it implies.
- The step's frame range is the clock's frames (the motion it was measured on).
- **Test:** a result with a clock (wall run 15's shape) has a `clock` step between `scale`/range steps and `uncertainty`, and its text contains the measured rate and the range's source domain.

## 33. Owner addendum (2026-10-31, from hand runs 8–9 and wall run 15): a σ below the floor is raised, not refused

Seen:
- Hand run 8 was one error away from an accepted verdict: hand length 0.190 m against a sourced range of 0.180–0.194 m, refused only by `RANGE_SIGMA_TOO_SMALL` (σ 0.0016 against a floor of 0.0019).
- Hand run 9 and wall run 15 hit the same error.
- In each case the agent built the check with `helpers.ranges.range_value`, as instructed. It passed the scale σ it had computed itself, while the validator's floor uses the validator's own scale σ, `computed.sigma_m_per_px`. The gap is a seam between the two, not a false claim of precision.

Rules:
- **A range check's σ below the floor is raised to the floor.** The floor is the endpoint error plus the validator's scale σ. The validator uses `max(σ, floor)` everywhere: scoring, `delta_sigma`, the outcome, the sentence and the calculation step. It records the raise as a caveat on the range check's step, for example "σ raised from 0.0016 m to 0.0019 m (endpoint and scale floor)". `RANGE_SIGMA_TOO_SMALL` is no longer an error. Raising σ can only weaken a verdict, never strengthen it.
- **A σ that is not a finite positive number is still an error.**
- **Tests:**
  - hand run 8's final evidence shape (σ 0.0016, floor 0.0019) is accepted, with the range check scored on σ 0.0019 and the caveat in its step;
  - a σ above the floor is used unchanged;
  - a missing or negative σ is still refused.

## 34. Owner addendum (2026-10-31, from wall run 14): a schema error names the keys to fix

Seen: wall run 14 had two references, a range check and a clock. It ended undetermined on one error: `value.scale.check_scale: expected type null, got dict`. Its `check_scale` was `{m_per_px, sigma_m_per_px}`, while the schema wants `{m_per_px, sigma}`. The message pointed at the wrong branch of the `anyOf` (null or object), so the agent could not see what to change.

- **When a value fails an `anyOf` / `oneOf` that allows an object, and the value is an object,** the error reports the object branch's own problems:
  - the missing required keys;
  - the keys the branch does not allow;
  - each wrong type, with its path.
  
  For example: "value.scale.check_scale: missing key 'sigma'; key 'sigma_m_per_px' is not allowed (expected {m_per_px, sigma})".
- The same applies to arrays and to every nested `anyOf` in the evidence schema.
- **Test:** wall run 14's `check_scale` shape gives exactly one error that names `sigma` as missing and `sigma_m_per_px` as not allowed. A null `check_scale` and a correct object both pass.

## 35. Owner addendum (2026-10-31): the clock step does not depend on segments

Seen: after § 32, wall run 15's final evidence has a `clock` (4.0 ± 0.3 Hz, `reads_normal = true`) and no free-flight segments. Its calculation steps still have no `clock` step. The code builds the step only inside the branch for results with segments, and the § 32 test used a result with a segment.

- The `clock` step of § 32 is built whenever the result has a `clock`, with or without segments. A result with neither a clock nor segments has no clock step.
- **Test:** wall run 15's shape has a `clock` step with the measured rate and the range's source domain. Its shape is no segments, one range check and a clock reading normal.

## 36. Owner addendum (2026-10-31, from wall run 16): a line the second look rejected is never used

Seen: wall run 16 was accepted with the wall at 13.2 ± 1.2 m. Its only scale reference, "event staff height beside wall base", was checked with `check_line`, and the blind look did not confirm it (`agrees: false`). The agent never re-measured it, yet the validator accepted the scale, because § 28 covers only range check lines. Wall run 15, scaled from the runner, gave 10.1 ± 0.5 m, 2.4σ away.

- **Every measured line in the evidence that has a `check_line` record must have a confirming record:** a reference's `extent_px`, a check scale's extent, and every range check extent. A matching record has the same frame and the same endpoints within 2 px. When the latest matching record says `agrees: false`, the evidence is refused with `LINE_NOT_CONFIRMED`. The error names the line and quotes what the second look saw.
- **Range check lines keep § 28's stronger rule:** they need a confirming record even when none was made.
- **Test:** wall run 16's final evidence shape is refused with `LINE_NOT_CONFIRMED` on `references[0]`. The same evidence passes when a later record for that line agrees. Evidence with no `check_line` record for a reference passes as before.

## 37. Owner addendum (2026-10-31, from Moon run 23): a reference is not dropped to escape a disagreement

Seen: Moon run 23 measured two references, the backpack (0.66 m) and the suited height. They disagreed by 14%, and the dry runs reported `THIRD_REFERENCE_REQUIRED`, then `REFERENCES_DISAGREE`. The agent removed the suited height and wrote `second_reference_absent_reason`: "Suited height was posture-biased 14 percent off the backpack scale…". The validator accepted the backpack alone. That reference was wrong: the mask covered the backpack together with its top unit, about 0.91 m in Moon run 22. The scale was 24% short, so g came out at 1.18 ± 0.08 m/s², and the verdict said "Not realistic on the Moon".

- **The validator reads this run's earlier dry runs** (`artifacts/t*_evidence.json` and `t*_submit_errors.json`). If any earlier dry run carried two or more references, the final evidence may not rest on one reference with a `second_reference_absent_reason`.
- **If any dry run reported `REFERENCES_DISAGREE` or `THIRD_REFERENCE_REQUIRED`,** the final evidence must settle it as the third-reference rule says: three references, two of which agree. Removing a reference never clears the disagreement.
- Refused evidence gets `REFERENCE_DROPPED`, naming the dropped reference and the dry run that carried it.
- **Test:** Moon run 23's final evidence, with one reference, plus its earlier dry runs, which carried two references and a disagreement, is refused with `REFERENCE_DROPPED`. A run that never measured a second reference may still state an absence reason, as before.

## 38. Owner addendum (2026-10-31, from Moon run 23): falling short of a range never decides "not realistic"

Seen: Moon run 23's verdict was decided by "jump height at apex 28.8 ± 2.1 cm is 3.8σ below the adult men vertical jump height norms minimum of 41 cm". A person can always jump lower, run slower or reach less than a norm, and a suited astronaut hopping on purpose does exactly that. Falling short of a range is no evidence against realism.

- **A range check whose measured value lies below the range's minimum** has the outcome `below`. Its step reads "below the typical range", and it never makes the verdict "not realistic" on its own. It is reported, and the verdict comes from the other checks; with no other deciding check, the verdict is "undetermined" with that reason.
- **Above the maximum keeps its current meaning.**
- **Test:**
  - Moon run 23's range check (0.288 m against a minimum of 0.41 m) yields outcome `below`, and on its own decides no "not realistic" verdict;
  - wall run 15's check (10.1 m against a maximum of 4.0 m) still decides "not realistic".

## 39. Owner addendum (2026-10-31, from Moon run 24): a loose reference does not settle a gap

Seen: Moon run 24 measured the backpack (0.66 m over 69.9 px, 0.00945 m/px) and the suited figure's width (0.82 m over 80.4 px, 0.01020 m/px). They differ by 7.6 %, and the dry run asked for a third reference (§ 15). The agent added the flagpole: 2.44 ± 0.80 m over 98.2 px, 0.0248 m/px, 2.6 times the other two. With a 33 % tolerance, the flagpole sat within 2σ of both, so every pair "agreed" and the scale went through. The flagpole decided nothing: it would have agreed with almost any scale. The scale rested on the backpack at 0.66 m, as in Moon run 23. g came out at 1.18 ± 0.08 m/s², and the verdict said "slowed down ×1.17".

- **A reference settles a gap only when it is tight enough to tell the two sides apart:** the relative σ of its own `m_per_px` is at most 5 %, the gap threshold of § 15.
- **The gap rule holds with any number of references.** Whenever two references differ by more than 5 % of their mean, at least one other reference with relative σ ≤ 5 % must lie within 2σ of both. Otherwise the evidence is refused with `THIRD_REFERENCE_REQUIRED`. The error names the gap pair, and each loose reference with its relative σ.
- **The pairwise 2σ check (§ 13.2) stays.** A loose reference still counts in the weighted scale and in the pairwise check; it just does not settle a gap.
- **Test:**
  - Moon run 24's three references are refused with `THIRD_REFERENCE_REQUIRED`, naming the flagpole as too loose: 0.66 ± 0.02 m over 69.87 px; 0.82 ± 0.05 m over 80.41 px; 2.4384 ± 0.8 m over 98.18 px.
  - The same pair with a third reference at 0.00985 m/px and 3 % σ passes.
  - Moon run 22's two references, 0.3 % apart, pass as before.
  - § 15's passing test uses a third reference with relative σ at most 5 %.

## 40. Owner addendum (2026-10-31, from wall run 18): a range distance counts from the measured value

Seen: wall run 18 measured the wall at 14.07 ± 2.50 m against a range maximum of 5.5 m. The verdict was "not realistic", with the reason "1.4σ above its range". But 1.4 was the distance of the 2σ interval's edge, (14.07 − 2 × 2.50 − 5.5) / 2.50, not the distance of the value. A reader takes "1.4σ" for "within 2σ", which contradicts the verdict. The world chips already count from the value (|ḡ − g_world| / σ).

- **`delta_sigma` of a range check is the distance of the measured value from the nearer bound, in σ:** (value − max) / σ above the range, (min − value) / σ below it, and 0 inside.
- **The outcome rule is unchanged:** a check is `outside` (or `below`, § 38) exactly when that distance exceeds 2, that is, when the whole 2σ interval lies beyond the bound.
- **Everything that prints the distance uses this number:** the sentence, the verdict reason, the calculation step and `range_checks[].delta_sigma`. This supersedes the wording in part 02 § 9 and part 12's `range_checks`.
- **Test:**
  - wall run 18's check (14.066 ± 2.504 m against a maximum of 5.5 m) gives `delta_sigma` 3.42 and `outside`;
  - wall run 15's check (10.145 ± 0.531 m against a maximum of 4.0 m) gives 11.57 and `outside`;
  - Moon run 23's check (0.288 ± 0.021 m against a minimum of 0.41 m) gives 5.8 and `below`;
  - a value 1.9σ above the maximum is `inside`, with `delta_sigma` 0.

## 41. Owner addendum (2026-10-31, from the Moon demo review): Earth is always weighed, and a missing clock reads as a plain statement

Seen: Moon run 22's result lists one candidate world, the Moon. The page shows "Moon 0.1σ ✓" and says nothing about Earth, yet a sceptic's first answer is "Earth, filmed in slow motion". Its clock step reads "No independent clock: no independent rhythm needed for first dry run; will add step clock if required". That is the agent's working note, not a statement for a reader.

- **Earth is always weighed.** The evidence may name Earth neither as a candidate nor as an excluded world. For a result with a measured g, the validator then adds Earth (9.81 m/s²) to `worlds.candidates`. It computes `delta_sigma`, `fits_native` and `retime_factor` for Earth exactly as for every other candidate.
- **The verdict does not change.** The verdict is decided over the agent's candidates, before Earth is added. The added entry only gives the page a chip.
- **A missing clock reads as a fixed sentence written by the validator:** "No independent clock in this clip: the speed is taken as filmed." `clock_absent_reason` stays in the result, but the step never prints the agent's text.
- **Test:**
  - Moon run 22's evidence gives two candidates: the Moon (0.1σ, fits at native speed) and Earth (about 33σ, does not fit, `retime_factor` about 2.48). The verdict stays "Realistic on the Moon". Its clock step reads exactly the fixed sentence.
  - Evidence that excludes Earth with frame evidence gets no Earth candidate.
  - Evidence that names Earth as a candidate keeps exactly one Earth entry.

## 42. Owner addendum (2026-10-31, from the sped-up Moon run): a speed factor is always above 1

Seen: the Moon clip, sped up ×2.46 by the owner, was correctly found too fast for the Moon. But the sentence read "Not realistic at this speed: sped up ×0.47; at real speed it fits the Moon". The validator printed `s` = presented ÷ real = 0.47. Part 02 §1 says display factors are above 1 in both directions.

- **The printed factor is `k`:** `k = s` when slowed (`s > 1`), `k = 1/s` when sped up (`s < 1`), two decimals. This holds in `sentence`, in every step text and in every reason the validator writes.
- **`verdict.factor` stores `k`,** with `direction` saying which way. `worlds.candidates[].retime_factor` stays `s` (part 12), so part 13 §41 keeps working.
- **Tests:**
  - a retimed evidence with `s` = 0.4665 reads "Not realistic at this speed: sped up ×2.14; at real speed it fits the Moon …", and `verdict.factor` = 2.14 (rounded) with `direction` = "sped";
  - a retimed evidence with `s` = 1.50 still reads "slowed down ×1.50";
  - no `sentence` or step text of a retimed result contains "×0." .

## 43. Owner addendum (2026-11-01, from the Moon and sped-up Moon runs): every candidate flight is decided; several flights give one g

- **The overview is recomputed.** The validator runs part 07's `motion_overview` computation on `first_look.overview.artifact` / `object_id` and compares its candidates with `overview.candidates` (a match = the frame ranges overlap by at least half of the shorter one).
  - No overview while the result measures a motion: dry run → push `MOTION_OVERVIEW_MISSING` ("segment the moving body over the whole clip and run motion_overview"); real submit → undetermined, reason "the motions in the clip were not surveyed".
  - The overview's masks do not cover the whole clip (first frame > 2 or last frame < N − 3): push `MOTION_OVERVIEW_PARTIAL`; real submit → undetermined, same reason.
  - A recomputed candidate without a decision: push `FLIGHT_NOT_CONSIDERED` naming its frames; real submit → undetermined, reason "a possible flight at frames a–b was not considered".
  - A `measured` candidate whose segment does not exist, or a segment that is in no candidate: `MOTION_NOT_MEASURED` (§14).
- **Several flights give one g.** With two or more measured segments, `verdict.g_measured` is the inverse-variance weighted mean of the segments' recomputed g (weights from each fit's σ). `repetition_spread` stays as in §14. Segments that disagree (the existing conflict rule, §3) make the verdict undetermined (conflicting segments).
- **Steps.** Each segment keeps its own `segment` and `fit` steps (in frame order, labelled "Jump 1", "Jump 2"); a step "Jumps agree" follows them: each jump's g with its σ, and the weighted mean.
- **A reference far from the motion.** A reference whose measuring frame lies more than 2 s before the first-check takeoff, or after it, without a reason in its `size_derivation.note`: push `REFERENCE_FAR_FROM_MOTION` (R-S11); a real submit accepts it with a caveat.
- **Tests:**
  - `fixtures/source/fake-1/` evidence with an overview listing only its measured flight: the dry run pushes `FLIGHT_NOT_CONSIDERED` naming frames ≈ 101–113;
  - the same evidence without `first_look.overview`: dry run `MOTION_OVERVIEW_MISSING`, real submit undetermined;
  - two synthetic segments with g = 1.60 ± 0.10 and 1.70 ± 0.20: g_measured = 1.62 (inverse-variance mean), and a "Jumps agree" step lists both;
  - a reference at frame 10 with the first-check takeoff at frame 135 (4.2 s) and no note: push `REFERENCE_FAR_FROM_MOTION`.

## 44. Owner addendum (2026-11-01, from four runs on the Moon and sped-up Moon clips): a size as quoted, a reference with a steady shape, next to the motion

Part 08's addendum of 2026-11-01 (R-S13, R-S14, R-S15, R-S11 tightened). The runs: Moon `20261101T094323Z-59f7b7eb` (figure "1.6 m" from sources quoting 1.70 m, on push-off frame 243), sped-up `20261101T085124Z-3219808f` (figure on frame 0, 3.4 s before the takeoff, its mask present next to the jump).

Each check below is an error: the submit is refused with the detail, and the agent can fix and submit again. A run that ends with the error is undetermined with the detail as its reason.

- **`SIZE_NOT_AS_QUOTED` (R-S13).** For each reference, from `sources[].value_m`:
  - `single`: `size_m` is within 1 % of one source's value;
  - `sum`: `size_m` is within 1 % of the sum of the values of distinct sources;
  - `mean`: `size_m` is within 1 % of their mean.
  The detail names the size, the mode and the quoted values: "suited figure height: 1.6 m (single) is not a quoted value; the sources quote 1.7, 1.7 m. Use the size as quoted; if the figure is not in the quoted state on this frame, measure it on another frame (R-S13)."
- **`REFERENCE_SHAPE_UNSTABLE` (R-S14).** For each reference with a mask (`mask.artifact`, `mask.object_id`): the mask height on the measuring frame against the median mask height over the frames of the same mask within ±1 s of it that lie outside every recomputed flight candidate ±0.3 s (§43). With 5 or more such frames and a difference above 5 %, the detail names both heights and the frames: "suited figure height on frame 243: mask 153 px, 21 % above its median 126 px on frames 213–236 at rest; measure it on a frame where it keeps its shape (R-S14)." With fewer than 5 such frames the check is skipped and the scale step says so.
- **`REFERENCE_FAR_FROM_MOTION` (tightened, R-S11).** When the reference's own mask holds its object on 5 or more frames within 2 s before the first-check takeoff and the measuring frame is outside that window, it is an error, whatever the note says. The detail names the window and the frames where the mask is present. Otherwise §43 stands (a push, excused by a note).
- **The gap detail points at part and whole.** The details of `REFERENCES_DISAGREE` and `THIRD_REFERENCE_REQUIRED` add: "First check each reference for a part/whole mismatch: list what its mask and line cover; a unit mounted on it, a lid or a base needs its own quoted size (mode sum), or a shorter line (R-S15)."
- **Tests:**
  - the Moon run's figure (1.6 m, `single`, sources 1.7 and 1.7) gives `SIZE_NOT_AS_QUOTED` naming 1.6 and 1.7; run 22's pack (0.9144 m, `sum`, sources 0.6604 and 0.254) and the sped-up run's pack (0.914 m, `sum`, 0.66 and 0.254) give none;
  - synthetic masks of a rectangle 100 px high on frames 0–60 and 125 px on frame 61 (30 fps, no candidates): a reference on frame 61 gives `REFERENCE_SHAPE_UNSTABLE` naming 125 and 100; on frame 50, none; with only 3 frames of mask around the measuring frame, none, and the scale step says the check was skipped;
  - a reference on frame 0 whose mask holds the object on frames 41–100, with the first-check takeoff at frame 101 (30 fps) and a note: `REFERENCE_FAR_FROM_MOTION` is an error; the same reference with a mask only on frames 0–20 and a note: a push only;
  - the details of `REFERENCES_DISAGREE` and `THIRD_REFERENCE_REQUIRED` contain "part/whole".

## 45. Owner addendum (2026-11-01, from four runs on the Moon and sped-up Moon clips): a measured line is not hidden, a candidate flight follows one parabola, a refused value is named

The runs: Moon `20261101T132149Z-a5d02c1f`, sped-up `20261101T123453Z-95885c4b`, Moon `20261101T123453Z-b6266ace`.

Each check below is an error, as in §44: the submit is refused with the detail, and a run that ends with it is undetermined with the detail as its reason.

- **A confirmed line counts as a measured reference (§37 widened).** Seen: the Moon run measured the suited height with `check_line` on frame 210 (turn 54, 129 px, confirmed). It disagreed with the backpack (0.66 m on 69 px), so the agent left it out of every dry run and wrote `second_reference_absent_reason`: "suited-body height disagrees". The scale was 28 % short and the verdict said "slowed ×1.18".
  - The validator reads this run's line checks (`artifacts/t*_check_line_*.json`). A line with `agrees: true` is **reported** when an extent in the evidence (a reference, the scale, a range check) is on the same frame with both endpoints within 3 px of it.
  - When the evidence rests on one reference with `second_reference_absent_reason` and an unreported confirmed line exists, the submit is refused with `REFERENCE_DROPPED`. The detail names the turn, the frame, the claim and the length in px: "turn 54, frame 210: 'height of the suited figure …', 129 px, confirmed and not reported. A reference you measured is reported; a disagreement is settled, not hidden. First check each reference for a part/whole mismatch (R-S15)."
  - A run whose confirmed lines are all reported may still state an absence reason, as before.
- **`FLIGHT_NOT_PARABOLIC`.** A candidate decided `measured` whose recomputed overview candidate (§43) has `centroid_r_squared` below 0.8. Seen: the Moon run measured frames 47–85 (r² 0.51, curvature 18 px/s² against 118 and 120 px/s² of the two other flights) and its g spread became ±0.70 m/s². The detail names the candidate, its r² and the r² of the other candidates: "F1 frames 47–85: the centroid track fits one parabola with r² 0.51 (F2 0.99, F3 0.99). A free flight follows one parabola; decide it not_a_flight with the reason."
- **A value that matches no branch is named (V1).** Seen: the sped-up run wrote `decision` "not a free flight" and "not measurable". The candidate schema is an `anyOf` of two branches, and the detail showed only the first branch ("segment_id: expected type string, got null"). The agent changed the wrong fields in 7 submits and the run ended undetermined.
  - When a value matches no branch of an `anyOf`, and the branches have a field with `const` or `enum` (here `decision`), the detail shows the errors of the branch whose `const`/`enum` accepts the value.
  - When no branch accepts it, the detail is "<field>: got <value>; allowed: <values of all branches>", for example "first_look.overview.candidates[0].decision: got 'not a free flight'; allowed: measured, not_a_flight, not_measurable".
- **Tests:**
  - synthetic run: evidence with one reference (frame 210, line 102,60 → 92,128) and an absence reason, plus a line check on frame 210 (105,60 → 117,189, `agrees: true`): `REFERENCE_DROPPED` naming frame 210 and 129 px; with that line added as the second reference: no `REFERENCE_DROPPED`; with the line check `agrees: false`: no `REFERENCE_DROPPED`;
  - a recomputed overview with candidates of r² 0.51, 0.99 and 0.99, all decided `measured`: `FLIGHT_NOT_PARABOLIC` names the first and its r²; with the first decided `not_a_flight`: none;
  - a candidate with `decision` "not a free flight", `segment_id` null and a reason: the detail contains "allowed: measured, not_a_flight, not_measurable" and does not contain "segment_id"; with `decision` "not_a_flight" and `segment_id` "hop_a": the detail names `segment_id` and the null it needs.

## 46. Owner addendum (2026-11-01, from four runs at max effort on the Moon and sped-up Moon clips): a corrected reference settles a gap, one reference never gives a verdict, unanswered alternatives come in one list

The runs: Moon `20261101T164859Z-155ff159` and `20261101T164859Z-91c3c3c4`, sped-up `20261101T164859Z-29a0a24d`.

- **A part/whole correction settles a disagreement (§37 refined).** Seen: the first Moon run's dry run had the backpack at 0.66 m and the suited figure at 1.70 m; they disagreed. Following R-S15, the agent found that the mask covers the pack with its top unit and changed the backpack to 0.914 m (`sum` of the quoted 0.66 and 0.254 m). The final two references agreed and g was 1.57 ± 0.24 m/s². The validator still made the verdict undetermined, "the references disagree: backpack height at 0.009823 m/px and kept scale at 0.013246 m/px".
  - A dry-run reference is **settled**, not dropped, when the final evidence has a reference on the same object (the same mask artifact and object id, or masks that overlap by more than 50 % on the measuring frame) and either its `size_derivation` is a `sum` whose sources include the earlier quoted value, or it has the same size measured on another frame (R-S14).
  - A disagreement from a dry run is cleared when every reference in it is settled or present in the final evidence, and the final references agree pairwise. Only a reference that leaves the evidence entirely needs §37's third reference.
- **One reference never gives a verdict (R-S6a, §13.1).** Seen: the second Moon run submitted one reference (the backpack at 0.66 m, PLSS only, while its own note said the mask covers the top cap) with the absence reason "only backpack measured so far". The code kept its verdict "slowed ×1.19" because the verdict was retimed with `clock: none, scene-pinned`. No part of this spec makes that exception. With one reference, every gravity verdict (world, impossible, retimed, with or without a clock) becomes undetermined, "scale rests on one reference"; the measured g and σ stay in the result.
- **Unanswered alternatives come in one list.** Seen: at high effort the blind check returns 3–8 alternatives per mask (2–4 at low). The sped-up run got nine separate `ALTERNATIVE_NOT_ADDRESSED` errors over three submits, answered them a few at a time and ended undetermined. Now one `ALTERNATIVE_NOT_ADDRESSED` error per reference lists every unanswered alternative, numbered, and ends with one ready-to-paste block: the `size_derivation` lines "'<alternative>': does not apply because …" for all of them, with a reminder that an alternative which changes the size goes to `mask_check.alternative_readings` with its `size_m` instead.
- **Tests:**
  - dry run: references backpack 0.66 m (`single`, mask A object 0) and figure 1.70 m disagree; final: backpack 0.914 m (`sum`, sources 0.66 and 0.254, mask A object 0) and figure 1.70 m agree: the verdict is not undetermined, and no `REFERENCE_DROPPED` or `THIRD_REFERENCE_REQUIRED`; the same final evidence without the backpack: `REFERENCE_DROPPED` as before;
  - one reference with an absence reason and a retimed preview with `clock: none, scene-pinned`: accepted, verdict undetermined, reason contains "one reference", `g_measured` present;
  - a reference whose blind check lists 5 alternatives, none answered: exactly one `ALTERNATIVE_NOT_ADDRESSED` for it, its detail contains all 5 texts numbered 1–5 and the words "does not apply because".

## 47. Owner addendum (2026-11-01, from four runs with 150 turns): a size comes from a named dimension

Seen: a Moon run took the oxygen purge unit as 0.381 m high from the museum line "3-D: 38.1cm × 17.8cm × 20.3cm". The line does not say which number is the height; the unit sits flat on top of the pack, and other sources give its height as 10 inches (0.254 m). The backpack came out 1.041 m and the run ended undetermined.

- **`SIZE_DIMENSION_UNLABELLED` (error, as in §44).** For each `sources[]` entry of a reference: when its value appears in the quote only inside a run of three or more numbers joined by "×" or "x" with no dimension word next to that number ("high", "tall", "height", "wide", "width", "deep", "depth", "long", "length", "diameter"), the submit is refused. The detail names the reference, the value and the quote: "oxygen purge unit: 0.381 m comes from '38.1cm × 17.8cm × 20.3cm', which does not name its dimensions. Use a source that says which number is the height (R-S13)."
- **Tests:** the quote "3-D: 38.1cm × 17.8cm × 20.3cm, 12.3kg" with value 0.381 gives the error; "The PLSS was 26 inches (66 cm) high, 18 inches (46 cm) wide" with 0.66 gives none; "Overall: 5 ft. 6 15/16 in. tall x 2 ft. 8 5/16 in. wide x 11 in. deep (170.02 x 82 x 27.9cm)" with 1.7002 gives none, because "tall" names that number.

## 48. Owner addendum (2026-11-02, from four runs after §47): a range check never re-measures a reference

Seen: Moon run `20261102T024430Z-85786ac8` measured g = 1.64 ± 0.24 m/s², which fits the Moon. Its references were the backpack at 0.914 m (`sum` of the PLSS 0.66 m and the top unit 0.254 m) and the suited figure at 1.70 m. It also submitted a range check "backpack height" on the same line as the backpack reference (frame 320, (84, 65)–(94, 132)), against the range [0.254, 0.66] m built from the two parts' heights. Its `answers` said it confirms the stacked top unit. The validator scored it 8.4σ above the range, and the verdict became "Not realistic on the Moon: backpack height 91.3 ± 3.0 cm".

- **`RANGE_CHECK_ON_REFERENCE` (error, in a dry run and a real submit).** An extent of a range check that lies on the same frame as a reference's `extent_px` or `check_scale` extent, with both endpoints within 3 px of that extent's endpoints (in either order), is refused. The scale comes from that line, so its measured length equals the quoted size by construction and tests nothing. The detail names both: "range check 'backpack height' measures the same line as reference 'backpack assembly height' on frame 320. The scale comes from that line, so this check tests nothing. Remove the range check, or measure a different object (R-R)."
- **Tests:**
  - Moon run `85786ac8`'s final evidence gives `RANGE_CHECK_ON_REFERENCE` for `range_checks[0]`, and its verdict is not "impossible";
  - the same range check moved to frame 321, or with one endpoint 5 px away, gives no `RANGE_CHECK_ON_REFERENCE`;
  - hand run 1's evidence (hand length and palm length range checks, references on other lines) gives none.

## 49. Owner addendum (2026-11-02, from four runs after §48): the shape check reads every mask of the same object

Seen: Moon run `20261102T095251Z-b825e17e` measured the suited figure as 1.70 m over 161 px on frame 244, two frames before the takeoff at 246, and the backpack as the PLSS alone, 0.66 m. The two wrong references agreed within 4 %, and the verdict was "slowed down ×1.13" at g = 1.27 m/s². The figure's reference mask (`t41_segment_0.npz`) covers only frames 240–244, all inside the flight candidate ±0.3 s, so §44's `REFERENCE_SHAPE_UNSTABLE` was skipped: "only 0 rest frames within ±1 s". The run's whole-clip mask of the same figure (`t6_segment_0.npz`, IoU 0.97 with the reference mask on frame 244) is 155 px high on frame 244 and has a median of 125 px over 22 rest frames (214–235).

- **The shape check reads every mask of the same object.** For a reference with a mask, the rest frames come from every `artifacts/t*_segment_*.npz` of this run whose object overlaps the reference's mask object on the measuring frame with IoU above 0.5. Each frame counts once, and the reference's own mask comes first. The 5 % rule and the ±1 s / ±0.3 s windows of §44 stay.
- **`REFERENCE_SHAPE_UNCHECKED` (error).** When those masks still give fewer than 5 rest frames, but the clip has 5 or more frames within ±1 s of the measuring frame that lie outside every flight candidate ±0.3 s, the submit is refused. The detail says: "<name>: its shape on frame <f> cannot be checked; segment it over frames <a>–<b> (its rest frames near the motion) or measure it on one of them (R-S14)". When the clip itself has fewer than 5 such frames (a still or a very short clip), the check is skipped as before.
- **Tests:**
  - run `b825e17e`'s evidence and masks: the figure reference gives `REFERENCE_SHAPE_UNSTABLE` naming 155 and 125 (from `t6_segment_0.npz`), not a skip;
  - the same reference with only its own mask `t41_segment_0.npz` in the artifacts gives `REFERENCE_SHAPE_UNCHECKED` naming frames 214–235;
  - synthetic masks of a rectangle 100 px high on frames 0–3 only, in a 4-frame clip: no error, and the scale step says the check was skipped.

## 50. Owner addendum (2026-11-02, from four runs after §49): every reference line is confirmed blind

Seen: Moon run `20261102T133200Z-4cd1c236` used a "suited figure width 0.82 m" along a diagonal line, (69, 105)–(148, 70), on frame 234, and the white pack as 0.66 m. Neither line had a `check_line` record. The two wrong sizes agreed, and the verdict was "slowed down ×1.16". §28 asks a confirming blind look only for range-check lines, and §36 only for lines that already have a record.

- **`REFERENCE_LINE_NOT_CONFIRMED` (error, in a dry run and a real submit).** Every reference's `extent_px` needs a `check_line` record of this run that matches it as §28 says (the same frame, both endpoints within 2 px) with `agrees: true` and a `dimension` other than "unclear" (part 07 §22). The same holds for a `check_scale` extent. The detail names the reference and says: "run check_line on this line with a claim that names its dimension, for example 'height of the <thing>' (R-S17)".
- A dry run lists this error for each reference that lacks a record; the other per-reference checks still run (§30).
- **Tests:**
  - run `4cd1c236`'s final evidence gives `REFERENCE_LINE_NOT_CONFIRMED` for both references;
  - a reference with a matching record `agrees: true`, `dimension: "height"` gives none; the same record with `dimension: "unclear"` gives the error; a record 3 px off at one endpoint gives the error.

## 51. Owner addendum (2026-11-03, from four runs after §50): one reference gives no verdict from range checks either; a range check never re-measures a reference's object

Seen: Moon run `20261102T222230Z-bf0cf9f7` had one reference, the backpack as the PLSS alone (0.66 m over 68 px, frame 220), with an absence reason. It added two range checks on the same scale:
- "suited figure height" on frame 205: 129 px gave 1.25 m against [1.6764, 1.7002] m, outcome `below`, which decides nothing on its own (§38);
- "backpack height" on frame 240, the reference's own object on another frame, against [0.25, 0.66] m, outcome inside.
The verdict was "Realistic on the Moon: backpack height 64.2 ± 3.0 cm is inside …", `decided_by` the backpack range check, while the measured g was 1.14 m/s². The figure check was the signal that the scale was 26 % off; the backpack check could only agree with its own reference.

- **One reference gives no verdict from range checks either (R-S6a, §46).** When the scale rests on one reference, every range check that uses the scale (`uses_scale: true`) is reported with its value but decides nothing: the verdict is undetermined, "scale rests on one reference", as for gravity. A range check that does not use the scale (a ratio, a clock) still decides as before.
- **`RANGE_CHECK_ON_REFERENCE` covers the reference's object on any frame (§48 widened).** A range-check extent is refused when both its endpoints lie within 3 px of the reference's object on the range check's frame, read from any mask of the same object (§49: IoU above 0.5 with the reference's mask on its measuring frame). The detail says the range check re-measures the reference "<name>" on frame <f>.
- **Tests:**
  - run `bf0cf9f7`'s final evidence: the verdict is undetermined, "scale rests on one reference", and the backpack range check gets `RANGE_CHECK_ON_REFERENCE` (frame 240) when the run's masks of that object cover frame 240;
  - hand run 1's evidence (two references, two range checks on other lines, no scale) keeps its verdict;
  - a range check with `uses_scale: false` and one reference still decides.

## 52. Owner addendum (2026-11-03, from four runs after §51): the shape check measures along the reference's own line

Seen: sped-up run `20261103T023347Z-02dc5ade` used two references on frame 130, a push-off frame. One was the backpack as the PLSS alone (0.66 m over 67.5 px). The other was a "suited figure width" of 0.82 m along the line (67, 115)–(146, 128), 80 px. The two wrong sizes agreed within 5 %, and the verdict was "sped up ×2.12". The figure's mask on frame 130 is 130 px high against a median of 131 px at rest, so §44's height check passed. Along the reference's own line the same mask spans 84 px against a median of 78 px on its rest frames (122–127, 159): 8 % wider than at rest.

- **`REFERENCE_SHAPE_UNSTABLE` measures along the reference's line (§44, §49).** The size of a mask on a frame is the spread of its pixels along the direction of the reference's `extent_px` line: the largest minus the smallest projection of the pixel centres on the unit vector from (x1, y1) to (x2, y2), plus 1 px. The measuring frame and every rest frame use the same direction. A vertical line gives the mask height, as before. A line of zero length gives the mask height. The rest frames, the windows and the 5 % rule of §44 and §49 stay.
- **The detail names the direction.** "<name> on frame <f>: mask <a> px along the measured line, <p> % above its median <m> px on frames <list> at rest; measure it on a frame where it keeps its shape along this line (R-S14)."
- **Tests:**
  - run `02dc5ade`'s final evidence and masks: the "suited figure width" reference gives `REFERENCE_SHAPE_UNSTABLE` naming 84 and 78; the "backpack height" reference gives none;
  - synthetic masks of a rectangle 50 px high and 100 px wide on frames 0–60 and 125 px wide on frame 61 (30 fps, no candidates): a horizontal reference line on frame 61 gives the error naming 125 and 100; a vertical reference line on frame 61 gives none;
  - the tests of §44 and §49 keep their numbers with vertical reference lines.

## 53. Owner addendum (2026-11-03, from four runs after §51): one quoted thing is one reference; a dry run asks for the moving thing

Seen: sped-up run `20261103T023347Z-258d5f07` reported "backpack height at frame 96" and "backpack height at frame 128", both 0.66 m (`single`) from the same source URL. It added the second one after `REFERENCE_DROPPED` named its confirmed line on frame 128. The two disagreed, and the run ended undetermined. Moon runs `20261103T023347Z-bce08ba3` and `20261103T023347Z-e84d1289` measured only the backpack. Neither reference mask is the motion overview's object (`first_look.overview`), the moving figure.

- **`REFERENCE_SAME_THING` (error, in a dry run and a real submit).** Two references whose `size_m` values are within 1 % of each other and whose `sources[].url` sets are equal are one quoted thing measured twice. The detail names both and says: "references[<i>] and references[<j>] quote the same size from the same sources: one thing measured twice is one reference. A second reference is a different thing: the moving thing itself, something it wears or carries, or a fixed thing beside it (R-S6b, R-S16)."
- **`SELF_REFERENCE_REQUIRED` (dry-run push, §16.2).** The moving thing is the object of `first_look.overview` (`artifact`, `object_id`). A reference is on the moving thing when its mask on its measuring frame overlaps that object's mask on the same frame with IoU above 0.5. The overview's mask and every mask of the same object count (§49). When `first_look.overview` is present and no reference is on the moving thing, the dry run lists this push: "references: none of them is the moving thing (object <oid> of <artifact>); measure its own quoted size on a rest frame along the dimension its source names, and keep the others (R-S16). Skip this only when the moving thing has no quoted size." A real submit is not refused for it.
- **Tests:**
  - run `258d5f07`'s final evidence gives `REFERENCE_SAME_THING` for references 0 and 1; the same evidence with the second reference's `size_m` 0.914 and two sources gives none;
  - the final evidence of runs `bce08ba3` and `e84d1289`, as a dry run, lists `SELF_REFERENCE_REQUIRED`; run `20261103T023347Z-02dc5ade`'s final evidence (its "suited figure width" mask is object 1 of `t6_segment_0.npz`, the overview's object) does not;
  - evidence without `first_look.overview` gives no `SELF_REFERENCE_REQUIRED`; a real submit of `bce08ba3`'s evidence does not list it as an error.

## 54. Owner addendum (2026-11-03, from the §53 check on the runs after §51): one object means IoU above 0.75

Seen: on Moon run `20261103T023347Z-e84d1289`, frame 228, the backpack reference mask (`t27_segment_0.npz` object 0) and a mask of the figure that wears it (`t79_segment_0.npz` object 0) have IoU 0.503. The overview's figure mask (`t6_segment_0.npz` object 1) and `t79` object 0 have IoU 0.896. With the 0.5 limit, `t79` counted as a mask of the backpack, the backpack counted as the moving thing, and the §53 push was not listed. In runs `bf0cf9f7`, `b825e17e`, `02dc5ade`, `bce08ba3` and `e84d1289`, two masks of one object from different `segment` calls have IoU 0.896–1.0 on the reference's frame. A backpack and the figure that wears it have IoU 0.41–0.50.

- **The same-object limit is IoU above 0.75.** Every same-object match of §49 (the shape check's masks), §51 (`RANGE_CHECK_ON_REFERENCE`) and §53 (`SELF_REFERENCE_REQUIRED`) uses IoU above 0.75 instead of 0.5. One named constant in `src/validate/` holds the limit, and every match reads it.
- **Tests:**
  - run `e84d1289`'s final evidence, as a dry run, lists `SELF_REFERENCE_REQUIRED`; on frame 228, `t79_segment_0.npz` object 0 is not a mask of the backpack reference's object, and `t47_segment_0.npz` object 0 (IoU 0.95) is;
  - synthetic masks with IoU 0.6 on the measuring frame are two objects, and masks with IoU 0.8 are one object;
  - the tests of §49, §51 and §53 keep their results.

## 55. Owner addendum (2026-11-04, from street-jump run 81): the camera detail names the field; a flight inside a longer candidate is judged on its own frames

Seen: on a handheld street-jump clip the camera pans about 30 px during the jump. Two dry runs (turns 96 and 139) got `CAMERA_UNACCOUNTED` ("use the relative_track artifact (R-M3)"); the agent had already built a scene-relative track, but both times it kept `camera.still` and changed nothing else. In the same runs, `motion_overview` merged the run-up, the jump and the landing into one candidate, F2 frames 40–166 (r² 0.39). The agent measured the jump as segment `jump_a`, frames 63–111, inside F2, and got `FLIGHT_NOT_PARABOLIC` for F2 twice. Deciding F2 `not_a_flight` would leave `jump_a` in no candidate (`MOTION_NOT_MEASURED`), so the run had no way out.

- **`CAMERA_UNACCOUNTED` names the fix.** When `camera.still` is refused because the reference moves, the detail keeps its first sentence and then says, in these words: `replace camera with {"relative_track_artifact": "<path>"}: a JSON list of {frame, x_px, y_px} rows of the subject's track minus the scene reference's track (helpers.tracks.relative_track), and fit that track`. The code and the 2 px threshold stay.
- **A measured segment inside a longer candidate is judged on its own frames.** For a candidate decided `measured` whose recomputed run has r² below 0.8: when the candidate's `segment_id` names a segment whose `frames.start`–`frames.end` lie inside the run and cover fewer frames than the run, the validator computes the centroid r² of the overview's own mask over the segment's frames only, the same way as for a run. When that r² is 0.8 or more, there is no `FLIGHT_NOT_PARABOLIC`. Otherwise the detail is the same as before and adds the segment's frames and r². A segment that covers the whole run is judged as before.
- **Tests:**
  - evidence with `camera.still` whose reference track moves 24 px: the `CAMERA_UNACCOUNTED` detail contains `relative_track_artifact` and `helpers.tracks.relative_track`;
  - a synthetic overview mask with a level run-up (frames 0–29), a parabola (frames 30–60) and a level run-out (frames 61–90) as one run of r² below 0.8, decided `measured` with a segment of frames 30–60: no `FLIGHT_NOT_PARABOLIC`; with a segment of frames 0–90: `FLIGHT_NOT_PARABOLIC` as before;
  - the same mask with frames 30–60 replaced by a level track with ±5 px noise: `FLIGHT_NOT_PARABOLIC`, and the detail names frames 30–60;
  - the existing `FLIGHT_NOT_PARABOLIC` tests of §45 keep their results.

## 56. Owner addendum (2026-11-04, from street-jump run 82): a named free flight is measured, not replaced by a range check

Seen: run 82 named the jump over the car (frames 63–111) in `first_look.motions` with `segment_id` null and `skip_reason` "height measured as range check against human norms, not as gravity fit". It had tracked the jump (centroid fit g ≈ 10.5 m/s² over frames 64–108) but reported no segment, no overview and no fit. The verdict came from one range check, and the page showed no mask of the jumper, no track and no airtime. Every motion rule (§14, §43, §45, §55) applies only to a measured motion, so leaving the motion out skipped all of them.

- **The rule applies when the evidence has no measured segment** and `first_look.motions` has an entry of 8 frames or more. Results with at least one segment keep free-text skip reasons, as before.
- **Then each such entry's `skip_reason` starts with one of five words and a colon**, and the validator checks the ones it can:
  - `cut:` — part 05's cut list has a cut inside the entry's frames;
  - `too short:` — the entry covers fewer than 8 frames;
  - `no flight:` — `first_look.overview` exists and its recomputed overview (§43) has no candidate overlapping the entry's frames by half of the shorter range; without an overview, the dry run pushes `MOTION_OVERVIEW_MISSING` as in §43;
  - `out of frame:` and `hidden:` — accepted as written.
- **Any other reason is refused** with `MOTION_SKIP_REASON` naming the entry: "first_look.motions[i] (frames a–b, 'description'): a named motion is measured as a segment, a free flight against the world's gravity, unless it cannot be. Start skip_reason with cut:, too short:, no flight:, out of frame: or hidden:. A range check goes beside a measured motion, never in its place." A real submit with this error is undetermined, reason "the named motion at frames a–b was not measured".
- When a reason's check fails (`cut:` without a cut, `too short:` on 8 frames or more, `no flight:` with an overlapping candidate), the same code names the entry and the failed check.
- **Tests (synthetic evidence, no model calls):**
  - no segments, one motion of frames 63–111 with skip_reason "height measured as range check against human norms, not as gravity fit": `MOTION_SKIP_REASON` naming entry 0 and frames 63–111; a real submit is undetermined;
  - the same with "too short: …": `MOTION_SKIP_REASON` naming the failed check; with frames 63–67 and "too short: …": none;
  - the same with "no flight: …" and no overview: `MOTION_OVERVIEW_MISSING`; with an overview whose recomputed candidate covers frames 60–115: `MOTION_SKIP_REASON`;
  - the same motion with a measured segment `jump_a` elsewhere in the evidence and another motion skipped with free text: no `MOTION_SKIP_REASON`;
  - the existing fixtures keep their results.

## 57. Owner addendum (2026-11-04, from street-jump run 83): the point-versus-centre allowance is at least what the masks show

Seen: on the street-jump clip the jumper tucks his legs in flight; his mask's height falls from about 490 px to 200 px and back. Fitted over the same frames 64–106 of run 83's own masks, with the camera's drift removed, the mask's area centroid gives g = 10.7 m/s² (R² 0.997), the mask's median row gives 9.6, the shirt alone 6.0 and the head 4.8. Only the centre of mass follows a parabola; a tracked point on a body that changes shape does not. The agent fills `point_vs_com` by judgment (the Moon run wrote 0.08 m/s²). With an allowance of that size, a correct measurement of 10.7 fails Earth by the 2σ rule of part 02 and reads as "sped up ×1.05", a false verdict. On the Moon runs' masks the two estimates differ by less than 1 % (the suited astronaut keeps his shape), so this changes nothing there.

- **The validator computes a shape term for each measured segment** from the segment's own masks (`segment.mask.artifact`, `object_id`) over the frames of its fit:
  - per frame, the mask's area centroid y and its median row (the row with half of the mask's pixels above it);
  - one parabola for each series on the measured timestamps (part 09's fit, unweighted);
  - shape term = |g from the centroid − g from the median row|, in m/s² at the segment's pixel scale.
  - Both series carry the same camera offset in every frame, so the difference needs no camera correction.
- **The error budget's `point_vs_com` component must be at least the largest shape term** over the measured segments (2 % tolerance, as §18). A smaller one pushes `ERROR_BUDGET_INCOMPLETE` on `error_budget.components` with: "point_vs_com {value} is smaller than the shape term {term} m/s² of segment {id}: the body changes shape in the fit (mask height {min}–{max} px); the area centroid gives g = {g1}, the median row gives g = {g2}. Set point_vs_com to at least {term} and recompute sigma_relative." A real submit with this error is undetermined, reason "the error budget leaves out the body's change of shape".
- A segment whose masks cannot be read gives `MISSING_FIELD` naming the input, never a shape term of 0.
- **Tests (synthetic masks, no model calls):**
  - a rectangle of constant size on a parabolic hop with planted g: shape term below 1 % of g; an evidence with `point_vs_com` 0.08 passes this check;
  - the same hop with the rectangle's bottom edge pulled up from 100 px to 50 px tall at the apex and back (legs tucking): shape term above 5 % of g; `point_vs_com` below it pushes `ERROR_BUDGET_INCOMPLETE` naming the segment and both g values; `point_vs_com` equal to it does not;
  - the existing fixtures keep their results.

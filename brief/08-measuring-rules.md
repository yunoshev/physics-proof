# 08 — Measuring Rules

**Owns:** `prompts/measuring_rules.md` (the agent-facing statement) and `src/rules/` (the code checks). **This is the lessons file.** Governing principle, from the first attempt: *the model broke rules that were only written in its prompt* — so every rule below states (a) the rule, (b) why (the failure that taught it), and (c) where it is **enforced in code**. Prompt text is the explanation; code is the guarantee. Enforcements are implemented either as tool/helper gates or as submit-time checks in `src/rules/` invoked by part 11.

## R-T — Time

- **R-T1.** All times come from measured frame timestamps (`timing.json`, part 05), never from the container's fps claim. *Enforced:* helpers (part 09) accept frame indices + the timing report and refuse a bare fps argument from agent code.
- **R-T2.** Before fitting anything, inspect the timeline report: exclude (or explicitly correct for) confirmed duplicated frames, and never fit across a cut. *Why:* duplicated frames fake zero-acceleration plateaus; a cut splices two motions into one "trajectory". *Enforced:* fit helpers take the timing report and reject frame sets containing confirmed duplicates/cuts unless the agent passes an explicit, logged correction (e.g. duplicates collapsed to one timestamp).
- **R-T3.** Absence of duplicates proves nothing about retiming: a motion-interpolated slow copy has none. Retiming is established only via physics + clock (R-C), never from timeline forensics.

## R-S — Scale (the biggest error source)

- **R-S1.** A reference's size is only as good as knowing what its mask covers. Every size-bearing reference must have a **blind mask check** (part 07 §4) attached. *Enforced:* submit check — a reference without a `check_mask` artifact is rejected.
- **R-S2.** The blind check reports *coverage, not identity*. If coverage admits two readings with different real sizes (Apollo lesson: backpack alone 0.66 m vs. backpack + top unit 0.91 m — that alone moved `g` by 1.4× and decided pass/fail), the agent must either (a) choose a reference whose coverage has a single reading, or (b) **carry both readings through**: compute `g` under each and fold the spread into σ (R-E). *Enforced:* if the check returns multiple readings, submission must contain a measurement per reading or a reasoned single-reading justification referencing the overlay; a silent single choice is rejected.
- **R-S3.** **Two extents of the same object are not two references.** *Why:* a wrong idea of what the object is spoils both extents, and they still agree with each other — the agent did this twice with the rule in its prompt. *Enforced in code:* the second reference's mask must be a **different object**: if the two masks overlap by more than **50% of the smaller mask's area** (same frame), submit rejects them as independent. Different objects at **about the same depth** as the measured body; if no such second object exists, the submission must state that and why (and σ must reflect a single-reference scale, R-E). A claimed-but-overlapping "second reference" is a hard reject, not a warning.
- **R-S4.** An extent seen at an angle mixes width and depth. Use a **face-on extent**, or one that doesn't change with rotation (e.g. the height of a standing person). If a projected extent is used anyway, σ must include a stated projection allowance. *Enforced:* each reference declares its extent type (`face_on` / `rotation_invariant` / `projected`); `projected` without a projection allowance in the error budget is rejected.
- **R-S5.** Scale is measured at the depth of the motion; a reference much nearer/farther than the body without a depth correction inflates σ or disqualifies (feeds R-S3's "say so and why").

## R-M — Motion

- **R-M1.** **Fit only unsupported motion.** Support intervals are found from the **lowest point of the body mask** over time (its trajectory flattens/rests at contact); contact frames are excluded from any gravity fit. *Enforced:* fit helpers require a support/interval mask; submit checks that fitted frames ∩ contact frames = ∅.
- **R-M2.** **Track a point rigid with the body.** The top/bottom of a whole-body mask moves with posture (arms up, knees bent) and is not a body point. Prefer a point on a rigid part (or a segment-local mask), and **check fit residuals for a trend**: a systematic residual trend means the "point" is deforming, not accelerating. *Enforced:* helpers return a residual-trend statistic with every fit; submit rejects fits whose trend exceeds the library threshold (part 09) without a re-track.
- **R-M3.** **Moving camera ⇒ measure relative to the scene.** If anything fixed in the scene (wall, ground line, background feature) moves in screen pixels beyond the helper threshold, trajectories must be computed **relative to that fixed reference** (e.g. runner relative to the wall), not in screen coordinates. *Enforced:* submit requires either a camera-still attestation backed by a reference-track measurement, or scene-relative trajectory artifacts. (Wall-run lesson: the camera tilts up to follow the runner; screen-pixel fitting would measure the camera, not the man.)

## R-C — The independent clock

- **R-C1.** Where a retiming/impossible distinction matters (part 02 §5), find an independent clock: a known natural rhythm in the scene (people's step rate is the canonical one).
- **R-C2.** **Step-rate signal (what worked, what failed).** The head-bob failed: perspective on a receding runner turns it into a slow trend, and the spectrum peak collapsed to the lowest frequency — once producing a *negative* frequency. The signal that works: **the width of the lowest 30% of the person's mask ÷ mask height**, sampled per frame; it peaks once per step. *Enforced by construction:* the clock helper (part 09) implements exactly this signal path: (a) detrend with a **running median**, never a global fit; (b) search only inside a stated frequency band and **never return a frequency outside it** (a peak at the band edge is reported as "no reliable clock", not clamped into a number); (c) return the spectrum/autocorrelation so the choice is auditable.
- **R-C3.** **Step ≠ stride.** A factor of two lurks here: the helper must test both interpretations (peak = step rate vs. peak = stride rate, i.e. 2 steps) and report which the harmonic structure supports. If both remain plausible and they change the verdict, the honest output is *undetermined* (part 02 §5). *Enforced:* clock artifacts contain both candidate rates; submit rejects a clock that silently picked one when the helper flagged ambiguity.
- **R-C4.** **Test retiming with numbers, never vibes.** If the clip would have to be slowed by `k` (`s = k`) for physics to fit, the **true** clock rate is `k ×` the **measured** rate (measured rate = true rate ÷ `s`). If that implied true rate falls outside the natural range for the activity, no playback speed explains the clip → *physically impossible* (given the scene's world). Conversely a measured rate already inside the natural range is a clock that "reads normal". The natural range used must be stated in the submission with its source (filtered search, part 07) — *enforced:* clock evidence without a stated natural range + source is rejected.

## R-W — Worlds

- **R-W1.** Candidate worlds come from the scene (part 02 §2). *Why:* the agent once tested the Moon for a city street, got "Moon is nearest", and answered "a sped-up Moon clip". *Enforced in code:* submission lists every world as `candidate` or `excluded` with **frame-referenced visual evidence** for each exclusion (artifact + frame indices); the validator computes fits **only for candidate worlds** and rejects a verdict naming an excluded or unexamined world. "Nearest of all worlds" is not a computable output of the validator.

## R-E — Honest error budget

- **R-E1.** σ is a budget, not a fit residual alone. It must itemise: reference-size uncertainty (including R-S2's multi-reading spread), pixel-scale uncertainty, fit uncertainty, tracked-point-vs-centre-of-mass allowance, and **spread across repetitions** where the clip offers them (e.g. a second hop fitted independently). *Enforced:* submit requires the itemised components and recomputes σ_total = quadrature sum (plus the R-S2 discrete-reading spread as an explicit term); a σ smaller than any single component is rejected.
- **R-E2.** Repetitions are fitted **independently** (own scale application, own support intervals) so their spread means something; copy-pasting one fit's numbers is detectable (identical residuals) and rejected.
- **R-E3.** **Cross-clip ratio is a cross-check, never a verdict.** Two clips of the *same event* share scale error, so their acceleration ratio recovers the relative slowdown even with a wrong scale (it gave 1.48 for our 1.5). The single-clip agent never sees another clip, so this belongs to the harness/page layer (parts 15/13), and *enforced:* nothing in a submission may reference another run's measurements.

## R-G — Ghost

- The ghost is **computed by code** from the fitted takeoff state (position, velocity) propagated under a *counterfactual* gravity at the measured scale — the world the verdict contrasts against (e.g. on a Moon-fitting clip, the Earth ghost: "on Earth he would have landed here"). It is an output of measurement (part 11 computes it from submitted fit parameters; part 13 draws it), never a curve the agent sketches. *Enforced:* submission carries takeoff state + scale; ghost points appear only in the validated result.

## Enforcement summary

| Rule | In prompt | In code | Where |
|---|---|---|---|
| R-T1/T2 | ✓ | ✓ | helpers refuse bad time bases; validator checks fitted frames |
| R-S1/S2 | ✓ | ✓ | submit: mask-check artifact + multi-reading handling required |
| R-S3 | ✓ | ✓ **hard reject** | mask-overlap > 50% of smaller ⇒ same object |
| R-S4/S5 | ✓ | ✓ | extent-type declaration + allowance required |
| R-M1/M2 | ✓ | ✓ | contact-frame exclusion; residual-trend gate |
| R-M3 | ✓ | ✓ | camera-motion measurement or scene-relative track required |
| R-C2/C3 | ✓ | ✓ **by construction** | helper only returns in-band, detrended, dual-interpretation results |
| R-C4 | ✓ | ✓ | natural range + source required |
| R-W1 | ✓ | ✓ **hard reject** | fits computed only over scene-candidate worlds |
| R-E1–E3 | ✓ | ✓ | validator recomputes σ; cross-run references rejected |

Anything in this table marked "in code" is tested in part 15 with a deliberately violating submission that must be rejected.

## Owner addendum (2026-10-28, from the eighth live run): two or three references, always

The eighth run took its scale from one reference, the backpack at 0.66 m, while the blind check offered the reading "upper block stacked on the pack" (0.91 m). The rules asked for a second reference only in particular cases (a person in the clip), and the agent stepped around them. A second and third object would have caught the error, whatever the clip shows. The rule is general and does not depend on roles in the clip; the moving object is not special.

- **R-S6. Scale comes from two or three references, always.** Measure at least two different things whose real sizes are known independently of each other, and aim for three: people, animals, vehicles, doors, furniture, signs, balls, tiles, equipment, or parts of these. A thing carried by or attached to another is a different thing: a worn backpack and its wearer's height are two references. Each reference has its own blind check (R-S1), its own size source and its own extent at the depth of the motion (R-S5). Every pair must agree within 2σ under the readings used. When they don't, find the wrong reading or size; never average a disagreement away. The scale is the references' inverse-variance weighted mean, computed by code.
- **R-S6a. One reference gives no verdict.** If the clip shows only one thing of known size at the depth of the motion, the run can still submit it with `second_reference_absent_reason`, but the verdict is *undetermined*, "scale rests on one reference".
- **R-S3 amended:** the code's overlap test rejects only near-identical masks (intersection over union above 0.8: the same mask passed twice). A mask nested inside another, such as a backpack inside its wearer, is a different thing.
- **R-S2 amended:** an alternative reading with a different size is priced in full (half the size difference as σ) unless another reference rules it out (part 11 §12).
- **Superseded:** the "a person is a second reference" rule (part 11 §9) and the subject's kind as a rule switch (part 07 §15, part 11 §12.1).
- **Test:** `prompts/measuring_rules.md` contains R-S6 and R-S6a, and contains no rule that depends on the subject being a person.

## Owner addendum (2026-10-28, from the eighth live run): every repetition is measured

The eighth run measured one hop on clip A. The clip has two (frames ≈ 241–277 and a second one later; the approved player shows Jump 1 and Jump 2). Its first look said "the foreground figure leaves the ground, hangs, and lands". The same rule as for scale (R-S6): several independent measurements catch what one cannot.

- **R-M4. Find and measure every repetition.** Before measuring, view the whole clip at a spacing of at most 0.25 s and list every interval in which the motion under test happens: each hop, throw, fall or swing (`first_look.motions`, part 12 §19). Measure each one as its own segment, or give a reason it can't be measured (cut off by the frame edge, hidden, too short). The segments' g must agree (the existing segment-conflict rule). Their spread is the `repetition_spread` component, and with two or more segments it replaces the split-window spread of a single one.
- **Test:** `prompts/measuring_rules.md` contains R-M4.

## Owner addendum (2026-10-28, from the ninth live run): the size matches what is seen; a gap calls for a third

The ninth run used two references, as R-S6 asks: the backpack (0.66 m over 65 px, 0.0102 m/px) and the figure's standing height (1.71 m over 152 px, 0.0113 m/px). For the height it took "the global average adult male, 171 cm" for a figure in a pressure suit with helmet and boots. The two were 10 % apart, inside 2σ because each σ was wide, and both were low. The result: g = 1.25 ± 0.09 m/s², undetermined.

- **R-S7. A size describes the thing as it is seen.** The size source must describe the same kind of thing in the same state as the mask covers: with what it wears, carries or stands on (headgear, footwear, mounted units, packaging, load). A generic class average (average adult, average car) is used only when nothing more specific is visible. Its σ is then that class's spread, and the evidence names what makes the specific size unknowable. *Enforced:* each reference's `size_derivation` carries `state_match`: what the mask shows that the size source also covers, and what it shows that the source does not.
- **R-S8. A gap between references calls for a third.** When two references differ by more than 5 % in `m_per_px`, even within 2σ, measure a third reference of a different thing before submitting, and report all three. *Enforced:* part 11 §15.
- **Test:** `prompts/measuring_rules.md` contains R-S7 and R-S8.
- **R-S9. Measure a reference on a still, sharp frame.** Take a reference's extent on a frame where it is at rest and unblurred. If it rides on the moving thing, use a frame before the motion starts (the approved player held Scale at frame 200, before the jump at 241). The player shows the Scale hold at that frame, so the scale is explained before the motion. Seen: the eighth run measured the backpack at frame 250, mid-flight.
- **R-S10. Identify, then research the specific thing** (part 01, decision of 2026-10-28). Before choosing sizes, work out from the frames what and who is in the clip, as specifically as the footage allows: place, era, event, the particular person, the model. Search for that instance's facts: the person's height, plus what the suit, helmet and boot soles add; the equipment's dimensions, including mounted units; the vehicle's model length. Record the identification and how the frames support it in `first_look.scene_card` (`scene`, `place_date`, `objects`) and in each reference's `size_derivation.note`. A generic class average (R-S7) is a fallback only when the frames don't allow anything more specific. Never search for the clip itself or its answer (part 07 §17). Seen: the ninth run measured a suited Apollo astronaut as "the global average adult male, 171 cm".
- **R-M5. One phase per window** (owner addendum 2026-10-28, from the second wall run). A fit window covers one stretch under one force law. Cut it where the support changes: takeoff, landing, a foot plant, a change of surface (ground to wall, wall to top), a turn. *Why:* wall run 2 fitted run-up, turn and climb as one parabola and got g = 0.26 m/s². *Enforced:* part 09 `residual_trend_z` ≤ 3, part 11 V7.
- **Dry-run pushes** (owner addendum 2026-10-28; part 11 §16). The dry run rejects three easy exits while there is still time to do better. A real submit still accepts them as undetermined.
  - `SECOND_REFERENCE_REQUIRED`: one reference. Try the moving thing itself (its size from R-S10's identification), what it wears or carries, and fixed things beside it. R-S6a's single reference is a last resort; when it stays, name each candidate and why it failed in `second_reference_absent_reason`.
  - `CLOCK_REQUIRED`: g fits no world and there is no clock. Any repeating motion is a clock candidate (R-C1): steps, swings, wing beats, turning wheels.
  - `MOTIONS_SCAN_MISSING`: the whole clip was not viewed at ≤ 0.25 s spacing (R-M4).


## Owner addendum (2026-10-29): the question first, one world

Part 01's addendum of 2026-10-29: the clip's own question, answered in the scene's world.

- **R-Q1 (new).** Before measuring, write `first_look.question` as the viewer's question: what the clip shows or claims that a viewer might doubt, in plain words, naming the scene's world when it is not obvious ("Can a person run up a wall this tall?", "Is this hop realistic on the Moon?"). Not physics vocabulary ("does the ascent match Earth gravity"). `first_look.summary` says in one or two sentences what happens and which measurement answers the question. *Why:* wall run 5 asked "Does the wall ascent match Earth gravity?", a question no viewer asks.
- **R-W1 (replaces the rule above).** The scene names one world: ordinary footage is on Earth, the Moon only when the frames show the Moon. `worlds.candidates` holds that world only and `worlds.excluded` is empty; a second candidate only when the question names it. Do not test, list, search or mention other worlds. *Why:* wall run 5 listed the Moon and Mars on a city street only to exclude them. *Enforced in code (unchanged):* fits are computed only for candidate worlds; a verdict naming an unlisted world is rejected.
- **Tests:** `prompts/measuring_rules.md` carries R-Q1 and the new R-W1 text (it contains "the viewer's question" and "Do not test, list, search or mention other worlds"); the rules accept a worlds listing with one candidate and an empty `excluded`.

## Owner addendum (2026-10-29): R-R — range checks

Part 01's second addendum of 2026-10-29: a measured quantity against a sourced real range.

- **R-R1. One quantity, one kind of thing.** A range check names one quantity (a length, height, ratio, duration or speed), what it belongs to in the clip, and a range for **the same quantity of the same kind of thing** from a source: human hand proportions for a hand, wall-run records for a wall run, a product's published size for that product. A typical value alone is not a range: the source must give a minimum and a maximum, or a distribution from which they are stated (for example "5th–95th percentile"), and the check says which.
- **R-R2. Sources, quoted.** Every bound comes from the filtered `web_search` with a verbatim quote containing the number, as for reference sizes (R-S). The query names what was identified in the frames, never the clip or its answer.
- **R-R3. Prefer ratios.** A ratio of two lengths in the same frame and at the same depth needs no scale; use one when the question allows. A length in metres uses the run's scale (R-S) and inherits its σ.
- **R-R4. Measured by code, drawn on the frame.** `run_python` measures the extents (endpoints in source pixels on one frame, from masks or from points the agent places and checks with `view_frames`) and writes the value, its σ and the extents to an artifact; the evidence cites it. σ includes the endpoint uncertainty (at least 1 px per endpoint) and, for metric values, the scale's σ.
- **R-R5. Which checks.** Choose the checks that answer the question: for a body that moves, g on its free or wall segments (R-M); for what the motion achieves (height reached, distance, duration), a range check against records or norms for that kind of body; for a still image, sizes and proportions against norms. Two or three checks are enough; each must matter to the question.
- **Tests:** the measuring rules text carries R-R1–R-R5 (it contains "the same quantity of the same kind of thing" and "Prefer ratios").

## Owner addendum (2026-11-01, from the Moon and sped-up Moon runs): the agent looks at the trajectories, then decides

Two runs on the same footage measured different jumps and drew different pages. R-M4 already asked for every repetition, but by eye on contact sheets each run saw only one jump. The decision of what to measure stays with the agent; it must take it from the trajectories, not from a glance.

- **R-M6. See every motion in the trajectories.** Before measuring a motion check, segment the moving body over the whole clip in one `segment` call, then call `motion_overview` (part 07 §21) on it and look at its chart and strips. List every candidate flight of that body in `first_look.motions` and in `first_look.overview` (part 12 §24): measured as its own segment, or with a reason it is not a free flight or cannot be measured ("walking step, rise 4 px, area jumps", "cut off by the frame edge", "too short: 3 frames"). A candidate the agent judges to be a real free flight of the body under test is measured.
- **R-M7. One measurement, the others confirm.** When there are several free flights, the agent chooses the one it measures best as the first check (most frames, clean mask, whole body in frame) and measures the others as confirmations, each as its own segment and its own fit (R-E1, R-E2). The verdict uses all of them (part 11 §43). The agent records which one it chose first and why in `first_look.overview`.
- **R-S11. A reference is measured next to the motion.** Measure the references on a still, sharp frame (R-S9) as close as possible before the takeoff of the first-check flight, at most 2 s before it, unless no such frame shows the reference; then say why in the reference's `size_derivation.note`. The Scale hold then stands just before the jump on every run.
- **R-S12. A still thing needs a short segment.** A reference that does not move in the clip (a pack seen on a still frame, a flag, a wall, a fence) is segmented on a short range around its measuring frame: at most 50 frames, the billed minimum (part 07 §3; confirm the small range). Only a moving body is segmented over the whole clip. Seen: the sped-up run segmented the astronaut, the backpack and the flag over all 192 frames each; two thirds of its SAM bill was the backpack and the flag.
- **Test:** `prompts/measuring_rules.md` contains R-M6, R-M7, R-S11 and R-S12.

## Owner addendum (2026-11-01, from four runs on the Moon and sped-up Moon clips): a size is used as quoted, on a frame where the thing keeps its shape

Four runs on the same footage gave four answers: Moon undetermined, Moon "slowed ×1.16", sped-up ×2.06, sped-up ×2.47 (true ×2.46). All four measured both jumps. The scale made the difference.

- The two right runs (and the accepted Moon run 22) sized the visible white pack as the life-support unit plus the unit mounted on top: 0.66 + 0.254 = 0.914 m over 69–71 px, and the suited figure as 1.70 m over 129–131 px on a frame where it stands at rest.
- The two wrong runs sized the same 65–69 px pack as the life-support unit alone, 0.66 m. The figure then disagreed by 22–30 %. One run measured the figure on frame 243, the push-off, where its mask is 153 px against 126 px at rest around it (+21 %), and wrote "1.70 m reduced about 10 cm for the visible crouch" to make the two agree. The other measured the figure on frame 0, 3.4 s before the takeoff, where it stands nearer the camera (175 px against 129 px next to the jump). The fourth run searched a third reference until it ran out of time and mask checks.
- The same trap was seen in the ninth run (28.10): 0.66 m over 65 px and the figure over 152 px.

Rules:

- **R-S13. A size is used as quoted.** `size_m` is a number from the sources: one source's value (`mode: single`), the sum of the values of parts that are each quoted (`mode: sum`), or their mean (`mode: mean`). Never adjust a quoted size by an estimate: no "reduced for a crouch", no "about 10 cm less", no "priced in tolerance". If the thing in the frame is not in the quoted state (bent, stretched, tilted, partly hidden), measure it on another frame, or use another reference. *Enforced:* part 11 §44.
- **R-S14. Measure where the thing keeps its shape.** Measure a reference on a frame where its mask has the same length along the measured line as on the frames around it at rest: within 5 % of the median over the frames within ±1 s that lie outside every flight candidate (±0.3 s). A body that moves changes its height and its width at push-off, landing and in a stride; its standing height is read on a frame where it stands. *Enforced:* part 11 §44, §52 (owner addendum 2026-11-03: the length is read along the reference's own line, not only as height).
- **R-S15. A gap between references: check part and whole first.** When two references disagree (`REFERENCES_DISAGREE`, `THIRD_REFERENCE_REQUIRED`), first check each one for a part/whole mismatch before searching for a third:
  1. List the parts the mask and the measured line cover. Use the blind check's readings and a close crop with `view_frames`.
  2. When the mask covers more than the quoted thing (a unit mounted on top, a lid, a base, a stand, a handle), search the size of each part and use `mode: sum`, or shorten the line to the quoted part.
  3. When the mask covers less than the quoted thing, find the size of the part that is seen.
  4. Only then measure a third reference. Never change a size to close a gap (R-S13).
- **R-S11 (tightened).** When the reference's own mask is present on frames within 2 s before the first-check takeoff, it is measured there. A reason in `size_derivation.note` excuses a far frame only when the reference is not in the frames of that window.
- **Test:** `prompts/measuring_rules.md` contains R-S13, R-S14 and R-S15, and the tightened R-S11 sentence.

## Owner addendum (2026-11-02, from four runs after part 11 §49): the moving thing's own size first; every reference line is checked blind

The runs: Moon `20261102T133200Z-4cd1c236`, sped-up `20261102T133200Z-71613abb`.
- The Moon run measured the white pack as the life-support unit alone (0.66 m over 71 px) and a "suited figure width 0.82 m" along a diagonal line, (69, 105)–(148, 70), on frame 234. It never checked either line with `check_line`. The two wrong sizes agreed, and the verdict was "slowed down ×1.16" at g = 1.20 m/s².
- The sped-up run had one reference after 105 turns. Its 17 segmentations tried the helmet, the flag, the head and a small top unit, mostly on frames 130–134 next to the push-off at 136. It never measured the moving figure's own height on its rest frames.
- In every right run of the last four rounds, one reference was the moving thing's own height on a rest frame.

- **R-S16. The moving thing's own size first.** When the thing that moves has a quoted size (a body's standing height, a ball's diameter, a vehicle's length), it is one of the references. Measure it on a rest frame before the motion that keeps its shape (R-S14), along the dimension the source names. Then add things it wears or carries, or fixed things beside it (R-S6).
- **R-S17. Every reference line is checked blind.** Run `check_line` on each reference's line, with a claim that names the dimension ("height of …", "width of …"). A reference whose line has no agreeing check, or whose blind look says the dimension is unclear, cannot set the scale (part 11 §50).
- **Test:** `prompts/measuring_rules.md` contains R-S16 and R-S17, and still contains no rule that depends on the subject being a person.

## Owner addendum (2026-11-03, from four runs after part 11 §51): one thing is one reference; the moving thing is measured; candidate decisions use the listed words

The runs: sped-up `20261103T023347Z-258d5f07`, Moon `20261103T023347Z-bce08ba3` and `20261103T023347Z-e84d1289`.
- The sped-up run reported the backpack twice, on frames 96 and 128, as two references with the same quoted size from the same source. Two lines on one thing cannot show that its quoted size is wrong.
- In three of the four runs no reference was the moving thing. Each run measured only the backpack as the life-support unit alone (0.66 m), and two of them ended with one reference.
- Every run spent its first submit on a candidate decision word that is not allowed ("not_measured", "not_free_flight", "not_free").

- **R-S6b. One thing is one reference.** A second reference is a different thing with its own quoted size. Measuring the same thing again on another frame gives a check of the line, not a second reference (part 11 §53).
- **R-S16 (enforced).** A dry run without a reference on the moving thing returns a push (part 11 §53). Skip it only when the moving thing has no quoted size.
- **R-M6 (words).** Each candidate in `first_look.overview.candidates` has `decision` set to exactly one of `measured`, `not_a_flight` or `not_measurable`. `measured` names its `segment_id`; the other two carry a `reason`.
- **Test:** `prompts/measuring_rules.md` contains R-S6b, the R-S16 push sentence and the three decision words.

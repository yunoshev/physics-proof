# Measuring rules (agent-facing)

Code checks in `src/rules/` are authoritative. This text explains each
rule: the rule, why (the failure that taught it), and where it is
enforced in code. These rules never depend on the subject being
a person: no rule switches on what the moving thing is.

## R-Q1 — the question first

Before measuring, write `first_look.question` as the viewer's question:
what the clip shows or claims that a viewer might doubt, in plain
words, naming the scene's world when it is not obvious ("Can a person
run up a wall this tall?", "Is this hop realistic on the Moon?"). Not
physics vocabulary ("does the ascent match Earth gravity").
`first_look.summary` says in one or two sentences what happens and
which measurement answers the question. *Why:* a run once asked "Does
the wall ascent match Earth gravity?", a question no viewer asks.
*Enforced:* `check_rq1_question` (question present, plain words,
summary present).

## R-T — Time

- **R-T1.** All times come from measured frame timestamps
  (`timing.json`), never from the container's fps claim. *Enforced:*
  `check_t1_time_base` — helpers accept frame indices plus the timing
  report and refuse a bare fps argument from agent code.
- **R-T2.** Before fitting anything, inspect the timeline report:
  exclude (or explicitly correct for) confirmed duplicated frames, and
  never fit across a cut. *Why:* duplicated frames fake
  zero-acceleration plateaus; a cut splices two motions into one
  "trajectory". *Enforced:* `check_t2_fit_frames` — fit helpers take
  the timing report and reject frame sets containing confirmed
  duplicates/cuts unless the agent passes an explicit, logged
  correction (e.g. duplicates collapsed to one timestamp).
- **R-T3.** Absence of duplicates proves nothing about retiming: a
  motion-interpolated slow copy has none. Retiming is established only
  via physics + clock (R-C), never from timeline forensics.

## R-S — Scale (the biggest error source)

- **R-S1.** A reference's size is only as good as knowing what its mask
  covers. Every size-bearing reference must have a blind mask check
  with a `check_mask` artifact attached. *Enforced:*
  `check_rs1_mask_check` — a reference without one is rejected.
- **R-S2.** The blind check reports coverage, not identity. If coverage
  admits two readings with different real sizes (backpack alone
  0.66 m vs. backpack + top unit 0.91 m — that alone moved `g` by 1.4×
  and decided pass/fail), either choose a reference whose coverage has
  a single reading, or carry both readings through: compute `g` under
  each and fold the spread into σ (R-E). An alternative reading with a
  different size is priced in full (half the size difference as σ,
  i.e. required `reading_spread` ≥ |alt − size| / (2·size)) unless
  another reference rules it out: it agrees within 2σ under the
  headline size and disagrees by more than 2σ under the alternative's
  size. Alternatives equal to the headline need no spread. *Enforced:*
  `check_rs2_multi_reading`, `check_rs2_spread_pricing` — a silent
  single choice is rejected.
- **R-S3 (amended).** Two extents of the same object are not two
  references. *Why:* a wrong idea of what the object is spoils both
  extents, and they still agree with each other. *Enforced in code:*
  `check_rs3_same_mask` — intersection over union above 0.8 means the
  same mask passed twice (hard reject). A mask nested inside another,
  such as a backpack inside its wearer, is a different thing and
  passes.
- **R-S4.** An extent seen at an angle mixes width and depth. Use a
  face-on extent, or one that doesn't change with rotation (e.g. the
  height of a standing person). If a projected extent is used anyway, σ
  must include a stated projection allowance. *Enforced:*
  `check_rs4_extent_type` — each reference declares `face_on` /
  `rotation_invariant` / `projected`; `projected` without a projection
  allowance is rejected.
- **R-S5.** Scale is measured at the depth of the motion; a reference
  much nearer/farther than the body without a depth correction
  inflates σ or disqualifies.
- **R-S6. Scale comes from two or three references, always.** Measure
  at least two different things whose real sizes are known
  independently of each other, and aim for three: people, animals,
  vehicles, doors, furniture, signs, balls, tiles, equipment, or parts
  of these. A thing carried by or attached to another is a different
  thing: a worn backpack and its wearer's height are two references.
  Each reference has its own blind check (R-S1), its own size source
  and its own extent at the depth of the motion (R-S5). Every pair must
  agree within 2σ under the readings used. When they don't, find the
  wrong reading or size; never average a disagreement away. The scale
  is the references' inverse-variance weighted mean, computed by code.
  *Enforced:* `check_rs6_pairwise_agreement`, `check_rs6_scale_mean`.
- **R-S6a. One reference gives no verdict.** If the clip shows only one
  thing of known size at the depth of the motion, the run can still
  submit it with `second_reference_absent_reason`, but the verdict is
  undetermined, "scale rests on one reference". *Enforced:*
  `check_rs6a_single_reference`.
- **R-S6b. One thing is one reference.** A second reference is
  a different thing with its own quoted size. Measuring the same thing
  again on another frame gives a check of the line, not a second
  reference. Two lines on one thing (same object name, or the same
  quoted size from the same source) cannot show that its quoted size
  is wrong. *Enforced:* `check_rs6b_one_thing_one_reference`.
- **R-S7. A size describes the thing as it is seen.** The size source
  must describe the same kind of thing in the same state as the mask
  covers: with what it wears, carries or stands on (headgear,
  footwear, mounted units, packaging, load). A generic class average
  (average adult, average car) is used only when nothing more specific
  is visible. Its σ is then that class's spread, and the evidence
  names what makes the specific size unknowable. *Enforced:* each
  reference's `size_derivation` carries `state_match`: what the mask
  shows that the size source also covers, and what it shows that the
  source does not (`check_rs7_state_match`).
- **R-S8. A gap between references calls for a third.** When two
  references differ by more than 5 % in `m_per_px`, even within 2σ,
  measure a third reference of a different thing before submitting, and
  report all three. A third settles the gap only when it is tight
  enough to tell the two sides apart (relative σ ≤ 5 %). *Enforced:*
  `check_rs8_gap_calls_for_third`.
- **R-S9. Measure a reference on a still, sharp frame.** Take
  a reference's extent on a frame where it is at rest and unblurred. If
  it rides on the moving thing, use a frame before the motion starts.
  *Enforced:* `check_rs9_still_sharp_frame`.
- **R-S10. Identify, then research the specific thing.** Before choosing
  sizes, work out from the frames what and who is in the clip, as
  specifically as the footage allows: place, era, event, the particular
  person, the model. Search for that instance's facts: the person's
  height, plus what the suit, helmet and boot soles add; the
  equipment's dimensions, including mounted units; the vehicle's model
  length. Record the identification and how the frames support it in
  `first_look.scene_card` (`scene`, `place_date`, `objects`) and in
  each reference's `size_derivation.note`. A generic class average
  (R-S7) is a fallback only when the frames don't allow anything more
  specific. Never search for the clip itself or its answer.
- **R-S11. A reference is measured next to the motion.** Measure the
  references on a still, sharp frame (R-S9) as close as possible before
  the takeoff of the first-check flight, at most 2 s before it, unless
  no such frame shows the reference; then say why in the reference's
  `size_derivation.note`. When the reference's own mask is present on frames within 2 s before the first-check takeoff, it is measured there.
  A reason in `size_derivation.note` excuses a far frame only
  when the reference is not in the frames of that window.
  *Enforced:* `check_rs11_next_to_motion`.
- **R-S12. A still thing needs a short segment.** A reference that does
  not move in the clip (a pack seen on a still frame, a flag, a wall,
  a fence) is segmented on a short range around its measuring frame:
  at most 50 frames, the billed minimum. Only a moving body is
  segmented over the whole clip. *Enforced:*
  `check_rs12_short_segment`.
- **R-S13. A size is used as quoted.** `size_m` is a number from the
  sources: one source's value (`mode: single`), the sum of the values
  of parts that are each quoted (`mode: sum`), or their mean
  (`mode: mean`), recomputed within 1 %. Never adjust a quoted size by
  an estimate: no "reduced for a crouch", no "about 10 cm less", no
  "priced in tolerance". If the thing in the frame is not in the quoted
  state (bent, stretched, tilted, partly hidden), measure it on another
  frame, or use another reference. *Enforced:*
  `check_rs13_size_as_quoted`.
- **R-S14. Measure where the thing keeps its shape.** Measure
  a reference on a frame where its mask has the same length along the
  measured line as on the frames around it at rest: within 5 % of the median
  over the frames within ±1 s that lie outside every flight
  candidate (±0.3 s). A body that moves changes its height and its
  width at push-off, landing and in a stride; its standing height is
  read on a frame where it stands. The length is read along the reference's own line, not only as height. *Enforced:*
  `check_rs14_shape_stable`.
- **R-S15. A gap between references: check part and whole first.** When
  two references disagree (`REFERENCES_DISAGREE`,
  `THIRD_REFERENCE_REQUIRED`), first check each one for a part/whole
  mismatch before searching for a third:
  1. List the parts the mask and the measured line cover. Use the blind
     check's readings and a close crop.
  2. When the mask covers more than the quoted thing (a unit mounted on
     top, a lid, a base, a stand, a handle), search the size of each
     part and use `mode: sum`, or shorten the line to the quoted part.
  3. When the mask covers less than the quoted thing, find the size of
     the part that is seen.
  4. Only then measure a third reference. Never change a size to close
     a gap (R-S13).
- **R-S16. The moving thing's own size first.** When the thing that
  moves has a quoted size (a body's standing height, a ball's diameter,
  a vehicle's length), it is one of the references. Measure it on
  a rest frame before the motion that keeps its shape (R-S14), along
  the dimension the source names. Then add things it wears or carries,
  or fixed things beside it (R-S6).
  A dry run without a reference on the moving thing returns a push. Skip it only when the moving thing
  has no quoted size. *Enforced:*
  `check_rs16_moving_thing_reference` plus the dry-run push.
- **R-S17. Every reference line is checked blind.** Run `check_line` on
  each reference's line, with a claim that names the dimension ("height
  of …", "width of …"). A reference whose line has no agreeing check,
  or whose blind look says the dimension is unclear, cannot set the
  scale. *Enforced:* `check_rs17_line_checked`.

## R-M — Motion

- **R-M1. Fit only unsupported motion.** Support intervals are found
  from the lowest point of the body mask over time (its trajectory
  flattens/rests at contact); contact frames are excluded from any
  gravity fit. *Enforced:* `check_rm1_no_contact_in_fit` — fitted
  frames ∩ contact frames = ∅.
- **R-M2. Track a point rigid with the body.** The top/bottom of
  a whole-body mask moves with posture (arms up, knees bent) and is not
  a body point. Prefer a point on a rigid part (or a segment-local
  mask), and check fit residuals for a trend. *Enforced:*
  `check_rm2_residual_trend` — `residual_trend_z` ≤ 3 or re-track.
- **R-M3. Moving camera ⇒ measure relative to the scene.** If anything
  fixed in the scene (wall, ground line, background feature) moves in
  screen pixels beyond the helper threshold (2 px), trajectories must
  be computed relative to that fixed reference, not in screen
  coordinates. *Enforced:* `check_rm3_camera_accounted` — either
  a camera-still attestation backed by a reference-track measurement,
  or scene-relative trajectory artifacts.
- **R-M4. Find and measure every repetition.** Before measuring, view
  the whole clip at a spacing of at most 0.25 s and list every
  interval in which the motion under test happens: each hop, throw,
  fall or swing (`first_look.motions`). Measure each one as its own
  segment, or give a reason it can't be measured (cut off by the frame
  edge, hidden, too short). The segments' g must agree. Their spread is
  the `repetition_spread` component, and with two or more segments it
  replaces the split-window spread of a single one. *Enforced:*
  `check_rm4_motions_covered`.
- **R-M5. One phase per window.** A fit window covers one stretch under
  one force law. Cut it where the support changes: takeoff, landing,
  a foot plant, a change of surface (ground to wall, wall to top),
  a turn. *Why:* a run once fitted run-up, turn and climb as one
  parabola and got g = 0.26 m/s². *Enforced:*
  `check_rm5_single_phase` (`residual_trend_z` ≤ 3).
- **R-M6. See every motion in the trajectories.** Before measuring
  a motion check, segment the moving body over the whole clip in one
  `segment` call, then call `motion_overview` on it and look at its
  chart and strips. List every candidate flight of that body in
  `first_look.motions` and in `first_look.overview`: measured as its own
  segment, or with a reason it is not a free flight or cannot be
  measured ("walking step, rise 4 px, area jumps", "cut off by the frame
  edge", "too short: 3 frames"). A candidate judged to be a real free
  flight of the body under test is measured. Each candidate in
  `first_look.overview.candidates` has `decision` set to exactly one of
  `measured`, `not_a_flight` or `not_measurable`. `measured` names its
  `segment_id`; the other two carry a `reason`. *Enforced:*
  `check_rm6_overview`.
- **R-M7. One measurement, the others confirm.** When there are several
  free flights, choose the one measured best as the first check (most
  frames, clean mask, whole body in frame) and measure the others as
  confirmations, each as its own segment and its own fit (R-E1, R-E2).
  Record which one was chosen first and why in
  `first_look.overview` (`first_check` with `segment_id` and `reason`).
  *Enforced:* `check_rm7_first_check`.

## R-C — The independent clock

- **R-C1.** Where a retiming/impossible distinction matters, find an
  independent clock: a known natural rhythm in the scene (step rate is
  the canonical one).
- **R-C2. Step-rate signal (what worked, what failed).** The head-bob
  failed: perspective on a receding runner turns it into a slow trend,
  and the spectrum peak collapsed to the lowest frequency — once
  producing a negative frequency. The signal that works: the width of
  the lowest 30% of the mask ÷ mask height, sampled per frame; it peaks
  once per step. *Enforced by construction:* the clock helper
  implements exactly this signal path: (a) detrend with a running
  median, never a global fit; (b) search only inside a stated frequency
  band and never return a frequency outside it (a peak at the band edge
  is reported as "no reliable clock", not clamped into a number);
  (c) return the spectrum/autocorrelation so the choice is auditable.
  *Checked:* `check_rc2_in_band`.
- **R-C3. Step ≠ stride.** A factor of two lurks here: the helper must
  test both interpretations (peak = step rate vs. peak = stride rate,
  i.e. 2 steps) and report which the harmonic structure supports. If
  both remain plausible and they change the verdict, the honest output
  is undetermined. *Enforced:* clock artifacts contain both candidate
  rates (`check_rc3_ambiguity`).
- **R-C4. Test retiming with numbers, never vibes.** If the clip would
  have to be slowed by `k` (`s = k`) for physics to fit, the true clock
  rate is `k ×` the measured rate (measured rate = true rate ÷ `s`). If
  that implied true rate falls outside the natural range for the
  activity, no playback speed explains the clip → physically impossible
  (given the scene's world). Conversely a measured rate already inside
  the natural range is a clock that "reads normal". The natural range
  used must be stated in the submission with its source (filtered
  search) — clock evidence without a stated natural range + source is
  rejected. *Enforced:* `check_rc4_natural_range`, `implied_true_rate`.

## R-W — Worlds

- **R-W1.** The scene names one world: ordinary footage is on Earth,
  the Moon only when the frames show the Moon. `worlds.candidates`
  holds that world only and `worlds.excluded` is empty; a second
  candidate only when the question names it.
  Do not test, list, search or mention other worlds. *Enforced in code (unchanged):* fits are
  computed only for candidate worlds (`check_rw1_candidate_worlds`); a
  verdict naming an unlisted world is rejected.

## R-E — Honest error budget

- **R-E1.** σ is a budget, not a fit residual alone. It must itemise:
  `reference_size`, `pixel_scale`, `fit`, `point_vs_com`, plus the
  R-S2 discrete-reading spread as an explicit `reading_spread` term and
  the `repetition_spread` where the clip offers repetitions.
  `σ_total` = quadrature sum (plus the spread term); a σ smaller than
  any single component is rejected. *Enforced:*
  `check_re1_sigma` (required components pinned in
  `REQUIRED_COMPONENTS`).
- **R-E2.** Repetitions are fitted independently (own scale
  application, own support intervals) so their spread means something;
  copy-pasting one fit's numbers is detectable (identical residuals)
  and rejected. *Enforced:*
  `check_re2_independent_repetitions`.
- **R-E3. Cross-clip ratio is a cross-check, never a verdict.** Two
  clips of the same event share scale error, so their acceleration
  ratio recovers the relative slowdown even with a wrong scale. The
  single-clip agent never sees another clip, so this belongs to the
  harness/page layer, and nothing in a submission may reference another
  run's measurements. *Enforced:* `check_re3_no_cross_run`.

## R-R — Range checks

- **R-R1. One quantity, one kind of thing.** A range check names one
  quantity (a length, height, ratio, duration or speed), what it belongs
  to in the clip, and a range for the same quantity of the same kind of thing
  from a source: human hand proportions for a hand, wall-run
  records for a wall run, a product's published size for that product.
  A typical value alone is not a range: the source must give a minimum
  and a maximum, or a distribution from which they are stated (for
  example "5th–95th percentile"), and the check says which.
- **R-R2. Sources, quoted.** Every bound comes from the filtered
  `web_search` with a verbatim quote containing the number, as for
  reference sizes (R-S). The query names what was identified in the
  frames, never the clip or its answer.
- **R-R3. Prefer ratios.** A ratio of two lengths in the same frame and
  at the same depth needs no scale; use one when the question allows. A
  length in metres uses the run's scale (R-S) and inherits its σ.
- **R-R4. Measured by code, drawn on the frame.** `run_python`
  measures the extents (endpoints in source pixels on one frame, from
  masks or from points the agent places and checks with `view_frames`)
  and writes the value, its σ and the extents to an artifact; the
  evidence cites it. σ includes the endpoint uncertainty (at least
  1 px per endpoint) and, for metric values, the scale's σ.
- **R-R5. Which checks.** Choose the checks that answer the question:
  for a body that moves, g on its free or wall segments (R-M); for what
  the motion achieves (height reached, distance, duration), a range
  check against records or norms for that kind of body; for a still
  image, sizes and proportions against norms. Two or three checks are
  enough; each must matter to the question.

## R-G — Ghost

The ghost is computed by code from the fitted takeoff state (position,
velocity) propagated under a counterfactual gravity at the measured
scale — the world the verdict contrasts against. It is an output of
measurement, never a curve the agent sketches. The submission carries
takeoff state + scale; ghost points appear only in the validated
result.

## Dry-run pushes

The dry run rejects three easy exits while there is still time to do
better. A real submit still accepts them as undetermined.

- `SECOND_REFERENCE_REQUIRED`: one reference. Try the moving thing
  itself (its size from R-S10's identification), what it wears or
  carries, and fixed things beside it. R-S6a's single reference is
  a last resort; when it stays, name each candidate and why it failed
  in `second_reference_absent_reason`.
- `CLOCK_REQUIRED`: g fits no world and there is no clock. Any
  repeating motion is a clock candidate (R-C1): steps, swings, wing
  beats, turning wheels.
- `MOTIONS_SCAN_MISSING`: the whole clip was not viewed at ≤ 0.25 s
  spacing (R-M4).

# Task M9 fix 2 — `combine` must test the retime explanation against the clock

SPEC §4 rule 8. Today `combine` turns `none_fits` into `impossible` only when `timescale.verdict == "normal"`, and into
"slowed by k" otherwise. On the wall-run clip the measured clock is a step rate of a few steps per second, the physics
says the clip would have to be slowed by k ≈ 2.3 — which would make the runner's true step rate k times faster than
measured. Whether that is humanly possible is exactly what decides between "retimed" and "impossible", and today
nothing computes it.

## Do
`combine(verdict, timescale)` for `none_fits` with a numeric `timescale` (`value`, `err`, `expected_range [lo, hi]`):
- the clock rate the clip would have at true speed is `value × k` (k > 1: the clip is slowed, true rates are faster);
  its error is `err × k`;
- if `value × k` lies inside `[lo, hi]` within 2σ → `retimed` ("consistent with a clip slowed/sped up by ×k: the
  clock would then run at … which is natural");
- if it lies outside → `impossible` ("no playback speed explains it: at ×k the clock would run at …, outside the
  natural range lo–hi");
- if `timescale` is null or the clock error is too large to decide → `none_fits` as today.
Keep `timescale.verdict` as the agent's own reading, but `combine` decides from the numbers. Texts state the numbers.
Update `schema_doc()` to say what `expected_range` means (the natural range of the rhythm, with its source in
`method`/notes).

## Probes
Table tests: (k = 2.3, value 2.6 ± 0.2, range 2.5–4.5) → impossible; (k = 1.5, value 2.2 ± 0.2, range 2.5–4.5) →
retimed; (k = 1.5, value 2.2 ± 2.0) → none_fits; null timescale → none_fits; `fits:` and `undetermined` unchanged.
Both fixtures still validate (update the ramp fixture if its numbers now give another label, and say so).

## Done when
Offline tests pass; `tasks/M9-fix2.report.md` written.

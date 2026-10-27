# Task M6c — a clock check that works on a real run-up

SPEC §4 rule 8 (check the clock independently). In the wall-run run (`runs/2026-10-27-wallrun-r2`) the agent measured
the run-up step rate from the bob of the runner's mask top with `step_rate` and got 1.03 ± 0.17 Hz. Frame-by-frame
viewing by the maintainer shows a step every ~6–7 frames at 24 fps (≈ 3.5–4 steps/s, ordinary running). So the clock
check said "undetermined" and the verdict became "slowed ×2.3" instead of "impossible". The maintainer reproduced it on
SAM masks of the run-up (frames 10–71, camera moving forward, runner receding):

- `step_rate(top_y / height)` → `{'hz': -0.71, 'period_frames': inf, 'peak_ratio': 21.8}` — a **negative frequency**:
  the peak sits at the lowest bin (the perspective trend), and the peak interpolation runs off the edge;
- leg spread (width of the lowest 30 % of the mask / mask height) → 2.57 ± 0.19 Hz, `peak_ratio` 3.0 — the right
  neighbourhood, but a weak peak.

## Do
1. Fix `step_rate`: never return a frequency outside `[min_hz, max_hz]`; when the strongest power is at an edge bin,
   say so (`edge: true`) and report the best interior peak instead. Detrend with a high-pass that removes a slowly
   changing perspective (e.g. subtract a running median over ~1 s) rather than only a quadratic; keep the old behaviour
   available by a parameter.
2. Add `gait_signal(obj_masks, *, band=0.3)` → per-frame leg spread of one person's mask (width of the lowest `band`
   of the mask divided by the mask height; `nan` where missing), with a docstring that says it peaks once per step and
   is insensitive to a receding runner and a panning camera. Document in `step_rate` which signal to use for people.
3. Tests: synthetic stick-figure masks walking at 3.5 steps/s while shrinking 2× (receding) and panning → `gait_signal`
   + `step_rate` give 3.5 within the reported error; a pure trend gives `edge: true` and no negative/inf values; old
   M6b tests still pass.

## Done when
Offline tests pass; `tasks/M6c.report.md` written. The maintainer reruns the run-up check on the real masks.

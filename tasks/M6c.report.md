# M6c report — a clock check that works on a real run-up

## Built
- `physics_proof/blocks.py`: fixed `step_rate`, added `gait_signal`, both in
  `__all__`; root `blocks.py` shim re-exports `gait_signal`.
- `tests/test_blocks_m6c.py`: 9 new offline tests (walker at 3.5 steps/s,
  trend edge cases, old-detrend parity, `gait_signal` errors).

## How each probe is covered
1. `step_rate` never leaves `[min_hz, max_hz]`: hz is clipped to the band and the
   parabolic shift clamped to ±0.5 bin; `period_frames = fps / hz` is always
   finite positive. Covered by `test_step_rate_hz_never_leaves_band` (drift +
   tone, random walk, both detrends).
2. Edge bins: strongest in-band power at an edge bin returns `edge: True` and the
   best interior peak's hz instead. Pure ramp/perspective/constant trends give
   `edge: True` with finite in-band hz (`test_step_rate_pure_trend_edge`).
3. High-pass detrend: default `detrend="median"` subtracts a running median over
   ~1 s (`scipy.ndimage.median_filter`, odd window of `round(fps)` samples) plus
   the residual mean; `detrend="quadratic"` keeps the exact old path
   (`test_step_rate_quadratic_detrend_kept`, incl. the M6b 3.2 Hz sine).
4. `gait_signal(obj_masks, *, band=0.3)`: union width of the lowest `band` of
   the mask / mask height, `nan` where empty. Docstring states once-per-step
   peaking and insensitivity to receding/panning; `step_rate` docstring says to
   use it for people instead of the mask-top row (`test_gait_signal_errors`).
5. Synthetic walker: scissoring stick figure at 3.5 steps/s shrinking 2x and
   panning, n=96 and n=62 (the run-up length) → 3.5 within `hz_err`,
   `edge: False`, `peak_ratio` > 10; receding vs fixed-scale gaits correlate
   > 0.9 (`test_gait_receding_pan_*`, `test_gait_scale_invariant`).
6. Old M6b tests still pass unchanged (11/11 in this run).

## Test output
- `tests/test_blocks_m6c.py` + `tests/test_blocks_m6b.py`: 20 passed.
- Full offline suite: 219 passed, 23 skipped (API-gated), ~40 s.

## Could not do / open questions
- Nothing outstanding: the maintainer reruns the run-up check on the real SAM
  masks (frames 10–71). Expectation: `gait_signal` + `step_rate` ≈ 2.5–3 Hz
  with `edge: False`; the old `top_y / height` path now reports `edge: True`.
- `step_rate` still raises on `nan` input; callers must drop empty-mask frames
  from `gait_signal` output first (documented in the docstring flow).

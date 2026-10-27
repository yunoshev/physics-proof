# M6b report — blocks for moving cameras and time scale

## Built
- `physics_proof/blocks.py` (+~230 lines): `relative_track` (target rows or
  `mask_stats` output vs a static mask: anchor top/bottom row, size
  `width_at` on `top + offset × height` or `height`; returns frames, value
  in reference sizes, `size_px`, zoom min/max/ratio; nan where missing),
  `step_rate` (quadratic detrend, Hann, periodogram; parabolic peak
  refinement, `hz_err` = half a DFT bin, `peak_ratio` = peak/median power,
  `ValueError` when fewer than 2 periods fit), `ghost`
  (`y0 + v0 t + a t²/2`, `t` from `frames[0]`).
- `decide`: new branch — `none_fits` with `g <= 0` keeps `k = None` and the
  text says "no playback speed explains the motion"; all other texts kept.
- `to_metres`: `g_px == 0` returns `(0.0, g_px_err / px_per_m)`, no div0.
- Root `blocks.py` shim re-exports the 3 new names (17 total).
- `tests/test_blocks_m6b.py`: 11 tests, fixed seeds, no API calls.

## Probes
1. Synthetic pan (+200 px) + zoom (1.3×) over wall + parabola (a = 2.0
   widths/s²): `relative_track` + `fit_parabola` gives 1.99999 (err 7e-6);
   zoom ratio 1.3; mask_stats-target mode also within 2 %.
2. 3.2 Hz sine + σ=0.3 noise, 24 fps, 2.5 s: hz = 3.19 ± 0.20 (covers 3.2,
   err < 0.3); `peak_ratio` 154 vs 3.0 for pure noise.
3. `ghost` matches the formula at 5 points; `a = 0` gives [1, 3, 5, 7].
4. g = 0.0 / −1.0 ± 0.5 vs `{"unsupported on Earth": 9.81}` → `none_fits`,
   k `None`, "no playback speed" (single sentence); 9.5 ± 0.5 → fits;
   old `decide` table (12 cases + boundary) still passes unchanged.
5. `to_metres(0.0, 0.2, 10.0, 0.5)` → `(0.0, 0.02)`.

## Test output
- `uv run pytest tests/test_blocks_m6b.py tests/test_blocks.py`: 48 passed.
- `uv run pytest` (full offline): 124 passed, 17 skipped (api/slow/macOS
  sandbox opt-outs, all pre-existing).

## Could not do (and why)
- Nothing missing. Existing function behaviour is unchanged (only the
  `g <= 0` `none_fits` text and the `g_px == 0` branch are new paths).

## Open questions
- The task's "below every hypothesis by more than k_sigma" clause also
  describes old case 3 (0.72 ± 0.05), which must keep its slow-clip text, so
  the new text is gated on `g <= 0` only — the two coincide for every
  wall-run probe. Say if a small-positive-g far below a hypothesis should
  also say "no playback speed" (it is explainable by slowdown today).

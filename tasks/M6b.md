# Task M6b — blocks for moving cameras and time scale

Spec: `SPEC.md` §1 "Second case: a viral wall run" and §3 "M6b". Extend `physics_proof/blocks.py` (keep every existing
function and test unchanged in behaviour); same style: docstrings state argument shapes and units, clear `TypeError` /
`ValueError` messages, no numpy errors leaking out.

Why: in the second case the phone camera pans and zooms while a runner climbs a vertical wall. To measure the runner's
vertical acceleration we need positions in a frame attached to the wall, a way to tell whether time in the clip runs
normally, and a predicted path to draw on the page.

## Build
1. `relative_track(target, reference, *, anchor="top", size="width_at", size_row_offset=0.1)`
   - `target`: list of per-frame point values (px rows, `None` allowed) or the output of `mask_stats` (then the centroid
     row is used; allow `point="centroid"|"top"|"bottom"`).
   - `reference`: a single-object mask array `[N, H, W]` of a static object (e.g. the wall), same frames.
   - Per frame: anchor row of the reference (`top` = first mask row, `bottom` = last), size = reference width measured
     on the row `top + size_row_offset × height` (the straight upper part of a tall object), or `size="height"`.
   - Returns dict: `frames`, `value` (target − anchor) / size per frame (reference sizes; `nan` where missing), `size_px`
     per frame, and a `zoom` summary (min/max of `size_px`) so the page can say how much the camera zoomed.
2. `step_rate(series, fps, *, min_hz=1.0, max_hz=8.0)` — detrend (subtract a quadratic), Hann window, periodogram;
   returns `{hz, hz_err, period_frames, n, peak_ratio}` where `hz_err` comes from the peak width (or a parabolic
   interpolation of the peak) and `peak_ratio` is the peak power over the median power (low = no clear rhythm).
   Needs at least 2 periods inside the series; otherwise `ValueError` with the reason.
3. `ghost(y0, v0, a, frames, fps)` — positions `y0 + v0 t + a t² / 2`, `t = (frame − frames[0]) / fps`, same units as
   `y0`; returns a list of floats.
4. `decide`: accepts any mapping of hypothesis names to accelerations (already does — keep it) and when the measured
   downward acceleration is ≤ 0, or below every hypothesis by more than `k_sigma`, the text says plainly that **no
   playback speed explains the motion** (k is `None` when g ≤ 0). Keep the existing texts for the other cases.
5. `to_metres`: must not divide by zero when `g_px == 0` (return `g = 0`, `g_err = g_px_err / px_per_m`).

## Probes (tests, offline)
1. Synthetic camera: a static "wall" rectangle and a point on a parabola with known acceleration in wall widths;
   the camera pans up 200 px and zooms 1.3× over the clip; `relative_track` + `fit_parabola` recover the acceleration
   within 2 %.
2. `step_rate` on `sin(2π·3.2·t)` + noise (σ = 0.3 of amplitude) at 24 fps over 2.5 s: 3.2 within `hz_err`, and
   `hz_err` < 0.3; pure noise gives `peak_ratio` < the value for the sine.
3. `ghost` equals the formula at 5 points; `ghost(…)` with `a = 0` is a straight line.
4. `decide` table: g = 0.0 ± 0.5 vs `{"unsupported on Earth": 9.81}` → `none_fits`, k `None`, text contains "no
   playback speed"; g = −1.0 ± 0.5 → same; g = 9.5 ± 0.5 → `fits:unsupported on Earth`; old 12 cases unchanged.
5. `to_metres(0.0, 0.2, 10.0, 0.5)` → `(0.0, 0.02)`.

## Done when
Offline tests pass (old and new); `tasks/M6b.report.md` written.

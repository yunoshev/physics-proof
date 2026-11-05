# 09 — Verified Helper Library

**Owns:** `src/helpers/` and its tests. **Small-code principle:** this library is deliberately tiny — a handful of pure functions over numpy arrays, each tested on synthetic data with a known answer. Spark imports these instead of re-deriving physics in ad-hoc code. If a function isn't needed by a lesson or a rule in part 08, it doesn't exist.

## 1. Shape

Four modules, no classes, no model calls, no network, no state:

| Module | Contents |
|---|---|
| `helpers/masks_io.py` | Save/load masks; clip facts; read chosen frames. |
| `helpers/tracks.py` | Mask statistics; largest connected piece; mask → tracked point; track quality flags; relative tracks. |
| `helpers/physics.py` | Parabola fit; scale; track → metres; world fit / retime factor; ghost. |
| `helpers/clock.py` | Gait signal; step-rate clock. |

Conventions:

- Functions take arrays and plain values, return plain values/dicts. Uncertainties are always `(value, sigma)` pairs, never bare numbers where an error is meaningful.
- Image coordinates: `y` grows downward in pixels; physics functions work in metres with `y` up. The conversion happens in exactly one place (`physics.track_to_metres`) so sign errors have one home.
- Time is always seconds from measured timestamps (part 05). No helper accepts a container fps.
- Helpers raise `ValueError` with a short machine-readable message (`"peak_at_band_edge"`, `"empty_mask"`). They never return plausible-looking garbage.

## 2. The functions

### masks_io

- `save_masks(path, masks)` / `load_masks(path)` — masks as `{object_id: {frame_index: bool array}}`, stored as one compressed `.npz` (SAM returns masks compressed per frame; this is the single decode/re-encode point). Round-trip must be lossless.
- `clip_facts(timing_path)` — frame count, measured fps, timestamps array, duplicate runs, cut indices. The only sanctioned way for agent code to learn timing (enforces R-T1).
- `read_frames(video_path, indices)` — decoded frames as arrays, in the order requested.

### tracks

- `mask_stats(mask)` — top, bottom, left, right, centroid, height, width, area for one frame's mask.
- `largest_component(mask)` — keep the largest connected piece (OpenCV connected components; a stray blob must not move the "bottom of the body").
- `track_point(masks, mode)` — per-frame track of a chosen point. `mode` ∈ {`centroid`, `bottom_centre`, `top_centre`, `lowest_point`}; the mode is recorded, because part 08 R-M2 cares *which* point was tracked. Returns `{frame, t, x_px, y_px}` rows.
- `track_quality(track, masks_by_object)` — flags, each a simple test:
  - **gaps:** frames missing between first and last;
  - **jumps:** frame-to-frame displacement above a threshold (in mask-heights per frame);
  - **splits:** second-largest component > 25% of the largest (posture split or a second object bleeding in);
  - **identity swaps:** with multiple objects, frame-to-frame IoU of object *i* drops while its IoU with object *j*'s previous mask rises. SAM object ids are unstable when objects overlap — this flag exists because of that, and a flagged segment must be re-tracked or excluded, not trusted.
- `relative_track(track_a, track_b)` — A's positions minus B's, aligned on common frames (wall-run: runner relative to a track fixed on the wall; enforces R-M3 mechanically).

### physics

- `fit_parabola(t, y_m)` — least squares `y = y0 + v0·t + ½·a·t²` with: `a` (hence `g_app = |a|`), σ from residuals with honest degrees of freedom, the residual series, and a **residual trend statistic** (slope of residuals vs. t, normalised). A large trend is the signature of a non-rigid tracked point (R-M2) and is returned, never hidden.
- `scale_from_reference(extent_px, extent_px_sigma, size_m, size_m_sigma)` → `(m_per_px, sigma)` by standard propagation.
- `track_to_metres(track, m_per_px, origin)` — pixel track → metres, flipping y, applying scale; errors carried as a single scale-relative term (per-point pixel noise is the fit's job).
- `worlds_fit(g_app, sigma, candidate_worlds)` — for each candidate `{name: g}`: fits at native speed (|Δ| ≤ 2σ test, part 02 §4), and if none fits, the retime factor `s = sqrt(g_world / g_app)` per candidate. Pure arithmetic over the candidate list it is given — it contains no scene judgement (R-W1 lives in validation, part 11).
- `ghost(takeoff_state, g_ghost, m_per_px, t_grid)` — propagate `{x0, y0, vx, vy}` under `g_ghost`, return the path and the landing point/time where it returns to takeoff height. (Part 11 decides *which* gravity the ghost uses; this just integrates.)

### clock

- `gait_signal(masks)` — per frame: width of the **lowest 30% of the mask rows** ÷ mask height. This is the signal that worked; head-bob is not implemented anywhere in the library (R-C2).
- `step_rate(signal, t, band_hz)` — detrend with a **running median** (window from config, odd, ~1 s), then a simple periodogram/FFT peak search **strictly inside** `band_hz`. If the peak sits at a band edge, return `None` with flag `"no_reliable_clock"` — a frequency outside the band is never returned, and an edge peak is never clamped into a number (the negative-frequency failure is designed out). Returns both interpretations explicitly: `as_step_hz` and `as_stride_hz` (= peak/2 as step rate, ×2 the other way), with the harmonic evidence for each, so R-C3's ambiguity is data, not a silent choice.

## 3. Synthetic tests (the library's licence to exist)

Every function ships with a test on synthetic data with a known answer, in `tests/helpers/`:

- synthetic masks of a rectangle in exact parabolic motion → track → metres → fit recovers the planted `g` within the quoted σ;
- a planted scale (known metres-per-pixel) is recovered; σ covers the planted error;
- a synthetic gait signal (width oscillation at a planted rate, plus a slow perspective trend) → the clock returns the planted rate, detrended, in-band; a signal whose peak is at the band edge returns `no_reliable_clock`;
- ghost from a known takeoff state lands at the analytic landing point;
- masks save/load round-trips exactly; duplicate/cut facts match a planted timing report.

Helpers are "verified" only while these tests pass. A helper that fails its test is removed from the importable set by the loop (part 06), not patched in place mid-run.

## 4. Documentation cannot drift from code

The helper documentation the agent sees is **generated from the helpers' own docstrings** (`src/helpers/gen_docs.py` → a generated file the loop injects, marked do-not-edit). Regenerating docs and getting a diff fails the build (wired in part 15). The prompt therefore never describes a helper that doesn't exist or a signature that changed.

## 5. Explicitly not in the library

No segmentation, no vision, no search, no verdict logic beyond the arithmetic of `worlds_fit`, no plotting beyond what a test needs. Anything else Spark needs, it builds under part 10 — with the same synthetic-test bar.

## 6. Owner addendum (2026-10-28, from the second wall run): a residual trend that can be non-zero

Seen: wall run 2 fitted one parabola over frames 55–180, which take in the level run-up, the turn and the climb. It got g = 0.26 ± 0.09 m/s², with `residual_trend` = 3.9 × 10⁻¹⁵. That statistic is zero by construction. Least-squares residuals are orthogonal to every column of the design, and `t` is one of those columns. So the check that R-M2 relies on can never fire.

- `fit_parabola` returns two new statistics, both computed on the same points as the fit:
  - **`residual_trend`:** the correlation between the residuals and the centred cubic term (t − t̄)³ made orthogonal to the design columns (1, t, t²), that is, the partial correlation of a cubic term.
  - **`residual_trend_z`:** the |t| statistic of the cubic coefficient `j` in the fit y = y0 + v0·t + ½·a·t² + j·t³.
- A `residual_trend_z` above 3 means the window is not one stretch of constant acceleration: it mixes phases (support, a change of surface, a turn) or the tracked point deforms. The docstring and the generated docs say so.
- **Tests:**
  - a noisy parabola (noise σ = 1 % of its rise) gives `residual_trend_z` < 3 in at least 95 of 100 seeds;
  - 30 points of level motion followed by 30 points of a parabola (continuous at the join, noise σ = 1 % of the rise) give `residual_trend_z` > 3 and |`residual_trend`| > 0.3;
  - `residual_trend` differs from the Pearson correlation of the residuals with `t`, which stays near zero.

Breaks on purpose: `tests/validate/test_validate_fixture.py` — the run-7 fixture stores the fit's statistics, so it changes with this section, and part 11 rebuilds it next (part 11 §16).

## 7. Owner addendum (2026-10-30, from wall runs 7–10 and hand runs 1–4): range checks and the clock built by the library

Seen: in eight live runs the agent measured the right things but lost its run to bookkeeping in the evidence.
- It typed in extent endpoints that were not on the measured object (hand run 2).
- It printed a value but not the endpoints (`RANGE_NUMBER_WITHOUT_PROVENANCE`).
- Its value did not recompute from its extents (`RANGE_FORMULA_MISMATCH`).
- Its σ was below the endpoint uncertainty (`RANGE_SIGMA_TOO_SMALL`).
- It wrote the clock range as `{min, max}` instead of `[lo, hi]` (wall runs 9 and 10).

Part 11 checks all of these, and the library makes the right numbers the easy ones. A fifth module, `helpers/ranges.py`, joins the table in §1, plus one function in `helpers/clock.py`. All are pure, with no model calls and no I/O except printing:

- `ranges.mask_extent(mask, direction=None)`:
  - returns `{x1, y1, x2, y2, length_px}` for the two mask pixels farthest apart along `direction`;
  - `direction` is a unit vector `(dx, dy)` in image coordinates, such as `(0, 1)` for vertical. With `None`, the mask's principal axis is used;
  - both endpoints are mask pixels, so they lie on the mask by construction (part 11 `RANGE_EXTENT_NOT_ON_MASK`), and `length_px` is their Euclidean distance;
  - an empty mask raises `ValueError` with a plain message.
- `ranges.range_value(kind, extents, m_per_px=None, m_per_px_sigma=None)`:
  - returns `{value, sigma, formula, uses_scale}`, computed exactly as part 11 §20 recomputes them;
  - `kind="ratio"` takes two extents: `value = extents[0].length_px / extents[1].length_px`, `formula = "<name0>_px / <name1>_px"`;
  - `kind="length"` takes one extent and the scale: `value = length_px × m_per_px`, `formula = "length_px × m_per_px"`;
  - σ propagates 1 px per endpoint, plus the scale's σ for a length. It is never below what part 11's `RANGE_SIGMA_TOO_SMALL` demands.
- `ranges.print_check(item)`: prints the item as one JSON line with every number, endpoints included. The `run_python` call that prints it is the check's `measurement_artifact`, so every number the evidence cites is in that artifact (part 11 `RANGE_NUMBER_WITHOUT_PROVENANCE`).
- `clock.clock_evidence(rate, signal_description, interpretation, natural_range_hz, natural_range_source, band_hz, window_frames, method)`:
  - returns the evidence `clock` object in the contract's shape (part 12), with `natural_range_hz` as `[lo, hi]`;
  - it also accepts `{min, max}` and converts it, and raises on a missing field with that field's name;
  - `rate` is `step_rate`'s result.

**Tests (synthetic):**
- `mask_extent` on a filled rectangle gives its corners along the axis, and on a disc its diameter within 1 px; the endpoints are mask pixels.
- `range_value("ratio", …)` and `range_value("length", …)` match part 11's recompute on the same inputs, and their σ passes part 11's floor. The test imports part 11's recompute and floor rather than restating them.
- `clock_evidence` with `{min, max}` returns `[lo, hi]`, and its output validates against part 12's schema for `clock`.
- The generated helper docs list the new functions (§4).

## 8. Owner addendum (2026-10-31, from Moon run 22): a ghost lands at the clip's landing level

Seen: in Moon run 22 the astronaut lands 0.19 m below the point where he took off. `ghost` ends every world's path where it returns to takeoff height, so the Moon path lands after 0.75 s while the real flight lasts 1.03 s. The page then looks as if the Moon does not fit, although the measured g = 1.59 m/s² matches the Moon's 1.62.

- `ghost(takeoff_state, g_ghost, m_per_px, t_grid, land_y_m=0.0)`: the landing is where the path, after its peak, reaches the height `land_y_m`, in metres relative to the takeoff point with y up. A landing below takeoff gives a negative `land_y_m`.
- `t_land = (vy + sqrt(vy² − 2·g·land_y_m)) / g`. With `land_y_m = 0` this is today's `2·vy/g`, so every existing call keeps its result. The path is sampled on the grid up to `t_land`, and the exact landing point is appended as before.
- When the path peaks below `land_y_m` (`vy² < 2·g·land_y_m`), the landing falls back to the return to takeoff height.
- **Tests:**
  - `vy = 0.61`, `g = 1.62`, `land_y_m = −0.19` gives `t_land ≈ 0.99 s`, and the path's last point has `y_m = −0.19`;
  - `land_y_m = 0` gives the same result as before;
  - a `land_y_m` above the peak falls back to `2·vy/g`.

## 9. Owner addendum (2026-11-04, from street-jump runs 78 and 80): a still-camera track that does not follow the mover

Seen: on a handheld street-jump clip, the agent tracked its scene reference by hand with a template next to the jumper (a pole behind him, a far corner the car passes). The template followed whatever crossed it, so the "fixed" point moved 36–42 px and part 11's V8 rejected `camera.still` (`CAMERA_UNACCOUNTED`). Run 81 then showed that the camera itself pans about 30 px during the jump, so the run needs a scene-relative track (part 11 §55); a still patch is still the way to measure that pan. The library has no way to track a fixed patch, so every run writes its own tracker.

Add two functions to `helpers.tracks`:

- **`find_still_patches(video_path, frames, avoid=None, size=64, count=3)`** → up to `count` boxes `(x, y, w, h)` of `size`×`size` pixels. A box qualifies only if, grown by 20 px on every side, it does not meet the bounding box of any mask in `avoid` (masks by object, as `load_masks` returns them) on any of `frames`. Among the qualifying boxes on the first of `frames`, it returns the ones with the most texture (variance of the Laplacian of the grey image), with centres at least `2·size` apart. Frames that a mask does not cover are not checked for that mask.
- **`still_track(video_path, frames, box, avoid=None)`** → rows `[{"frame", "x_px", "y_px"}]`, one per frame in `frames`, the same row format as a `reference_track_artifact`. It measures the shift of the box's grey patch from the first of `frames` to each frame by phase correlation with a Hann window (sub-pixel), and returns the box centre plus that shift. It first applies the same `avoid` test as `find_still_patches` and raises `ValueError` naming the object and the frame when the box meets a mover.
- Both docstrings (and so `HELPERS_DOCS.md`) say how to use them: for `camera.still`, pass every frame of the fit window and the masks of every moving thing as `avoid`; take the first box from `find_still_patches`, track it with `still_track`, save the rows as a workspace JSON file and cite that file as `reference_track_artifact`. A template tracked by hand next to a moving thing follows it and reads as camera motion.
- **Tests (synthetic video written to a temporary file, no model calls):**
  - a static textured background with a bright square that moves across it: `find_still_patches` with the square's masks as `avoid` returns boxes that never meet the square, and `still_track` on the first box moves at most 0.5 px over all frames;
  - the same background shifted by 3 px to the right from frame 10 on: `still_track` reports a shift of 3 ± 0.5 px from frame 10 on and 0 ± 0.5 px before;
  - a box on the square's path raises `ValueError` naming the square and a frame;
  - rows have exactly the keys `frame`, `x_px`, `y_px`, one row per requested frame, in order.

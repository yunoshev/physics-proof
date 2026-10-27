# Task M10 fix 1 — `build` on runs made before M8 fix 2

After M8 fix 2, `verdict.worlds_tested` / `worlds_ruled_out` are required for `none_fits`, and `finish` recomputes
`decide` with exactly `worlds_tested`. `build` must keep working on runs made before that (all runs under `runs/`
dated 2026-10-27 lack the fields): today 4 tests in `tests/test_page_m10.py` fail with a RuntimeError.

## Do
- In `build`: when a run lacks `worlds_tested`, fill it with the worlds the stored verdict was decided against (the keys
  of `verdict.sigmas`), mark the page data `legacy_worlds: true`, and let the page show one line in the Verdict step:
  "This run predates the scene check of worlds; tested against: …". Do not edit run files.
- Pages of new runs show `worlds_ruled_out` in the Verdict step ("Ruled out by the scene: Moon — trees moving in the
  wind, people walking").
- `page_texts` can override the new strings.

## Probes
The 4 failing tests pass again; a new test builds a run with `worlds_ruled_out` and finds the line in the page data.

## Done when
All offline tests pass; `tasks/M10-fix1.report.md` written.

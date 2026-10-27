# Task M10 fix 1 report — `build` on runs made before M8 fix 2

## Built
- [physics_proof/page.py](/Users/ayunoshev/Projects/Personal/physics-proof/physics_proof/page.py): `recompute_analysis` fills a missing `verdict.worlds_tested` from the stored `sigmas` keys (and `worlds_ruled_out` with `[]`), and recomputes `decide` against exactly `worlds_tested`, mirroring `finish`; `prepare_page` gains `legacy_worlds` flag plus `ruled_out_line` / `legacy_line` in the page data, both prefixed from new `DEFAULT_TEXTS` keys (`verdict.ruled_out`, `verdict.legacy_worlds`) so `page_texts` overrides them; `build_page` detects legacy runs from the stored file and never writes to run files.
- [player/player.js](/Users/ayunoshev/Projects/Personal/physics-proof/player/player.js): `renderVerdict` appends the two page-data lines to the Verdict step; [player/HASH](/Users/ayunoshev/Projects/Personal/physics-proof/player/HASH) updated to the new template hash.
- [tests/test_page_m10.py](/Users/ayunoshev/Projects/Personal/physics-proof/tests/test_page_m10.py): new `test_verdict_worlds_lines_in_page_data`.

## Probe coverage
- The 4 failing tests pass again: legacy `none_fits` runs validate after the fill (empty ruled-out list is legal when every listed world was tested).
- New test: a wallrun copy with `worlds_tested` + `worlds_ruled_out` builds, and the page data holds `Ruled out by the scene: Moon — trees moving in the wind, people walking`; the `page_texts` override swaps the prefix; a raw moonb-r2 build yields `legacy_worlds: true` with `This run predates the scene check of worlds; tested against: Earth, Moon`, and the stored `analysis.json` is byte-identical after the build.

## Test output
- `tests/test_page_m10.py`: 12 passed.
- Full offline suite: 239 passed, 23 skipped (API-gated).
- Node stub check of `renderVerdict`: both lines render, absent when null.

## Not done / open
- Nothing outstanding; legacy `fits:Moon` runs also get `worlds_tested` filled and show the legacy line, per the task wording.

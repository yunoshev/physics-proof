# Task M5-fix2 report — Seatbelt filters are OR-ed, wrap in require-all

## Built
- `physics_proof/sandbox.py`:
  - New `_deny_rule(operation, filters)` helper: more than one filter is
    wrapped in `(require-all ...)` for AND; a single filter stays bare.
  - All three denies in `_sandbox_profile` use it: `file-read*` is now
    `(subpath HOME)` + carve-outs under one `require-all`; `file-write*`
    wraps its two `require-not`; `process-exec*` wraps all `require-not`
    literals.
  - `_sandbox_profile` docstring rewritten: dropped the "deny wins
    regardless of order" claim; states only the verified facts — no
    leading `(allow default)` denies everything (exit 71), and filters
    in one rule are OR-ed so multi-filter rules need `require-all`.
- `scripts/sandbox_selfcheck.py`: profile is read inside the
  `TemporaryDirectory` block (it was read after cleanup → crash). The
  profile file (`scripts/NNN.sb`) is still kept next to the script.
- `tests/test_sandbox.py`: new offline
  `test_profile_multi_filter_denies_use_require_all` parses the generated
  profile (string-aware s-expr splitter) and asserts no deny rule has more
  than one top-level filter, and every `require-all` wraps several.

## Probe coverage
- Fix 1 (OR→AND): covered by the new offline test; sandbox behavior
  itself must be confirmed on the Mac.
- Fix 2 (self-check crash): `scripts/sandbox_selfcheck.py` now prints the
  profile before running; verified here it reaches the run stage.
- Fix 3 (profile-text unit test): the new test above.

## Test output
- `uv run pytest -q`: 98 passed, 15 skipped (2 API, 13 sandbox —
  `sandbox-exec` cannot apply profiles in this shell).
- `uv run python scripts/sandbox_selfcheck.py`: prints profile, then
  `sandbox_apply: Operation not permitted` (expected here — nested
  sandbox is blocked), exit 1, no traceback.

## Maintainer to run on the Mac
- `uv run pytest tests/test_sandbox.py` and
  `uv run python scripts/sandbox_selfcheck.py` (expect ok=True, stdout 1).

## Open questions
- None for this fix; if sandbox tests still fail, send the new stderr.

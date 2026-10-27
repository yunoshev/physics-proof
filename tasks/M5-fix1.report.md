# Task M5-fix1 report — sandbox profile fix + Python 3.13 pin

## Built
- `.python-version` (`3.13`); `pyproject.toml`: `requires-python = ">=3.13,<3.14"`;
  re-synced: `.venv/bin/python` is now 3.13.3 (was a 3.14 symlink into `~/.local/share/uv`).
- `physics_proof/sandbox.py`:
  - `_sandbox_profile` now starts with `(allow default)`. Root cause of all 12 Mac
    failures: the old profile had only deny rules and no allow, so Seatbelt's default-deny
    blocked the interpreter exec itself (`execvp ... Operation not permitted`, exit 71).
  - Exec deny carves out the venv interpreter path AND its realpath, plus both the
    `PATH`-found and resolved form of `ffmpeg`/`ffprobe` (Seatbelt checks both).
  - Home-read carve-outs now only list candidates at-or-under home (smaller profile);
    added venv site-packages (`_site_dirs()`) to the candidates.
  - `run_python` launches the resolved interpreter directly; the `-I` bootstrap
    (`_runner_source`) re-adds site-packages to `sys.path` with the repo root first,
    so `import blocks` still hits our shim.
- `scripts/sandbox_selfcheck.py`: prints the generated profile, runs `print(1)` via
  `run_python`, shows ok/exit/stdout/stderr; exits 1 unless output is exactly `1`.

## Probe coverage
- Every failing Mac test traces to the interpreter exec denial (fixed by allow-default
  + both-path exec carve-outs); per-behavior sandbox tests themselves are unchanged.
- `test_seatbelt_deny_wins_either_order` re-checked: it tests Seatbelt semantics with its
  own profiles, not ours; our profile already uses the `require-not` pattern it justifies.
  No change needed. (Why it failed on the Mac is unexplained from here — it execs
  `/bin/cat`, not python; please report its new output.)
- Verified here without Seatbelt: generated profile text is correct; the resolved-exe
  `-I` bootstrap imports `blocks`/`numpy`/`matplotlib` and `fit_parabola` prints
  `G-OK 2.0...` (matches the `test_sandbox_import_blocks` substring assertion).

## Test output
- `uv run pytest -q`: 97 passed, 15 skipped (2 API, 13 sandbox — nested `sandbox-exec`
  is blocked in this shell: `sandbox_apply: Operation not permitted`).
- Could not run `tests/test_sandbox.py` myself for the same reason.

## Maintainer to run on the Mac
- `uv run pytest tests/test_sandbox.py` and `uv run python scripts/sandbox_selfcheck.py`.

## Open questions
- If `test_seatbelt_deny_wins_either_order` still fails, send its stderr — Seatbelt
  version differences in deny/allow precedence would force a profile redesign.

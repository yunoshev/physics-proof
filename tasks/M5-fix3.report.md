# Task M5-fix3 report — shim spawn denied; last rule wins

## Causes (from the Mac symptoms)
1. `posix_spawn: .../Python.app/.../Python: Undefined error: 0`, exit 1,
   empty stdout: Homebrew `bin/python3.13` is a launcher shim that spawns
   `Resources/Python.app/Contents/MacOS/Python` next to itself (confirmed
   with `strings`: the shim embeds that relative path). Our
   `deny process-exec*` allowlist held only the shim path, so the shim's
   own spawn was denied and the interpreter never started. Same root
   cause for all 11 sandbox tests and the self-check.
2. `allow file-read*` after `deny file-read*` permits the read: when
   several Seatbelt rules match, the **last matching rule wins** — not
   "deny wins either order" as the old test/comment claimed. Our profile
   (`(allow default)` first, denies after) is already correct for this.

## Built
- `physics_proof/sandbox.py`:
  - New `_shim_targets(exe, base_prefix)`: existing framework app
    binaries (`<Versions/X>/Resources/Python.app/.../Python`, probed via
    both the resolved exe tree and `sys.base_prefix`); empty elsewhere.
  - `_sandbox_profile` adds them to the process-exec carve-outs
    (both literal forms, deduped). No widening: still exact literals,
    still interpreter + ffmpeg/ffprobe only.
  - Docstring now states last-match-wins (denies after allow) and the
    shim carve-out; keeps the verified OR-filters/`require-all` note.
- `tests/test_sandbox.py`:
  - `test_seatbelt_deny_wins_either_order` replaced by
    `test_seatbelt_last_matching_rule_wins`: deny-last refused (non-zero,
    empty stdout), allow-last permitted (exit 0, `stdout == b"x"`).
  - New offline `test_profile_denies_come_last`: every `(deny …)` form
    comes after `(allow default)` in the generated profile.
  - New offline `test_profile_carves_out_shim_target`: fake framework
    tree → target found by `_shim_targets` and present in the profile;
    plain layout → no extra carve-out.

## Probe coverage
- Symptom 1: fixed by the shim carve-out; verified the generated profile
  on this Mac contains the exact denied path. Real run must be confirmed
  by the maintainer (nested `sandbox-exec` is blocked in my shell).
- Symptom 2: rewritten sandbox test asserts exactly what the Mac showed.
- Security properties from `tasks/M5.md` unchanged: no network, writes
  confined, home reads denied with the same carve-outs, exec limited to
  the interpreter (+ its shim target) and ffmpeg/ffprobe.

## Test output
- `uv run pytest -q`: 100 passed, 15 skipped (2 API, 13 sandbox —
  `sandbox-exec` cannot apply profiles in this shell).
- Profile probe: shim target resolves to the same
  `.../3.13.3/.../Python.app/Contents/MacOS/Python` path as the Mac error.

## Maintainer to run on the Mac
- `uv run pytest tests/test_sandbox.py` (expect the 11 sandbox tests
  plus the renamed seatbelt test to pass) and
  `uv run python scripts/sandbox_selfcheck.py` (expect ok=True, stdout 1).

## Open questions
- None for this fix; if the shim spawns anything else at startup, send
  the new stderr and the carve-out list grows the same way.

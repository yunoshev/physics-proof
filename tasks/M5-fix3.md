# Task M5 fix 3 — sandbox tests on the Mac, round 3

After fix 2 the profile rules are combined correctly, and the interpreter now starts inside the sandbox. The maintainer
ran the suite on the Mac again: **12 failed, 98 passed**. Only symptoms are given here; find the causes yourself.

1. `scripts/sandbox_selfcheck.py`:
   ```
   ok=False
   exit_code=1
   stderr=python3.13: posix_spawn: /opt/homebrew/Cellar/python@3.13/3.13.3/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python: Undefined error: 0
   ```
   The same stderr appears in 11 sandbox tests (`test_sandbox_blocks_socket`, `…home_write_denied`, `…home_read_denied`,
   `…blocks_shell`, `…env_scrubbed`, `…timeout_fast`, `…returns_plot`, `…returns_two_newest_images`,
   `…import_blocks`, `…ffprobe`, `…truncates_output`), all with empty stdout and exit code 1.
2. `test_seatbelt_deny_wins_either_order` fails on the case where an `allow file-read*` rule comes **after** a
   `deny file-read*` rule for the same subpath: `sandbox-exec` exits 0 and the file is read (`stdout=b'x'`). The test
   expected a non-zero exit.

Keep every security property from `tasks/M5.md`. Update tests, comments and docstrings to state only what the Mac
actually showed.

## Done when
Offline tests that run in your environment pass; `tasks/M5-fix3.report.md` written. The maintainer reruns the sandbox
tests and the self-check on the Mac.

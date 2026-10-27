# Task M5 fix 1 — sandbox tests fail on the real Mac

Your M5 run could not execute the sandbox-layer tests: inside your own sandbox, nested `sandbox-exec` is blocked, so they
were skipped. The maintainer ran the suite on the Mac, outside any sandbox. Result: **12 failed, 33 passed** in
`tests/test_sandbox.py`. Every failure has the same cause:

```
sandbox-exec: execvp() of '/Users/ayunoshev/Projects/Personal/physics-proof/.venv/bin/python' failed: Operation not permitted
exit_code = 71, stdout = ''
```

Failed: `test_sandbox_blocks_socket`, `test_sandbox_home_write_denied`, `test_sandbox_home_read_denied`,
`test_sandbox_blocks_shell`, `test_sandbox_env_scrubbed`, `test_sandbox_timeout_fast`, `test_sandbox_returns_plot`,
`test_sandbox_returns_two_newest_images`, `test_sandbox_import_blocks`, `test_sandbox_ffprobe`,
`test_sandbox_truncates_output`, `test_seatbelt_deny_wins_either_order`.

Facts from the Mac:
- `.venv/bin/python` is a symlink to `~/.local/share/uv/python/cpython-3.14.0-macos-aarch64-none/bin/python3.14`
  (uv picked 3.14 although the project is meant for 3.13).
- The generated profile allows `process-exec` for the interpreter, but the exec of the venv path is denied — Seatbelt
  checks the path being executed and the resolved file; a rule for only one of them is not enough.

## Do
1. Pin Python 3.13: add `.python-version` with `3.13` and set `requires-python = ">=3.13,<3.14"`; re-sync the
   environment.
2. In the profile, allow `process-exec` (and `file-read*` / `file-read-metadata` as needed) for **both** the venv
   interpreter path and its `realpath`, and the interpreter's install directory (stdlib), while keeping every other
   rule (no network, writes only in the workspace, home reads denied except the carve-outs, exec only interpreter +
   ffmpeg + ffprobe). Simplest robust option: launch the resolved interpreter path directly and keep the venv's
   `site-packages` on `sys.path` via the bootstrap, then allow exec of exactly that resolved file.
3. Re-check `test_seatbelt_deny_wins_either_order` against what the profile really does.
4. You cannot run these tests yourself (nested sandbox). Reason carefully, keep the profile small, and add a script
   `scripts/sandbox_selfcheck.py` that the maintainer can run on the Mac: it prints the generated profile and runs a
   trivial `print(1)` through `run_python`, showing exit code and stderr.

## Done when
Offline tests that can run in your environment pass; `tasks/M5-fix1.report.md` says what changed and why. The maintainer
then runs `uv run pytest tests/test_sandbox.py` and `uv run python scripts/sandbox_selfcheck.py` on the Mac.

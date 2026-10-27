# Task M5 fix 2 — Seatbelt filters inside one rule are OR-ed

After fix 1 the sandbox tests still fail on the Mac (10 failures), now with
`sandbox-exec: execvp() of '/opt/homebrew/Cellar/python@3.13/3.13.3/Frameworks/Python.framework/Versions/3.13/bin/python3.13' failed: Operation not permitted`.
`scripts/sandbox_selfcheck.py` also crashes: it reads `ws/scripts/001.sb` after `run_python` has already removed it.

## Root cause (verified by the maintainer with `sandbox-exec` directly)
In SBPL, several filters inside one rule are combined with **OR**, not AND. So

```
(deny process-exec* (require-not (literal "/bin/echo")) (require-not (literal "/bin/ls")))
```

denies every exec (any path is "not echo" OR "not ls") — `/bin/echo` fails. Wrapping the filters in `require-all`
gives the intended meaning:

```
(deny process-exec* (require-all (require-not (literal "/bin/echo")) (require-not (literal "/bin/ls"))))
```

With this profile `/bin/echo hi` prints `hi` and `/bin/cat` is denied. The same bug is in all three rules of
`_sandbox_profile`:
- `deny file-read*` with `(subpath HOME)` plus `require-not` carve-outs → must be
  `(require-all (subpath HOME) (require-not …) (require-not …))`;
- `deny file-write*` with two `require-not` → must be `(require-all (require-not workspace) (require-not /dev/null))`;
- `deny process-exec*` with several `require-not` → must be `(require-all …)`.

## Do
1. Fix the three rules with `require-all`. Fix the docstring (it currently says deny wins regardless of order; keep
   only what is verified: filters in one rule are OR-ed; use `require-all` for AND).
2. Keep the profile file (`scripts/NNN.sb`) next to the script for the log, or make the self-check print the profile
   before running; it must not crash.
3. Add an offline unit test on the generated profile text: every deny rule with more than one filter wraps them in
   `require-all`.
4. You still cannot run the sandbox-layer tests yourself; the maintainer runs them on the Mac.

## Done when
Offline tests that run in your environment pass; `tasks/M5-fix2.report.md` written.

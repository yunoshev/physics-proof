# 10 — Self-Built Tools

**Owns:** `src/selfbuilt/`. Spark may extend its own toolkit during a run, under a gate strict enough that a self-built tool can never become an unexamined source of numbers. **Small-code principle:** the whole mechanism is a directory, a JSON registry, and one test-runner invocation. No plugin framework.

## 1. The contract

A self-built tool is exactly two files, written by Spark via `run_python` into the run workspace:

```
workspace/selfbuilt/sb_<name>.py        # the module (prefix sb_ is mandatory)
workspace/selfbuilt/test_sb_<name>.py   # its synthetic test
```

- The module is **one file**, importing only stdlib, numpy/scipy/OpenCV, and `src/helpers/`. No network (the sandbox already enforces this), no reading outside the workspace — and the test is held to a tighter rule (§2).
- The module must not shadow a helper, a stdlib name, or another `sb_` module. Name collisions are rejected by the registry, not resolved.

## 2. The gate: importable only if the test passes

1. The test must be **self-contained synthetic**: it constructs its own input data with a known answer and asserts the module recovers that answer within a stated tolerance. To make "self-contained" enforceable rather than aspirational, the test is run in a **fresh temporary directory containing only the two files** — analysis artifacts are physically unreachable, so a test that secretly fits the real clip cannot pass. (This is the simple version of the check; it catches the failure we care about — a "test" that just echoes the run's own numbers.)
2. Execution runs under the same sandbox as `run_python` (part 07), with a short timeout.
3. On a pass: the loop registers the tool and adds `workspace/selfbuilt/` to the import path for subsequent `run_python` calls in this run. On a fail: the module is **not importable** — the path is never added for it — and the failure output is returned to Spark.
4. **Limits, enforced by the loop's ledger (part 06):** at most **4 self-built tools** per run, at most **3 attempts each** (every test execution counts, pass or fail). At the cap, further builds are refused with a structured error; the run proceeds with helpers only.

## 3. The registry

`workspace/selfbuilt/registry.json`, written only by our code:

```json
{"tools": [{"name": "sb_wall_line", "module_sha256": "…", "test_sha256": "…",
            "attempts": 2, "status": "passed", "purpose": "<agent's one-line claim>",
            "registered_at_turn": 17}]}
```

The registry is the run's memory of what was built. If a passing tool is later edited, its hash no longer matches the registry and it stops being importable until re-tested (re-testing consumes an attempt). No silent mutation of a trusted tool.

## 4. Appearance in the result

If any submitted evidence was produced using a self-built tool, the submission must name it; part 11 checks the name against the registry (status `passed`, hash matches). The result file (part 12) lists every registered tool — name, purpose, attempts — whether or not it was used, so a judge can see exactly what the agent built for itself. Numbers from an unregistered or failed tool are invalid by construction: the code that produced them could not have imported it.

## 5. Promotion (human only)

There is **no agent-facing promote action**. The maintainer command:

```
python -m src.selfbuilt.promote <run-id> <sb_name>
```

- re-runs the tool's test standalone (must pass again, outside the run),
- copies module → `src/helpers/promoted/<name>.py` and test → `tests/helpers/test_<name>.py`,
- refuses name conflicts and refuses if either file was modified since registration,
- and stops there: wiring it into the documented helper set (docstring → generated docs, part 09 §4) is a deliberate human edit of the spec'd library, reviewed like any other change.

Promotion is the only path by which run-generated code outlives its run (cf. part 04 §4), and it carries its synthetic test with it — a promoted tool that later fails its test is demoted by the same rule as any helper (part 09 §3).

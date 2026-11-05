# Skill — macOS sandbox for agent Python

The agent's Python runs under `sandbox-exec` with a Seatbelt profile (brief part 07 §6): read only the run workspace/artifacts/input + the helper library, write only workspace/artifacts, no network, scrubbed environment. Facts learned the hard way:

- **Filters inside one rule are OR-ed.** If a rule must require A **and** B, use `require-all` — a plain multi-filter rule allows the file if *any* filter matches, which quietly punches holes.
- **The last matching rule wins.** Order matters; put specific denies/allowances after broad ones deliberately, and comment the ordering in the profile.
- **Homebrew's Python launcher re-executes a different binary**: the interpreter the user invokes re-execs `…/Python.app/Contents/MacOS/Python`, and *that* path must be in the allowed-executables list or every run fails with a confusing exec denial.
- **Nested sandboxes are blocked:** the coding agent (Muse) itself runs inside a sandbox in which `sandbox-exec` cannot run. Tests that exercise the real sandbox profile therefore cannot run inside the coding agent — they are marked `maintainer` and run by the owner outside (brief part 15 §3). Never "fix" a sandbox test failure by weakening the profile from inside the agent; a skip-marked test is the correct outcome there.
- Profile shape that worked: deny-by-default base, explicit allows for the workspace subtree, the interpreter + its framework paths, and read-only access to `src/helpers/`; explicit network deny last. Deny-by-default is the point — the first attempt's sandbox could read the whole repo, including expected answers (brief part 07 §6).

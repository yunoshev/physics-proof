# Agent instructions for physics-proof

You are building the code of this repository from `SPEC.md`, one module at a time. Each task lives in `tasks/<module>.md`
and names exactly what to build; do only that task.

## Ground rules
- Read `SPEC.md` (the module's section and section 2, Principles) and the task file before writing code. Do not edit
  `SPEC.md`, `README.md`, `LICENSE`, `AGENTS.md` or other tasks.
- Stay inside this repository. Do not run `git` (the maintainer reviews and commits). Do not install anything globally.
- Python 3.13 with `uv`: dependencies go into `pyproject.toml`; run things with `uv run …`; tests with `uv run pytest`.
- Package code in `physics_proof/`, tests in `tests/`, small data fixtures in `tests/fixtures/`, config in `config/`,
  one-off scripts in `scripts/`.
- The API key comes only from the environment variable `META_API_KEY`. Never print, log, save or put it in an exception
  message. Tests use a fake key.
- Tests are offline by default. Anything that calls the real API is marked `@pytest.mark.api`, is skipped unless
  `-m api` is given, prints its cost, and costs less than one cent.
- Style: type hints, small functions, short docstrings, no clever tricks. Scripts print with `flush=True`. Never put a
  backslash inside an f-string expression.
- Video and data we commit must be ours or public domain. Synthetic test clips are generated with ffmpeg (`lavfi`
  sources; this ffmpeg has no `drawtext` filter).

## When you finish a task
1. Run the offline tests; all must pass.
2. Write `tasks/<module>.report.md`: what you built (files), how each probe from the task is covered, test output summary,
   anything you could not do and why, open questions. Keep it under 60 lines.

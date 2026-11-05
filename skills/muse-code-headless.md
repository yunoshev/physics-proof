# Skill — Muse (coding agent) in headless mode

How the coding agent that builds this project is driven (brief part 15 owns the workflow; this file is the mechanics). The agent writes **all** code; the owner never edits generated files by hand (part 15 §2 enforces this by hash).

This is the *build-time* agent. It is not the analysis runtime: the product's agent loop (brief part 06) calls `muse-spark-1.3-contributor` through the Meta Model API, while Muse below is how the spec is turned into code. Both are Meta models; don't confuse their configs.

## Invocation

```sh
printf %s "$META_API_KEY" | muse exec --api-key-stdin --json \
  --model <model> --reasoning-effort <low|medium|high|max> \
  --max-model-steps <N> --no-foreign-personal-context \
  --disable-reminders --trust-workspace --approval-mode never \
  --sandbox-network enabled --workspace . "<prompt>"
```

- The API key is piped on stdin — it never appears in the prompt, in argv beyond the flag, or in any file or log.
- `--no-foreign-personal-context` is load-bearing: the only inputs are the prompt's contents (one spec part + `PLAN.md` + the relevant skills). One part per invocation.
- `--max-model-steps <N>` comes from the dev-loop config for that part and is recorded in `ITERATIONS.md` alongside the result.

## Reading the output

With `--json` the command prints **JSONL events**. Two payload kinds matter:

- **`run_usage`** — per model: input, cached, output, reasoning tokens, and the number of calls. This is the *only* source for generation cost in `ITERATIONS.md` (brief part 15 §2). Dev-loop converts tokens to dollars with the price rows in `skills/meta-api.md` for the model used; if a model has no price row there, it records tokens and `cost: unknown` — it never invents a price.
- **`run_terminal`** — the outcome. Anything other than a clean success (truncation, step limit, error) is a **failed generation**, even if files were written: the dev loop discards and re-runs or reports, never treats partial output as "mostly done". Reasoning tokens count toward output limits (see `skills/meta-api.md`), so request generous headroom.

### Exact event shapes (observed 2026-10-27)

Each JSONL line is an envelope; the fields that matter sit under `payload`, identified by `payload.kind`
(`payload_type` names the same thing with dots). Example lines, trimmed:

```json
{"payload_type": "run.usage", "payload": {"kind": "run_usage", "models": [{"model": "muse-spark-1.3-contributor", "input_tokens": 1093053, "cached_tokens": 1046740, "output_tokens": 22850, "reasoning_tokens": 11417, "calls": 21}], "calls": 21, "completed_calls": 21, "failed_calls": 0}}
{"payload_type": "run.terminal.completed", "payload": {"kind": "run_terminal", "terminal": "completed", "text": "<the agent's final message>", "reason": null}}
```

- Usage: sum `payload.models[]` entries per `model`; `cached_tokens` is the cached part of `input_tokens` (price it at the
  cached rate, the rest at the input rate); `reasoning_tokens` is already inside `output_tokens` — never price it twice.
- Success is exactly `payload.terminal == "completed"`; any other value is a failed generation. `payload.text` is the
  agent's own summary — keep it for the iteration log.

## Model and effort tiers

| Job | Model | Effort |
|---|---|---|
| `PLAN.md` (once; must hold the whole spec at once) | `muse-spark-1.3` | `max` |
| Per-part generation (default) | `muse-spark-1.3-contributor` | `medium` |
| Hard parts: `06` (agent loop), `11` (result validation), `13` (player) | `muse-spark-1.3-contributor` | `high` |

Don't generate a routine part at a higher tier "to be safe" — cost discipline is part of the demo story (brief part 14).

## Rules

- **Known environmental block:** Muse runs inside a sandbox where nested `sandbox-exec` is blocked. Tests that exercise the real analysis sandbox profile therefore cannot run inside the coding agent — they are marked `maintainer` and run by the owner outside (brief part 15 §3, `skills/macos-sandbox.md`). Never weaken a profile or unmark a test to make it "pass" in-agent; a skip-marked test is the correct outcome there.
- **No improvisation outside the spec:** if a part seems wrong or incomplete, stop and report the gap for a spec edit — do not invent behaviour in code. The spec-and-regenerate loop only works if generated code contains nothing the spec didn't say.
- **Regeneration hygiene:** the dev-loop tool deletes a part's owned files before regenerating them (brief part 15 §2). Anything that must survive regeneration lives in the spec, `PLAN.md`, a skill, or a test — never in a comment in generated code.

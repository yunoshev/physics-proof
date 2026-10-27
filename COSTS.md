# What this costs

Every model call in this project goes through Meta Model API and is logged. Building the harness is done by Muse Code
on `muse-spark-1.3-contributor`; the tool itself calls Spark and SAM 3.1. Costs below use the list prices for the
contributor tier: input $0.10, **cached input $0.002**, output $0.20 per 1M tokens; SAM 3.1 $0.20 per 1k frames.
Muse Code re-sends the conversation every step, so ~95 % of its input is cached — that is why a module costs cents.

**Check against the invoice:** Meta Model API billing showed **€0.38** outstanding on 2026-10-27 (≈ 18:00 Lisbon, after
M1–M6b; billing lags up to an hour). The table total below is in USD at list prices.

## Building the harness (Muse Code)

| Module | What | Model calls | Input, new | Input, cached | Output | Cost, USD |
|---|---|---|---|---|---|---|
| — | API probes before the build (Spark video input, SAM 3.1 on 466 frames, tool calling) | — | — | — | — | 0.100 |
| M1 | Meta API client, cost ledger, recorded fixtures | 55 | 184 428 | 4 771 173 | 54 631 | 0.039 + 0.050 API in tests |
| M2 | Video: exact frames, fps, duplicates, contact sheets, normalize | 40 | 182 079 | 2 392 405 | 35 715 | 0.030 |
| M6 | Physics blocks: masks, track quality, parabola fit, verdict | 22 | 99 623 | 1 379 013 | 33 033 | 0.019 |
| M5 | Python sandbox: static review + macOS Seatbelt runner | 26 | 108 657 | 2 029 705 | 51 346 | 0.025 |
| M5 fix 1–3 | sandbox tests run on the Mac (the agent cannot nest Seatbelt); three rounds | 63 | 223 469 | 3 382 411 | 42 489 | 0.038 |
| M3 | SAM 3.1 tool: frame-accurate cut, cache, budget, overlay sheet, id-swap check | 30 | 108 095 | 2 487 757 | 31 867 | 0.022 + 0.010 API in tests |
| M4 | search tool with a blindness filter | 25 | 121 873 | 1 785 767 | 29 879 | 0.022 + 0.004 API in tests |
| M6b | blocks for moving cameras and time scale | 24 | 107 083 | 1 709 351 | 33 034 | 0.021 |
| — | maintainer check of M3 on the Moon clip (70 SAM frames) | — | — | — | — | 0.014 |
| — | maintainer feasibility check on the wall-run clip (2 × 100 SAM frames) | — | — | — | — | 0.040 |
| M4 fix 1 | blindness patterns: pronoun quantities, generative vocabulary, event names, feasibility | 23 | 108 162 | 1 346 373 | 24 211 | 0.018 |
| M4 fix 2 | context-free classifier layer for blindness, fail-closed | 33 | 80 675 | 2 481 696 | 26 286 | 0.018 + 0.005 API in tests |
| M1 fix 1 | ledger prices cached input | 21 | 90 917 | 981 219 | 5 408 | 0.012 |
| M9 + fix 1 | analysis schema, validator, combine, schema_doc | 35 | 238 382 | 2 204 591 | 58 453 | 0.040 |
| M7 | context-free mask check | 25 | 135 994 | 2 050 855 | 22 789 | 0.022 + 0.000 API in tests |
| M8 | agent loop, minimal finish, run command | 71 | 237 453 | 11 749 493 | 59 003 | 0.059 + 0.003 API in tests |
| E1 + fix 1 | acceptance clips (Apollo 16 A, slowed B), eval checker | 77 | 240 807 | 5 176 505 | 45 427 | 0.044 |
| **Total so far** | | | | | | **≈ 0.65** |

## Analysing one video

To be measured on the Moon and wall-run clips (one full agent run: Spark turns, SAM 3.1 frames, searches, page build).
Reference points from the probes: Spark reads video at ≈ 121 tokens per second of footage; SAM 3.1 segments 100 frames
for $0.02 (it bills at least 50 frames per request).

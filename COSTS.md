# What this costs

Every model call in this project goes through Meta Model API and is logged. Building the harness is done by Muse Code
on `muse-spark-1.3-contributor`; the tool itself calls Spark and SAM 3.1. Prices are the list prices from `config/prices.json`
(USD); cached input tokens are counted at the full input price, so these numbers are an upper bound. The actual invoice is
in EUR on the Meta Model API billing page and will be added at the end.

## Building the harness (Muse Code)

| Module | What | Model calls | Input tokens (cached) | Output tokens | Cost, USD |
|---|---|---|---|---|---|
| — | API probes before the build (Spark video input, SAM 3.1 on 466 frames, tool calling) | 22 + 1 SAM | — | — | 0.10 |
| M1 | Meta API client, cost ledger, recorded fixtures | 55 | 4 955 601 (4 771 173) | 54 631 | 0.51 + 0.05 API in tests |
| M2 | Video: exact frames, fps, duplicates, contact sheets, normalize | 40 | 2 574 484 (2 392 405) | 35 715 | 0.26 |
| M6 | Physics blocks: masks, track quality, parabola fit, verdict | 22 | 1 478 636 (1 379 013) | 33 033 | 0.15 |
| M5 | Python sandbox: static review + macOS Seatbelt runner | 26 | 2 138 362 (2 029 705) | 51 346 | 0.22 |
| M5 fix 1–3 | sandbox tests run on the Mac (the agent cannot nest Seatbelt); three fix rounds | 22 + 16 + 25 | 3 605 880 (3 382 411) | 42 489 | 0.37 |
| M3 | SAM 3.1 tool: frame-accurate cut, cache, budget, overlay sheet, id-swap check | 30 | 2 595 852 (2 487 757) | 31 867 | 0.27 + 0.01 API in tests |
| — | maintainer check of M3 on the Moon clip (70 frames) | 1 SAM | — | — | 0.014 |
| M4 | search tool with a blindness filter | 25 | 1 907 640 (1 785 767) | 29 879 | 0.20 + 0.004 API in tests |
| — | maintainer feasibility check on the wall-run clip (runner + wall, 2 × 100 frames) | 2 SAM | — | — | 0.04 |
| **Total so far** | | | | | **≈ 2.20** |

## Analysing one video

To be measured on the Moon clips (one full agent run: Spark turns, SAM 3.1 frames, searches, page build).
Reference points from the probes: Spark reads video at ≈ 121 tokens per second of footage; SAM 3.1 segments a
466-frame clip for $0.09 (it bills at least 50 frames per request).

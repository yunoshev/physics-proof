# 03 — Test Clips and Acceptance

**Owns:** the test clips, the clip-preparation script, the acceptance harness, and the prompt-leak test. The acceptance constants in §4 live **only** in the test harness. They must never be imported by, embedded in, or reachable from the analysis runtime or the agent's prompt (see §5).

## 1. The clips

### Clip A — Apollo 16 "jump salute", original

- Source: downloaded from the **Apollo Lunar Surface Journal** by the repo's clip-preparation script, then re-encoded with **metadata stripped**.
- 352×240, **29.97 fps measured** (not the container's claim — the analysis must use a measured frame rate; part 05), 466 frames ≈ 15.5 s.
- Static camera, no audio.
- Stored in the repo (produced by the script).

### Clip B — Apollo 16 "jump salute", slowed ×1.5

- Derived from A by the same script: slowed ×1.5 with **motion interpolation** back to the same frame rate — so **no duplicated frames, same fps**, and nothing in the metadata says it was slowed.
- 697 frames (≈ 15.5 × 1.5 s at 29.97 fps), otherwise identical provenance to A.
- Stored in the repo (produced by the script). A and B must be indistinguishable to the system except through the motion itself.

### Clip C — Wall run

- Third-party viral clip: a man runs up a vertical wall. **Not stored in the repo** (rights); passed to the system and to the test harness **by path**.
- 720×1280 portrait, 24 fps, 240 frames = 10 s, HEVC.
- **Camera tilts up** to follow the runner (motion must be measured relative to the wall — part 08). Contains **3 duplicated frames** (timing must survive them — parts 05/08).
- Note: HEVC shows black in Chrome; the copy placed next to the player page must be H.264 (part 13). The *analysis* input remains the original file as passed.

## 2. Blindness protocol

1. Each clip is handed to the analysis under an **anonymous file name** (part 05) with metadata stripped. The system is told nothing about the clip: no name, no source, no expected verdict, no tolerances.
2. Runs are independent: no workspace, cache, or memory from a previous run may inform the next (except the human-promoted verified helper library, part 10, which contains no clip-specific information).
3. The web-search blindness filter (part 07) prevents looking the clip or its answer up.
4. The harness runs the *same one-command entrypoint* a user would run. No test-only flags that change agent behaviour.

## 3. Run protocol

- Each clip is analysed **3 times** (fresh runs).
- A clip **passes if at least 2 of 3 runs** meet every criterion in §4 for that clip.
- Every individual run, pass or fail, must additionally satisfy the universal criteria in §4.4 — a run that exceeds them counts as a failure of that run regardless of its verdict.

## 4. Acceptance criteria

### 4.1 Clip A

- Verdict: **Moon gravity**.
- Measured `g` satisfies `|g − 1.62| ≤ 2σ` **and** `σ ≤ 0.35 m/s²`.

### 4.2 Clip B

- **No scene-allowed world fits at native speed** (the result must show this, not silently jump to a factor).
- Verdict is a retiming verdict with recovered slowdown factor **1.5 ± 0.25** (retimed to the scene-pinned world, per part 02 §5.3).

### 4.3 Clip C (wall run)

- Overall verdict: **Physically impossible**.
- The wall segment's measured vertical acceleration is **more than 5σ from Earth g**.
- The independent clock **reads normal** (`s_clock` consistent with 1 — this is what licenses "impossible" over "retimed", part 02 §5).

### 4.4 Universal (every run of every clip)

- Cost **< $2** and wall time **< 30 minutes** (typical target: 7–11 min; cost accounting in part 14).
- The run performs **at least one blind mask check** (part 07) and the result records it.
- The run produces a **valid result file** (part 12) that passes part 11's checks — including "undetermined: budget" runs.
- No number in the result lacks code provenance (part 11).

## 5. The prompt-leak test (mandatory)

The acceptance constants of §4 — expected verdicts per clip, `σ ≤ 0.35`, `1.5 ± 0.25`, the 5σ wall threshold, the 2-of-3 rule — are **answers**, and the analysis agent must never see them.

- The harness captures **everything sent to Spark** (system prompt, tool descriptions, helper-library docs surfaced to the model, all turn messages) for a run of each clip, serialises it, and asserts that none of the harness's forbidden strings/values appear: clip names and identities ("Apollo", "wall run", file names), per-clip expected verdicts, and the §4 tolerance values as expectations.
- Generic physics is not a leak: the world-gravity table of part 02 (Earth 9.81, Moon 1.62, Mars 3.71) defines the candidate worlds for *every* clip and may be known to the agent; what is forbidden is any statement of which world, factor, or tolerance is expected for *this* clip.
- Structural guarantee, not just a string scan: the analysis runtime must not import or read the test harness, this part's constants, or the clip-preparation script's ground-truth parameters. The scan is the check; the separation is the mechanism. (Part 04 fixes the module boundary; part 15 wires the test.)

A leak-test failure fails the whole acceptance suite, even if all verdicts are correct — a system that was told the answer proves nothing.

## 6. What "done" means for the hackathon

All three clips passing §3–§5, published as precomputed player pages with a gallery (part 15), with the demo video recorded from those passing runs.

## Owner addendum (2026-10-28): the leak scan covers what we send, not what the agent finds

Part 01's decision of 2026-10-28 lets the agent identify the scene from the frames and search for facts about it, so its own messages and its own search results may name the place, the mission or the person ("Apollo", "John Young"). The leak scan covers everything the system and the operator put in front of the agent: the fixed prompt, tool descriptions, helper docs, ingest metadata, the operator's words, and the harness. In those, clip identities and per-clip expectations stay forbidden. The agent's own turn texts and the results of its own `web_search` queries are not scanned for identities. They are still scanned for this part's acceptance constants and per-clip expected verdicts, which no search can supply. Test: a captured run whose agent turn and search result say "Apollo" passes the scan; the same word in the system prompt or in an operator message fails it.

# 05 — Ingest and Anonymisation

**Owns:** `src/ingest/`, and the timing report every measurement depends on. **Lesson source:** "Time" — the container's frame rate can lie; our own clip tool once produced duplicated frames by forcing a constant frame rate.

## 1. Input contract

The CLI receives one filesystem path. From that moment:

1. The file is **copied** (never moved, never modified) into `runs/<run-id>/input/` under the fixed anonymous name `clip.<ext>`.
2. The original filename, path, and any container metadata are recorded in `logs/` only. Container metadata is **stripped** from the copy (stream copy through ffmpeg with metadata mapping disabled, or re-encode where stripping requires it).
3. Audio, if present, is dropped from the agent-visible copy: the product is silent, and audio is an identity leak channel.
4. Nothing else about the file — no directory listing, no sibling files — is visible to the agent, the sandbox, or any tool result.

The agent's world begins at `input/clip.<ext>` and `input/timing.json`.

## 2. Probing and *measured* frame rate

The container's claimed fps is **never trusted and never passed to the agent as fact**. Ingest runs ffprobe over the decoded frame timestamps and produces `timing.json`:

- `claimed_fps` (container claim, kept for the discrepancy log only),
- `measured_fps`: median of inter-frame timestamp deltas, with the delta distribution (min/p05/p95/max),
- `frame_count`, `duration_s`,
- `timestamps`: implicit — all downstream code converts frame index → seconds via the measured timestamps, never via `index / claimed_fps`.

If timestamps are irregular (VFR), `measured_fps` is reported as a distribution and the timing report says so; part 08's rules then require per-frame timestamps in any fit.

## 3. Timeline hygiene report (mandatory, before any measuring)

`timing.json` also records, from decoded frames:

- **Duplicated frames:** exact duplicates (identical decoded bytes) and near-duplicates (perceptual hash within a stated threshold) — indices and runs. Near-duplicate threshold is a named constant; slow genuine motion must not false-positive silently, so near-duplicates are labelled "suspect", exact duplicates "confirmed".
- **Cuts:** frame pairs whose visual difference exceeds the scene-change threshold — indices.
- **Interpolation suspicion:** a heuristic flag only (e.g. uniformly smooth sub-frame motion with no duplicates in a clip whose physics will later imply retiming). It must be labelled *suspicion, not evidence*: a motion-interpolated slowed copy has no duplicates and a normal frame rate, and **only physics plus an independent clock can catch it** (part 02 §5). Ingest must never "detect slow motion".

This report exists so the agent *can* look before measuring; part 08 makes looking a rule, and part 11 checks that fits respect confirmed duplicates/cuts.

## 4. Generated-clip verification (our own tooling is not trusted)

Any clip this project generates (clips A and B, part 03) must pass the same duplicate check after generation. The known failure — forcing a constant frame rate during encoding silently duplicating frames — is avoided by piping raw frames at the source rate, and the acceptance harness asserts: A has **0 confirmed duplicates**; B has **0 confirmed duplicates and the same measured fps as A**. A generated clip that fails is regenerated, never analysed. (Generation itself is owned by `scripts/make_clips.py`, part 03; the verifier is owned here so analysis and generation share one definition of "duplicate".)

## 5. What ingest does *not* do

- No transcoding for analysis: the agent gets the (metadata-stripped) original encoding, including HEVC. Transcoding to H.264 happens only for the player copy (part 13), outside the run workspace's anonymous input.
- No frame extraction at ingest: choosing frames is the agent's job (part 07). Ingest decodes only what's needed for probing and the timeline report.
- No content description of any kind. `timing.json` contains numbers and indices only — no captions, no thumbnails, no model output.

## 6. Outputs and failure behaviour

Outputs: `input/clip.<ext>`, `input/timing.json`, `logs/probe.json`. Failure to probe or decode → the run ends immediately with a valid *undetermined* result ("undetermined: unreadable video", via part 11's synthesis path) rather than a crash or a hang.

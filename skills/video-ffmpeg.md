# Skill — Video / ffmpeg pitfalls

Owning brief parts: 05 (ingest), 03/15 (clip generation), 13 (page assets). Every item here is a failure that already happened once.

- **The container's fps can lie.** Never trust the header/`avg_frame_rate` for timing. Decode and read per-frame timestamps (PTS); the measured fps is the median inter-frame delta (brief part 05 §2). All frame→seconds conversion goes through measured timestamps.
- **Duplicated frames happen silently two ways:** (a) forcing constant frame rate on encode (`-r` / `fps=` filters) duplicates frames to fill the rate — this bit our own clip tool; (b) sources contain them natively (the wall-run clip has 3). **Generate by piping raw frames one-frame-in/one-frame-out** at the source timing; then *verify* the output with the duplicate detector (exact byte compare per decoded frame + a perceptual-hash pass for near-duplicates, brief part 05 §3–4).
- **Motion-interpolated slow copies have no duplicates and a normal fps.** No ffmpeg probe can catch them; only physics + an independent clock can (brief parts 02 §5, 08 R-T3). Don't write a "slow-motion detector".
- **Metadata is an identity leak:** strip it from the analysis copy (`-map_metadata -1`, drop audio, fixed anonymous filename, brief part 05 §1). The Apollo clips A and B must differ *only* in frame count/duration after generation — same measured fps, no duplicates, no metadata hints (asserted in brief part 15 §3).
- **HEVC shows black in Chrome.** Analysis reads the original fine (ffmpeg/OpenCV); the **page copy must be H.264** (`libx264`, `yuv420p`, `+faststart`). Transcode only the presentation copy; never analyse the transcode (brief part 13 §9).
- **Spark vision wants mp4** (inline ≤ 50 MB, else Files API — `skills/meta-api.md`): a *viewing copy* for the model is fine; it is not an analysis input.
- **Variable frame rate is real:** if PTS deltas are irregular, report a distribution, not a single fps, and let fits use per-frame timestamps (brief part 05 §2, part 08 R-T1).
- Decoding for probes/contact sheets: extract exact frame indices (`select` by frame number after decode), not by seeking to seconds — keyframe seeking lands on the wrong frame silently.

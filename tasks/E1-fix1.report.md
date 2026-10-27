# E1-fix1 report — clip A holds exactly the source frames

## Cause
Source `a16salute.mpg` is MPEG-1 with `r_frame_rate 60000/1001` but
`avg_frame_rate 30000/1001`. The old single-ffmpeg A command
(`-fps_mode cfr -r 30000/1001` straight from the timestamps) resampled that
timeline and duplicated 2 frames to fit it: A had 468 frames with exact
duplicates at 47→48 and 58→59, while the source decodes to 466 clean frames.

## Built
- `scripts/make_moon_clips.py`: A is now a rawvideo pipe. Decode stage
  (`-f rawvideo -pix_fmt yuv420p -fps_mode passthrough`) emits every source
  frame exactly once; encode stage reads the pipe at the measured rate and
  writes CFR H.264 at that same rate, so N in = N out. B is unchanged
  (`setpts=1.5*PTS,minterpolate`), now sourced from the frame-exact A.
  Removed the dead `measured_fps`/`source_sar` helpers (main probes once).
- `tests/test_e1.py`: new `@pytest.mark.slow`
  `test_clip_a_matches_source_frames` runs on the committed A.mp4 and
  asserts frame count == 466 (decoded source count) and no duplicate runs.
- Regenerated `examples/moon/A.mp4`, `B.mp4`, `SOURCE.md` (new commands,
  frame-exact note, same public-domain rights text).

## New frame counts (real run, ffmpeg 9.0.2)
- Source: 352x240, 30000/1001 fps, 466 decoded frames, no duplicate runs.
- A.mp4: 30000/1001 fps, **466** frames, zero duplicate runs; per-frame MAD
  vs source ≈ 1–3 (single CRF-18 encode, yuv420p pipe, no colorspace loss).
- B.mp4: 30000/1001 fps, **697** frames (≈466×1.5 minus minterpolate edge
  effect, same −2 as before); sub-threshold pairs are interpolation, as
  expected. Both files ≤ 10 MB; re-ran twice, sha256 bit-identical.

## Probe coverage
- New slow test passes on the committed files (3.8 s).
- `--dry-run` still prints all commands incl. `setpts`/`minterpolate`.
- Full offline suite: 176 passed, 19 skipped (API opt-ins), `uv run pytest`.

## Could not do / open questions
- Nothing outstanding. Note: `video.normalize` uses the same old
  single-ffmpeg CFR pattern and can add frames the same way (the E1 report
  already flagged 466→468); fixing M2 is outside this task.

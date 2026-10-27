# Task E1 fix 1 — clip A must hold exactly the source frames

The maintainer checked the clips with `physics_proof.video` (`frame_diffs`, `duplicate_runs`):
- the source `a16salute.mpg` decodes to **466** frames with no duplicates (also seen in M2's check);
- `examples/moon/A.mp4` has **468** frames, with exact duplicates at frames 47→48 and 58→59 (difference ≈ 0) —
  the encoding inserted them;
- `examples/moon/B.mp4` has 700 frames; its low-difference pairs come from interpolation, which is expected.

A duplicated frame inside the jump shifts the timing the whole measurement depends on. Make A a one-to-one re-encode of
the decoded source frames at the measured rate (no frames added or dropped), and build B from that same frame-exact
timing. Add a test (marked `slow`, runs on the committed files) that A has the source's frame count and no duplicate
runs. Re-run the script, re-commit the clips, update `SOURCE.md` with the new commands.

## Done when
Offline tests pass; `tasks/E1-fix1.report.md` written with the new frame counts.

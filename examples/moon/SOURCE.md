# Source of examples/moon

Source file: `a16salute.mpg` from the Apollo Lunar Surface Journal,
Apollo 16 Video Library page https://www.apollojournals.org/alsj/a16/video16.html (direct file https://www.apollojournals.org/alsj/a16/a16salute.mpg).
The page offers "a short, 2.7 MB MPEG-1 clip of better resolution and at
29.97 fps, showing only the two jumps" of John Young's jump salute
(Apollo 16, 21 April 1972).

Rights: NASA footage; the ALSJ page states its video clips are in the
public domain ("The video clips are in the public domain").
Transcript/commentary on that site is separately copyrighted and is
not reproduced here.

## How A.mp4 and B.mp4 were made

A.mp4 is a one-to-one re-encode of the 466 decoded
source frames to H.264 (yuv420p, CRF 18), no audio, no metadata
(`-map_metadata -1`), at the frame rate measured by
`physics_proof.video.probe`: 30000/1001 fps (466 frames).
The decode stage pipes every frame once (rawvideo, `passthrough`);
the encode stage reads the pipe at the measured rate and writes CFR
at that same rate, so no frames are added or dropped (an earlier
single-ffmpeg `-r` re-encode duplicated 2 frames to fit the CFR
timeline; see tasks/E1-fix1.md).
B.mp4 slows A by x1.5 (`setpts=1.5*PTS`) and
interpolates (`minterpolate`) back to A's rate (697 frames).

Exact commands (run from the repository root; the first two form one
pipe, decode stdout into encode stdin):

    ffmpeg -v error -i /var/folders/_7/znjmxtkn27nf910l6vdym4gw0000gp/T/moon-src-3szngz7w/a16salute.mpg -map '0:v:0' -vf 'pad=ceil(iw/2)*2:ceil(ih/2)*2' -f rawvideo -pix_fmt yuv420p -fps_mode passthrough - |
        ffmpeg -y -v error -f rawvideo -framerate 30000/1001 -video_size 352x240 -pix_fmt yuv420p -i - -fps_mode cfr -r 30000/1001 '-c:v' libx264 -x264-params 'sar=200\:219' -pix_fmt yuv420p -crf 18 -preset medium -an -map_metadata -1 /Users/ayunoshev/Projects/Personal/physics-proof-wt/e1/examples/moon/A.mp4
    ffmpeg -y -v error -i /Users/ayunoshev/Projects/Personal/physics-proof-wt/e1/examples/moon/A.mp4 -vf 'setpts=1.5*PTS,minterpolate=fps=30000/1001:mi_mode=mci' -fps_mode cfr -r 30000/1001 '-c:v' libx264 -pix_fmt yuv420p -crf 18 -preset medium -an -map_metadata -1 /Users/ayunoshev/Projects/Personal/physics-proof-wt/e1/examples/moon/B.mp4

Built with: ffmpeg version 9.0.2 Copyright (c) 2000-2026 the FFmpeg developers
Encoder flags are fixed, so re-running this script gives bit-identical
files on the same ffmpeg build (verified by comparing sha256).

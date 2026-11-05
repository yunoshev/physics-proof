from helpers import masks_io, tracks
m12=masks_io.load_masks("artifacts/t12_segment_0.npz")
print(m12.keys())
m0=m12["0"]
facts=masks_io.clip_facts("input/timing.json")
ts={f: facts["timestamps"][f] for f in range(facts["frame_count"])}
tr=tracks.track_point(m0, mode="centroid", timestamps=ts)
for r in tr:
    if 130 <= r["frame"] <= 160:
        print(f'{r["frame"]} t={r["t"]:.3f} x={r["x_px"]:.1f} y={r["y_px"]:.1f}')
print(tracks.track_quality(tr, {"0": m0}))
# stats for object
import json
with open("artifacts/t12_segment_stats_0.json") as f:
    st=json.load(f)
# print frames 135,140,143
for e in st:
    if e["frame"] in [0,10,135,140,143,150]:
        print(e)

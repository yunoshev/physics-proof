from helpers import masks_io, tracks
m=masks_io.load_masks("artifacts/t9_segment_0.npz")
m1=m["1"]
facts=masks_io.clip_facts("input/timing.json")
ts={f: facts["timestamps"][f] for f in range(facts["frame_count"])}
tr=tracks.track_point(m1, mode="centroid", timestamps=ts)
for r in tr:
    if 130 <= r["frame"] <= 160:
        print(f'{r["frame"]} t={r["t"]:.3f} x={r["x_px"]:.1f} y={r["y_px"]:.1f}')
print("---quality lowest---")
tr2=tracks.track_point(m1, mode="lowest_point", timestamps=ts)
print(tracks.track_quality(tr2, {"1": m1}))
print("---quality centroid---")
print(tracks.track_quality(tr, {"1": m1}))
# area per frame
import json
with open("artifacts/t9_segment_stats_0.json") as f:
    st=json.load(f)
print(str(st)[:2000])

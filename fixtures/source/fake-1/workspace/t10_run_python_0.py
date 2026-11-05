from helpers import masks_io, tracks
import json
m=masks_io.load_masks("artifacts/t9_segment_0.npz")
print(m.keys())
# object ids: check types
for k in m:
    print(k, type(k), len(m[k]), sorted(list(m[k].keys()))[:5])
facts=masks_io.clip_facts("input/timing.json")
ts={f: facts["timestamps"][f] for f in range(facts["frame_count"])}
# track bottom and centroid for object 1 (foreground)
# masks dict for object 1: {frame: mask}
m1=m[1] if 1 in m else m["1"]
print("m1 frames", len(m1))
# lowest point track
tr_low=tracks.track_point(m1, mode="lowest_point", timestamps=ts)
tr_cent=tracks.track_point(m1, mode="centroid", timestamps=ts)
tr_top=tracks.track_point(m1, mode="top_centre", timestamps=ts)
# print around hop 120-180
for r in tr_low:
    if 120 <= r["frame"] <= 190:
        print(f'{r["frame"]} t={r["t"]:.3f} y={r["y_px"]:.1f} x={r["x_px"]:.1f}')

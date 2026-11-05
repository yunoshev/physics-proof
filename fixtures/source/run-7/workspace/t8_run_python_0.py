from helpers import masks_io, tracks
import json
masks=masks_io.load_masks("artifacts/t7_segment_0.npz")
print(masks.keys())
for k,v in masks.items():
    print(k, len(v), sorted(list(v.keys()))[:5], sorted(list(v.keys()))[-5:])
    # shape
    import numpy as np
    ex=list(v.values())[0]
    print(" shape", ex.shape)

facts=masks_io.clip_facts("input/timing.json")
ts={f:float(facts["timestamps"][f]) for f in sorted(masks["1"].keys())}

# track modes for object 1
for mode in ["centroid","bottom_centre","top_centre","lowest_point"]:
    tr=tracks.track_point(masks["1"], mode=mode, timestamps=ts)
    print(mode, tr[:2], tr[len(tr)//2], tr[-2:])

# stats bottom over time
import numpy as np
frames=sorted(masks["1"].keys())
bots=[]
for f in frames:
    s=tracks.mask_stats(masks["1"][f])
    bots.append((f, s["bottom"], s["top"], s["left"], s["right"], s["area"]))
for b in bots[::10]:
    print(b)
print("--- all bots")
for b in bots:
    print(b)

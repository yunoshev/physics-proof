from helpers import masks_io, tracks, physics
import json
# load astronaut and backpack masks
astro=masks_io.load_masks("artifacts/t8_segment_0.npz")['0']
pack=masks_io.load_masks("artifacts/t13_segment_0.npz")['0']
print("astro frames", len(astro), "pack frames", len(pack))
# facts
facts=masks_io.clip_facts("input/timing.json")
ts=facts["timestamps"]
# check IoU on frame 210
import numpy as np
def iou(a,b):
    inter=np.logical_and(a,b).sum()
    union=np.logical_or(a,b).sum()
    return inter/union if union else 0
for f in [200,210,220,230]:
    if f in astro and f in pack:
        print(f, "iou", float(iou(astro[f], pack[f])), "astro area", int(astro[f].sum()), "pack area", int(pack[f].sum()))
# backpack track centroid
tr=tracks.track_point({k:v for k,v in pack.items()}, mode="centroid", timestamps={k:float(ts[k]) for k in pack})
print(tr[:3], tr[-3:])
# quality
q=tracks.track_quality(tr, {'0':pack})
print(q)

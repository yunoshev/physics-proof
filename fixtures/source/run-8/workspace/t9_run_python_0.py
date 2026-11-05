from helpers import masks_io, tracks
import json, numpy as np
masks=masks_io.load_masks('artifacts/t6_segment_0.npz')
facts=masks_io.clip_facts('input/timing.json')
ts=facts['timestamps']
# detailed bottom/top per frame 235-285 for obj 1
print("frame t top bottom height")
for f in range(235,286):
    m=masks['1'][f]
    s=tracks.mask_stats(m)
    print(f, round(float(ts[f]),4), s['top'], s['bottom'], s['height'], s['width'], round(s['centroid_x'],1), round(s['centroid_y'],1))

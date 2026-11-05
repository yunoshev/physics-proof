from helpers import masks_io, tracks
from helpers import ranges as R
import json
# cv2 to get image size
import cv2
for p in ["artifacts/t13_segment_preview_0.jpg","artifacts/t8_segment_preview_0.jpg","artifacts/t20_segment_preview_0.jpg"]:
    im=cv2.imread(p)
    print(p, None if im is None else im.shape)
# compute extents on frame 200
astro=masks_io.load_masks("artifacts/t8_segment_0.npz")['0'][200]
pack=masks_io.load_masks("artifacts/t13_segment_0.npz")['0'][200]
for label, m in [("astro", astro), ("pack", pack)]:
    s=tracks.mask_stats(m)
    print(label, s)
    e=R.mask_extent(m, direction=(0,1))
    print(label, "extent", e)
# flag stability for camera
flag=masks_io.load_masks("artifacts/t20_segment_0.npz")['0']
facts=masks_io.clip_facts("input/timing.json")
ts=facts["timestamps"]
tr=tracks.track_point({k:v for k,v in flag.items()}, mode="centroid", timestamps={k:float(ts[k]) for k in flag})
print("flag track sample", tr[0], tr[40], tr[80])
# range of flag centroid
import numpy as np
xs=np.array([r['x_px'] for r in tr]); ys=np.array([r['y_px'] for r in tr])
print("flag x range", xs.min(), xs.max(), "std", xs.std(), "y range", ys.min(), ys.max(), "std", ys.std())

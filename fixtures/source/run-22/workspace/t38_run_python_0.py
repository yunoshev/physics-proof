from helpers import masks_io, tracks
from helpers import ranges as R, physics as P
import json, cv2, numpy as np
# flag extent at frame 200
flag=masks_io.load_masks("artifacts/t20_segment_0.npz")['0'][200]
s=tracks.mask_stats(flag)
print(s)
print(R.mask_extent(flag, direction=(1,0)))
print(R.mask_extent(flag, direction=(0,1)))
print(R.mask_extent(flag, direction=None))
# pack and astro at 200 with vertical
pack=masks_io.load_masks("artifacts/t13_segment_0.npz")['0'][200]
astro=masks_io.load_masks("artifacts/t8_segment_0.npz")['0'][200]
for lbl,m in [("pack",pack),("astro",astro),("flag",flag)]:
    for d in [(0,1),(1,0),None]:
        print(lbl,d,R.mask_extent(m,direction=d))

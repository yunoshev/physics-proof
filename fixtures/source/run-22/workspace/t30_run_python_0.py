from PIL import Image
import os
for p in ["artifacts/t13_segment_preview_0.jpg","artifacts/t8_segment_preview_0.jpg"]:
    try:
        im=Image.open(p)
        print(p, im.size)
    except Exception as e:
        print(p,e)
# also look at masks for helmet attempt t27
from helpers import masks_io, tracks
m=masks_io.load_masks("artifacts/t27_segment_0.npz")
print(m.keys())
for k in m:
    print("obj",k, sorted(m[k].keys())[:3])
    for f in [200,210,215]:
        if f in m[k]:
            try:
                s=tracks.mask_stats(m[k][f])
                print(k,f,s)
            except Exception as e:
                print(k,f,"empty",e)

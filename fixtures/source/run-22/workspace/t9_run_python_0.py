from helpers import masks_io, tracks
import json
masks=masks_io.load_masks("artifacts/t8_segment_0.npz")
print(masks.keys())
for k,v in masks.items():
    print(k, len(v), sorted(list(v.keys()))[:5], sorted(list(v.keys()))[-5:])
    # stats for few frames
    for f in [200,230,240,250,260,270,280,290,300]:
        if f in v:
            s=tracks.mask_stats(v[f])
            print(f" obj {k} frame {f} top={s['top']} bottom={s['bottom']} h={s['height']} w={s['width']} area={s['area']} cx={s['centroid']}")
    print("---")
with open("artifacts/t8_segment_stats_0.json") as f:
    st=json.load(f)
print(type(st), str(st)[:2000])

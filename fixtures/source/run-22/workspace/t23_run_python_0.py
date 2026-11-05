from helpers import masks_io, tracks
from helpers import ranges as R
import numpy as np
astro_masks=masks_io.load_masks("artifacts/t8_segment_0.npz")
print("objs", list(astro_masks.keys()))
for oid in astro_masks:
    m=astro_masks[oid]
    print("oid", oid, "n", len(m))
    for f in [200,218,236]:
        if f in m:
            try:
                s=tracks.mask_stats(m[f])
                print(f" oid {oid} f{f} top={s['top']} bot={s['bottom']} h={s['height']} w={s['width']} area={s['area']}")
            except Exception as e:
                print(oid,f,"empty")
# pack
pack=masks_io.load_masks("artifacts/t13_segment_0.npz")['0']
for f in [200,214,228]:
    s=tracks.mask_stats(pack[f])
    print(f" pack f{f} top={s['top']} bot={s['bottom']} h={s['height']} w={s['width']} area={s['area']}")
# extents at 200
for label, m in [("astro0", astro_masks['0'][200]), ("pack", pack[200])]:
    e=R.mask_extent(m, direction=(0,1))
    print(label, e)
# also flag
flag=masks_io.load_masks("artifacts/t20_segment_0.npz")['0']
for f in [200,218,236,254,272]:
    try:
        s=tracks.mask_stats(flag[f])
        print(f" flag f{f} top={s['top']} bot={s['bottom']} h={s['height']} w={s['width']} area={s['area']}")
    except: print("flag empty",f)

from helpers import masks_io, tracks
import json
masks=masks_io.load_masks("artifacts/t8_segment_0.npz")
m0=masks['0']
# bottom per frame
for f in sorted(m0.keys()):
    try:
        s=tracks.mask_stats(m0[f])
        print(f"{f} top={s['top']} bot={s['bottom']} h={s['height']} area={s['area']} cy={s['centroid']['y']:.1f} cx={s['centroid']['x']:.1f}")
    except Exception as e:
        print(f"{f} empty {e}")

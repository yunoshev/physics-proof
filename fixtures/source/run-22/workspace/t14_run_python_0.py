from helpers import masks_io, tracks
masks=masks_io.load_masks("artifacts/t13_segment_0.npz")
m=masks['0']
print(len(m))
for f in [200,210,220,230,235,240,243,244,245,250,255,260,265,270,273,275,280,285]:
    if f in m:
        try:
            s=tracks.mask_stats(m[f])
            print(f"{f} top={s['top']} bot={s['bottom']} h={s['height']} w={s['width']} area={s['area']} cy={s['centroid']['y']:.1f} cx={s['centroid']['x']:.1f}")
        except Exception as e:
            print(f, "empty")
    else:
        print(f,"missing")

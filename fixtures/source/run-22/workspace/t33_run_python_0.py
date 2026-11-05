from helpers import masks_io, tracks
m=masks_io.load_masks("artifacts/t27_segment_0.npz")
print(list(m.keys()))
for k in m:
    print("===",k)
    for f in sorted(m[k].keys()):
        try:
            s=tracks.mask_stats(m[k][f])
            print(f, s)
        except Exception as e:
            print(f,"empty")

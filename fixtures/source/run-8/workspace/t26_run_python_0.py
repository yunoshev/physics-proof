from helpers import masks_io, tracks, physics
import numpy as np, json
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')['0']
full=masks_io.load_masks('artifacts/t6_segment_0.npz')['1']
# choose scale frame 250 for backpack
f=250
m=bp[f]
# find extent: top/bottom of mask (largest component already? assume)
s=tracks.mask_stats(m)
print(s)
# precise vertical extent: use top/bottom, x = centroid_x
x=s['centroid_x']; y1=s['top']; y2=s['bottom']
print('backpack extent', x,y1,y2, 'len', y2-y1)
# full person height at frame 210 (standing) and 242 (extended)
for f2 in [205,210,242,243]:
    s2=tracks.mask_stats(full[f2])
    print(f2, s2['top'], s2['bottom'], s2['height'], s2['width'], round(s2['centroid_x'],1))
# flag pole stability already done
# compute scales
for L,size in [(67,0.66),(153,1.71)]:
    mpp, sig = physics.scale_from_reference(L, 2.0, size, 0.05)
    print(L,size,mpp,sig)

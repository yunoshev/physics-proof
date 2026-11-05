from helpers import masks_io, tracks, physics
import json, numpy as np
masks=masks_io.load_masks('artifacts/t6_segment_0.npz')
facts=masks_io.clip_facts('input/timing.json')
ts=facts['timestamps']

# tracks for obj 1 top_centre over 244-275 window
frames=list(range(244,276))
d={f:masks['1'][f] for f in frames}
tr=tracks.track_point(d, mode='top_centre', timestamps={f:float(ts[f]) for f in frames})
print(tr[:3], tr[-3:])
# quality
masks_by={'1':d}
print(tracks.track_quality(tr, masks_by, object_id='1'))

# also flag stability: load flag masks
mflag=masks_io.load_masks('artifacts/t8_segment_0.npz')
print('flag objs', list(mflag.keys()))
for f in [244,254,264,275]:
    s=tracks.mask_stats(mflag['0'][f])
    print(f, s['left'], s['top'], s['right'], s['bottom'], s['centroid_x'], s['centroid_y'])

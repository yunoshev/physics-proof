from helpers import masks_io, tracks
import json
masks=masks_io.load_masks('artifacts/t6_segment_0.npz')
print({k: sorted(v.keys())[:3] for k,v in masks.items()})
print({k: len(v) for k,v in masks.items()})
# stats for object 1 (foreground)
import numpy as np
facts=masks_io.clip_facts('input/timing.json')
ts={f: facts['timestamps'][f] for f in sorted(masks['1'].keys())}
# track points
for mode in ['top_centre','centroid','bottom_centre','lowest_point']:
    tr=tracks.track_point({f:masks['1'][f] for f in sorted(masks['1'].keys())}, mode=mode, timestamps=ts)
    print(mode, tr[0], tr[len(tr)//2])
# mask stats: bottom trajectory
for f in [235,240,241,245,250,253,260,265,270,275,276,280]:
    if f in masks['1']:
        s=tracks.mask_stats(masks['1'][f])
        print(f, 'top',s['top'],'bot',s['bottom'],'left',s['left'],'right',s['right'],'h',s['height'],'w',s['width'],'cy',round(s['centroid_y'],1))

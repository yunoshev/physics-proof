import json, os
print(os.listdir("artifacts"))
# attempt to understand check_mask extents by trying tool? Can't from here. Just prepare evidence draft.
from helpers import masks_io, tracks
from helpers import ranges as R, physics as P
import numpy as np, cv2
facts=masks_io.clip_facts("input/timing.json")
ts=facts["timestamps"]
# compute outline lengths already have
# compute scales
pack_ext=70.57619995437555
astro_ext=130.86252328302402
# sizes
plss_m=0.6604  # 26in
ops_m=0.254    # 10in
total_m=plss_m+ops_m
print(total_m, total_m/pack_ext, 1.70/astro_ext)
# fit
pack_all=masks_io.load_masks("artifacts/t13_segment_0.npz")['0']
tr=tracks.track_point({k:v for k,v in pack_all.items()}, mode="centroid", timestamps={k:float(ts[k]) for k in pack_all})
sel=[r for r in tr if 244<=r['frame']<=273]
t=np.array([r['t'] for r in sel]); y=np.array([r['y_px'] for r in sel])
res=P.fit_parabola(t,y)
print(res)
# repetitions
for s,e in [(244,258),(259,273)]:
    selx=[r for r in tr if s<=r['frame']<=e]
    tx=np.array([r['t'] for r in selx]); yx=np.array([r['y_px'] for r in selx])
    print(s,e,P.fit_parabola(tx,yx))

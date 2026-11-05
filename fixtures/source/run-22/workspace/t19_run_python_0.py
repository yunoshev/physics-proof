from helpers import masks_io, tracks, physics
import numpy as np
facts=masks_io.clip_facts("input/timing.json")
ts=facts["timestamps"]
pack=masks_io.load_masks("artifacts/t13_segment_0.npz")['0']
# centroid track
tr=tracks.track_point({k:v for k,v in pack.items()}, mode="centroid", timestamps={k:float(ts[k]) for k in pack})
# isolate 244-273
sel=[r for r in tr if 244<=r['frame']<=273]
t=np.array([r['t'] for r in sel])
y_px=np.array([r['y_px'] for r in sel])
print("n",len(sel))
# quick fit in px to see curvature: y_px = downward positive, so parabola opening upward for gravity? Actually y down, so gravity increases y -> a positive
# fit parabola
res=physics.fit_parabola(t, y_px)
print(res)
# also astro centroid for comparison
astro=masks_io.load_masks("artifacts/t8_segment_0.npz")['0']
tr2=tracks.track_point({k:v for k,v in astro.items()}, mode="centroid", timestamps={k:float(ts[k]) for k in astro})
sel2=[r for r in tr2 if 244<=r['frame']<=273]
t2=np.array([r['t'] for r in sel2])
y2=np.array([r['y_px'] for r in sel2])
print("astro", physics.fit_parabola(t2,y2))
# try larger window 244-275
for s,e in [(244,273),(245,272),(244,270)]:
    selx=[r for r in tr if s<=r['frame']<=e]
    tx=np.array([r['t'] for r in selx]); yx=np.array([r['y_px'] for r in selx])
    r=physics.fit_parabola(tx,yx)
    print(s,e, "a=",r['a'],"gapp=",r['g_app'],"rmse",r['rmse'],"trend_z",r['residual_trend_z'])

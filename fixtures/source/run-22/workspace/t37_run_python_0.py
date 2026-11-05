from helpers import masks_io, tracks
from helpers import ranges as R, physics as P
import json, cv2, numpy as np
facts=masks_io.clip_facts("input/timing.json")
ts=facts["timestamps"]
# outlines via contours
def outline_of(mask, max_pts=16):
    m=(mask.astype(np.uint8))*255
    cnts,_=cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts: return []
    c=max(cnts, key=cv2.contourArea)
    peri=cv2.arcLength(c, True)
    approx=cv2.approxPolyDP(c, 0.01*peri, True)
    pts=approx.reshape(-1,2)
    # if too many, simplify more
    if len(pts)>32:
        approx=cv2.approxPolyDP(c, 0.02*peri, True)
        pts=approx.reshape(-1,2)
    return [[float(x),float(y)] for x,y in pts]

pack=masks_io.load_masks("artifacts/t13_segment_0.npz")['0'][200]
astro=masks_io.load_masks("artifacts/t8_segment_0.npz")['0'][200]
print("pack outline", outline_of(pack)[:5], len(outline_of(pack)))
print("astro outline", outline_of(astro)[:5], len(outline_of(astro)))
# extents
print("pack extent", R.mask_extent(pack, direction=(0,1)))
print("astro extent", R.mask_extent(astro, direction=(0,1)))
# save outlines for evidence
import os
os.makedirs("workspace", exist_ok=True)
with open("workspace/outlines.json","w") as f:
    json.dump({"pack": outline_of(pack), "astro": outline_of(astro)}, f)
# build track + fit for segment
pack_all=masks_io.load_masks("artifacts/t13_segment_0.npz")['0']
tr=tracks.track_point({k:v for k,v in pack_all.items()}, mode="centroid", timestamps={k:float(ts[k]) for k in pack_all})
# restrict to 244-273
sel=[r for r in tr if 244<=r['frame']<=273]
print("sel n", len(sel))
t=np.array([r['t'] for r in sel])
y=np.array([r['y_px'] for r in sel])
x=np.array([r['x_px'] for r in sel])
res=P.fit_parabola(t, y)
print(res['a'], res['g_app_sigma'], res['rmse'], res['residual_trend_z'])
# also x drift linear?
# save track artifact
track_rows=[{"frame":r['frame'],"x_px":float(r['x_px']),"y_px":float(r['y_px'])} for r in sel]
with open("workspace/track_leap.json","w") as f:
    json.dump(track_rows, f)
print("wrote track", len(track_rows))
# fit curve px: y_fit = y0+v0*t+0.5*a*t^2 ; x_fit linear? For display, use measured x? Fit x linear
coefx=np.polyfit(t,x,1)
print("xfit", coefx)
curve=[]
for r in sel:
    tt=float(r['t']); 
    yf=float(res['y0']+res['v0']*tt+0.5*res['a']*tt*tt)
    xf=float(coefx[0]*tt+coefx[1])
    curve.append({"t_s":tt,"x_px":xf,"y_px":yf})
with open("workspace/curve.json","w") as f:
    json.dump(curve,f)
print(curve[:2], curve[-2:])
# flag track for camera
flag=masks_io.load_masks("artifacts/t20_segment_0.npz")['0']
trf=tracks.track_point({k:v for k,v in flag.items()}, mode="centroid", timestamps={k:float(ts[k]) for k in flag})
selF=[r for r in trf if 244<=r['frame']<=273]
rowsF=[{"frame":r['frame'],"x_px":float(r['x_px']),"y_px":float(r['y_px'])} for r in selF]
with open("workspace/ref_flag_track.json","w") as f:
    json.dump(rowsF,f)
print("flag track", len(rowsF))

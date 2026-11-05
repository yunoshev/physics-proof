from helpers import masks_io, tracks, physics
import json, numpy as np, pathlib
facts=masks_io.clip_facts("input/timing.json")
masks_bp=masks_io.load_masks("artifacts/t12_segment_0.npz")
masks_full=masks_io.load_masks("artifacts/t7_segment_0.npz")
masks_flag=masks_io.load_masks("artifacts/t14_segment_0.npz")

# --- scale frame 255 backpack
f_scale=255
s=tracks.mask_stats(masks_bp["0"][f_scale])
print(s)
# extent endpoints: use left-right mid? Actually vertical extent: x = (left+right)/2, y top->bottom
x_mid=(s["left"]+s["right"])/2
x1=x_mid; y1=float(s["top"]); x2=x_mid; y2=float(s["bottom"])
length=float(abs(y2-y1))
print(x1,y1,x2,y2,length)
# scale
size_m=0.66; size_tol=0.05  # use 0.05 to be safe (source spread 0.66 vs 0.80? EMU 0.66 vs 0.80)
extent_sigma=2.0
mpp, sig_mpp=physics.scale_from_reference(length, extent_sigma, size_m, size_tol)
print(f"mpp {mpp} sig {sig_mpp}")

# --- tracks
ts_bp={f:float(facts["timestamps"][f]) for f in sorted(masks_bp["0"].keys())}
tr_bpc=tracks.track_point(masks_bp["0"], mode="centroid", timestamps=ts_bp)
sel=[r for r in tr_bpc if 246<=r["frame"]<=275]
print("sel n",len(sel))
# save track artifact
track_rows=[{"frame":r["frame"],"t":r["t"],"x_px":r["x_px"],"y_px":r["y_px"]} for r in sel]
open("workspace/track_hop_a.json","w").write(json.dumps(track_rows))
print("wrote track",len(track_rows))

# flag ref track (centroid) for camera
ts_flag={f:float(facts["timestamps"][f]) for f in sorted(masks_flag["0"].keys())}
tr_flag=tracks.track_point(masks_flag["0"], mode="centroid", timestamps=ts_flag)
ref_rows=[{"frame":r["frame"],"t":r["t"],"x_px":r["x_px"],"y_px":r["y_px"]} for r in tr_flag if 246<=r["frame"]<=275]
open("workspace/ref_flag_track.json","w").write(json.dumps(ref_rows))
print("wrote ref",len(ref_rows))

# --- fit main
pts=physics.track_to_metres(sel,(mpp,sig_mpp),origin=(0,186.0))
t=np.array([p["t"]-pts["points"][0]["t"] for p in pts["points"]])
y=np.array([p["y_m"] for p in pts["points"]])
fit=physics.fit_parabola(t,y)
print("main fit",fit["g_app"],fit["g_app_sigma"],fit["residual_trend"],fit["rmse"])
# takeoff level
print("takeoff y 186, bottom at 245-246", tracks.mask_stats(masks_full["1"][245])["bottom"], tracks.mask_stats(masks_full["1"][246])["bottom"])
# apex frame: min y_px in sel
apex=min(sel,key=lambda r:r["y_px"])
print("apex",apex)
# fit curve in px: need x_px linear + y_px parabola
# fit x linear: x_px vs t
import numpy as np
tt=np.array([r["t"]-sel[0]["t"] for r in sel])
xx=np.array([r["x_px"] for r in sel])
# linear fit x = x0+vx*t (in px)
A=np.vstack([np.ones_like(tt),tt]).T
coeff,res,_,_=np.linalg.lstsq(A,xx,rcond=None)
x0_px, vx_px=coeff[0],coeff[1]
print("x lin",x0_px,vx_px)
# y fit in px: convert metre fit back to px: y_px = origin_y - y_m/mpp
y0,v0,a=fit["y0"],fit["v0"],fit["a"]
# sample curve at each sel t
curve=[]
for r in sel:
    dt=r["t"]-sel[0]["t"]
    ym=y0+v0*dt+0.5*a*dt*dt
    ypx=186.0-ym/mpp
    xpx=float(x0_px+vx_px*dt)
    curve.append({"t_s":float(r["t"]-sel[0]["t"]),"x_px":float(xpx),"y_px":float(ypx)})
print(curve[:2],curve[-2:])
open("workspace/fit_curve_tmp.json","w").write(json.dumps(curve))
# outline simplification for backpack at 255
mask=masks_bp["0"][255]
# find contour via opencv
import cv2
m8=(mask.astype(np.uint8))*255
contours,_=cv2.findContours(m8,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
cnt=max(contours,key=cv2.contourArea)
peri=cv2.arcLength(cnt,True)
eps=0.01*peri
approx=cv2.approxPolyDP(cnt,eps,True)
print("contour pts",len(cnt),"approx",len(approx))
outline=[[float(p[0][0]),float(p[0][1])] for p in approx]
print(outline[:10])
# ensure <=256
# also cap to 32 pts if needed (already small)
open("workspace/outline_tmp.json","w").write(json.dumps(outline))
# repetitions
for a,b in [(246,260),(261,275)]:
    sh=[r for r in tr_bpc if a<=r["frame"]<=b]
    ph=physics.track_to_metres(sh,(mpp,sig_mpp),origin=(0,186.0))
    th=np.array([p["t"]-ph["points"][0]["t"] for p in ph["points"]])
    yh=np.array([p["y_m"] for p in ph["points"]])
    fh=physics.fit_parabola(th,yh)
    print(a,b,fh["g_app"],fh["g_app_sigma"],fh["residual_trend"])

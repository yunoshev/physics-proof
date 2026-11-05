from helpers import masks_io, tracks, physics
import json, numpy as np
facts=masks_io.clip_facts("input/timing.json")
masks_bp=masks_io.load_masks("artifacts/t12_segment_0.npz")
masks_full=masks_io.load_masks("artifacts/t7_segment_0.npz")
masks_flag=masks_io.load_masks("artifacts/t14_segment_0.npz")

# scale: backpack height at frame 255
f_scale=255
s=tracks.mask_stats(masks_bp["0"][f_scale])
print(s)
# extent: vertical: x mid, y top-bottom
x1=x2=(s["left"]+s["right"])/2
y1=s["top"]; y2=s["bottom"]
length=np.hypot(x2-x1, y2-y1)
print(x1,y1,x2,y2,length)
# scale_from_reference
mpp, sig = physics.scale_from_reference(length, 2.0, 0.66, 0.03)
print(mpp, sig)
# second: width as check? but need different object - skip
# flag for camera top track
ts_flag={f:float(facts["timestamps"][f]) for f in sorted(masks_flag["0"].keys())}
tr_flag_top=tracks.track_point(masks_flag["0"], mode="top_centre", timestamps=ts_flag)
xs=[r["x_px"] for r in tr_flag_top if 246<=r["frame"]<=275]
ys=[r["y_px"] for r in tr_flag_top if 246<=r["frame"]<=275]
print("flag top x",min(xs),max(xs),max(xs)-min(xs))
print("flag top y",min(ys),max(ys),max(ys)-min(ys))
# backpack centroid track for hop
ts_bp={f:float(facts["timestamps"][f]) for f in sorted(masks_bp["0"].keys())}
tr_bpc=tracks.track_point(masks_bp["0"], mode="centroid", timestamps=ts_bp)
sel=[r for r in tr_bpc if 246<=r["frame"]<=275]
print(len(sel))
pts=physics.track_to_metres(sel, (mpp, sig), origin=(0,186.0))
t=np.array([p["t"]-pts["points"][0]["t"] for p in pts["points"]])
y=np.array([p["y_m"] for p in pts["points"]])
fit=physics.fit_parabola(t,y)
print(fit)
# halves
for a,b in [(246,260),(261,275)]:
    sh=[r for r in tr_bpc if a<=r["frame"]<=b]
    ph=physics.track_to_metres(sh,(mpp,sig),origin=(0,186.0))
    th=np.array([p["t"]-ph["points"][0]["t"] for p in ph["points"]])
    yh=np.array([p["y_m"] for p in ph["points"]])
    print(a,b,physics.fit_parabola(th,yh))

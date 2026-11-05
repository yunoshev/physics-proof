from helpers import masks_io, tracks, physics
import json, numpy as np
facts=masks_io.clip_facts("input/timing.json")
masks_bp=masks_io.load_masks("artifacts/t12_segment_0.npz")
ts_bp={f:float(facts["timestamps"][f]) for f in sorted(masks_bp["0"].keys())}
tr=tracks.track_point(masks_bp["0"], mode="centroid", timestamps=ts_bp)
length=67.0; ext_sig=2.0; size_m=0.66; size_tol=0.05
mpp, sig_mpp=physics.scale_from_reference(length, ext_sig, size_m, size_tol)
print(mpp,sig_mpp)
def fit_win(a,b):
    sel=[r for r in tr if a<=r["frame"]<=b]
    pts=physics.track_to_metres(sel,(mpp,sig_mpp),origin=(0,186.0))
    t=np.array([p["t"]-pts["points"][0]["t"] for p in pts["points"]])
    y=np.array([p["y_m"] for p in pts["points"]])
    f=physics.fit_parabola(t,y)
    return sel,f
sel_main,fmain=fit_win(246,274)
print("main",fmain["g_app"],fmain["g_app_sigma"],fmain["residual_trend"],fmain["rmse"],"n",fmain["n"])
for a,b in [(246,260),(261,274)]:
    s,f=fit_win(a,b)
    print(a,b,"g",f["g_app"],"sig",f["g_app_sigma"],"trend",f["residual_trend"],"n",f["n"])
# point vs com using full centroid
masks_full=masks_io.load_masks("artifacts/t7_segment_0.npz")
ts_full={f:float(facts["timestamps"][f]) for f in sorted(masks_full["1"].keys())}
tr_full=tracks.track_point(masks_full["1"], mode="centroid", timestamps=ts_full)
sel2=[r for r in tr_full if 246<=r["frame"]<=274]
pts2=physics.track_to_metres(sel2,(mpp,sig_mpp),origin=(0,186.0))
t2=np.array([p["t"]-pts2["points"][0]["t"] for p in pts2["points"]])
y2=np.array([p["y_m"] for p in pts2["points"]])
f2=physics.fit_parabola(t2,y2)
print("full",f2["g_app"])

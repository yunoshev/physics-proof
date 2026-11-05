from helpers import masks_io, tracks, physics
import json, numpy as np
facts=masks_io.clip_facts("input/timing.json")
masks_bp=masks_io.load_masks("artifacts/t12_segment_0.npz")
ts_bp={f:float(facts["timestamps"][f]) for f in sorted(masks_bp["0"].keys())}
tr_bpc=tracks.track_point(masks_bp["0"], mode="centroid", timestamps=ts_bp)
# scale numbers
length=67.0; ext_sig=2.0; size_m=0.66; size_tol=0.05
mpp, sig_mpp=physics.scale_from_reference(length, ext_sig, size_m, size_tol)
print(mpp, sig_mpp)
# main 246-274
sel=[r for r in tr_bpc if 246<=r["frame"]<=274]
pts=physics.track_to_metres(sel,(mpp,sig_mpp),origin=(0,186.0))
t=np.array([p["t"]-pts["points"][0]["t"] for p in pts["points"]])
y=np.array([p["y_m"] for p in pts["points"]])
fit=physics.fit_parabola(t,y)
print("main",fit["g_app"],fit["g_app_sigma"])
# reps
for a,b in [(246,260),(261,274)]:
    sh=[r for r in tr_bpc if a<=r["frame"]<=b]
    ph=physics.track_to_metres(sh,(mpp,sig_mpp),origin=(0,186.0))
    th=np.array([p["t"]-ph["points"][0]["t"] for p in ph["points"]])
    yh=np.array([p["y_m"] for p in ph["points"]])
    fh=physics.fit_parabola(th,yh)
    print(a,b,fh["g_app"],fh["g_app_sigma"])
# error components
g=fit["g_app"]
ref_c=g*size_tol/size_m
px_c=g*ext_sig/length
fit_c=fit["g_app_sigma"]
print("ref",ref_c,"px",px_c,"fit",fit_c)
# point vs com: compare backpack centroid vs full-body centroid fit (246-274)
masks_full=masks_io.load_masks("artifacts/t7_segment_0.npz")
ts_full={f:float(facts["timestamps"][f]) for f in sorted(masks_full["1"].keys())}
tr_full=tracks.track_point(masks_full["1"], mode="centroid", timestamps=ts_full)
sel2=[r for r in tr_full if 246<=r["frame"]<=274]
pts2=physics.track_to_metres(sel2,(mpp,sig_mpp),origin=(0,186.0))
t2=np.array([p["t"]-pts2["points"][0]["t"] for p in pts2["points"]])
y2=np.array([p["y_m"] for p in pts2["points"]])
fit2=physics.fit_parabola(t2,y2)
print("fullcent",fit2["g_app"])
print("point diff",abs(g-fit2["g_app"]))
# repetition spread: std of [1.1214,1.0394] vs main?
import numpy as np
reps=np.array([1.1214766814132977,1.0394505895358979])
print("rep std pop",reps.std(ddof=0),"spread half-range",abs(reps[0]-reps[1])/2, "mean",reps.mean())
# sigma total quadrature
comps=np.array([ref_c,px_c,fit_c,abs(g-fit2["g_app"]),reps.std(ddof=0)])
print("quad",np.sqrt((comps**2).sum()))
print("rel",np.sqrt((comps**2).sum())/g)

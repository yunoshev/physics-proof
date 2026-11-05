import json
from helpers import masks_io, tracks, physics
import numpy as np
facts=masks_io.clip_facts("input/timing.json")
masks_bp=masks_io.load_masks("artifacts/t12_segment_0.npz")
ts_bp={f:float(facts["timestamps"][f]) for f in sorted(masks_bp["0"].keys())}
tr=tracks.track_point(masks_bp["0"], mode="centroid", timestamps=ts_bp)
mpp=0.009850746268656717; sig=0.0005356834331214545
sel=[r for r in tr if 246<=r["frame"]<=274]
pts=physics.track_to_metres(sel,(mpp,sig),origin=(0,186.0))
t0=sel[0]["t"]
t_rel=np.array([p["t"]-t0 for p in pts["points"]])
y=np.array([p["y_m"] for p in pts["points"]])
fit=physics.fit_parabola(t_rel,y)
print(fit)
# rebuild curve with absolute t_s
tt_abs=np.array([r["t"] for r in sel])
xx=np.array([r["x_px"] for r in sel])
A=np.vstack([np.ones_like(tt_abs),tt_abs]).T
coeff,_,_,_=np.linalg.lstsq(A,xx,rcond=None)
print("x abs fit",coeff)
y0,v0,a=fit["y0"],fit["v0"],fit["a"]
curve=[]
for r in sel:
    dt=r["t"]-t0
    ym=y0+v0*dt+0.5*a*dt*dt
    ypx=186.0-ym/mpp
    # x from abs fit
    xpx=float(coeff[0]+coeff[1]*r["t"])
    curve.append({"t_s":float(r["t"]),"x_px":float(xpx),"y_px":float(ypx)})
print(curve[0],curve[len(curve)//2],curve[-1])
open("workspace/fit_curve.json","w").write(json.dumps(curve))
# update evidence
ev=json.load(open("workspace/evidence.json"))
ev["segments"][0]["fit_curve_px"]=curve
open("workspace/evidence.json","w").write(json.dumps(ev))
print("updated curve len",len(curve))

from helpers import masks_io, tracks, physics
import json, numpy as np
facts=masks_io.clip_facts("input/timing.json")
length=67.0; ext_sig=2.0; size_m=0.66; size_tol=0.03
mpp, sig=physics.scale_from_reference(length, ext_sig, size_m, size_tol)
print(mpp, sig)
g=1.176821560760549
ref_c=g*size_tol/size_m
px_c=g*ext_sig/length
fit_c=0.029488126218625413
pv_c=0.04936038031750245
rep_c=0.037758225752962615
import math
tot=math.sqrt(ref_c**2+px_c**2+fit_c**2+pv_c**2+rep_c**2)
print(ref_c,px_c,fit_c,pv_c,rep_c,tot,tot/g)
# flag top track rebuild
masks_flag=masks_io.load_masks("artifacts/t14_segment_0.npz")
ts_flag={f:float(facts["timestamps"][f]) for f in sorted(masks_flag["0"].keys())}
tr_flag_top=tracks.track_point(masks_flag["0"], mode="top_centre", timestamps=ts_flag)
ref_rows=[{"frame":r["frame"],"t":r["t"],"x_px":float(r["x_px"]),"y_px":float(r["y_px"])} for r in tr_flag_top if 246<=r["frame"]<=274]
open("workspace/ref_flag_track.json","w").write(json.dumps(ref_rows))
print(ref_rows[:2], ref_rows[-2:])
xs=[r["x_px"] for r in ref_rows]; ys=[r["y_px"] for r in ref_rows]
print("x rng",max(xs)-min(xs),"y rng",max(ys)-min(ys))

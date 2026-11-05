from helpers import masks_io, tracks, physics
import numpy as np
facts=masks_io.clip_facts("input/timing.json")
masks_bp=masks_io.load_masks("artifacts/t12_segment_0.npz")
ts_bp={f:float(facts["timestamps"][f]) for f in sorted(masks_bp["0"].keys())}
tr=tracks.track_point(masks_bp["0"], mode="centroid", timestamps=ts_bp)
mpp=0.66/67
for a,b in [(246,254),(247,255),(248,256),(246,260),(250,260),(252,262),(246,274)]:
    sel=[r for r in tr if a<=r["frame"]<=b]
    if len(sel)<4: continue
    pts=physics.track_to_metres(sel,(mpp,0),origin=(0,186.0))
    t=np.array([p["t"]-pts["points"][0]["t"] for p in pts["points"]])
    y=np.array([p["y_m"] for p in pts["points"]])
    try:
        fit=physics.fit_parabola(t,y)
        print(a,b,len(sel),round(fit["g_app"],3),round(fit["g_app_sigma"],3),round(fit["rmse"],5))
    except Exception as e:
        print(a,b,"fail",e)
# show y series
sel=[r for r in tr if 246<=r["frame"]<=275]
pts=physics.track_to_metres(sel,(mpp,0),origin=(0,186.0))
for p in pts["points"]:
    print(p["frame"],round(p["y_m"],4))

from helpers import masks_io, tracks, physics
import numpy as np
facts=masks_io.clip_facts("input/timing.json")
ts_all={f:float(facts["timestamps"][f]) for f in range(facts["frame_count"])}
masks_full=masks_io.load_masks("artifacts/t7_segment_0.npz")
masks_bp=masks_io.load_masks("artifacts/t12_segment_0.npz")
# backpack centroid track
ts_bp={f:float(facts["timestamps"][f]) for f in sorted(masks_bp["0"].keys())}
tr_bpc=tracks.track_point(masks_bp["0"], mode="centroid", timestamps=ts_bp)
for r in tr_bpc:
    if r["frame"] in [246,252,254,260,274]:
        print(r)
# fit backpack centroid 246-274
sel=[r for r in tr_bpc if 246<=r["frame"]<=274]
print("n",len(sel))
# scale
mpp=0.66/68
origin_y=186 # ground
pts=physics.track_to_metres(sel, mpp, origin=(0,origin_y))
t=np.array([p["t"]-pts["points"][0]["t"] for p in pts["points"]])
y=np.array([p["y_m"] for p in pts["points"]])
print("t span",t[-1], "y",y[:5], y[len(y)//2-2:len(y)//2+3], y[-5:])
fit=physics.fit_parabola(t,y)
print("bp centroid fit",fit)
# also top_centre of full (backpack top)
ts_full={f:float(facts["timestamps"][f]) for f in sorted(masks_full["1"].keys())}
for mode in ["top_centre","centroid"]:
    tr=tracks.track_point(masks_full["1"], mode=mode, timestamps=ts_full)
    sel2=[r for r in tr if 246<=r["frame"]<=274]
    pts2=physics.track_to_metres(sel2, mpp, origin=(0,origin_y))
    t2=np.array([p["t"]-pts2["points"][0]["t"] for p in pts2["points"]])
    y2=np.array([p["y_m"] for p in pts2["points"]])
    print(mode, physics.fit_parabola(t2,y2))
# try bottom exclusion: contact frames? bottom flat at 186 before 246 and after 275, so 246-274 excludes contact, good
# halves for repetition spread
for a,b in [(246,260),(260,274),(246,274)]:
    selh=[r for r in tr_bpc if a<=r["frame"]<=b]
    ptsh=physics.track_to_metres(selh, mpp, origin=(0,origin_y))
    th=np.array([p["t"]-ptsh["points"][0]["t"] for p in ptsh["points"]])
    yh=np.array([p["y_m"] for p in ptsh["points"]])
    print(a,b, physics.fit_parabola(th,yh))

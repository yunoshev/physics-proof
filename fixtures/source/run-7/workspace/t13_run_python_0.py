from helpers import masks_io, tracks, physics, clock
import numpy as np, json
masks_bp=masks_io.load_masks("artifacts/t12_segment_0.npz")
print(masks_bp.keys())
frames=sorted(masks_bp["0"].keys())
for f in frames[::5]:
    s=tracks.mask_stats(masks_bp["0"][f])
    print(f, s)
facts=masks_io.clip_facts("input/timing.json")
# try outline simplification later; first get extents
# foreground full masks
masks_full=masks_io.load_masks("artifacts/t7_segment_0.npz")
# check backpack vs full overlap at same frame 255
import numpy as np
f=255
a=masks_full["1"][f]
b=masks_bp["0"][f]
print("areas", a.sum(), b.sum(), (a&b).sum(), (a&b).sum()/b.sum())
# also flag idea: need static ref - will segment later
# quick fit test: use top_centre track 246-274
ts={ff:float(facts["timestamps"][ff]) for ff in sorted(masks_full["1"].keys())}
tr=tracks.track_point(masks_full["1"], mode="centroid", timestamps=ts)
# filter 246-274
sel=[r for r in tr if 246<=r["frame"]<=274]
print(sel[:3], sel[-3:])
# scale guess: backpack height px?
s255=tracks.mask_stats(masks_bp["0"][255])
print("bp255",s255, "h",s255["bottom"]-s255["top"]+1)
# scale from 0.66m
hpx=s255["bottom"]-s255["top"]+1
mpp=0.66/hpx
print("mpp guess",mpp)
# convert centroid track to metres, origin at takeoff ground?
# origin y = takeoff ground level ~186 px? Actually track_to_metres origin
pts=physics.track_to_metres(sel, mpp, origin=(0,186))
print(pts["points"][:3])
t=np.array([p["t"]-pts["points"][0]["t"] for p in pts["points"]])
y=np.array([p["y_m"] for p in pts["points"]])
print("t",t[:5], "y",y[:5])
fit=physics.fit_parabola(t,y)
print(fit)

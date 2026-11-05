from helpers import masks_io, tracks
masks=masks_io.load_masks("artifacts/t7_segment_0.npz")
import json
facts=masks_io.clip_facts("input/timing.json")
ts={f:float(facts["timestamps"][f]) for f in sorted(masks["0"].keys())}
for mode in ["centroid","top_centre","bottom_centre"]:
    tr=tracks.track_point(masks["0"], mode=mode, timestamps=ts)
    print(mode, [(r["frame"],round(r["x_px"],1),round(r["y_px"],1)) for r in tr if r["frame"]%10==0][:10])
    sel=[r for r in tr if 225<=r["frame"]<=315]
    ys=[r["y_px"] for r in sel]
    xs=[r["x_px"] for r in sel]
    print("  y range",min(ys),max(ys),max(ys)-min(ys),"x range",min(xs),max(xs))
# stats for object 0
for f in [225,235,245,250,255,260,265,270,275,285,295]:
    s=tracks.mask_stats(masks["0"][f])
    print(f,s)

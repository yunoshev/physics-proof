from helpers import masks_io, tracks, physics, clock
import numpy as np, json
facts=masks_io.clip_facts("input/timing.json")
masks_full=masks_io.load_masks("artifacts/t7_segment_0.npz")
masks_bp=masks_io.load_masks("artifacts/t12_segment_0.npz")
masks_flag=masks_io.load_masks("artifacts/t14_segment_0.npz")
print("flag frames", sorted(masks_flag["0"].keys())[:3], sorted(masks_flag["0"].keys())[-3:])
for f in [246,255,265,274]:
    s=tracks.mask_stats(masks_flag["0"][f])
    print(f,s)
# centroid flag track for camera
ts_flag={f:float(facts["timestamps"][f]) for f in sorted(masks_flag["0"].keys())}
tr_flag=tracks.track_point(masks_flag["0"], mode="centroid", timestamps=ts_flag)
print(tr_flag[:3])
print(tr_flag[-3:])
# range of flag centroid over fit window 246-274
xs=[r["x_px"] for r in tr_flag if 246<=r["frame"]<=274]
ys=[r["y_px"] for r in tr_flag if 246<=r["frame"]<=274]
print("flag x range", min(xs), max(xs), max(xs)-min(xs))
print("flag y range", min(ys), max(ys), max(ys)-min(ys))
# backpack stats full window
for f in [246,255,265,274,275]:
    if f in masks_bp["0"]:
        s=tracks.mask_stats(masks_bp["0"][f])
        print("bp",f,s)
# full body stats apex search
ts_full={f:float(facts["timestamps"][f]) for f in sorted(masks_full["1"].keys())}
tr_top=tracks.track_point(masks_full["1"], mode="top_centre", timestamps=ts_full)
tr_cent=tracks.track_point(masks_full["1"], mode="centroid", timestamps=ts_full)
# find apex (min y_px = highest) in 246-274
sel_top=[r for r in tr_top if 246<=r["frame"]<=274]
sel_cent=[r for r in tr_cent if 246<=r["frame"]<=274]
print("top apex", min(sel_top, key=lambda r:r["y_px"]))
print("cent apex", min(sel_cent, key=lambda r:r["y_px"]))
# also bottom min?
# gait signal over walking intervals: use full masks 225-315
masks_for_gait={f:masks_full["1"][f] for f in sorted(masks_full["1"].keys())}
gait=clock.gait_signal(masks_for_gait, timestamps={f:float(facts["timestamps"][f]) for f in masks_for_gait})
print("gait len",len(gait), gait[:3], gait[len(gait)//2])
# step_rate over full?
import numpy as np
sig=np.array([g["signal"] for g in gait])
t=np.array([g["t"] for g in gait])
print("sig mean",sig.mean(),"std",sig.std())
res=clock.step_rate(sig,t,band_hz=(0.5,4.0))
print(res)
# try walking only before hop 225-245
sel_idx=[i for i,g in enumerate(gait) if 225<=g["frame"]<=245]
sig2=sig[sel_idx]; t2=t[sel_idx]
print("pre len",len(sig2))
try:
    print(clock.step_rate(sig2,t2,band_hz=(0.5,4.0)))
except Exception as e:
    print("pre fail",e)
# walking after 275-315
sel_idx2=[i for i,g in enumerate(gait) if 275<=g["frame"]<=315]
sig3=sig[sel_idx2]; t3=t[sel_idx2]
print("post len",len(sig3))
try:
    print(clock.step_rate(sig3,t3,band_hz=(0.5,4.0)))
except Exception as e:
    print("post fail",e)

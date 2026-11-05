from helpers import masks_io, tracks, physics
import json, numpy as np
masks=masks_io.load_masks("artifacts/t7_segment_0.npz")
facts=masks_io.clip_facts("input/timing.json")
# check qual
tr_top=tracks.track_point(masks["1"], mode="top_centre", timestamps={f:float(facts["timestamps"][f]) for f in masks["1"]})
tr_c=tracks.track_point(masks["1"], mode="centroid", timestamps={f:float(facts["timestamps"][f]) for f in masks["1"]})
# bottom series to find takeoff/landing
frames=sorted(masks["1"].keys())
bots=[tracks.mask_stats(masks["1"][f])["bottom"] for f in frames]
tops=[tracks.mask_stats(masks["1"][f])["top"] for f in frames]
print("frames",frames[0],frames[-1])
# print around takeoff landing
for f,b,t in zip(frames,bots,tops):
    if 240<=f<=280:
        print(f,b,t)
# quality
print(tracks.track_quality(tr_top, {"1":masks["1"]}, object_id="1"))
print(tracks.track_quality(tr_c, {"1":masks["1"]}, object_id="1"))

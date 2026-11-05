from helpers import masks_io, tracks, physics
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
facts=masks_io.clip_facts("input/timing.json")
import numpy as np
ts={f: facts["timestamps"][f] for f in range(facts["frame_count"])}
tr=tracks.track_point(m_pack, mode="centroid", timestamps=ts)
# try window 136-150
t=np.array([r["t"] for r in tr if 136<=r["frame"]<=150])
ypx=np.array([r["y_px"] for r in tr if 136<=r["frame"]<=150])
print(len(t), t[0], t[-1])
# assume scale 0.01 for now to get g in px/s2 then convert
# fit y_px vs t (y grows down, so parabola opens upward: y = y0 + vy*t +0.5*a*t2 with a positive for gravity? In pixel coords gravity is +y. So fit directly, g_px = a)
res=physics.fit_parabola(t, ypx)
print(res)
# also try 135-152
t2=np.array([r["t"] for r in tr if 135<=r["frame"]<=152])
ypx2=np.array([r["y_px"] for r in tr if 135<=r["frame"]<=152])
print(physics.fit_parabola(t2, ypx2))
# try bottom? 

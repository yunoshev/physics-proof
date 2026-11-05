from helpers import masks_io, clock
import numpy as np
facts=masks_io.clip_facts("input/timing.json")
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
for (a,b) in [(0,100),(10,100),(20,110),(30,120),(0,130),(40,120),(50,130),(60,130)]:
    sub={f:m_fig[f] for f in range(a,b)}
    sig=clock.gait_signal(sub)
    t=np.array([facts["timestamps"][f] for f in range(a,b)])
    s=np.array([r["gait"] for r in sig])
    for band in [(1.0,4.0),(0.8,3.0),(1.0,3.0)]:
        try:
            res,flag=clock.step_rate(s,t,band_hz=band)
            print(f"{a}-{b} band{band} -> {res} flag {flag}")
        except Exception as e:
            print(f"{a}-{b} band{band} err {e}")

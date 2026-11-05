from helpers import masks_io, clock
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
facts=masks_io.clip_facts("input/timing.json")
import numpy as np
ts=np.array([facts["timestamps"][f] for f in sorted(m_fig.keys())])
# gait signal full
sig=clock.gait_signal(m_fig)
print(len(sig))
# try step_rate over walking 0-120
sub={f:m_fig[f] for f in range(0,120)}
sig2=clock.gait_signal(sub)
t2=np.array([facts["timestamps"][f] for f in range(0,120)])
s2=np.array([r["gait"] for r in sig2])
print("sig mean", s2.mean())
res,flag=clock.step_rate(s2, t2, band_hz=(1.0,4.0))
print("res", res, "flag", flag)
# also 20-100
sub2={f:m_fig[f] for f in range(20,110)}
sig3=clock.gait_signal(sub2)
t3=np.array([facts["timestamps"][f] for f in range(20,110)])
s3=np.array([r["gait"] for r in sig3])
res2,flag2=clock.step_rate(s3, t3, band_hz=(1.0,4.0))
print("res2", res2, "flag2", flag2)

from helpers import masks_io, tracks, physics
import numpy as np
facts=masks_io.clip_facts("input/timing.json")
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
ts={f: facts["timestamps"][f] for f in range(facts["frame_count"])}
tr_pack=tracks.track_point(m_pack, mode="centroid", timestamps=ts)
def test(a,b):
    sel=[r for r in tr_pack if a<=r["frame"]<=b]
    t=np.array([r["t"] for r in sel]); y=np.array([r["y_px"] for r in sel])
    res=physics.fit_parabola(t,y)
    print(f"{a}-{b} n={len(sel)} a={res['a']:.1f} sigma={res['g_app_sigma']:.1f} rmse={res['rmse']:.3f} trend={res['residual_trend_z']:.2f}")
for w in [(136,150),(137,149),(136,151),(137,150),(138,150),(136,149),(135,152),(135,151),(137,151),(138,149),(139,149),(137,148)]:
    test(*w)

from helpers import masks_io, ranges, tracks, physics
import json, math
facts=masks_io.clip_facts("input/timing.json")
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
# extents at frame 10
e_fig_raw=ranges.mask_extent(m_fig[10], direction=(0,1))
e_pack_raw=ranges.mask_extent(m_pack[10], direction=(0,1))
print(e_fig_raw, e_pack_raw)
# pack scale
size_pack=0.914
tol_pack=0.03
e_pack_len=float(e_pack_raw["length_px"])
m_pack_scale=size_pack/e_pack_len
sig_pack=m_pack_scale*math.sqrt((tol_pack/size_pack)**2+(math.sqrt(2)/e_pack_len)**2)
print(f"pack scale {m_pack_scale} sigma {sig_pack}")
# figure scale with 1.59
size_fig=1.59
tol_fig=0.10
e_fig_len=float(e_fig_raw["length_px"])
m_fig_scale=size_fig/e_fig_len
sig_fig=m_fig_scale*math.sqrt((tol_fig/size_fig)**2+(math.sqrt(2)/e_fig_len)**2)
print(f"fig scale {m_fig_scale} sigma {sig_fig}")
# agreement: diff / combined sigma
diff=abs(m_pack_scale-m_fig_scale)
comb=math.sqrt(sig_pack**2+sig_fig**2)
print(f"diff {diff} comb {comb} diff/comb {diff/comb} 2sigma? {diff/comb<=2}")
print(f"gap {(max(m_pack_scale,m_fig_scale)/min(m_pack_scale,m_fig_scale)-1)*100:.2f}%")
# combined scale inverse-variance weighted
w1=1/sig_pack**2
w2=1/sig_fig**2
m_comb=(m_pack_scale*w1+m_fig_scale*w2)/(w1+w2)
sig_comb=math.sqrt(1/(w1+w2))
print(f"combined {m_comb} sigma {sig_comb}")
# g with combined?
ts={f: facts["timestamps"][f] for f in range(facts["frame_count"])}
tr_pack=tracks.track_point(m_pack, mode="centroid", timestamps=ts)
import numpy as np
sel=[r for r in tr_pack if 136<=r["frame"]<=150]
t=np.array([r["t"] for r in sel]); y=np.array([r["y_px"] for r in sel])
res=physics.fit_parabola(t,y)
print(res)
g_comb=res["g_app"]*m_comb
print(f"g_comb {g_comb}")
# fit sigma
g_fit_sig=res["g_app_sigma"]*m_comb
print(f"g_fit_sig {g_fit_sig}")
# total error budget with reading_spread 1.013? Let's compute components in g units using combined scale?
# reference_size: from size tolerances? Approx g* size_rel? For combined, size_rel? Use pack+fig? Let's approximate reference_size = g* sqrt((tol_pack/size_pack)^2 weighted?) Simpler keep previous components but update scale.
# For now compute required reading_spread: half diff pack vs lower (0.914-0.66)/2=0.127 relative 0.127/0.914=0.139 *g
spread=0.127/0.914*g_comb
print(f"reading spread {spread}")

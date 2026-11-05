from helpers import masks_io, ranges, tracks, physics
import json, math
facts=masks_io.clip_facts("input/timing.json")
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
m_flag=masks_io.load_masks("artifacts/t25_segment_0.npz")["0"]
e_fig_raw=ranges.mask_extent(m_fig[10], direction=(0,1))
e_pack_raw=ranges.mask_extent(m_pack[10], direction=(0,1))
print(e_fig_raw, e_pack_raw)
# headline size 0.66+0.254=0.914
size_m=0.914
size_tol=0.03
e_pack_len=float(e_pack_raw["length_px"])
m_per_px=size_m/e_pack_len
px_rel=math.sqrt(2)/e_pack_len
sig_rel=math.sqrt((size_tol/size_m)**2+px_rel**2)
sigma_m=m_per_px*sig_rel
print(f"m_per_px={m_per_px} sigma={sigma_m}")
# lengths
e_fig={"name":"figure","x1":float(e_fig_raw["x1"]),"y1":float(e_fig_raw["y1"]),"x2":float(e_fig_raw["x2"]),"y2":float(e_fig_raw["y2"]),"length_px":float(e_fig_raw["length_px"]),"frame":10}
e_pack_d={"name":"pack","x1":float(e_pack_raw["x1"]),"y1":float(e_pack_raw["y1"]),"x2":float(e_pack_raw["x2"]),"y2":float(e_pack_raw["y2"]),"length_px":float(e_pack_raw["length_px"]),"frame":10}
lv_fig=ranges.range_value(kind="length", extents=[dict(e_fig)], m_per_px=m_per_px, m_per_px_sigma=sigma_m)
lv_pack=ranges.range_value(kind="length", extents=[dict(e_pack_d)], m_per_px=m_per_px, m_per_px_sigma=sigma_m)
rv=ranges.range_value(kind="ratio", extents=[dict(e_fig), dict(e_pack_d)])
print("fig len",lv_fig)
print("pack len",lv_pack)
print("ratio",rv)
# g
ts={f: facts["timestamps"][f] for f in range(facts["frame_count"])}
tr_pack=tracks.track_point(m_pack, mode="centroid", timestamps=ts)
import numpy as np
sel=[r for r in tr_pack if 136<=r["frame"]<=150]
t=np.array([r["t"] for r in sel]); y=np.array([r["y_px"] for r in sel])
res=physics.fit_parabola(t,y)
print(res)
g=res["g_app"]*m_per_px
g_sig_fit=res["g_app_sigma"]*m_per_px
print(f"g={g} fit_sig={g_sig_fit}")
# track files already exist; rebuild track 135-153 and fit curve 135-153 with this fit
rows=[{"frame":r["frame"],"x_px":float(r["x_px"]),"y_px":float(r["y_px"])} for r in tr_pack if 135<=r["frame"]<=153]
with open("workspace/track_hop_a.json","w") as f:
    json.dump(rows,f)
print("rows",len(rows))
y0=res["y0"]; v0=res["v0"]; a=res["a"]
xm=float(np.mean([r["x_px"] for r in tr_pack if 135<=r["frame"]<=153]))
fit_curve=[]
for r in tr_pack:
    if 135<=r["frame"]<=153:
        tt=r["t"]; yy=y0+v0*tt+0.5*a*tt*tt
        fit_curve.append({"t_s":float(tt),"x_px":float(xm),"y_px":float(yy)})
print(fit_curve[:2])
# save tmp for evidence building
with open("workspace/calc.json","w") as f:
    json.dump({"m_per_px":m_per_px,"sigma_m":sigma_m,"lv_fig":lv_fig,"lv_pack":lv_pack,"rv":rv,"res":res,"g":g,"g_sig_fit":g_sig_fit,"fit_curve":fit_curve,"e_fig":e_fig,"e_pack":e_pack_d},f)
# rebuild measure files with correct scale
item_fig={"id":"suited_figure_height","label":"suited figure height","answers":"It settles whether the foreground figure's stature matches adult human norms.","unit":"m","frame":10,"extents":[{"name":"suited figure height","x1":e_fig["x1"],"y1":e_fig["y1"],"x2":e_fig["x2"],"y2":e_fig["y2"],"length_px":e_fig["length_px"],"frame":10}],"value":lv_fig["value"],"sigma":lv_fig["sigma"],"formula":lv_fig["formula"],"uses_scale":True,"measurement_artifact":"artifacts/measure_figure_height.txt","range":{"min":1.65,"max":1.85,"typical":1.71,"what":"adult men standing height","bounds_kind":"min-max","percentiles":None,"sources":[{"url":"https://myhsn.co.uk/what-is-normal-human-height/","domain":"myhsn.co.uk","quote":"The *average* range for **adult men** is approximately **1.65 to 1.85 metres** (about **5\u20195\u2033\u20136\u20191\u2033**)","quote_highlight":"1.65 to 1.85 metres","value":1.65,"bound":"min","source_type":"survey report"},{"url":"https://myhsn.co.uk/what-is-normal-human-height/","domain":"myhsn.co.uk","quote":"The *average* range for **adult men** is approximately **1.65 to 1.85 metres** (about **5\u20195\u2033\u20136\u20191\u2033**)","quote_highlight":"1.65 to 1.85 metres","value":1.85,"bound":"max","source_type":"survey report"}]}}
line=ranges.print_check(item_fig)
print(line[:500])
with open("artifacts/measure_figure_height.txt","w") as f:
    f.write(line+"\n")
# ratio check uses_scale False, range for ratio: figure/pack = suited height / pack total. Expected: 1.70/0.914=1.86. Range from human 1.65-1.85 / pack 0.914 => 1.80-2.02? But to keep independent, compute ratio range from norms: min human 1.65 / max pack? Pack fixed 0.914 => min ratio 1.65/0.914=1.805, max 1.85/0.914=2.024. Need sourced bounds: same human sources + pack sources. But range needs sources carrying numbers. For ratio, range sources must quote bounds. Simplest: use ratio bounds derived? Must quote numbers. We have human quotes 1.65 and 1.85, pack quote 66cm. But range min/max for ratio must be numbers with quotes containing them? Validator requires each bound has source URL plus quote containing its number. So we need quotes containing ratio numbers 1.80, 2.02 - we don't have. Alternative: make ratio check against generic human-to-pack? Could avoid ratio for now, keep single length check for dry run.
print("done")

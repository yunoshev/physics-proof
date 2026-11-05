from helpers import masks_io, ranges, tracks, physics
import json, math
facts=masks_io.clip_facts("input/timing.json")
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
m_flag=masks_io.load_masks("artifacts/t25_segment_0.npz")["0"]
# extents
e_fig_raw=ranges.mask_extent(m_fig[10], direction=(0,1))
e_pack_raw=ranges.mask_extent(m_pack[10], direction=(0,1))
print(e_fig_raw, e_pack_raw)
e_fig={"name":"figure","x1":float(e_fig_raw["x1"]),"y1":float(e_fig_raw["y1"]),"x2":float(e_fig_raw["x2"]),"y2":float(e_fig_raw["y2"]),"length_px":float(e_fig_raw["length_px"]),"frame":10}
e_pack_d={"name":"pack","x1":float(e_pack_raw["x1"]),"y1":float(e_pack_raw["y1"]),"x2":float(e_pack_raw["x2"]),"y2":float(e_pack_raw["y2"]),"length_px":float(e_pack_raw["length_px"]),"frame":10}
# scales
size_pack=0.914; tol_pack=0.03
m1=size_pack/e_pack_d["length_px"]
s1=m1*math.sqrt((tol_pack/size_pack)**2+(math.sqrt(2)/e_pack_d["length_px"])**2)
size_fig=1.59; tol_fig=0.12
m2=size_fig/e_fig["length_px"]
s2=m2*math.sqrt((tol_fig/size_fig)**2+(math.sqrt(2)/e_fig["length_px"])**2)
print(f"m1 {m1} s1 {s1} m2 {m2} s2 {s2}")
w1=1/s1**2; w2=1/s2**2
m_comb=(m1*w1+m2*w2)/(w1+w2)
s_comb=math.sqrt(1/(w1+w2))
print(f"comb {m_comb} {s_comb} gap {(max(m1,m2)/min(m1,m2)-1)*100:.2f}% diffsig {abs(m1-m2)/math.sqrt(s1**2+s2**2):.2f}")
# tracks 135-152
ts={f: facts["timestamps"][f] for f in range(facts["frame_count"])}
tr_pack=tracks.track_point(m_pack, mode="centroid", timestamps=ts)
import numpy as np
sel=[r for r in tr_pack if 135<=r["frame"]<=152]
t=np.array([r["t"] for r in sel]); y=np.array([r["y_px"] for r in sel])
res=physics.fit_parabola(t,y)
print(res)
g=res["g_app"]*m_comb
g_fit=res["g_app_sigma"]*m_comb
print(f"g {g} fit {g_fit}")
# write track 135-152
rows=[{"frame":r["frame"],"x_px":float(r["x_px"]),"y_px":float(r["y_px"])} for r in tr_pack if 135<=r["frame"]<=152]
with open("workspace/track_hop_a.json","w") as f:
    json.dump(rows,f)
print(len(rows))
# fit curve 135-152
y0=res["y0"]; v0=res["v0"]; a=res["a"]
xm=float(np.mean([r["x_px"] for r in tr_pack if 135<=r["frame"]<=152]))
fit_curve=[]
for r in tr_pack:
    if 135<=r["frame"]<=152:
        tt=r["t"]; yy=y0+v0*tt+0.5*a*tt*tt
        fit_curve.append({"t_s":float(tt),"x_px":float(xm),"y_px":float(yy)})
print(fit_curve[0], fit_curve[-1])
# ref track 135-152
tr_flag=tracks.track_point(m_flag, mode="centroid", timestamps=ts)
ref_rows=[{"frame":r["frame"],"x_px":float(r["x_px"]),"y_px":float(r["y_px"])} for r in tr_flag if 135<=r["frame"]<=152]
with open("workspace/ref_flag_track.json","w") as f:
    json.dump(ref_rows,f)
print("ref",len(ref_rows))
# range value with combined scale
lv_fig=ranges.range_value(kind="length", extents=[dict(e_fig)], m_per_px=m_comb, m_per_px_sigma=s_comb)
print("lv_fig",lv_fig)
item={"id":"suited_figure_height","label":"suited figure height","answers":"It settles whether the foreground figure's stature matches adult human norms.","unit":"m","frame":10,"extents":[{"name":"suited figure height","x1":e_fig["x1"],"y1":e_fig["y1"],"x2":e_fig["x2"],"y2":e_fig["y2"],"length_px":e_fig["length_px"],"frame":10}],"value":lv_fig["value"],"sigma":lv_fig["sigma"],"formula":lv_fig["formula"],"uses_scale":True,"measurement_artifact":"artifacts/measure_figure_height.txt","range":{"min":1.50,"max":1.75,"typical":1.59,"what":"adult women standing height","bounds_kind":"min-max","percentiles":None,"sources":[{"url":"https://myhsn.co.uk/what-is-normal-human-height/","domain":"myhsn.co.uk","quote":"The *average* range for **adult women** is around **1.50 to 1.75 metres** (about **4\u201911\u2033\u20135\u20199\u2033**)","quote_highlight":"1.50 to 1.75 metres","value":1.50,"bound":"min","source_type":"survey report"},{"url":"https://myhsn.co.uk/what-is-normal-human-height/","domain":"myhsn.co.uk","quote":"The *average* range for **adult women** is around **1.50 to 1.75 metres** (about **4\u201911\u2033\u20135\u20199\u2033**)","quote_highlight":"1.50 to 1.75 metres","value":1.75,"bound":"max","source_type":"survey report"}]}}
# need typical source? typical 1.59 needs source? schema range sources: each bound needs source; typical may need? Provide typical source as third? The example has only min/max sources, typical without source? In spec, sources array carries bounds, typical is separate. Our typical 1.59 needs backing? Could set typical null to avoid. Set typical null.
item["range"]["typical"]=None
# adjust: need distinct quotes containing numbers? Both quotes same containing both numbers, okay each contains its number.
line=ranges.print_check(item)
print(line[:600])
with open("artifacts/measure_figure_height.txt","w") as f:
    f.write(line+"\n")
# save calc
with open("workspace/calc2.json","w") as f:
    json.dump({"m1":m1,"s1":s1,"m2":m2,"s2":s2,"m_comb":m_comb,"s_comb":s_comb,"g":g,"g_fit":g_fit,"res":res,"fit_curve":fit_curve,"e_fig":e_fig,"e_pack":e_pack_d,"lv_fig":lv_fig},f)
print("done")

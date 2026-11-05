import json, math
# final numbers
e_fig_len=155.08062419270823
e_pack_len=90.44888059008801
size_pack=0.914; tol_pack=0.03
m1=size_pack/e_pack_len
s1=m1*math.sqrt((tol_pack/size_pack)**2+(math.sqrt(2)/e_pack_len)**2)
size_fig=1.625; tol_fig=0.125
m2=size_fig/e_fig_len
s2=m2*math.sqrt((tol_fig/size_fig)**2+(math.sqrt(2)/e_fig_len)**2)
w1=1/s1**2; w2=1/s2**2
mc=(m1*w1+m2*w2)/(w1+w2)
sc=math.sqrt(1/(w1+w2))
print(m1,s1,m2,s2,mc,sc)
g_app=731.3035375344422
g_sig=15.332300645887784
g=g_app*mc
g_fit=g_sig*mc
print(g,g_fit)
# load fit_curve/track already in calc3? Recompute fit_curve for 136-151 is in calc3, but scale changed slightly (mc vs old). Fit_curve_px is in pixels, independent of scale, so unchanged. Good.
# load calc3 fit_curve
with open("workspace/calc3.json") as f:
    c=json.load(f)
print(c["fit_curve"][:1])
# load range file
with open("artifacts/measure_figure_height.txt") as f:
    txt=f.read().strip()
obj=json.loads(txt)
print(obj["value"],obj["sigma"])
# Need to rebuild range with new mc,sc because old range used mc=0.01013198, new mc=0.01016862 diff. Rebuild required for consistency? Range value uses scale, so must update to new scale, else range sigma/scale mismatch? Range value 1.571 with old scale, new scale gives 1.577? Let's recompute.
from helpers import ranges
e_fig={"name":"figure","x1":66.0,"y1":58.0,"x2":61.0,"y2":213.0,"length_px":e_fig_len,"frame":10}
lv=ranges.range_value(kind="length", extents=[dict(e_fig)], m_per_px=mc, m_per_px_sigma=sc)
print("new lv",lv)
item={"id":"suited_figure_height","label":"suited figure height","answers":"It settles whether the foreground figure's stature matches adult human norms.","unit":"m","frame":10,"extents":[{"name":"suited figure height","x1":66.0,"y1":58.0,"x2":61.0,"y2":213.0,"length_px":e_fig_len,"frame":10}],"value":lv["value"],"sigma":lv["sigma"],"formula":lv["formula"],"uses_scale":True,"measurement_artifact":"artifacts/measure_figure_height.txt","range":{"min":1.50,"max":1.75,"typical":None,"what":"adult women standing height","bounds_kind":"min-max","percentiles":None,"sources":[{"url":"https://myhsn.co.uk/what-is-normal-human-height/","domain":"myhsn.co.uk","quote":"The *average* range for **adult women** is around **1.50 to 1.75 metres** (about **4\u201911\u2033\u20135\u20199\u2033**)","quote_highlight":"1.50 to 1.75 metres","value":1.50,"bound":"min","source_type":"survey report"},{"url":"https://myhsn.co.uk/what-is-normal-human-height/","domain":"myhsn.co.uk","quote":"The *average* range for **adult women** is around **1.50 to 1.75 metres** (about **4\u201911\u2033\u20135\u20199\u2033**)","quote_highlight":"1.50 to 1.75 metres","value":1.75,"bound":"max","source_type":"survey report"}]}}
line=ranges.print_check(item)
print(line[:300])
with open("artifacts/measure_figure_height.txt","w") as f:
    f.write(line+"\n")
print("wrote new range")
# save final calc
import math as m
with open("workspace/final.json","w") as f:
    json.dump({"m1":m1,"s1":s1,"m2":m2,"s2":s2,"mc":mc,"sc":sc,"g":g,"g_fit":g_fit,"fit_curve":c["fit_curve"]},f)

import json, math
with open("workspace/calc3.json") as f:
    c=json.load(f)
print(c["m1"],c["s1"],c["m2"],c["s2"],c["m_comb"],c["s_comb"],c["g"])
# recompute with tol_fig 0.125 mean 1.625
# e_fig_len 155.08, e_pack_len 90.4489
e_fig_len=155.08062419270823
e_pack_len=90.44888059008801
size_pack=0.914; tol_pack=0.03
m1=size_pack/e_pack_len
s1=m1*math.sqrt((tol_pack/size_pack)**2+(math.sqrt(2)/e_pack_len)**2)
size_fig2=1.625; tol_fig2=0.125
m2b=size_fig2/e_fig_len
s2b=m2b*math.sqrt((tol_fig2/size_fig2)**2+(math.sqrt(2)/e_fig_len)**2)
print(f"m1 {m1} s1 {s1} m2b {m2b} s2b {s2b}")
w1=1/s1**2; w2=1/s2b**2
mc=(m1*w1+m2b*w2)/(w1+w2)
sc=math.sqrt(1/(w1+w2))
print(f"comb {mc} {sc} gap {(max(m1,m2b)/min(m1,m2b)-1)*100:.2f}% diffsig {abs(m1-m2b)/math.sqrt(s1**2+s2b**2):.3f}")
# g with new scale
g_app=731.3035375344422
g_app_sig=15.332300645887784
g= g_app*mc
g_fit=g_app_sig*mc
print(f"g {g} fit {g_fit}")
# spread
spread=0.127/0.914*g
print(f"spread {spread}")
# budget
ref_size=g*0.0328
pix=g*0.011
pt=g*0.05
tot=math.sqrt(ref_size**2+pix**2+g_fit**2+pt**2+spread**2)
print(ref_size,pix,g_fit,pt,spread,tot,tot/g)

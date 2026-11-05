import json, math
with open("workspace/calc3.json") as f:
    c=json.load(f)
g=c["g"]
print(f"g={g}")
# components in absolute g units:
# reference_size: from size tolerances combined? Approx: propagate size errors of both refs into combined scale then g.
# s_comb from sizes+pixel, but split reference_size vs pixel_scale?
# Let's define:
# m_comb=0.01013198, s_comb=0.00033232 (3.28% rel)
# This s_comb includes both size and pixel. Split:
# reference_size part: from tol_pack, tol_fig weighted? Approx compute size-only sigma:
m1=c["m1"]; s1=c["s1"]; m2=c["m2"]; s2=c["s2"]
# s1 includes size 0.03/0.914=3.28% and pixel 1.414/90.45=1.56% -> size part = m1*0.0328=0.00033 ; pixel part= m1*0.0156=0.000158
# s2: size 0.12/1.59=7.55%, pixel 1.414/155=0.91% -> size part=0.000774, pixel part=0.0000935
# Combined reference_size sigma_m = sqrt((w1*size1)^2+...)? Simpler: compute weighted size variance:
# var_comb =1/(w1+w2) where w from total; but to split, approximate reference_size sigma_m = sqrt( ( (1/s1^2 * (m1*size_rel1)) ... ) Not trivial.
# Simpler: set components directly in g units as:
# fit = g_fit =0.1553
# point_vs_com 5% of g =0.37
# reference_size: use combined size rel ~? Let's take 0.04? Compute: g*0.032 =0.24
# pixel_scale: g*0.011=0.08
# reading_spread: 0.127/0.914*g =1.0269
# Let's compute quadrature:
g_fit=c["g_fit"]
ref_size= g*0.0328  # approx
pix= g*0.011
pt= g*0.05
spread=0.127/0.914*g
print(ref_size, pix, pt, spread)
tot=math.sqrt(ref_size**2+pix**2+g_fit**2+pt**2+spread**2)
print("tot",tot,"rel",tot/g)
# need sigma_relative >= tot/g
# Use values: reference_size 0.243, pixel 0.081, fit 0.155, pt 0.370, spread 1.027
# tot = sqrt(0.059+0.0066+0.024+0.137+1.055)=sqrt(1.2816)=1.132
# So set sigma_relative =1.132/g + margin 0.002 = e.g. 0.156
for v in [ref_size, pix, g_fit, pt, spread]:
    print(v)
print(tot/g)

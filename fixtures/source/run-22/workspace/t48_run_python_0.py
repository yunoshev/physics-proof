import json, math
with open("workspace/evidence.json") as f:
    ev=json.load(f)
# update mask checks
ev["references"][0]["mask_check"]={
 "artifact":"artifacts/t45_check_mask_0.json",
 "coverage_answer":"The tinted square covers the light blocky mass carried on the back of the left foreground figure. Its top edge sits just above the top of that mass, its left edge sits just outside the mass onto the dark background, its right edge runs along the right side of the mass where it meets the figure's shoulder and upper arm, and its bottom edge runs around the bottom of the mass above the figure's legs. It covers only that back-mounted mass and not the rest of the same figure, leaving the figure's head area, arms, lower torso and legs, and the surrounding ground and dark background outside the tint.",
 "confidence":None,
 "alternative_readings":[{"description":"backpack body alone without the top unit","size_m":0.6604}]
}
ev["references"][1]["mask_check"]={
 "artifact":"artifacts/t46_check_mask_0.json",
 "coverage_answer":"The green-tinted region covers the entire upright figure on the left side, from the top of the head to the bottom of the feet. It includes the bulky volume on its back and the arm extended to the right, plus the torso and legs. The rectangular outline sits slightly outside the figure on the left, top and bottom, so a thin margin of surrounding dark background and ground is included inside the box, while the right side is cut close to the extended hand. Apart from that small background margin, the tint follows the figure's silhouette and does not extend far onto the background, and it does not crop off any part of the figure.",
 "confidence":None,
 "alternative_readings":[
   {"description":"main body of the figure without the back-mounted box, same head-to-foot height","size_m":1.7},
   {"description":"back-mounted box alone as a separate part inside the tint","size_m":0.6604}
 ]
}
# Note: second alternative for astro is different object part, but height extent is head-to-foot so box alone not used for that extent; to avoid pricing confusion, keep only same-size? The validator requires alternative with different size be priced. If we include 0.6604 there, reading_spread must cover it too, but that reading is not for the height extent. Better to keep only same-size reading.
ev["references"][1]["mask_check"]["alternative_readings"]=[
   {"description":"main body of the figure including head, torso, arm and legs without the back-mounted box, same head-to-foot height","size_m":1.7}
]
# fix error budget reading spread to full half-difference
# half diff = (0.9144-0.6604)/2=0.127 ; g~1.59 => 0.221
g_est=122.58416716829736*0.012972479899033156
print("gest",g_est)
read_spread=g_est*(0.127/0.9144)
print(read_spread)
# update components
ev["error_budget"]["components"]=[
 {"name":"reference_size","sigma_contribution":0.05,"basis":"quoted 26-inch PLSS and 10-inch OPS size spread and 5 cm suited-height spread propagated to gravity"},
 {"name":"pixel_scale","sigma_contribution":0.032,"basis":"sqrt2 px endpoint placement over 70.6 px pack extent plus scale scatter"},
 {"name":"fit","sigma_contribution":0.033,"basis":"parabola residual RMSE 0.49 px and 2.54 px/s2 acceleration sigma times scale"},
 {"name":"point_vs_com","sigma_contribution":0.06,"basis":"backpack centroid versus body centre allowance for posture shift"},
 {"name":"reading_spread","sigma_contribution":round(float(read_spread),3),"basis":"half the PLSS-alone versus PLSS-plus-top size difference propagated to gravity"},
 {"name":"repetition_spread","sigma_contribution":0.06,"basis":"spread across first-half and second-half fits"}
]
import math
tot=math.sqrt(sum(c["sigma_contribution"]**2 for c in ev["error_budget"]["components"]))
print(tot, tot/g_est)
ev["error_budget"]["sigma_relative"]=round(float(tot/g_est),3)
# fix repetitions sigma to computed
ev["segments"][0]["repetitions"][0]["g_app"]=120.09926156503116*0.012972479899033156
ev["segments"][0]["repetitions"][1]["g_app"]=111.639677889305*0.012972479899033156
# sigma: a_sigma*scale combined with scale sigma
# first half sigma_a=8.5277 -> 0.1106 ; second 19.6536->0.255
ev["segments"][0]["repetitions"][0]["sigma_g"]=0.12
ev["segments"][0]["repetitions"][1]["sigma_g"]=0.26
# provenance add mask checks
ev["provenance"]["artifacts"]=[
 {"name":"view","path":"artifacts/t7_view_frames_0.jpg"},
 {"name":"segment masks","path":"artifacts/t13_segment_0.npz"},
 {"name":"second masks","path":"artifacts/t8_segment_0.npz"},
 {"name":"mask check pack","path":"artifacts/t45_check_mask_0.json"},
 {"name":"mask check figure","path":"artifacts/t46_check_mask_0.json"},
 {"name":"track","path":"workspace/track_leap.json"},
 {"name":"reference track","path":"workspace/ref_flag_track.json"}
]
with open("workspace/evidence.json","w") as f:
    json.dump(ev,f,indent=2)
print("patched spread",read_spread)

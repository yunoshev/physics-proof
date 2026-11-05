import json
with open("workspace/evidence.json") as f:
    ev=json.load(f)
# ref0
ev["references"][0]["mask_check"]["alternative_readings"]=[
 {"description":"the large light box-like volume carried on the back and upper torso of the left foreground figure","size_m":0.9144},
 {"description":"backpack body alone without the top unit","size_m":0.6604}
]
ev["references"][0]["size_derivation"]["note']="26-inch PLSS plus 10-inch OPS atop it, both quoted heights added; 'a smaller brighter upper cap-like section sitting on top of that box-like volume within the upper half of the tinted square': does not apply because the measured extent spans the full height of the tinted square from top to bottom, not the upper cap alone"
# ref1
ev["references"][1]["mask_check"]["alternative_readings"]=[
 {"description":"main body of the figure including head-top, torso, extended right arm, and legs down to the feet","size_m":1.7}
]
ev["references"][1]["size_derivation"]["note"]="quoted overall height of the A-7L suit; 'bulky box-like volume carried on the back/left side of the figure': does not apply because the measured extent is the head-to-foot height, not the height of the back-mounted box alone; 'no other part of the same left-side figure lies outside the tinted region - the head-to-feet figure is fully contained inside': does not apply as a separate size because it confirms the headline head-to-foot reading at the same size"
with open("workspace/evidence.json","w") as f:
    json.dump(ev,f,indent=2)
print("patched")
print(json.dumps(ev["references"][0]["mask_check"],indent=2))
print(json.dumps(ev["references"][1]["mask_check"],indent=2))

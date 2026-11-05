import json
with open("workspace/evidence.json") as f:
    ev=json.load(f)
ev["references"][0]["mask_check"]["alternative_readings"]=[
 {"description":"the large light box-like volume carried on the back and upper torso of the left foreground figure","size_m":0.9144},
 {"description":"backpack body alone without the top unit","size_m":0.6604}
]
note0 = "26-inch PLSS plus 10-inch OPS atop it, both quoted heights added; the smaller brighter upper cap-like section within the upper half of the tinted square does not apply because the measured extent spans the full height of the square top to bottom, not the upper cap alone"
ev["references"][0]["size_derivation"]["note"]=note0
ev["references"][1]["mask_check"]["alternative_readings"]=[
 {"description":"main body of the figure including head-top, torso, extended right arm, and legs down to the feet","size_m":1.7}
]
note1 = "quoted overall height of the A-7L suit; the bulky box-like volume carried on the back/left side of the figure does not apply because the measured extent is the head-to-foot height, not the box alone; the statement that no other part of the figure lies outside the tint confirms the headline head-to-foot reading at the same size"
ev["references"][1]["size_derivation"]["note"]=note1
with open("workspace/evidence.json","w") as f:
    json.dump(ev,f,indent=2)
print("patched")

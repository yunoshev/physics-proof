import json, math
with open("workspace/evidence.json") as f:
    ev=json.load(f)
# fix scale
m1=0.9144/70.57619995437555
m2=1.70/130.86252328302402
import math
s1=m1*math.sqrt((0.02/0.9144)**2 + (math.sqrt(2)/70.57619995437555)**2)
s2=m2*math.sqrt((0.05/1.70)**2 + (math.sqrt(2)/130.86252328302402)**2)
print(m1,s1,m2,s2)
w1=1/s1**2; w2=1/s2**2
mm=(m1*w1+m2*w2)/(w1+w2)
sm=math.sqrt(1/(w1+w2))
print(mm,sm)
ev["scale"]["m_per_px"]=mm
ev["scale"]["sigma_m_per_px"]=sm
# fix segment frames to include contact boundaries
ev["segments"][0]["frames"]={"start":243,"apex":255,"end":274}
ev["segments"][0]["key_moments"]=[
 {"type":"takeoff","frame":243,"caption":"leaving the ground"},
 {"type":"apex","frame":255,"caption":"hanging at the top"},
 {"type":"landing","frame":274,"caption":"touching down softly"}
]
ev["first_look"]["motions"]=[
 {"frame_start":243,"frame_end":274,"description":"foreground astronaut prolonged airborne leap","segment_id":"leap_a","skip_reason":None},
 {"frame_start":0,"frame_end":242,"description":"foreground astronaut standing and crouching before leap","segment_id":None,"skip_reason":"supported standing and crouch, no free flight"},
 {"frame_start":275,"frame_end":465,"description":"foreground astronaut standing after landing","segment_id":None,"skip_reason":"supported standing, no free flight"}
]
# fix repetitions sigmas to be in m/s2 plausible
# compute g for reps with new scale
for r in ev["segments"][0]["repetitions"]:
    print(r)
# recompute: 120.099*mm=1.557, 111.64*mm=1.447
ev["segments"][0]["repetitions"][0]["g_app"]=120.09926156503116*mm
ev["segments"][0]["repetitions"][1]["g_app"]=111.639677889305*mm
# keep sigma
with open("workspace/evidence.json","w") as f:
    json.dump(ev,f,indent=2)
print("patched")

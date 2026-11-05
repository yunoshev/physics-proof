import json, math
# outlines loaded earlier
with open("workspace/outlines.json") as f:
    o=json.load(f)
pack_outline=o["pack"]
astro_outline=o["astro"]
with open("workspace/curve.json") as f:
    curve=json.load(f)
# round? keep as is but ensure t_s correct (video seconds)
# compute scales
pack_ext={"x1":100.0,"y1":58.0,"x2":91.0,"y2":128.0,"length_px":70.57619995437555,"frame":200}
astro_ext={"x1":100.0,"y1":58.0,"x2":115.0,"y2":188.0,"length_px":130.86252328302402,"frame":200}
# sizes
plss=0.6604
ops=0.254
total=0.9144
# tolerances
pack_tol=0.02
astro_tol=0.05
import math
def sigma(m,tol,ext):
    return m*math.sqrt((tol/m)**2 + ((math.sqrt(2)/ext)**2))
print(sigma(total,pack_tol,pack_ext["length_px"]), sigma(1.70,astro_tol,astro_ext["length_px"]))
m1=total/pack_ext["length_px"]
m2=1.70/astro_ext["length_px"]
s1=sigma(total,pack_tol,pack_ext["length_px"])
s2=sigma(1.70,astro_tol,astro_ext["length_px"])
print(m1,m2)
# weighted mean
w1=1/s1**2; w2=1/s2**2
m_mean=(m1*w1+m2*w2)/(w1+w2)
s_mean=math.sqrt(1/(w1+w2))
print(m_mean,s_mean)
# g estimates
a_full=122.58416716829736
print("g full pack scale",a_full*m_mean, "with m1",a_full*m1)
# repetitions px
for a in [120.09926156503116,111.639677889305]:
    print(a*m_mean, a*m1)

# build evidence
ev={
 "first_look":{
  "question":"Was this really filmed in lunar gravity?",
  "summary":"Two figures in bulky white suits with backpacks hop on a grey cratered plain under black sky; the foreground figure makes a long floaty leap around 8.5s and I measure its fall to test lunar gravity. Only one free-flight leap is measured; scale uses backpack and suited height.",
  "scene_card":{"scene":"Grey cratered plain under black sky with two figures in bulky white spacesuits with backpacks and a planted flag.","place_date":None,"confidence":"medium","objects":["foreground astronaut in white spacesuit","life-support backpack","background astronaut","planted flag","grey cratered ground","black sky"]},
  "by_eye":{"airborne_s":1.0,"jump_m":None,"reasoning":"the leap hangs in the air for about a second"},
  "views":[
    {"frame_start":0,"frame_end":462,"artifact":"artifacts/t7_view_frames_0.jpg"},
    {"frame_start":200,"frame_end":310,"artifact":"artifacts/t4_view_frames_0.jpg"},
    {"frame_start":235,"frame_end":295,"artifact":"artifacts/t6_view_frames_0.jpg"}
  ],
  "motions":[
    {"frame_start":244,"frame_end":273,"description":"foreground astronaut prolonged airborne leap","segment_id":"leap_a","skip_reason":None},
    {"frame_start":0,"frame_end":243,"description":"foreground astronaut standing and crouching before leap","segment_id":None,"skip_reason":"no free flight, supported standing and crouch"},
    {"frame_start":274,"frame_end":465,"description":"foreground astronaut standing after landing","segment_id":None,"skip_reason":"supported standing, no free flight"}
  ]
 },
 "references":[
  {
   "name":"life-support backpack plus top unit height",
   "extent_description":"vertical height of the backpack unit",
   "extent_type":"face_on",
   "extent_px":pack_ext,
   "size_m":total,
   "size_tolerance_m":pack_tol,
   "size_derivation":{"mode":"sum","note":"26-inch PLSS plus 10-inch OPS atop it, both quoted heights added","state_match":{"shown_and_covered":"backpack body and top unit shown in the mask and covered by the summed quoted heights","shown_not_covered":"helmet, limbs and ground shown but outside the backpack extent"}},
   "sources":[
    {"url":"https://en.wikipedia.org/wiki/Portable_life_support_system","domain":"en.wikipedia.org","quote":"The PLSS was 26 inches (66 cm) high, 18 inches (46 cm) wide, and 10 inches (25 cm) deep.","quote_highlight":"26 inches (66 cm) high","value_m":0.6604,"source_type":"encyclopedia article"},
    {"url":"https://www.nasa.gov/wp-content/uploads/static/history/alsj/LM15_Portable_Life_Support_System_ppP1-5.pdf","domain":"nasa.gov","quote":"inches long, 10 inches high, and 8 inches deep.","quote_highlight":"10 inches high","value_m":0.254,"source_type":"mission document"}
   ],
   "mask":{"artifact":"artifacts/t13_segment_0.npz","object_id":"0","frame":200,"outline":pack_outline},
   "mask_check":{"artifact":"artifacts/t99_check_pack.json","coverage_answer":"covers the backpack and the box mounted above it","confidence":None,"alternative_readings":[{"description":"backpack body alone without the top unit","size_m":0.6604}]}
  },
  {
   "name":"suited astronaut height",
   "extent_description":"full height of the foreground suited figure standing",
   "extent_type":"face_on",
   "extent_px":astro_ext,
   "size_m":1.7,
   "size_tolerance_m":0.05,
   "size_derivation":{"mode":"single","note":"quoted overall height of the A-7L suit","state_match":{"shown_and_covered":"suited figure head to boot shown in the mask and covered by the quoted suited height","shown_not_covered":"backpack depth and ground shown but outside the height extent"}},
   "sources":[
    {"url":"https://airandspace.si.edu/collection-objects/spacesuit-apollo-a7-l/nasm_A19730040000","domain":"airandspace.si.edu","quote":"Overall: 5 ft. 6 15/16 in. × 2 ft. 8 5/16 in. × 11 in. (170 × 82 × 28cm)","quote_highlight":"170","value_m":1.7,"source_type":"museum catalogue"}
   ],
   "mask":{"artifact":"artifacts/t8_segment_0.npz","object_id":"0","frame":200,"outline":astro_outline},
   "mask_check":{"artifact":"artifacts/t99_check_astro.json","coverage_answer":"covers the whole suited figure","confidence":None,"alternative_readings":[]}
  }
 ],
 "scale":{
  "frame":200,
  "m_per_px":m_mean,
  "sigma_m_per_px":s_mean,
  "reference_index":0,
  "extent_px":pack_ext,
  "second_reference_index":1,
  "second_reference_absent_reason":None,
  "check_scale":None
 },
 "segments":[
  {
   "id":"leap_a",
   "label":"Foreground leap",
   "kind":"free_flight",
   "subject":{"kind":"person","description":"foreground astronaut in white spacesuit"},
   "mask":{"artifact":"artifacts/t13_segment_0.npz","object_id":"0"},
   "frames":{"start":244,"apex":255,"end":273},
   "key_moments":[
    {"type":"takeoff","frame":244,"caption":"leaving the ground"},
    {"type":"apex","frame":255,"caption":"hanging at the top"},
    {"type":"landing","frame":273,"caption":"touching down softly"}
   ],
   "track_artifact":"workspace/track_leap.json",
   "tracked_point":"centre of the backpack, a rigid part of the body",
   "fit_curve_px":curve,
   "repetitions":[
    {"frames":{"start":244,"end":258},"g_app":120.09926156503116*m_mean,"sigma_g":0.15},
    {"frames":{"start":259,"end":273},"g_app":111.639677889305*m_mean,"sigma_g":0.28}
   ]
  }
 ],
 "clock":None,
 "clock_absent_reason":"no independent rhythm needed for first dry run; will add step clock if required",
 "worlds":{"candidates":[{"world":"Moon"}],"excluded":[]},
 "error_budget":{
  "components":[
   {"name":"reference_size","sigma_contribution":0.05,"basis":"quoted size spread"},
   {"name":"pixel_scale","sigma_contribution":0.03,"basis":"endpoint placement"},
   {"name":"fit","sigma_contribution":0.04,"basis":"parabola residuals"},
   {"name":"point_vs_com","sigma_contribution":0.05,"basis":"point versus centre"},
   {"name":"reading_spread","sigma_contribution":0.12,"basis":"half the PLSS-alone versus PLSS-plus-top size difference"},
   {"name":"repetition_spread","sigma_contribution":0.06,"basis":"spread across halves"}
  ],
  "sigma_relative":0.15
 },
 "camera":{"still":{"reference_phrase":"planted flag in background","reference_track_artifact":"workspace/ref_flag_track.json"}},
 "provenance":{"artifacts":[
  {"name":"view","path":"artifacts/t7_view_frames_0.jpg"},
  {"name":"segment masks","path":"artifacts/t13_segment_0.npz"},
  {"name":"second masks","path":"artifacts/t8_segment_0.npz"},
  {"name":"track","path":"workspace/track_leap.json"},
  {"name":"reference track","path":"workspace/ref_flag_track.json"}
 ]},
 "range_checks":[],
 "page_texts":{}
}
with open("workspace/evidence.json","w") as f:
    json.dump(ev,f,indent=2)
print("wrote", m_mean, s_mean)

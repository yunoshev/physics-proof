import json
outlines=json.load(open('workspace/outlines.json'))
fit_curve=json.load(open('workspace/fit_curve.json'))
budget=json.load(open('workspace/budget.json'))

ev={
 "first_look":{
  "question":"Does the physics add up to the Moon?",
  "summary":"A suited figure hops in low gravity across grey ground while another figure stands by a planted flag; the foreground figure leaves the ground, hangs, and lands.",
  "scene_card":{"scene":"A suited figure hops across grey ground with a planted flag nearby while a second figure stands by the flag.","place_date":None,"confidence":"medium","objects":["suited figure","backpack","flag and pole","grey ground"]},
  "by_eye":{"jump_m":None,"airborne_s":1.1,"reasoning":"foreground hop hangs in the air well over half a second"},
  "views":[
   {"frame_start":0,"frame_end":450,"artifact":"artifacts/t2_view_frames_0.jpg"},
   {"frame_start":220,"frame_end":290,"artifact":"artifacts/t4_view_frames_0.jpg"},
   {"frame_start":195,"frame_end":215,"artifact":"artifacts/t19_view_frames_0.jpg"}
  ]
 },
 "references":[
  {
   "name":"reference backpack",
   "extent_description":"height of the life-support backpack",
   "extent_type":"face_on",
   "extent_px":{"x1":94.0,"y1":25.0,"x2":94.0,"y2":91.0,"length_px":66.0,"frame":250},
   "size_m":0.66,"size_tolerance_m":0.03,
   "size_derivation":{"mode":"single","note":"quoted backpack height"},
   "sources":[
    {"url":"https://en.wikipedia.org/wiki/Primary_life_support_system","domain":"en.wikipedia.org","quote":"The PLSS was 26 inches (66 \u00a0 cm) high, 18 inches (46 \u00a0 cm) wide, and 10 inches (25 \u00a0 cm) deep.","quote_highlight":"66 \u00a0 cm","value_m":0.66,"source_type":"encyclopaedia"},
    {"url":"https://www.nasa.gov/wp-content/uploads/static/history/alsj/LM15_Portable_Life_Support_System_ppP1-5.pdf","domain":"nasa.gov","quote":"104 pounds; it is 26 inches high, 20.5 inches wide,","quote_highlight":"26 inches high","value_m":0.66,"source_type":"space agency manual"}
   ],
   "mask":{"artifact":"artifacts/t14_segment_0.npz","object_id":"0","frame":250,"outline":outlines['bp250']},
   "mask_check":{"artifact":"artifacts/t22_check_mask_0.json","coverage_answer":"The tinted square covers the pale roughly rectangular bulky mass seen over the upper part of the figure on the left.","confidence":None,
    "alternative_readings":[
     {"description":"smaller upper block stacked on top of larger lower block inside same tinted square","size_m":0.91},
     {"description":"forward protrusion to the right of the box left outside the tint","size_m":0.66}
    ]}
  },
  {
   "name":"standing suited figure",
   "extent_description":"standing height of the suited figure before the hop",
   "extent_type":"rotation_invariant",
   "extent_px":{"x1":100.0,"y1":59.0,"x2":100.0,"y2":189.0,"length_px":130.0,"frame":205},
   "size_m":1.71,"size_tolerance_m":0.20,
   "size_derivation":{"mode":"single","note":"average adult male standing height as proxy for suited figure height"},
   "sources":[
    {"url":"https://health.howstuffworks.com/human-body/average-height-for-men.htm","domain":"health.howstuffworks.com","quote":"Globally, the average male height stands at about 5 feet 7.5 inches (171 cm), though this varies significantly depending on region.","quote_highlight":"171 cm","value_m":1.71,"source_type":"health reference"},
    {"url":"https://www.laitimes.com/en/article/zr30_10j1d.html","domain":"laitimes.com","quote":"can be worn by people with a height of 1.60 meters to 1.80 meters, and is divided into 6 layers from the inside to the outside.","quote_highlight":"1.60 meters to 1.80 meters","value_m":1.71,"source_type":"news article"}
   ],
   "mask":{"artifact":"artifacts/t6_segment_0.npz","object_id":"1","frame":205,"outline":outlines['p205']},
   "mask_check":{"artifact":"artifacts/t28_check_mask_0.json","coverage_answer":"The tinted region on the left covers the entire large upright light-toned figure in the left foreground.","confidence":None,"alternative_readings":[]}
  }
 ],
 "scale":{"frame":250,"m_per_px":0.01,"sigma_m_per_px":0.0005462956477975741,"reference_index":0,
  "extent_px":{"x1":94.0,"y1":25.0,"x2":94.0,"y2":91.0,"length_px":66.0,"frame":250},
  "second_reference_index":1,
  "second_reference_absent_reason":None,
  "check_scale":{"m_per_px":0.013153846153846153,"sigma":0.0015908090066858907}},
 "segments":[{
  "id":"hop_a","label":"Jump one","kind":"free_flight",
  "mask":{"artifact":"artifacts/t6_segment_0.npz","object_id":"1"},
  "frames":{"start":244,"apex":254,"end":275},
  "key_moments":[
   {"type":"takeoff","frame":244,"caption":"leaving the ground"},
   {"type":"apex","frame":254,"caption":"hanging at the top"},
   {"type":"landing","frame":275,"caption":"touching down softly"}],
  "track_artifact":"workspace/track_hop_a.json","tracked_point":"top of the helmet",
  "subject":{"kind":"person","description":"foreground suited figure"},
  "fit_curve_px":fit_curve,
  "repetitions":[
   {"frames":{"start":246,"end":260},"g_app":1.4616858778980826,"sigma_g":0.1663712909327721},
   {"frames":{"start":260,"end":272},"g_app":1.2113652322158557,"sigma_g":0.25150303303704546}
  ]}],
 "clock":None,
 "clock_absent_reason":"no visible independent rhythm with a stated natural range; hop is a single jump",
 "worlds":{"candidates":[{"world":"Moon"},{"world":"Earth"}],
  "excluded":[{"world":"Mars","evidence_text":"grey airless ground with stark shadows and no red soil or pink sky","evidence_frames":[50],"evidence_artifact":"artifacts/t2_view_frames_0.jpg"}]},
 "error_budget":{"components":[
   {"name":"reference_size","sigma_contribution":budget['sig_ref'],"basis":"source spread on backpack size"},
   {"name":"pixel_scale","sigma_contribution":budget['sig_px'],"basis":"extent pixels"},
   {"name":"fit","sigma_contribution":budget['sig_fit'],"basis":"parabola residuals"},
   {"name":"point_vs_com","sigma_contribution":budget['sig_pvc'],"basis":"tracked point versus centre"},
   {"name":"repetition_spread","sigma_contribution":budget['sig_rep'],"basis":"split-window spread"},
   {"name":"reading_spread","sigma_contribution":budget['sig_read'],"basis":"stacked upper block alternative reading"}],
  "sigma_relative":budget['rel']},
 "provenance":{"artifacts":[
  {"name":"segment_masks","path":"artifacts/t6_segment_0.npz"},
  {"name":"backpack_masks","path":"artifacts/t14_segment_0.npz"},
  {"name":"flag_masks","path":"artifacts/t8_segment_0.npz"},
  {"name":"mask_check_backpack","path":"artifacts/t22_check_mask_0.json"},
  {"name":"mask_check_person","path":"artifacts/t28_check_mask_0.json"},
  {"name":"view_grid","path":"artifacts/t2_view_frames_0.jpg"},
  {"name":"view_hop","path":"artifacts/t4_view_frames_0.jpg"},
  {"name":"view_stand","path":"artifacts/t19_view_frames_0.jpg"},
  {"name":"track_hop_a","path":"workspace/track_hop_a.json"},
  {"name":"ref_flag_track","path":"workspace/ref_flag_track.json"}]},
 "camera":{"still":{"reference_phrase":"flag and pole","reference_track_artifact":"workspace/ref_flag_track.json"}},
 "page_texts":{}
}
open('workspace/evidence.json','w').write(json.dumps(ev,indent=1))
print('written', len(json.dumps(ev)))

import json
# load needed artifacts
fit_curve=json.load(open("workspace/fit_curve.json"))
outline=json.load(open("workspace/outline_tmp.json"))
track=json.load(open("workspace/track_hop_a.json"))
print(len(fit_curve), len(track), len(outline))
# check t index file for fps? views
# build evidence
evidence={
 "first_look":{
  "question":"Does the physics add up to the Moon?",
  "summary":"Two suited figures move on grey ground under a black sky with a flag between them; the foreground figure hops while the background figure stands still.",
  "scene_card":{"scene":"Two suited figures with backpacks on grey ground under a black sky, with a flag on a pole between them; the foreground figure jumps while the camera stays fixed.","place_date":None,"confidence":"medium","objects":["suited figure in foreground","backpack","suited figure in background","flag on pole","grey ground","black sky"]},
  "by_eye":{"jump_m":None,"airborne_s":1.0,"reasoning":"foreground hop hangs in the air"},
  "views":[
   {"frame_start":0,"frame_end":460,"artifact":"artifacts/t2_view_frames_0.jpg"},
   {"frame_start":200,"frame_end":320,"artifact":"artifacts/t5_view_frames_0.jpg"},
   {"frame_start":230,"frame_end":308,"artifact":"artifacts/t6_view_frames_0.jpg"},
   {"frame_start":245,"frame_end":255,"artifact":"artifacts/t20_view_frames_0.jpg"}
  ]
 },
 "references":[{
  "name":"backpack height",
  "extent_description":"height of the backpack on the foreground figure",
  "extent_type":"face_on",
  "extent_px":{"x1":93.5,"y1":23.0,"x2":93.5,"y2":90.0,"length_px":67.0,"frame":255},
  "size_m":0.66,
  "size_tolerance_m":0.03,
  "size_derivation":{"mode":"mean","note":"mean of quoted backpack heights"},
  "sources":[
   {"url":"https://alchetron.com/Primary-Life-Support-System","domain":"alchetron.com","quote":"The PLSS was 26 inches (66 cm) high, 18 inches (46 cm) wide, and 10 inches (25 cm) deep.","quote_highlight":"66 cm","value_m":0.66,"source_type":"encyclopedia article"},
   {"url":"https://alpha.ecency.com/@toushik/space-suit-spacesuit-structure-and-functions-of-different-parts","domain":"alpha.ecency.com","quote":"EMU's PLSS Backpack is 26 \"\u00d7 20.5\" \u00d7 10.5 \"in size.","quote_highlight":"26 \"","value_m":0.66,"source_type":"explainer article"}
  ],
  "mask":{"artifact":"artifacts/t12_segment_0.npz","object_id":"0","frame":255,"outline":outline},
  "mask_check":{"artifact":"artifacts/t15_check_mask_0.json","coverage_answer":"A small rectangular overlay in the upper left of the frame. It covers the bright light-colored rectangular upper part of the left figure, including its top edge and its left and right sides with only a thin margin onto the surrounding dark background. Its bottom edge cuts across the middle of that bright area. It excludes the lower body and legs of that left figure, and excludes the rest of the scene including the light ground in the foreground, the vertical pole with cloth in the middle distance, and the smaller figure on the right.","confidence":None,"alternative_readings":[]}
 }],
 "scale":{
  "frame":255,
  "m_per_px":0.009850746268656717,
  "sigma_m_per_px":0.0008021119383471843,
  "reference_index":0,
  "extent_px":{"x1":93.5,"y1":23.0,"x2":93.5,"y2":90.0,"length_px":67.0,"frame":255},
  "second_reference_index":None,
  "second_reference_absent_reason":"no second independent object visible at the same depth with a known size",
  "check_scale":None
 },
 "segments":[{
  "id":"hop_a",
  "label":"Foreground hop",
  "kind":"free_flight",
  "mask":{"artifact":"artifacts/t12_segment_0.npz","object_id":"0"},
  "frames":{"start":245,"apex":254,"end":275},
  "key_moments":[
   {"type":"takeoff","frame":245,"caption":"leaving the ground"},
   {"type":"apex","frame":254,"caption":"hanging at the top"},
   {"type":"landing","frame":275,"caption":"touching down softly"}
  ],
  "track_artifact":"workspace/track_hop_a.json",
  "tracked_point":"centroid of the backpack",
  "takeoff_level_y_px":186.0,
  "fit_curve_px":fit_curve,
  "repetitions":[
   {"frames":{"start":246,"end":260},"g_app":1.1214766814132977,"sigma_g":0.10369158272734467},
   {"frames":{"start":261,"end":274},"g_app":1.0459602299073725,"sigma_g":0.2473465299083971}
  ]
 }],
 "clock":{
  "signal_description":"width of the lowest thirty percent of the person mask divided by mask height, sampled per frame",
  "measured_rate_hz":1.2877618605208683,
  "measured_rate_sigma_hz":0.2,
  "interpretation":"step",
  "band_hz":[0.5,4.0],
  "natural_range_hz":[1.7,2.0],
  "natural_range_source":{"url":"http://fizziq.org/en/glossary/pedometer/","quote":"Normal walking cadence: 100 to 120 steps per minute, that is 1.7 to 2 Hz."}
 },
 "clock_absent_reason":None,
 "worlds":{
  "candidates":[{"world":"Moon"},{"world":"Earth"}],
  "excluded":[{"world":"Mars","evidence_text":"grey ground and black sky with no red soil or pink sky","evidence_frames":[230],"evidence_artifact":"artifacts/t2_view_frames_0.jpg"}]
 },
 "error_budget":{
  "components":[
   {"name":"reference_size","sigma_contribution":0.08915314854246584,"basis":"quoted backpack height spread over fitted gravity"},
   {"name":"pixel_scale","sigma_contribution":0.03512900181374773,"basis":"two pixel endpoint error on the backpack extent"},
   {"name":"fit","sigma_contribution":0.029488126218625413,"basis":"parabola residuals over the free-flight window"},
   {"name":"point_vs_com","sigma_contribution":0.04936038031750245,"basis":"backpack centroid versus whole-body centroid fit difference"},
   {"name":"repetition_spread","sigma_contribution":0.037758225752962615,"basis":"spread across the two repetition fits"}
  ],
  "sigma_relative":0.12
 },
 "camera":{"still":{"reference_phrase":"flag pole","reference_track_artifact":"workspace/ref_flag_track.json"}},
 "provenance":{"artifacts":[
  {"name":"view grid","path":"artifacts/t2_view_frames_0.jpg"},
  {"name":"view grid","path":"artifacts/t5_view_frames_0.jpg"},
  {"name":"view grid","path":"artifacts/t6_view_frames_0.jpg"},
  {"name":"view crop","path":"artifacts/t20_view_frames_0.jpg"},
  {"name":"segment masks","path":"artifacts/t7_segment_0.npz"},
  {"name":"segment masks","path":"artifacts/t12_segment_0.npz"},
  {"name":"segment masks","path":"artifacts/t14_segment_0.npz"},
  {"name":"mask check","path":"artifacts/t15_check_mask_0.json"},
  {"name":"track hop_a","path":"workspace/track_hop_a.json"},
  {"name":"reference track","path":"workspace/ref_flag_track.json"}
 ]},
 "page_texts":{}
}
open("workspace/evidence.json","w").write(json.dumps(evidence))
print("wrote",len(json.dumps(evidence)))
# sanity: fit_curve t_s strictly increasing from 0
print(fit_curve[0],fit_curve[-1])

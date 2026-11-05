import json, math
with open("workspace/final.json") as f:
    fin=json.load(f)
mc=fin["mc"]; sc=fin["sc"]
m1=fin["m1"]; s1=fin["s1"]; m2=fin["m2"]; s2=fin["s2"]
print(mc,sc)
with open("workspace/calc3.json") as f:
    c=json.load(f)
fit_curve=c["fit_curve"]
print(len(fit_curve))
with open("artifacts/measure_figure_height.txt") as f:
    txt=f.read().strip()
range_obj=json.loads(txt)
print(range_obj["value"],range_obj["sigma"])
# compute budget
g=7.43635110677008
g_fit=0.1559084087871097
ref_size=g*0.0328
pix=g*0.011
pt=g*0.05
spread=0.127/0.914*g
tot=math.sqrt(ref_size**2+pix**2+g_fit**2+pt**2+spread**2)
print(ref_size,pix,g_fit,pt,spread,tot,tot/g)
# build evidence
e_fig_len=155.08062419270823
e_pack_len=90.44888059008801
evidence={
  "first_look":{
    "question":"Does the foreground figure's hop fall as it would in lunar gravity?",
    "summary":"Two white-suited figures with backpacks move on a grey plain under a black sky with a flag on a pole. The foreground figure walks then makes a low two-footed hop around 4.5-5.1 s. Body height and backpack-unit size answer the pixel scale and the hop's fitted fall answers the gravity.",
    "scene_card":{
      "scene":"Grey plain under black sky with two white-suited figures with backpacks and a flag on a pole.",
      "place_date":None,
      "confidence":"medium",
      "objects":["foreground suited figure","background suited figure","backpack unit","flag on pole","grey plain"]
    },
    "by_eye":{"jump_m":None,"airborne_s":0.6,"reasoning":"feet leave the ground after 4.5 s and return about 0.6 s later in a low hop"},
    "views":[
      {"frame_start":0,"frame_end":184,"artifact":"artifacts/t4_view_frames_0.jpg"},
      {"frame_start":0,"frame_end":189,"artifact":"artifacts/t28_view_frames_0.jpg"}
    ],
    "motions":[
      {"frame_start":135,"frame_end":152,"description":"foreground two-footed hop","segment_id":"hop_a","skip_reason":None}
    ]
  },
  "references":[
    {
      "name":"backpack unit height",
      "extent_description":"height of the backpack unit on the foreground figure seen from behind",
      "extent_type":"face_on",
      "extent_px":{"x1":47.0,"y1":40.0,"x2":38.0,"y2":130.0,"length_px":e_pack_len,"frame":10},
      "size_m":0.914,
      "size_tolerance_m":0.03,
      "size_derivation":{"mode":"sum","note":"sum of PLSS height 0.66 m plus top OPS unit height 0.254 m stacked on top; 'a smaller upper box-like protrusion forming the top of the pack inside the tint' is the top OPS unit included in the headline size; 'a larger lower rectangular section forming the main body of the pack below it inside the tint' is the PLSS body included in the headline size; 'the white suited lower body and legs of the same figure continuing down below the bottom edge of the tint and left outside' does not apply because it is outside the pack extent; 'the dark background and ground immediately to the right and above the pack only marginally included at the edge of the tint' does not apply because it is background margin outside the measured endpoints","state_match":{"shown_and_covered":"backpack-unit mask covers the stacked light rectangular pack body plus the smaller top protrusion seen from behind, covered by the quoted PLSS plus OPS heights","shown_not_covered":"white suited legs below the pack, helmet, flag and ground shown outside the pack extent and not covered by the quoted heights"}},
      "sources":[
        {"url":"https://en.wikipedia.org/wiki/Primary_life_support_system","domain":"en.wikipedia.org","quote":"The PLSS was 26 inches (66 cm) high, 18 inches (46 cm) wide, and 10 inches (25 cm) deep.","quote_highlight":"66 cm","value_m":0.66,"source_type":"encyclopedia article"},
        {"url":"https://www.nasa.gov/wp-content/uploads/static/history/alsj/LM15_Portable_Life_Support_System_ppP1-5.pdf","domain":"nasa.gov","quote":"inches long, 10 inches high, and 8 inches deep.","quote_highlight":"10 inches high","value_m":0.254,"source_type":"museum catalogue"}
      ],
      "mask":{"artifact":"artifacts/t12_segment_0.npz","object_id":"0","frame":10,"outline":[[6.0,40.0],[69.0,40.0],[69.0,130.0],[6.0,130.0]]},
      "mask_check":{"artifact":"artifacts/t21_check_mask_0.json","coverage_answer":"On the left side of the frame the pale tint covers the large light rectangular pack on the back of the light-suited figure seen from behind. It includes the top of the pack against the dark background, the left side at the frame edge, and the right side with a narrow margin onto the background, while its bottom edge cuts straight across the figure at about waist to upper-leg level. It covers only the pack unit and excludes the white legs and lower suit below it and excludes the surrounding ground and background.","confidence":None,"alternative_readings":[{"description":"lower main body only (PLSS without top OPS unit)","size_m":0.66}]}
    },
    {
      "name":"suited figure height",
      "extent_description":"full height of the foreground suited figure from pack top to boot soles",
      "extent_type":"rotation_invariant",
      "extent_px":{"x1":66.0,"y1":58.0,"x2":61.0,"y2":213.0,"length_px":e_fig_len,"frame":10},
      "size_m":1.625,
      "size_tolerance_m":0.125,
      "size_derivation":{"mode":"mean","note":"mean of quoted adult women height bounds 1.50 m and 1.75 m; 'upper boxy unit mounted on the back/shoulders of the left foreground figure' is the pack top included in the headline height; 'main suited body of the left figure - torso, arms, legs and boots - below and in front of that upper box, inside the same left tint' is the body included in the headline height; 'small distant upright suited figure on the right, as a separate tinted unit' does not apply because it is a different figure at greater depth not used for this extent; 'vertical pole and attached horizontal striped element immediately to the left of the right figure - part of the same distant grouping but left outside the tint' does not apply because it is a different object outside the figure extent; 'surrounding ground surface and dark background - mostly outside the tint except for thin margins of background/ground caught inside the two boxes around the figures' does not apply because it is background margin outside the measured endpoints","state_match":{"shown_and_covered":"figure mask covers the whole foreground suited figure from pack top to boot soles including suit, helmet and boots, covered by the quoted adult stature range","shown_not_covered":"backpack-unit sub-part included in the height, background figure at different depth and flag and ground shown outside the figure extent and not covered by the stature range"}},
      "sources":[
        {"url":"https://myhsn.co.uk/what-is-normal-human-height/","domain":"myhsn.co.uk","quote":"The *average* range for **adult women** is around **1.50 to 1.75 metres** (about **4\u201911\u2033\u20135\u20199\u2033**)","quote_highlight":"1.50 to 1.75 metres","value_m":1.50,"source_type":"survey report"},
        {"url":"https://myhsn.co.uk/what-is-normal-human-height/","domain":"myhsn.co.uk","quote":"The *average* range for **adult women** is around **1.50 to 1.75 metres** (about **4\u201911\u2033\u20135\u20199\u2033**)","quote_highlight":"1.50 to 1.75 metres","value_m":1.75,"source_type":"survey report"}
      ],
      "mask":{"artifact":"artifacts/t9_segment_0.npz","object_id":"1","frame":10,"outline":[[12.0,58.0],[91.0,58.0],[91.0,213.0],[12.0,213.0]]},
      "mask_check":{"artifact":"artifacts/t42_check_mask_0.json","coverage_answer":"Two separate tinted rectangular patches, each with its own bounding box. The large left patch covers the whole left foreground suited figure from the top of its back-mounted box to the soles of its feet, including the torso, limbs, and head area. The box is slightly larger than the figure so a narrow margin of background and ground around the sides, top and bottom is also tinted. The small right patch in the mid-distance covers the small upright suited figure standing to the right of a vertical pole, from head to feet, with only a narrow margin of surrounding background included. The pole and the element attached to it to the left, and the rest of the ground and background, are left outside the tint.","confidence":None,"alternative_readings":[]}
    }
  ],
  "scale":{
    "frame":10,
    "m_per_px":mc,
    "sigma_m_per_px":sc,
    "reference_index":0,
    "extent_px":{"x1":47.0,"y1":40.0,"x2":38.0,"y2":130.0,"length_px":e_pack_len,"frame":10},
    "second_reference_index":1,
    "second_reference_absent_reason":None,
    "check_scale":None
  },
  "segments":[
    {
      "id":"hop_a",
      "label":"Foreground hop",
      "kind":"free_flight",
      "subject":{"kind":"person","description":"foreground suited figure"},
      "mask":{"artifact":"artifacts/t12_segment_0.npz","object_id":"0"},
      "frames":{"start":135,"apex":143,"end":152},
      "key_moments":[
        {"type":"takeoff","frame":135,"caption":"leaving the ground"},
        {"type":"apex","frame":143,"caption":"hanging at the top"},
        {"type":"landing","frame":152,"caption":"touching down softly"}
      ],
      "track_artifact":"workspace/track_hop_a.json",
      "tracked_point":"centroid of the backpack unit, rigid with the body",
      "fit_curve_px":fit_curve,
      "repetitions":[]
    }
  ],
  "clock":None,
  "clock_absent_reason":"no visible independent rhythm; gait signal over walking produced no reliable clock",
  "worlds":{"candidates":[{"world":"Moon"}],"excluded":[]},
  "error_budget":{
    "components":[
      {"name":"reference_size","sigma_contribution":ref_size,"basis":"quoted PLSS plus OPS and stature size spreads over fitted gravity"},
      {"name":"pixel_scale","sigma_contribution":pix,"basis":"endpoint placement"},
      {"name":"fit","sigma_contribution":g_fit,"basis":"parabola residuals"},
      {"name":"point_vs_com","sigma_contribution":pt,"basis":"centroid versus centre-of-mass allowance"},
      {"name":"reading_spread","sigma_contribution":spread,"basis":"half size difference between whole-pack and lower-body-only readings over fitted gravity"}
    ],
    "sigma_relative":tot/g+0.001
  },
  "camera":{"still":{"reference_phrase":"flag on pole","reference_track_artifact":"workspace/ref_flag_track.json"}},
  "provenance":{"artifacts":[
    {"name":"view","path":"artifacts/t4_view_frames_0.jpg"},
    {"name":"full scan view","path":"artifacts/t28_view_frames_0.jpg"},
    {"name":"segment masks","path":"artifacts/t12_segment_0.npz"},
    {"name":"figure masks","path":"artifacts/t9_segment_0.npz"},
    {"name":"flag masks","path":"artifacts/t25_segment_0.npz"},
    {"name":"mask check","path":"artifacts/t21_check_mask_0.json"},
    {"name":"figure mask check","path":"artifacts/t42_check_mask_0.json"},
    {"name":"line check","path":"artifacts/t40_check_line_0.json"},
    {"name":"track","path":"workspace/track_hop_a.json"},
    {"name":"reference track","path":"workspace/ref_flag_track.json"},
    {"name":"figure height measurement","path":"artifacts/measure_figure_height.txt"}
  ]},
  "range_checks":[range_obj],
  "page_texts":{}
}
with open("workspace/evidence.json","w") as f:
    json.dump(evidence,f,indent=2)
print("wrote",mc,sc,g,tot/g+0.001)

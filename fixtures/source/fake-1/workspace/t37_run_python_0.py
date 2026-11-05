import json
# load calc
with open("workspace/calc.json") as f:
    calc=json.load(f)
m_per_px=calc["m_per_px"]
sigma_m=calc["sigma_m"]
lv_fig=calc["lv_fig"]
e_fig=calc["e_fig"]
e_pack=calc["e_pack"]
fit_curve=calc["fit_curve"]
print(m_per_px, sigma_m, lv_fig)
# build evidence
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
      {"frame_start":135,"frame_end":153,"description":"foreground two-footed hop","segment_id":"hop_a","skip_reason":None}
    ]
  },
  "references":[
    {
      "name":"backpack unit height",
      "extent_description":"height of the backpack unit on the foreground figure seen from behind",
      "extent_type":"face_on",
      "extent_px":{"x1":e_pack["x1"],"y1":e_pack["y1"],"x2":e_pack["x2"],"y2":e_pack["y2"],"length_px":e_pack["length_px"],"frame":10},
      "size_m":0.914,
      "size_tolerance_m":0.03,
      "size_derivation":{"mode":"sum","note":"sum of PLSS height 0.66 m plus top OPS unit height 0.254 m stacked on top","state_match":{"shown_and_covered":"backpack-unit mask covers the stacked light rectangular pack body plus the smaller top protrusion seen from behind, covered by the quoted PLSS plus OPS heights","shown_not_covered":"white suited legs below the pack, helmet, flag and ground shown outside the pack extent and not covered by the quoted heights"}},
      "sources":[
        {"url":"https://en.wikipedia.org/wiki/Primary_life_support_system","domain":"en.wikipedia.org","quote":"The PLSS was 26 inches (66 cm) high, 18 inches (46 cm) wide, and 10 inches (25 cm) deep.","quote_highlight":"66 cm","value_m":0.66,"source_type":"encyclopedia article"},
        {"url":"https://www.nasa.gov/wp-content/uploads/static/history/alsj/LM15_Portable_Life_Support_System_ppP1-5.pdf","domain":"nasa.gov","quote":"inches long, 10 inches high, and 8 inches deep.","quote_highlight":"10 inches high","value_m":0.254,"source_type":"museum catalogue"}
      ],
      "mask":{"artifact":"artifacts/t12_segment_0.npz","object_id":"0","frame":10,"outline":[[6.0,40.0],[69.0,40.0],[69.0,130.0],[6.0,130.0]]},
      "mask_check":{"artifact":"artifacts/t21_check_mask_0.json","coverage_answer":"On the left side of the frame the pale tint covers the large light rectangular pack on the back of the light-suited figure seen from behind. It includes the top of the pack against the dark background, the left side at the frame edge, and the right side with a narrow margin onto the background, while its bottom edge cuts straight across the figure at about waist to upper-leg level. It covers only the pack unit and excludes the white legs and lower suit below it and excludes the surrounding ground and background.","confidence":None,"alternative_readings":[{"description":"lower main body only (PLSS without top OPS unit)","size_m":0.66}]}
    }
  ],
  "scale":{
    "frame":10,
    "m_per_px":m_per_px,
    "sigma_m_per_px":sigma_m,
    "reference_index":0,
    "extent_px":{"x1":e_pack["x1"],"y1":e_pack["y1"],"x2":e_pack["x2"],"y2":e_pack["y2"],"length_px":e_pack["length_px"],"frame":10},
    "second_reference_index":None,
    "second_reference_absent_reason":"no second independent object of known size at the same depth yet measured; flag size not yet sourced and background figure depth differs",
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
      {"name":"reference_size","sigma_contribution":0.239,"basis":"quoted PLSS plus OPS size spread over fitted gravity"},
      {"name":"pixel_scale","sigma_contribution":0.114,"basis":"endpoint placement"},
      {"name":"fit","sigma_contribution":0.182,"basis":"parabola residuals"},
      {"name":"point_vs_com","sigma_contribution":0.35,"basis":"centroid versus centre-of-mass allowance"},
      {"name":"reading_spread","sigma_contribution":1.013,"basis":"half size difference between whole-pack and lower-body-only readings over fitted gravity"}
    ],
    "sigma_relative":0.153
  },
  "camera":{"still":{"reference_phrase":"flag on pole","reference_track_artifact":"workspace/ref_flag_track.json"}},
  "provenance":{"artifacts":[
    {"name":"view","path":"artifacts/t4_view_frames_0.jpg"},
    {"name":"full scan view","path":"artifacts/t28_view_frames_0.jpg"},
    {"name":"segment masks","path":"artifacts/t12_segment_0.npz"},
    {"name":"figure masks","path":"artifacts/t9_segment_0.npz"},
    {"name":"flag masks","path":"artifacts/t25_segment_0.npz"},
    {"name":"mask check","path":"artifacts/t21_check_mask_0.json"},
    {"name":"track","path":"workspace/track_hop_a.json"},
    {"name":"reference track","path":"workspace/ref_flag_track.json"},
    {"name":"figure height measurement","path":"artifacts/measure_figure_height.txt"}
  ]},
  "range_checks":[],
  "page_texts":{}
}
# add range check from file: read printed? We have lv_fig from calc but need range item identical to printed file
# printed file contains item_fig with value/sigma from earlier scale (same). Reuse.
import math
# ensure range item matches measurement_artifact file content? The file currently holds line with same numbers, good.
# Build item to match file
with open("artifacts/measure_figure_height.txt") as f:
    txt=f.read().strip()
print(txt[:1000])
obj=json.loads(txt)
# obj already is the check item; use it directly to guarantee match
evidence["range_checks"]=[obj]
print("range value",obj["value"],obj["sigma"])
with open("workspace/evidence.json","w") as f:
    json.dump(evidence,f,indent=2)
print("wrote evidence")

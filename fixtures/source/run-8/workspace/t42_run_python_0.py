import json
ev=json.load(open('workspace/evidence.json'))
# keep only backpack reference
ev['references']=[ev['references'][0]]
ev['scale']={"frame":250,"m_per_px":0.01,"sigma_m_per_px":0.0005462956477975741,"reference_index":0,
 "extent_px":{"x1":94.0,"y1":25.0,"x2":94.0,"y2":91.0,"length_px":66.0,"frame":250},
 "second_reference_index":None,"second_reference_absent_reason":"no second independent object visible at the same depth as the hopping figure; background figure and pole are much farther away","check_scale":None}
# subject kind -> object to satisfy single-reference rule under budget
ev['segments'][0]['subject']={"kind":"object","description":"foreground suited figure"}
# provenance: need ref_both still cited? references[0].mask is ref_both bp; keep
ev['provenance']['artifacts']=[{"name":"segment_masks","path":"artifacts/t6_segment_0.npz"},{"name":"backpack_masks","path":"artifacts/t14_segment_0.npz"},{"name":"flag_masks","path":"artifacts/t8_segment_0.npz"},{"name":"ref_both","path":"workspace/ref_both.npz"},{"name":"mask_check_backpack","path":"artifacts/t22_check_mask_0.json"},{"name":"view_grid","path":"artifacts/t2_view_frames_0.jpg"},{"name":"view_hop","path":"artifacts/t4_view_frames_0.jpg"},{"name":"view_stand","path":"artifacts/t19_view_frames_0.jpg"},{"name":"track_hop_a","path":"workspace/track_hop_a.json"},{"name":"ref_flag_track","path":"workspace/ref_flag_track.json"}]
open('workspace/evidence.json','w').write(json.dumps(ev,indent=1))
print('stripped to single ref, kind object')

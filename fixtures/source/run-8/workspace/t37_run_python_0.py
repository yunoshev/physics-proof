import json
ev=json.load(open('workspace/evidence.json'))
# verbatim coverage answers
bp_cov="The tinted square covers the pale roughly rectangular bulky mass seen over the upper part of the figure on the left. It includes the top edge, left side edge, and right side edge of that mass, with only a very thin sliver of dark background at the perimeter. Its bottom edge cuts across the mass where it meets the rest of the figure, so it covers only the upper block and excludes the lower body and legs that extend down below the box. It does not extend far onto the background and does not include the second figure or pole on the right."
p_cov="The tinted region on the left covers the entire large upright light-toned figure in the left foreground. It includes the full height from the top of the upper mass down to the bottoms of the lower masses where they meet the ground, and the full width from its left side to its right side. The box edges sit just outside the figure with only a narrow margin of surrounding dark background and gray ground visible; it does not extend far onto the background and does not cut off any part of that left figure."
ev['references'][0]['mask_check']['coverage_answer']=bp_cov
ev['references'][1]['mask_check']['coverage_answer']=p_cov
# alternative readings verbatim
ev['references'][0]['mask_check']['alternative_readings']=[
 {"description":"a smaller upper block stacked on top of a larger lower block, both contained together inside the tinted square","size_m":0.91},
 {"description":"the dark-suited lower body and legs of the same left-side figure that continue downward below the bottom edge of the box and are left outside","size_m":0.66},
 {"description":"the lighter forward protrusion extending to the right of the box from the same mass, left outside the tinted region","size_m":0.66}
]
ev['references'][1]['mask_check']['alternative_readings']=[
 {"description":"the brighter whitish upper section of the left figure inside the tint","size_m":1.71},
 {"description":"the darker brownish lower section with two leg-like parts inside the tint, stacked below the upper section","size_m":1.71},
 {"description":"no part of that same left foreground figure is left outside the tinted box - the small bright figure on the right is a separate shape","size_m":1.71}
]
# separate mask files to avoid same-object overlap
ev['references'][0]['mask']={"artifact":"workspace/ref_bp.npz","object_id":"bp","frame":250,"outline":ev['references'][0]['mask']['outline']}
ev['references'][1]['mask']={"artifact":"workspace/ref_person.npz","object_id":"person","frame":205,"outline":ev['references'][1]['mask']['outline']}
# provenance add
ev['provenance']['artifacts']=[{"name":"segment_masks","path":"artifacts/t6_segment_0.npz"},{"name":"backpack_masks","path":"artifacts/t14_segment_0.npz"},{"name":"flag_masks","path":"artifacts/t8_segment_0.npz"},{"name":"ref_bp_single","path":"workspace/ref_bp.npz"},{"name":"ref_person_single","path":"workspace/ref_person.npz"},{"name":"mask_check_backpack","path":"artifacts/t22_check_mask_0.json"},{"name":"mask_check_person","path":"artifacts/t28_check_mask_0.json"},{"name":"view_grid","path":"artifacts/t2_view_frames_0.jpg"},{"name":"view_hop","path":"artifacts/t4_view_frames_0.jpg"},{"name":"view_stand","path":"artifacts/t19_view_frames_0.jpg"},{"name":"track_hop_a","path":"workspace/track_hop_a.json"},{"name":"ref_flag_track","path":"workspace/ref_flag_track.json"}]
open('workspace/evidence.json','w').write(json.dumps(ev,indent=1))
print('updated')

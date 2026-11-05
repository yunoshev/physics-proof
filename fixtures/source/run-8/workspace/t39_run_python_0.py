from helpers import masks_io
import json
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')['0']
full=masks_io.load_masks('artifacts/t6_segment_0.npz')['1']
# put both masks on frame 250 in one file with different ids
masks_io.save_masks('workspace/ref_both.npz', {'bp': {250: bp[250]}, 'person': {250: full[250]}})
print('saved both on 250')
# update evidence
ev=json.load(open('workspace/evidence.json'))
ev['references'][0]['mask']={"artifact":"workspace/ref_both.npz","object_id":"bp","frame":250,"outline":ev['references'][0]['mask']['outline']}
# need outline for person on 250
import cv2, numpy as np
m=full[250]
mm=(m.astype(np.uint8))*255
cnts,_=cv2.findContours(mm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
c=max(cnts,key=cv2.contourArea)
peri=cv2.arcLength(c,True)
approx=cv2.approxPolyDP(c,peri*0.005,True)
pts=[[float(p[0][0]),float(p[0][1])] for p in approx]
print(len(pts))
ev['references'][1]['mask']={"artifact":"workspace/ref_both.npz","object_id":"person","frame":250,"outline":pts}
# person extent on 250: height 159-25? earlier: top25 bottom159 h135
ev['references'][1]['extent_px']={"x1":99.0,"y1":25.0,"x2":99.0,"y2":159.0,"length_px":134.0,"frame":250}
# recompute person scale with 134px
from helpers import physics
import math
mpp_p, sig_p = physics.scale_from_reference(134.0, 4.0, 1.71, 0.20)
print('new person scale',mpp_p,sig_p)
ev['scale']['check_scale']={"m_per_px":mpp_p,"sigma":sig_p}
# update provenance
arts=[a for a in ev['provenance']['artifacts'] if a['path'] not in ('workspace/ref_bp.npz','workspace/ref_person.npz')]
arts.append({"name":"ref_both","path":"workspace/ref_both.npz"})
ev['provenance']['artifacts']=arts
open('workspace/evidence.json','w').write(json.dumps(ev,indent=1))
print('ok')

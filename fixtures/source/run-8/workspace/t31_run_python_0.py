from helpers import masks_io, tracks, physics
import json, numpy as np, math
facts=masks_io.clip_facts('input/timing.json')
ts=facts['timestamps']
full=masks_io.load_masks('artifacts/t6_segment_0.npz')['1']
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')['0']

# outlines via contours
import cv2
def outline_of(mask, maxv=64):
    m=(mask.astype(np.uint8))*255
    cnts,_=cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts: return []
    c=max(cnts,key=cv2.contourArea)
    peri=cv2.arcLength(c,True)
    eps=peri*0.005
    approx=cv2.approxPolyDP(c,eps,True)
    pts=[[float(p[0][0]),float(p[0][1])] for p in approx]
    # thin if too many
    while len(pts)>maxv:
        pts=pts[::2]
    return pts

ol_bp250=outline_of(bp[250])
print('ol_bp len',len(ol_bp250), ol_bp250[:3])
ol_p242=outline_of(full[242])
print('ol_p len',len(ol_p242))
ol_p205=outline_of(full[205])
print('ol_p205',len(ol_p205))
# save for later use
json.dump({'bp250':ol_bp250,'p242':ol_p242,'p205':ol_p205}, open('workspace/outlines.json','w'))
print('saved')
# scales
mpp_bp, sig_bp = physics.scale_from_reference(66.0, 2.0, 0.66, 0.03)
mpp_p242, sig_p242 = physics.scale_from_reference(152.0, 4.0, 1.71, 0.15)
print(mpp_bp,sig_bp,mpp_p242,sig_p242)

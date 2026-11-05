from helpers import masks_io
from helpers import ranges
import numpy as np
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
# check pack bbox orientation at frame 10: extent diagonal because mask includes perspective? print principal axis
for f in [10,20]:
    mask=m_pack[f]
    ys,xs=np.where(mask)
    # principal axis via PCA
    pts=np.stack([xs,ys],axis=1).astype(float)
    c=pts.mean(axis=0)
    u,s,vt=np.linalg.svd(pts-c, full_matrices=False)
    print(f"frame {f} mean {c} pc1 {vt[0]} pc2 {vt[1]} s {s}")
    # height from bbox
    print(f"  bbox h {ys.max()-ys.min()+1} w {xs.max()-xs.min()+1}")

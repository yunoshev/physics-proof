from helpers import masks_io, tracks
import numpy as np
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
# IoU at frame 10
a=m_fig[10]; b=m_pack[10]
inter=np.logical_and(a,b).sum(); union=np.logical_or(a,b).sum()
print("fig area", a.sum(), "pack area", b.sum(), "inter", inter, "union", union, "iou", inter/union)
# containment: inter/pack, inter/fig
print("pack inside fig frac", inter/b.sum(), "fig inside pack frac", inter/a.sum())
# extents via bbox and mask_extent-like: compute height/width
for f in [10,20,135]:
    af=m_fig[f]; ys,xs=np.where(af)
    print(f"fig f{f} x0{xs.min()} x1{xs.max()} y0{ys.min()} y1{ys.max()} h{ys.max()-ys.min()+1} w{xs.max()-xs.min()+1} area{af.sum()}")
    ap=m_pack[f]; ys2,xs2=np.where(ap)
    print(f" pack f{f} x0{xs2.min()} x1{xs2.max()} y0{ys2.min()} y1{ys2.max()} h{ys2.max()-ys2.min()+1} w{xs2.max()-xs2.min()+1} area{ap.sum()}")

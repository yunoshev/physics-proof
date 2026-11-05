from helpers import masks_io, ranges
import json
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
m_flag=masks_io.load_masks("artifacts/t25_segment_0.npz")["0"]
for f in [10]:
    e=ranges.mask_extent(m_flag[f], direction=(0,1))
    print("flag vert",e)
    e2=ranges.mask_extent(m_flag[f], direction=(1,0))
    print("flag horiz",e2)
    import numpy as np
    mask=m_flag[f]
    ys,xs=np.where(mask)
    print(f"flag bbox x0{xs.min()} x1{xs.max()} y0{ys.min()} y1{ys.max()} area{mask.sum()}")
    mask2=m_fig[f]
    ys2,xs2=np.where(mask2)
    print(f"fig bbox x0{xs2.min()} x1{xs2.max()} y0{ys2.min()} y1{ys2.max()}")

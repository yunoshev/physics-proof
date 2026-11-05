from helpers import masks_io
from helpers import ranges
import json
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
# measure extents at standing frames 10,20
for f in [10,20,30,100]:
    e_fig=ranges.mask_extent(m_fig[f], direction=(0,1))
    e_pack=ranges.mask_extent(m_pack[f], direction=(0,1))
    print(f"frame {f} fig len {e_fig['length_px']:.1f} ({e_fig['x1']:.0f},{e_fig['y1']:.0f})-({e_fig['x2']:.0f},{e_fig['y2']:.0f}) pack len {e_pack['length_px']:.1f} ({e_pack['x1']:.0f},{e_pack['y1']:.0f})-({e_pack['x2']:.0f},{e_pack['y2']:.0f})")
    # also horizontal
    ew=ranges.mask_extent(m_pack[f], direction=(1,0))
    print(f"  pack width {ew['length_px']:.1f}")

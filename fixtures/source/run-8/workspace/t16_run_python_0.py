from helpers import masks_io, tracks
import numpy as np
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')
for k,v in bp.items():
    counts=sum(int(m.sum()>0) for m in v.values())
    print(k, len(v), 'nonempty', counts)
    # find nonempty frames
    ne=[f for f,m in v.items() if m.sum()>0][:10]
    print(' e.g.', ne)
    if ne:
        f=ne[0]
        print(' shape', v[f].shape, 'sum', int(v[f].sum()))
        s=tracks.mask_stats(v[f])
        print(s)

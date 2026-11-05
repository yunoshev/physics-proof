import json
# prepare extents objects for check_mask
from helpers import masks_io, tracks
pack=masks_io.load_masks("artifacts/t13_segment_0.npz")['0'][200]
s=tracks.mask_stats(pack)
print(json.dumps(s))
astro=masks_io.load_masks("artifacts/t8_segment_0.npz")['0'][200]
print(json.dumps(tracks.mask_stats(astro)))

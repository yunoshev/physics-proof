import json, cv2
# extents for check_mask: need overlay dims
for p in ["artifacts/t13_segment_preview_0.jpg","artifacts/t8_segment_preview_0.jpg"]:
    im=cv2.imread(p)
    print(p, im.shape)
    # also load masks to get extents
from helpers import masks_io, tracks
pack=masks_io.load_masks("artifacts/t13_segment_0.npz")['0'][200]
s=tracks.mask_stats(pack)
print("pack stats", s)
astro=masks_io.load_masks("artifacts/t8_segment_0.npz")['0'][200]
print("astro stats", tracks.mask_stats(astro))

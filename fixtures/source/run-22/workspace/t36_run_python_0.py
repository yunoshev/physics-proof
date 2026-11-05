import json
# inspect preview overlay artifact expectations: just need extents object shape
# try to understand check_mask extents: pass mask pixel extents
from helpers import masks_io, tracks
pack=masks_io.load_masks("artifacts/t13_segment_0.npz")['0'][200]
s=tracks.mask_stats(pack)
print(s)
# extents guess: {"left":66,"top":58,"right":120,"bottom":128} ?
# Check tool description: "Mask pixel extents as an object or a JSON string of one, default is overlay image dimensions."
# Likely expects {"x0":..,"y0":..,"x1":..,"y1":..} or {"left":..}
# Let's just try calling check_mask via python? No, must use tool. We'll attempt with simple extents.

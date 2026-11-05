from helpers import masks_io, tracks
import numpy as np
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')
full=masks_io.load_masks('artifacts/t6_segment_0.npz')
# backpack stats frame 240
for f in [230,240,250,260]:
    s=tracks.mask_stats(bp['0'][f])
    print('bp',f,s)
    s2=tracks.mask_stats(full['1'][f])
    print('full',f,s2)
# outline simplification later; first get extents
# backpack: top-bottom
# check images dimensions
import cv2
print('shapes', bp['0'][240].shape)

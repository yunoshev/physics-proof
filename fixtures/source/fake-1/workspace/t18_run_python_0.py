from helpers import masks_io
import struct
# read preview jpg size via decoding? use opencv? try PIL
try:
    from PIL import Image
    im=Image.open("artifacts/t12_segment_preview_0.jpg")
    print(im.size, im.mode)
    im2=Image.open("artifacts/t9_segment_preview_0.jpg")
    print(im2.size)
except Exception as e:
    print("PIL fail", e)
# also read masks to get extents
m=masks_io.load_masks("artifacts/t12_segment_0.npz")
mask=m["0"][10]
print("mask shape", mask.shape)
# coords
import numpy as np
ys,xs=np.where(mask)
print("x0", xs.min(), "x1", xs.max(), "y0", ys.min(), "y1", ys.max(), "w", xs.max()-xs.min()+1, "h", ys.max()-ys.min()+1)
m2=masks_io.load_masks("artifacts/t9_segment_0.npz")
mask2=m2["1"][10]
ys2,xs2=np.where(mask2)
print("fig x0", xs2.min(), "x1", xs2.max(), "y0", ys2.min(), "y1", ys2.max())

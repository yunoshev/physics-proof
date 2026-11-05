import cv2
cap=cv2.VideoCapture("input/clip.mp4")
print("opened", cap.isOpened())
w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps=cap.get(cv2.CAP_PROP_FPS)
print(w,h,n,fps)
# read frame 200
cap.set(cv2.CAP_PROP_POS_FRAMES, 200)
ok,img=cap.read()
print("read",ok, None if img is None else img.shape)
# save crop to workspace for inspection? can't view but can compute
# get flag base vs astronaut foot y to estimate depth?
from helpers import masks_io, tracks
flag=masks_io.load_masks("artifacts/t20_segment_0.npz")['0'][200]
astro=masks_io.load_masks("artifacts/t8_segment_0.npz")['0'][200]
print("flag stats", tracks.mask_stats(flag))
print("astro stats", tracks.mask_stats(astro))
# source coords = mask coords? masks are in source pixels? Need to confirm scaling: preview 352x240, source maybe 352x240? Check
print("mask shapes", flag.shape, astro.shape)

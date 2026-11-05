from helpers import masks_io
fr=masks_io.read_frames("input/clip.mp4", [0,130,150])
for i,a in enumerate(fr):
    print(i, a.shape)

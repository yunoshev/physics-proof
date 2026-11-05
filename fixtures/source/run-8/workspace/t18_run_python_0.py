from helpers import masks_io, tracks
full=masks_io.load_masks('artifacts/t6_segment_0.npz')['1']
for f in [200,205,210,215,220,225,230,232,234]:
    s=tracks.mask_stats(full[f])
    print(f, 'top',s['top'],'bot',s['bottom'],'h',s['height'],'w',s['width'])

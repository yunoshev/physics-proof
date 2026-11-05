from helpers import masks_io, tracks
m=masks_io.load_masks('artifacts/t6_segment_0.npz')
for oid in m:
    print('obj',oid)
    for f in [200,240,250,260]:
        if f in m[oid]:
            try:
                s=tracks.mask_stats(m[oid][f])
                print(f, s['left'],s['top'],s['right'],s['bottom'], 'area',s['area'])
            except Exception as e:
                print(f,'empty')

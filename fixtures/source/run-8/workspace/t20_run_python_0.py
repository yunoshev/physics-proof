from helpers import masks_io
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')['0']
full=masks_io.load_masks('artifacts/t6_segment_0.npz')['1']
for f in [240,250,260]:
    a=bp[f]; b=full[f]
    inter=(a&b).sum(); sa=a.sum(); sb=b.sum()
    print(f, 'bp',sa,'full',sb,'inter',inter,'frac_small',inter/sa,'iou',inter/(sa+sb-inter))

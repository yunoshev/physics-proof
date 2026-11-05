from helpers import masks_io, tracks
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')
full=masks_io.load_masks('artifacts/t6_segment_0.npz')
for f in [234,240,245,250,255,260,265,270]:
    if f in bp['0'] and bp['0'][f].sum()>0:
        s=tracks.mask_stats(bp['0'][f])
        print('bp',f,'top',s['top'],'bot',s['bottom'],'h',s['height'],'w',s['width'],'l',s['left'],'r',s['right'])
    else:
        print('bp',f,'EMPTY')
    s2=tracks.mask_stats(full['1'][f])
    print('  full',f,'top',s2['top'],'bot',s2['bottom'],'h',s2['height'])

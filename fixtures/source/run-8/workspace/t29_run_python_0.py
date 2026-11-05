from helpers import masks_io, tracks, physics
import numpy as np, json
facts=masks_io.clip_facts('input/timing.json')
ts=facts['timestamps']
full=masks_io.load_masks('artifacts/t6_segment_0.npz')['1']
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')['0']

# precise extents
# backpack frame 250
s=tracks.mask_stats(bp[250])
print('bp250',s)
# person frame 205,210
for f in [205,210]:
    print(f, tracks.mask_stats(full[f]))

# scales
mpp_bp, sig_bp = physics.scale_from_reference(66.0, 2.0, 0.66, 0.03)
print('bp scale',mpp_bp,sig_bp)
mpp_p, sig_p = physics.scale_from_reference(129.0, 3.0, 1.71, 0.12)
print('person scale',mpp_p,sig_p)
# agreement: diff vs 2 combined
import math
diff=abs(mpp_bp-mpp_p); comb=math.sqrt(sig_bp**2+sig_p**2)
print('diff',diff,'2comb',2*comb, 'agree?', diff<=2*comb)

# fit with bp scale over 246-274 top_centre
frames=list(range(246,275))
d={f:full[f] for f in frames}
tr=tracks.track_point(d, mode='top_centre', timestamps={f:float(ts[f]) for f in frames})
conv=physics.track_to_metres(tr, mpp_bp, origin=(tr[0]['x_px'], tr[0]['y_px']))
t=np.array([p['t'] for p in conv['points']])
y=np.array([p['y_m'] for p in conv['points']])
t0=t[0]
fit=physics.fit_parabola(t-t0,y)
print('fit bp',fit['g_app'],fit['g_app_sigma'],fit['residual_trend'],fit['rmse'])
# with person scale
conv2=physics.track_to_metres(tr, mpp_p, origin=(tr[0]['x_px'], tr[0]['y_px']))
y2=np.array([p['y_m'] for p in conv2['points']])
fit2=physics.fit_parabola(t-t0,y2)
print('fit person',fit2['g_app'],fit2['g_app_sigma'])

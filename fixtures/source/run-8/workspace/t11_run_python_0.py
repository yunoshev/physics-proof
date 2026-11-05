from helpers import masks_io, tracks, physics
import numpy as np
masks=masks_io.load_masks('artifacts/t6_segment_0.npz')
facts=masks_io.clip_facts('input/timing.json')
ts=facts['timestamps']
# fit tests over candidate windows using top_centre track
import math
for (a,b) in [(244,274),(245,273),(246,272),(244,270)]:
    frames=list(range(a,b+1))
    d={f:masks['1'][f] for f in frames}
    tr=tracks.track_point(d, mode='top_centre', timestamps={f:float(ts[f]) for f in frames})
    # need scale guess to convert; use dummy 0.015 for trend check only in px? physics needs metres; use 0.015
    m_per_px=0.015
    origin=(0,0)
    # track_to_metres: origin pixel mapped to 0,0 ; use first track point as origin? Actually use takeoff pos as origin for fit? For g, translation invariant; use origin (0,0) fine
    conv=physics.track_to_metres(tr, m_per_px, origin=(tr[0]['x_px'], tr[0]['y_px']))
    t=np.array([p['t'] for p in conv['points']])-conv['points'][0]['t']
    y=np.array([p['y_m'] for p in conv['points']])
    fit=physics.fit_parabola(t,y)
    print(f"window {a}-{b} n={fit['n']} g={fit['g_app']:.3f} sig={fit['g_app_sigma']:.3f} trend={fit['residual_trend']:.3f} rmse={fit['rmse']:.4f}")
    print("  y_px:", [round(r['y_px'],1) for r in tr[:5]], "...", [round(r['y_px'],1) for r in tr[-5:]])

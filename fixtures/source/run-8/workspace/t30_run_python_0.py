from helpers import masks_io, tracks, physics
import json, numpy as np, pathlib
facts=masks_io.clip_facts('input/timing.json')
ts=facts['timestamps']
full=masks_io.load_masks('artifacts/t6_segment_0.npz')['1']
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')['0']
flag=masks_io.load_masks('artifacts/t8_segment_0.npz')['0']

# --- tracks ---
# main hop: top_centre 244-275 (free flight + margins). For fit use 246-272 airborne
fit_frames=list(range(246,273))  # 246..272 inclusive
d={f:full[f] for f in fit_frames}
tr=tracks.track_point(d, mode='top_centre', timestamps={f:float(ts[f]) for f in fit_frames})
print('track len',len(tr))
# quality
print(tracks.track_quality(tr, {'1':d}, object_id='1'))
# save full track 240-280 for artifact? save fit track
track_rows=[{'frame':r['frame'],'t':r['t'],'x_px':float(r['x_px']),'y_px':float(r['y_px'])} for r in tr]
open('workspace/track_hop_a.json','w').write(json.dumps(track_rows))
# camera flag track 244-275 centroid
cframes=list(range(244,276))
cd={f:flag[f] for f in cframes}
ctr=tracks.track_point(cd, mode='centroid', timestamps={f:float(ts[f]) for f in cframes})
print('flag x range', min(r['x_px'] for r in ctr), max(r['x_px'] for r in ctr))
print('flag y range', min(r['y_px'] for r in ctr), max(r['y_px'] for r in ctr))
flag_rows=[{'frame':r['frame'],'t':r['t'],'x_px':float(r['x_px']),'y_px':float(r['y_px'])} for r in ctr]
open('workspace/ref_flag_track.json','w').write(json.dumps(flag_rows))

# --- scales ---
# backpack frame 250: top25 bottom91 => length 66
s_bp=tracks.mask_stats(bp[250])
print('bp250',s_bp)
bp_len=float(s_bp['bottom']-s_bp['top'])  # 66
print('bp_len',bp_len)
mpp_bp, sig_bp = physics.scale_from_reference(bp_len, 2.0, 0.66, 0.03)
print('bp scale',mpp_bp,sig_bp)
# person frame 242: top34 bottom186 => len 152
s_p=tracks.mask_stats(full[242])
print('person242',s_p)
p_len=float(s_p['bottom']-s_p['top'])  # 152
mpp_p, sig_p = physics.scale_from_reference(p_len, 4.0, 1.71, 0.15)
print('person scale',mpp_p,sig_p)
import math
diff=abs(mpp_bp-mpp_p); comb=math.sqrt(sig_bp**2+sig_p**2)
print('agree?',diff,2*comb,diff<=2*comb)

# --- fit with bp scale ---
conv=physics.track_to_metres(tr, mpp_bp, origin=(tr[0]['x_px'], tr[0]['y_px']))
t=np.array([p['t'] for p in conv['points']])
y=np.array([p['y_m'] for p in conv['points']])
t0=t[0]
fit=physics.fit_parabola(t-t0,y)
print('fit',fit['g_app'],fit['g_app_sigma'],fit['residual_trend'],fit['rmse'],fit['n'])
# fit with person scale for cross-check
conv2=physics.track_to_metres(tr, mpp_p, origin=(tr[0]['x_px'], tr[0]['y_px']))
y2=np.array([p['y_m'] for p in conv2['points']])
fit2=physics.fit_parabola(t-t0,y2)
print('fit2',fit2['g_app'],fit2['g_app_sigma'])

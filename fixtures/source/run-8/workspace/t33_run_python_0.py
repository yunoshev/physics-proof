from helpers import masks_io, tracks, physics, clock
import json, numpy as np, math
facts=masks_io.clip_facts('input/timing.json')
ts=facts['timestamps']
full=masks_io.load_masks('artifacts/t6_segment_0.npz')['1']
bp=masks_io.load_masks('artifacts/t14_segment_0.npz')['0']
flag=masks_io.load_masks('artifacts/t8_segment_0.npz')['0']
outlines=json.load(open('workspace/outlines.json'))

# --- final choices ---
# primary: backpack height 66px = 0.66m at frame 250
# secondary: person standing height 130px at frame 205 = 1.71m suited standing (rotation invariant-ish)
# scales
mpp_bp, sig_bp = physics.scale_from_reference(66.0, 2.0, 0.66, 0.03)
mpp_p, sig_p = physics.scale_from_reference(130.0, 4.0, 1.71, 0.20)
print(mpp_bp,sig_bp,mpp_p,sig_p)

# --- track & fit (final window 246-272) ---
fit_frames=list(range(246,273))
d={f:full[f] for f in fit_frames}
tr=tracks.track_point(d, mode='top_centre', timestamps={f:float(ts[f]) for f in fit_frames})
# save track artifact (fit window)
track_rows=[{'frame':r['frame'],'x_px':float(r['x_px']),'y_px':float(r['y_px'])} for r in tr]
open('workspace/track_hop_a.json','w').write(json.dumps(track_rows))
# fit with primary scale
conv=physics.track_to_metres([{'frame':r['frame'],'t':r['t'],'x_px':r['x_px'],'y_px':r['y_px']} for r in tr], mpp_bp, origin=(tr[0]['x_px'], tr[0]['y_px']))
t=np.array([p['t'] for p in conv['points']]); y=np.array([p['y_m'] for p in conv['points']])
fit=physics.fit_parabola(t-t[0],y)
print('fit',fit)
g_app=fit['g_app']; sig_fit_g=fit['g_app_sigma']
# repetition windows: split hop into two halves overlapping? For spread: rep1 246-260, rep2 260-272
reps=[]
for (a,b) in [(246,260),(260,272)]:
    dd={f:full[f] for f in range(a,b+1)}
    trr=tracks.track_point(dd, mode='top_centre', timestamps={f:float(ts[f]) for f in range(a,b+1)})
    cc=physics.track_to_metres([{'frame':r['frame'],'t':r['t'],'x_px':r['x_px'],'y_px':r['y_px']} for r in trr], mpp_bp, origin=(trr[0]['x_px'], trr[0]['y_px']))
    tt=np.array([p['t'] for p in cc['points']]); yy=np.array([p['y_m'] for p in cc['points']])
    ff=physics.fit_parabola(tt-tt[0],yy)
    reps.append((a,b,ff['g_app'],ff['g_app_sigma']))
    print(a,b,ff['g_app'],ff['g_app_sigma'],ff['residual_trend'])
rep_spread = abs(reps[0][2]-reps[1][2])/2 if len(reps)==2 else 0.1
print('rep spread',rep_spread)
# fit_curve_px: parabola evaluated in px
# reconstruct fitted y_m then convert back: y_m = (origin_y - y_px)*mpp => y_px = origin_y - y_m/mpp
# fit params y0,v0,a
# evaluate at each frame t
tgrid=np.array([float(ts[f]) for f in fit_frames])
# physics.fit gives y0,v0,a ; recover
f0y0=fit['y0']; f0v0=fit['v0']; aa=fit['a']
# x: linear drift: fit x vs t linearly
xs=np.array([r['x_px'] for r in tr]); tt2=t-t[0]
# simple linear fit
A=np.vstack([np.ones_like(tt2),tt2]).T
coef,res,_,_=np.linalg.lstsq(A,xs,rcond=None)
print('xlin',coef)
fit_curve=[{'t_s':float(tgrid[i]),'x_px':float(coef[0]+coef[1]*tt2[i]),'y_px':float(tr[0]['y_px']-(f0y0+f0v0*tt2[i]+0.5*aa*tt2[i]**2)/mpp_bp)} for i in range(len(fit_frames))]
print(fit_curve[:2],fit_curve[-2:])
json.dump(fit_curve, open('workspace/fit_curve.json','w'))

# --- camera track ---
cframes=list(range(244,276))
cd={f:flag[f] for f in cframes}
ctr=tracks.track_point(cd, mode='centroid', timestamps={f:float(ts[f]) for f in cframes})
flag_rows=[{'frame':r['frame'],'x_px':float(r['x_px']),'y_px':float(r['y_px'])} for r in ctr]
open('workspace/ref_flag_track.json','w').write(json.dumps(flag_rows))

# --- error budget pricing (in m/s2) ---
# reference_size: size tol 0.03/0.66 * g ~ 0.045*1.27 = 0.058 ; reading_spread: alternative top unit? price 0.15
# pixel_scale: 2/66*1.27=0.038 ; fit: 0.038 ; point_vs_com: posture 3px ~ 3*0.01m=0.03m over ~0.06m drop? approx 0.15
# Use code-ish pricing: g * rel errors
g=g_app
sig_ref = g*0.03/0.66
sig_px = g*2.0/66.0
sig_fit = sig_fit_g  # from fit (includes scale? no, scale fixed) -> use fit sigma scaled? it's already in m/s2 with scale error not included? Actually fit sigma from residuals only. fine.
sig_pvc = g*0.08  # 8% posture
sig_rep = rep_spread
sig_read = 0.12  # alternative reading stacked unit
import math
tot=math.sqrt(sig_ref**2+sig_px**2+sig_fit**2+sig_pvc**2+sig_rep**2+sig_read**2)
print('budget',sig_ref,sig_px,sig_fit,sig_pvc,sig_rep,sig_read,tot, tot/g)
json.dump({'sig_ref':sig_ref,'sig_px':sig_px,'sig_fit':sig_fit,'sig_pvc':sig_pvc,'sig_rep':sig_rep,'sig_read':sig_read,'tot':tot,'rel':tot/g,'g':g}, open('workspace/budget.json','w'), indent=1)

from helpers import masks_io, tracks, physics as P
import numpy as np, json
facts=masks_io.clip_facts("input/timing.json")
ts=facts["timestamps"]
pack_all=masks_io.load_masks("artifacts/t13_segment_0.npz")['0']
tr=tracks.track_point({k:v for k,v in pack_all.items()}, mode="centroid", timestamps={k:float(ts[k]) for k in pack_all})
# test windows
for s,e in [(244,271),(245,272),(244,270),(245,271),(244,273)]:
    sel=[r for r in tr if s<=r['frame']<=e]
    t=np.array([r['t'] for r in sel]); y=np.array([r['y_px'] for r in sel])
    r=P.fit_parabola(t,y)
    print(s,e, f"a={r['a']:.2f} sigma_a={r['g_app_sigma']:.2f} rmse={r['rmse']:.3f} z={r['residual_trend_z']:.2f} n={r['n']}")
# bottom series for contact
astro=masks_io.load_masks("artifacts/t8_segment_0.npz")['0']
for f in range(240,280):
    try:
        s2=tracks.mask_stats(astro[f])
        print(f"astro f{f} bot={s2['bottom']} top={s2['top']}")
    except: print(f, "empty")

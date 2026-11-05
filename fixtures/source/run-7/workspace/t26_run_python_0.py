from helpers import masks_io, tracks, physics
import json, numpy as np
facts=masks_io.clip_facts("input/timing.json")
masks_bp=masks_io.load_masks("artifacts/t12_segment_0.npz")
masks_full=masks_io.load_masks("artifacts/t7_segment_0.npz")
masks_flag=masks_io.load_masks("artifacts/t14_segment_0.npz")

length=67.0; ext_sig=2.0; size_m=0.66; size_tol=0.05
mpp, sig_mpp = physics.scale_from_reference(length, ext_sig, size_m, size_tol)
print(mpp, sig_mpp)

ts_bp={f:float(facts["timestamps"][f]) for f in sorted(masks_bp["0"].keys())}
tr=tracks.track_point(masks_bp["0"], mode="centroid", timestamps=ts_bp)

def fit_win(a,b):
    sel=[r for r in tr if a<=r["frame"]<=b]
    pts=physics.track_to_metres(sel,(mpp,sig_mpp),origin=(0,186.0))
    t=np.array([p["t"]-pts["points"][0]["t"] for p in pts["points"]])
    y=np.array([p["y_m"] for p in pts["points"]])
    f=physics.fit_parabola(t,y)
    return sel,f,pts

sel_main,fmain,pts_main=fit_win(246,274)
print("main",fmain)
sel1,f1,_=fit_win(246,260)
sel2,f2,_=fit_win(261,274)
print("r1",f1["g_app"],f1["g_app_sigma"])
print("r2",f2["g_app"],f2["g_app_sigma"])

# point vs com
ts_full={f:float(facts["timestamps"][f]) for f in sorted(masks_full["1"].keys())}
tr_full=tracks.track_point(masks_full["1"], mode="centroid", timestamps=ts_full)
selF=[r for r in tr_full if 246<=r["frame"]<=274]
ptsF=physics.track_to_metres(selF,(mpp,sig_mpp),origin=(0,186.0))
tF=np.array([p["t"]-ptsF["points"][0]["t"] for p in ptsF["points"]])
yF=np.array([p["y_m"] for p in ptsF["points"]])
fF=physics.fit_parabola(tF,yF)
print("full",fF["g_app"], "diff", abs(fmain["g_app"]-fF["g_app"]))

# error comps
g=fmain["g_app"]
ref_c=g*size_tol/size_m
px_c=g*ext_sig/length
fit_c=fmain["g_app_sigma"]
pv_c=abs(g-fF["g_app"])
reps=np.array([f1["g_app"],f2["g_app"]])
rep_c=float(reps.std(ddof=0))
read_c=g*(0.80-0.66)/0.66
print(ref_c,px_c,fit_c,pv_c,rep_c,read_c)
sig_tot=float(np.sqrt(ref_c**2+px_c**2+fit_c**2+pv_c**2+rep_c**2+read_c**2))
print("sig_tot",sig_tot,"rel",sig_tot/g)

# rebuild track files 246-274
track_rows=[{"frame":r["frame"],"t":r["t"],"x_px":float(r["x_px"]),"y_px":float(r["y_px"])} for r in sel_main]
open("workspace/track_hop_a.json","w").write(json.dumps(track_rows))
print("track rows",len(track_rows))

ts_flag={f:float(facts["timestamps"][f]) for f in sorted(masks_flag["0"].keys())}
tr_flag=tracks.track_point(masks_flag["0"], mode="centroid", timestamps=ts_flag)
ref_rows=[{"frame":r["frame"],"t":r["t"],"x_px":float(r["x_px"]),"y_px":float(r["y_px"])} for r in tr_flag if 246<=r["frame"]<=274]
open("workspace/ref_flag_track.json","w").write(json.dumps(ref_rows))
print("ref rows",len(ref_rows))

# fit curve px
tt=np.array([r["t"]-sel_main[0]["t"] for r in sel_main])
xx=np.array([r["x_px"] for r in sel_main])
A=np.vstack([np.ones_like(tt),tt]).T
coeff,_,_,_=np.linalg.lstsq(A,xx,rcond=None)
x0_px,vx_px=float(coeff[0]),float(coeff[1])
y0,v0,a=fmain["y0"],fmain["v0"],fmain["a"]
curve=[]
for r in sel_main:
    dt=r["t"]-sel_main[0]["t"]
    ym=y0+v0*dt+0.5*a*dt*dt
    ypx=186.0-ym/mpp
    xpx=x0_px+vx_px*dt
    curve.append({"t_s":float(dt),"x_px":float(xpx),"y_px":float(ypx)})
open("workspace/fit_curve.json","w").write(json.dumps(curve))
print("curve",len(curve),curve[0],curve[-1])
# outline already in workspace/outline_tmp.json
print(open("workspace/outline_tmp.json").read())

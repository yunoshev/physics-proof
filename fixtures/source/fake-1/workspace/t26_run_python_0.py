from helpers import masks_io, tracks
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
facts=masks_io.clip_facts("input/timing.json")
ts={f: facts["timestamps"][f] for f in range(facts["frame_count"])}
tr=tracks.track_point(m_fig, mode="lowest_point", timestamps=ts)
# print lowest across whole clip every 8 frames + full around hop
for r in tr:
    if r["frame"]%16==0 or 130<=r["frame"]<=160:
        print(f'{r["frame"]} t={r["t"]:.3f} y={r["y_px"]:.1f}')

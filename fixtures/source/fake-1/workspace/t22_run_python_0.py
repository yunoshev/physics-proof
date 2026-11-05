from helpers import masks_io, tracks, physics
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
facts=masks_io.clip_facts("input/timing.json")
ts={f: facts["timestamps"][f] for f in range(facts["frame_count"])}
tr_pack=tracks.track_point(m_pack, mode="centroid", timestamps=ts)
for r in tr_pack:
    if 130 <= r["frame"] <= 170:
        print(f'{r["frame"]} t={r["t"]:.4f} x={r["x_px"]:.1f} y={r["y_px"]:.1f}')
print("---fig lowest---")
tr_low=tracks.track_point(m_fig, mode="lowest_point", timestamps=ts)
for r in tr_low:
    if 125 <= r["frame"] <= 165:
        print(f'{r["frame"]} y={r["y_px"]:.1f}')

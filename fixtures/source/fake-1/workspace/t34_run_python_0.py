from helpers import masks_io, ranges
import json
m_fig=masks_io.load_masks("artifacts/t9_segment_0.npz")["1"]
m_pack=masks_io.load_masks("artifacts/t12_segment_0.npz")["0"]
facts=masks_io.clip_facts("input/timing.json")
# extents at frame 10
e_fig=ranges.mask_extent(m_fig[10], direction=(0,1))
e_pack=ranges.mask_extent(m_pack[10], direction=(0,1))
print(e_fig)
print(e_pack)
# ratio
rv=ranges.range_value(kind="ratio", extents=[e_fig, e_pack])
print(rv)
# print check item skeleton (without range yet)
item={"id":"figure_pack_ratio","label":"figure / pack height","answers":"It settles whether body and hardware proportions match human and equipment norms.","unit":"ratio","frame":10,"extents":[{"name":"suited figure height","x1":e_fig["x1"],"y1":e_fig["y1"],"x2":e_fig["x2"],"y2":e_fig["y2"],"length_px":e_fig["length_px"],"frame":10},{"name":"backpack unit height","x1":e_pack["x1"],"y1":e_pack["y1"],"x2":e_pack["x2"],"y2":e_pack["y2"],"length_px":e_pack["length_px"],"frame":10}],"value":rv["value"],"sigma":rv["sigma"],"formula":rv["formula"],"uses_scale":False,"measurement_artifact":"artifacts/measure_ratio.txt","range":{"min":1.6,"max":2.9,"typical":1.87,"what":"ratio of suited height to backpack-unit height","bounds_kind":"min-max","percentiles":None,"sources":[{"url":"https://example.com","domain":"example.com","quote":"x","quote_highlight":"x","value":1.6,"bound":"min","source_type":"x"}]}}
print(ranges.print_check(item))

# generated from brief/13 · part 13 owns this file
"""Per-clip page assembly and gallery build (brief part 13).

Reads only part 12's result file plus the artifacts it names in
``provenance``. Invoked by part 15; see ``tools/dev_loop`` and
``scripts/demo/build_demo_pages.py``.
"""

from .build import (build_gallery, build_page, decode_loop,
                    decode_smooth_loop, encode_loop, select_figure,
                    smooth_raw_loop, template_hash, trace_mask_contour,
                    trace_raw_loop)

__all__ = ["build_gallery", "build_page", "decode_loop",
           "decode_smooth_loop", "encode_loop", "select_figure",
           "smooth_raw_loop", "template_hash", "trace_mask_contour",
           "trace_raw_loop"]

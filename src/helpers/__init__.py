# generated from brief/09 · part 09 owns this file
"""The verified helper library Spark may import (part 09).

Pure functions over numpy arrays — no classes, no model calls, no
network, no state. Five modules:

- :mod:`src.helpers.masks_io`: save/load masks, clip facts, read
  chosen frames;
- :mod:`src.helpers.tracks`: mask statistics, largest connected
  piece, mask → tracked point, track quality flags, relative tracks;
- :mod:`src.helpers.physics`: parabola fit, scale, track → metres,
  world fit / retime factor, ghost;
- :mod:`src.helpers.clock`: gait signal, step-rate clock, clock
  evidence object;
- :mod:`src.helpers.ranges`: mask extents, range values, check
  printing.

The agent-facing documentation is generated from the helpers' own
docstrings (:mod:`src.helpers.gen_docs` → ``HELPERS_DOCS.md``,
marked do-not-edit).
"""

from __future__ import annotations

__all__ = ["clock", "gen_docs", "masks_io", "physics", "ranges", "tracks"]

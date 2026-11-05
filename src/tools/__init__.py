# generated from brief/07 · part 07 owns this file
"""The agent tool surface Spark orchestrates (part 07).

Eight tools, all returning ``{"ok", "summary", "files", "metrics",
"error?"}`` with run-relative ``artifacts/t<turn>_<tool>_<n>.<ext>``
names: ``view_frames``, ``segment``, ``check_mask``, ``web_search``,
``run_python``, ``check_line``, ``motion_overview``, ``submit``. The
schemas in :mod:`src.tools.schemas` are the single source the loop
and the clients use.
"""

from __future__ import annotations

from src.tools import (  # noqa: F401 — the tool surface
    check_line,
    check_mask,
    motion_overview,
    run_python,
    segment,
    submit,
    view_frames,
    web_search,
)
from src.tools import (  # noqa: F401 — shared tool-layer modules
    common,
    result,
    sandbox,
    schemas,
    timing,
)

__all__ = [
    "check_line",
    "check_mask",
    "motion_overview",
    "run_python",
    "segment",
    "submit",
    "view_frames",
    "web_search",
    "common",
    "result",
    "sandbox",
    "schemas",
    "timing",
]

# generated from brief/07 · part 07 owns this file
"""Result envelopes for every agent tool (part 07 §1).

Every tool returns ``{"ok", "summary", "files", "metrics",
"error?"}``. Any image, mask, table, or plot lives in
``artifacts/`` under a deterministic name
(``t<turn>_<tool>_<n>.<ext>``); the result references it. A result
that produces data but names no file is a bug in the tool.
"""

from __future__ import annotations

__all__ = [
    "ok_result",
    "err_result",
]


def ok_result(summary, files=None, metrics=None) -> dict:
    """Success envelope: short human summary plus named files."""
    return {
        "ok": True,
        "summary": str(summary),
        "files": [str(f) for f in (files or [])],
        "metrics": dict(metrics or {}),
    }


def err_result(code, detail="", summary="", files=None,
               metrics=None) -> dict:
    """Structured failure envelope — never an exception to the agent.

    ``code`` is a short machine-readable name (``bad_range``,
    ``path_rejected``, ``sam_failed``, ...); ``detail`` carries the
    specifics. Both ride into the rendered text (part 06 §6), so the
    agent sees the code and the field, not just the summary.
    """
    return {
        "ok": False,
        "summary": str(summary or detail),
        "files": [str(f) for f in (files or [])],
        "metrics": dict(metrics or {}),
        "error": {"code": str(code), "detail": str(detail)},
    }

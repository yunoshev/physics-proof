# generated from brief/06 · part 06 owns this file
"""Rendering tool results for the agent (part 06 addenda, 4th live run).

The agent sees everything a tool returns except image bytes: the
summary, the named files, the error code and detail, and every other
structured field (a submit error list once hid in ``metrics.errors``
and cost twelve turns of probing). Long results are truncated with a
marker naming the full artifact on disk.
"""

from __future__ import annotations

import json

from src.loop.history import IMAGE_SUFFIXES

__all__ = [
    "RESULT_TEXT_CAP",
    "image_files",
    "render_tool_result",
]

#: Per-result text kept verbatim before truncation names the artifact.
RESULT_TEXT_CAP = 12000


def image_files(files) -> list:
    """Result files that ride to the model as images (by suffix)."""
    return [str(f) for f in (files or [])
            if str(f).lower().endswith(IMAGE_SUFFIXES)]


def _metrics_text(metrics) -> str:
    if not isinstance(metrics, dict) or not metrics:
        return ""
    try:
        return json.dumps(metrics, indent=2, sort_keys=True,
                          ensure_ascii=True, default=str)
    except (TypeError, ValueError):
        return str(metrics)


def render_tool_result(tool: str, result: dict) -> str:
    """The full agent-visible text of one tool result (no image bytes)."""
    result = result if isinstance(result, dict) else {"summary": result}
    ok = bool(result.get("ok"))
    summary = str(result.get("summary", "") or "")
    files = [str(f) for f in (result.get("files", []) or [])]
    metrics = result.get("metrics", {}) or {}
    error = result.get("error", {}) or {}
    if ok:
        head = f"result of {tool} (ok)"
    elif isinstance(error, dict) and error.get("code"):
        head = (f"result of {tool} (error {error.get('code')}): "
                f"{error.get('detail', '')}".rstrip())
    else:
        head = f"result of {tool} (error)"
    lines = [head]
    if summary and summary not in head:
        lines.append(summary)
    if files:
        lines.append("files: " + ", ".join(files))
    metrics_text = _metrics_text(metrics)
    if metrics_text:
        lines.append("metrics:")
        lines.append(metrics_text)
    text = "\n".join(lines).strip()
    if len(text) <= RESULT_TEXT_CAP:
        return text
    marker_files = ", ".join(files) if files else "no artifact file"
    marker = (f"\n…[result truncated at {RESULT_TEXT_CAP} chars; "
              f"full result in {marker_files}]")
    return text[:RESULT_TEXT_CAP] + marker

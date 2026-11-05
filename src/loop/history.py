# generated from brief/06 · part 06 owns this file
"""Conversation history as stateless turns (skills/meta-api.md).

The previous responses' output items — commentary plus every
``function_call`` item — are replayed verbatim, each paired with its
``function_call_output`` by ``call_id`` (part 06 addendum 2026-10-27,
third live run). Older image results are pruned per §4 in place, but
calls and text results stay.

Message shape (consumed by :mod:`src.clients.spark`): ``role`` is one of
``system`` / ``user`` / ``assistant`` / ``tool``. ``content`` holds
``{"type": "text", "text"}`` and (tool messages only)
``{"type": "image", "artifact"}`` blocks. Assistant messages carry
``function_calls``; tool messages carry ``call_id`` and ``tool``.
"""

from __future__ import annotations

import copy
import hashlib
import json

from src import config as _config

__all__ = [
    "History",
    "IMAGE_SUFFIXES",
    "image_placeholder",
]

#: Artifact suffixes treated as images for context pruning (§4).
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def image_placeholder(artifact: str) -> str:
    """The in-place replacement for a pruned image (§4)."""
    return f"[image omitted; see {artifact}]"


class History:
    """One run's conversation; the loop's only agent-visible state."""

    def __init__(self) -> None:
        self.messages: list = []

    def append_system(self, text: str) -> None:
        self.messages.append({"role": "system",
                              "content": [{"type": "text",
                                           "text": str(text)}]})

    def append_user(self, text: str) -> None:
        self.messages.append({"role": "user",
                              "content": [{"type": "text",
                                           "text": str(text)}]})

    def append_assistant(self, text: str, tool_calls: list) -> None:
        message: dict = {
            "role": "assistant",
            "content": ([{"type": "text", "text": str(text)}]
                        if str(text or "") else []),
            "function_calls": [dict(call) for call in (tool_calls or [])],
        }
        self.messages.append(message)

    def append_tool(self, call_id: str, tool: str, rendered: str,
                    image_artifacts: list) -> None:
        content: list = [{"type": "text", "text": str(rendered)}]
        for artifact in image_artifacts or []:
            content.append({"type": "image",
                            "artifact": str(artifact)})
        self.messages.append({"role": "tool",
                              "call_id": str(call_id),
                              "tool": str(tool),
                              "content": content})
        self._prune_images()

    def _prune_images(self) -> None:
        """Keep only the last two image-bearing tool results' images."""
        holders = [m for m in self.messages
                   if m.get("role") == "tool"
                   and any(b.get("type") == "image"
                           for b in m.get("content", [])
                           if isinstance(b, dict))]
        stale = holders[:-2]
        stale_ids = {id(m) for m in stale}
        for message in self.messages:
            if id(message) not in stale_ids:
                continue
            pruned: list = []
            for block in message.get("content", []):
                if (isinstance(block, dict)
                        and block.get("type") == "image"):
                    pruned.append({
                        "type": "text",
                        "text": image_placeholder(
                            str(block.get("artifact", ""))),
                    })
                else:
                    pruned.append(block)
            message["content"] = pruned

    def snapshot(self) -> dict:
        """The spark-client request (model, messages, output limit)."""
        return {
            "model": str(_config.SPARK_MODEL),
            "messages": copy.deepcopy(self.messages),
            "max_output_tokens": int(_config.MAX_OUTPUT_TOKENS),
        }

    def prompt_hash(self) -> str:
        """Short hash of the current conversation for the operator log."""
        canonical = json.dumps(self.messages, sort_keys=True,
                               ensure_ascii=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

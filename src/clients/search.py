# generated from brief/04 · part 04 owns this file
"""Web-search client: the API's built-in ``web_search`` tool (§6).

Implements the ``web_search`` backend exactly as
:func:`src.tools.web_search.web_search` defines it: ``(query) ->
{"answer", "sources"}``. The tool asks for a strict JSON answer of at
most 5 ``{"text", "source_url", "quote"}`` items; this client reads
the sources from that answer (billing is per call, plus tokens, which
the tool debits itself at call time).
"""

from __future__ import annotations

from src import config as _config
from src.accounting import FailedCallError

from ._http import auth_headers, request_with_retries
from .blind import extract_json_object
from .spark import _extract_usage

__all__ = [
    "SEARCH_ANSWER_SCHEMA",
    "MAX_FACT_ITEMS",
    "make_search_client",
]

#: At most this many fact items per answer (the tool caps again).
MAX_FACT_ITEMS = 5

#: Strict answer shape: at most 5 sourced facts, all fields required.
SEARCH_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "source_url": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["text", "source_url", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["facts"],
    "additionalProperties": False,
}

#: The fact question. Every item needs all three fields so
#: ``references[].sources`` can quote them.
SEARCH_QUESTION = (
    "Answer with generic facts only (at most 5), each with its text, "
    "source URL and verbatim quote: "
)


def make_search_client(api_key, *, base_url=None, model=None,
                       timeout=None, sleep=None):
    """The ``web_search`` backend (part 04 §6)."""
    key = str(api_key)
    base = str(base_url or _config.API_BASE_URL)
    limit = float(timeout if timeout is not None
                  else _config.API_TIMEOUT_S)

    def search_client(query) -> dict:
        """Run one query; return ``{"answer", "facts", "sources"}``."""
        if not isinstance(query, str) or not query.strip():
            raise FailedCallError("web search needs a non-empty query")
        body = {
            "model": model or _config.SPARK_MODEL,
            "input": [{
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": SEARCH_QUESTION + query.strip(),
                }],
            }],
            "stream": True,
            "store": False,
            "max_output_tokens": 4096,
            "tools": [{"type": "web_search"}],
            "tool_choice": "auto",
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "search_facts",
                    "schema": SEARCH_ANSWER_SCHEMA,
                    "strict": True,
                },
            },
        }
        terminal, _ = request_with_retries(
            f"{base}/responses", auth_headers(key), body,
            timeout=limit, sleep=sleep)
        kind = (terminal or {}).get("type")
        if kind != "response.completed":
            raise FailedCallError(
                f"web search ended {kind or 'without a terminal event'}")
        inner = terminal.get("response") or {}
        texts = []
        for item in inner.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for part in item.get("content") or []:
                if (isinstance(part, dict)
                        and part.get("type") == "output_text"
                        and part.get("text")):
                    texts.append(str(part["text"]))
        parsed = extract_json_object("".join(texts), ("facts",))
        items = (parsed.get("facts") if isinstance(parsed, dict) else [])
        facts = []
        if isinstance(items, list):
            for entry in items[:MAX_FACT_ITEMS]:
                if not isinstance(entry, dict):
                    continue
                facts.append({
                    "text": str(entry.get("text", "")),
                    "source_url": str(entry.get("source_url", "")
                                      or entry.get("url", "")),
                    "quote": str(entry.get("quote", "")),
                })
        sources = [f["source_url"] for f in facts if f["source_url"]]
        return {
            "answer": facts,
            "facts": facts,
            "sources": sources,
            "usage": _extract_usage(terminal or {}),
        }

    return search_client

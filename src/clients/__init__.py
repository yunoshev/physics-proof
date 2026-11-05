# generated from brief/04 · part 04 owns this file
"""Live adapters to the Meta Model API (part 04 §6).

The only code that talks HTTP. Every external call in the system is
injected (``run_loop(spark_client=…, …)`` and the part-07 tools take
callables); this package implements each callable against the real
API, exactly to the interface its consumer already defines:

- :mod:`src.clients.spark` — the agent turn
  (``(request) -> response`` per :mod:`src.loop.run`).
- :mod:`src.clients.blind` — the blind mask check
  (``(blind_request) -> {"description", "alternatives", "usage"?}``)
  and the line checks (``kind: "line_look"`` / ``"line_match"`` per
  the 2026-10-31 addendum; the look carries ``view``/``dimension``
  per part 07 §22), and the search-blindness classifier
  (``(query) -> str``) per :mod:`src.tools.check_mask` /
  :mod:`src.tools.check_line` / :mod:`src.tools.web_search`.
- :mod:`src.clients.sam` — SAM 3.1
  (``(phrase, frame_indices, frames) -> {object_id: [arrays]}``) per
  :mod:`src.tools.segment`.
- :mod:`src.clients.search` — web search
  (``(query) -> {"answer", "sources"}``) per
  :mod:`src.tools.web_search`.
- :mod:`src.clients.files` — Files API upload/delete (used by SAM).

Protocol facts (``skills/meta-api.md``, ``skills/sam-3-1.md``):
streaming ``/responses``, flat strict tools, stateless turns with
``store:false``; usage from the terminal event only; retry
429/500/502/503/504, transport deaths and truncated streams (4
attempts, ``2**attempt + U(0,1)`` s, numeric ``Retry-After`` wins,
waits capped at 60 s); other 4xx are never retried.

Where an interface cannot carry something the API needs, the client
adapts internally and the gap is named in :mod:`src.clients.sam`
(SAM ``video_frames_processed``) and :mod:`src.clients.blind` (the
classifier's token cost has no ledger channel in the tool's call).
"""

from __future__ import annotations

from src import config as _config

from .blind import make_blind_client, make_classifier
from .files import FilesApi, delete_file, upload_file
from .sam import make_sam_client, sam_billed_frames
from .search import make_search_client
from .spark import make_spark_client

__all__ = [
    "FilesApi",
    "delete_file",
    "make_blind_client",
    "make_classifier",
    "make_sam_client",
    "make_search_client",
    "make_spark_client",
    "sam_billed_frames",
    "upload_file",
    "build_clients",
]


def build_clients(api_key, *, base_url=None, run_dir=None,
                  tools=None, timeout=None, sleep=None) -> dict:
    """All live callables for one run (part 04 §6).

    Args:
        api_key: ``META_API_KEY`` value (never logged or stored).
        base_url: API base (config default).
        run_dir: The run root (resolves tool-result image artifacts
            for the agent client; the key itself never enters it).
        tools: Tool definitions the Spark client sends (defaults to
            part 07's export — the client keeps no copy of its own).
        timeout: Per-read timeout in seconds (config default).
        sleep: Backoff sleep (tests inject a fake).

    Returns:
        ``{"spark_client", "blind_spark_client", "classifier",
        "sam_client", "search_client", "files"}``.
    """
    key = str(api_key)
    base = str(base_url or _config.API_BASE_URL)
    kwargs = {"timeout": float(timeout or _config.API_TIMEOUT_S)}
    if sleep is not None:
        kwargs["sleep"] = sleep
    spark_client = make_spark_client(key, base_url=base,
                                     run_dir=run_dir, tools=tools,
                                     **kwargs)
    blind_client = make_blind_client(key, base_url=base, **kwargs)
    classifier = make_classifier(key, base_url=base, **kwargs)
    sam_client = make_sam_client(key, base_url=base, **kwargs)
    search_client = make_search_client(key, base_url=base, **kwargs)
    return {
        "spark_client": spark_client,
        "blind_spark_client": blind_client,
        "classifier": classifier,
        "sam_client": sam_client,
        "search_client": search_client,
        "files": FilesApi(key, base_url=base, **kwargs),
    }

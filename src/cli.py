# generated from brief/04 · part 04 owns this file
"""The one command: path in → run → player-ready output (part 04 §6).

``uv run python -m src.cli <video>`` analyses a clip end to end and
prints the run folder. Every exit path leaves a valid ``result.json``
plus ``summary.json`` behind: ingest failures, missing model keys,
budget stops and crashes all end through the part-11 synthesis path,
never with a missing file.

The API key (``META_API_KEY``, fallback ``MODEL_API_KEY``) is read
here and only here. It is passed to the client factories as a value
and never reaches logs, exceptions, results, prompts or the run
folder. With no key the run still completes, through the existing
synthesis path with reason ``"no model configured"``.
"""

from __future__ import annotations

import datetime
import json
import os
import secrets
import sys
import traceback
from pathlib import Path

from src import config as _config

__all__ = [
    "generate_run_id",
    "read_api_key",
    "synthesize_undetermined",
    "run_analysis",
    "main",
]


def generate_run_id() -> str:
    """A run ID carrying no clip identity (part 04 §4).

    UTC timestamp plus a random suffix: sortable, unique, and free of
    anything the prompt-leak audit could read as an identity.
    """
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(4)}"


def read_api_key(env=None) -> str | None:
    """The model key, or None when no model is configured.

    ``META_API_KEY`` wins; ``MODEL_API_KEY`` (the docs' name) is the
    fallback. The value is never logged or stored.
    """
    mapping = env if env is not None else os.environ
    try:
        key = mapping.get("META_API_KEY") or mapping.get("MODEL_API_KEY")
    except AttributeError:
        return None
    if isinstance(key, str) and key.strip():
        return key
    return None


def synthesize_undetermined(run_dir, run_id, reason, detail="",
                            ledger=None, errors=None) -> dict:
    """Last-resort writer: a valid undetermined run, always (part 11 §4).

    The loop owns this path through :mod:`src.loop.synthesis`; this
    re-export exists so the loop's own ``except`` fallback (and the
    CLI's dead ends) can always write files without importing the
    loop. Returns ``{"status", "reason", "result_path",
    "summary_path"}``.
    """
    from src.loop.synthesis import (  # noqa: PLC0415 — writer is loop-side
        synthesize_undetermined as _write,
    )

    return _write(str(run_dir), str(run_id), str(reason),
                  detail=str(detail or ""), ledger=ledger, errors=errors)


def _ensure_layout(base: Path) -> None:
    for sub in (_config.INPUT_DIR_NAME, _config.WORKSPACE_DIR_NAME,
                _config.ARTIFACTS_DIR_NAME, _config.LOGS_DIR_NAME):
        (base / sub).mkdir(parents=True, exist_ok=True)


def _finalise(base: Path, run_id: str, status: str, reason: str = "",
              extra: dict | None = None) -> dict:
    """The one return shape: run dir plus both player-ready files."""
    outcome: dict = {
        "run_id": str(run_id),
        "run_dir": str(base),
        "result_path": str(base / _config.RESULT_FILENAME),
        "summary_path": str(base / _config.SUMMARY_FILENAME),
        "status": str(status),
    }
    if reason:
        outcome["reason"] = str(reason)
    if extra:
        outcome.update(dict(extra))
    return outcome


def run_analysis(video_path, run_id=None, runs_dir=None, *,
                 clients=None, ledger=None) -> dict:
    """Analyse one clip end to end (part 04 §6).

    Args:
        video_path: Filesystem path of the source clip (copied, never
            moved; the original name stays out of the run).
        run_id: Run identifier (generated when None — timestamp plus
            random suffix, carrying no clip identity).
        runs_dir: Parent of the run folder (``runs/`` by default).
        clients: Optional prebuilt client mapping (``spark_client``,
            ``blind_spark_client``, ``classifier``, ``sam_client``,
            ``search_client``); built from the environment when None.
        ledger: Optional run ledger (fresh per run by default).

    Returns:
        ``{"run_id", "run_dir", "result_path", "summary_path",
        "status"}`` with ``status`` ``submitted`` or ``undetermined``.
        ``result.json`` and ``summary.json`` always exist afterwards.
    """
    rid = str(run_id) if run_id else generate_run_id()
    root = Path(str(runs_dir)) if runs_dir else Path(_config.RUNS_DIR_NAME)
    base = root / rid
    base.mkdir(parents=True, exist_ok=True)
    _ensure_layout(base)

    # Ingest first: the agent's world begins at input/clip.* plus
    # input/timing.json. An unreadable video ends here as a valid
    # undetermined file (part 11 §4), never a crash.
    try:
        from src.ingest import IngestError, ingest  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover — packaging fault
        synthesize_undetermined(str(base), rid, "ingest unavailable",
                                detail=str(exc)[:500])
        return _finalise(base, rid, "undetermined",
                         reason="ingest unavailable")
    try:
        ingest(str(video_path), str(base))
    except IngestError as exc:
        synthesize_undetermined(str(base), rid, "unreadable video",
                                detail=str(exc)[:500])
        return _finalise(base, rid, "undetermined",
                         reason="unreadable video")
    except Exception as exc:  # noqa: BLE001 — every exit yields files
        synthesize_undetermined(str(base), rid, "ingest failed",
                                detail=f"{type(exc).__name__}"[:200])
        return _finalise(base, rid, "undetermined",
                         reason="ingest failed")

    # Live clients, built once per run. No key means the loop's
    # existing synthesis path with reason "no model configured".
    mapping = dict(clients) if clients is not None else None
    if mapping is None:
        key = read_api_key()
        if key is None:
            mapping = {}
        else:
            try:
                from src.clients import (  # noqa: PLC0415 — live adapters
                    build_clients,
                )
                mapping = build_clients(key, run_dir=str(base))
            except Exception as exc:  # noqa: BLE001 — files, not traces
                synthesize_undetermined(
                    str(base), rid, "client setup failed",
                    detail=f"{type(exc).__name__}"[:200])
                return _finalise(base, rid, "undetermined",
                                 reason="client setup failed")

    from src.loop import run_loop  # noqa: PLC0415 — part-06 frame

    try:
        loop_out = run_loop(
            str(base), rid,
            spark_client=(mapping or {}).get("spark_client"),
            blind_spark_client=(mapping or {}).get("blind_spark_client"),
            classifier=(mapping or {}).get("classifier"),
            sam_client=(mapping or {}).get("sam_client"),
            search_client=(mapping or {}).get("search_client"),
            ledger=ledger)
    except Exception as exc:  # noqa: BLE001 — every exit yields files
        try:
            logs = base / _config.LOGS_DIR_NAME
            logs.mkdir(parents=True, exist_ok=True)
            (logs / "cli_fault.txt").write_text(
                "".join(traceback.format_exception(exc))[-8000:],
                encoding="utf-8")
        except OSError:
            pass
        synthesize_undetermined(str(base), rid, "run failed",
                                detail=f"{type(exc).__name__}"[:200])
        return _finalise(base, rid, "undetermined", reason="run failed")

    status = str((loop_out or {}).get("status", "undetermined"))
    return _finalise(
        base, rid, status if status in ("submitted", "undetermined")
        else "undetermined",
        reason=str((loop_out or {}).get("reason", "")),
        extra={"turns": (loop_out or {}).get("turns", 0)})


def main(argv=None) -> int:
    """Entry point: ``cli <video-path> [--run-id …] [--runs-dir …]``."""
    args = list(sys.argv[1:] if argv is None else argv)
    run_id = None
    runs_dir = None
    positional: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--run-id" and index + 1 < len(args):
            run_id = args[index + 1]
            index += 2
        elif token == "--runs-dir" and index + 1 < len(args):
            runs_dir = args[index + 1]
            index += 2
        elif token.startswith("--"):
            print(f"unknown flag {token}", file=sys.stderr)
            return 2
        else:
            positional.append(token)
            index += 1
    if len(positional) != 1:
        print("usage: python -m src.cli <video-path> "
              "[--run-id ID] [--runs-dir DIR]", file=sys.stderr)
        return 2
    outcome = run_analysis(positional[0], run_id=run_id, runs_dir=runs_dir)
    # The one command prints the run folder (part 04 §6).
    print(outcome["run_dir"])
    try:
        summary = json.loads(Path(outcome["summary_path"]).read_text(
            encoding="utf-8"))
        print(json.dumps({
            "status": outcome["status"],
            "cost_usd": ((summary.get("cost_usd") or {}).get("total")
                         if isinstance(summary, dict) else None),
            "turns": outcome.get("turns", 0),
        }))
    except (OSError, ValueError):
        print(json.dumps({"status": outcome["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

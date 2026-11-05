# generated from brief/06 · part 06 owns this file
"""Run-end synthesis owned by the loop (part 06 §§5–6).

Budget exhaustion, spent submit attempts, a missing model, and tool
catastrophes all end through this path: a valid undetermined
``result.json`` (part 11's synthesis) plus the ledger's ``summary.json``.
A budget-stopped run is a completed run. This module never raises on
content — every exit writes files.

:func:`synthesize_undetermined` is also the CLI's last resort for its
dead ends (part 04 §6): it imports only this module, never the loop.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import config as _config

__all__ = [
    "log_fault",
    "synthesize_undetermined",
]


def _safe_write_summary(ledger, run_dir, result_path,
                        budget_outcome: str) -> str:
    """Write ``summary.json`` from the ledger, with a valid fallback."""
    summary_path = Path(str(run_dir)) / str(_config.SUMMARY_FILENAME)
    try:
        if ledger is not None and hasattr(ledger, "write_summary"):
            summary = ledger.write_summary(result_path, budget_outcome,
                                           run_dir=str(run_dir))
        else:
            raise AttributeError("no ledger")
    except Exception:  # noqa: BLE001 — every exit writes files
        try:
            turns = int(ledger.turns)
        except (TypeError, ValueError, AttributeError):
            turns = 0
        summary = {
            "contract_version": int(_config.CONTRACT_VERSION),
            "run_id": Path(str(run_dir)).name or "run",
            "cost_usd": {"total": 0.0, "spark_input": 0.0,
                         "spark_cached": 0.0, "spark_output": 0.0,
                         "sam": 0.0, "search": 0.0},
            "turns": turns,
            "model": str(_config.SPARK_MODEL),
            "sam_frames_billed": 0,
            "searches": 0,
            "mask_checks": 0,
            "wall_time_s": 0.0,
            "budget_outcome": str(budget_outcome),
            "result_path": str(result_path),
        }
    try:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2,
                                           sort_keys=True) + "\n",
                                encoding="utf-8")
    except OSError:
        pass
    return str(summary_path)


def synthesize_undetermined(run_dir, run_id, reason, detail="",
                            ledger=None, errors=None) -> dict:
    """Write ``result.json`` + ``summary.json``; never raise on content.

    Returns ``{"status", "reason", "result_path", "summary_path",
    "turns"}``. ``reason`` is the short machine word (``budget``,
    ``submit attempts``, ``no model configured``, ...); ``detail``
    names the crossed budget (``turns >= 90``).
    """
    base = Path(str(run_dir))
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    result_path = str(base / str(_config.RESULT_FILENAME))
    try:
        from src.validate.synthesis import (  # noqa: PLC0415
            synthesize_undetermined as _build,
        )
        from src.validate.synthesis import (  # noqa: PLC0415
            write_result as _write,
        )
        result = _build(str(base), str(run_id), str(reason),
                        detail=str(detail or ""),
                        errors=list(errors or []) if errors else None)
        result_path = _write(str(base), result)
    except Exception:  # noqa: BLE001 — last resort stays valid-shaped
        try:
            payload = {
                "contract_version": int(_config.CONTRACT_VERSION),
                "verdict": {"kind": "undetermined",
                            "reason": str(reason)},
                "sentence": f"Undetermined: {reason}.",
            }
            base.mkdir(parents=True, exist_ok=True)
            Path(result_path).write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass
    try:
        outcome = ("budget_undetermined"
                   if str(reason) == "budget" else "completed")
        summary_path = _safe_write_summary(ledger, str(base), result_path,
                                           outcome)
    except Exception:  # noqa: BLE001 — files, not traces
        summary_path = str(base / str(_config.SUMMARY_FILENAME))
    try:
        turns = int(ledger.turns) if ledger is not None else 0
    except (TypeError, ValueError, AttributeError):
        turns = 0
    text = str(reason) + (f": {detail}" if detail else "")
    try:
        from src.accounting import Ledger as _Ledger  # noqa: PLC0415
        if ledger is not None and isinstance(ledger, _Ledger):
            try:
                ledger.write_ledger_log(str(base))
            except (OSError, TypeError, ValueError, AttributeError):
                pass
    except Exception:  # noqa: BLE001 — logs never break synthesis
        pass
    return {"status": "undetermined", "reason": text,
            "result_path": result_path, "summary_path": summary_path,
            "turns": turns}


def log_fault(run_dir, name: str, exc: BaseException) -> str:
    """Operator-only fault record under ``logs/``; never a traceback out."""
    import traceback
    try:
        logs = Path(str(run_dir)) / str(_config.LOGS_DIR_NAME)
        logs.mkdir(parents=True, exist_ok=True)
        path = logs / name
        path.write_text("".join(traceback.format_exception(exc))[-8000:],
                        encoding="utf-8")
        return f"logs/{name}"
    except OSError:
        return ""

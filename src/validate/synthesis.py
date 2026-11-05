# generated from brief/11 · part 11 owns this file
"""The synthesis path and the sole result writer (brief §§4–5, 10).

Budget exhaustion or exhausted submit attempts produce a result
anyway: a minimal valid part-12 file with an undetermined verdict.
``synthesize_undetermined`` never raises on content. ``write_result``
is the only writer of ``result.json`` in the system.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import config as _config

__all__ = [
    "synthesize_undetermined",
    "write_result",
]

_GENERIC_QUESTION = "Does the physics add up?"


def _run_dir(run_dir) -> Path:
    try:
        return Path(str(run_dir))
    except (TypeError, ValueError):
        return Path(".")


def _video_block(run_dir):
    """Best-effort video block from ``input/timing.json``."""
    block = {"coded_width": 352, "coded_height": 240,
             "sample_aspect": {"num": 1, "den": 1},
             "measured_fps": 0.0, "frame_count": 0, "duration_s": 0.0}
    try:
        timing = json.loads(
            (_run_dir(run_dir) / "input" / "timing.json").read_text(
                encoding="utf-8"))
    except (OSError, ValueError):
        return block
    if not isinstance(timing, dict):
        return block
    for key in ("measured_fps", "duration_s"):
        try:
            block[key] = float(timing.get(key, 0.0) or 0.0)
        except (TypeError, ValueError):
            pass
    try:
        block["frame_count"] = int(timing.get("frame_count", 0) or 0)
    except (TypeError, ValueError):
        pass
    return block


def _wonder_for(run_dir):
    """``(question, wonder)`` from the run's plan (§§21, 23)."""
    try:
        from .io import load_wonder
    except ImportError:
        return None, None
    try:
        question, wonder = load_wonder({"run_dir": str(
            _run_dir(run_dir))})
    except (TypeError, ValueError, AttributeError, OSError):
        return None, None
    return question, wonder


def _plain_words(errors) -> str:
    """The first two errors in plain words (brief §23)."""
    words = []
    if isinstance(errors, list):
        for error in errors:
            if not isinstance(error, dict):
                continue
            detail = str(error.get("detail", "") or "").strip()
            if not detail:
                continue
            cut = len(detail)
            for mark in (". ", "; ", ": "):
                pos = detail.find(mark)
                if 0 < pos < cut:
                    cut = pos
            words.append(detail[:cut][:160].rstrip(" .;:,"))
            if len(words) == 2:
                break
    return "; ".join(w for w in words if w)


def _not_finished_reason(errors) -> str:
    """``not finished: `` plus the first two errors in plain words."""
    plain = _plain_words(errors)
    if plain:
        return f"not finished: {plain}"
    return "not finished"


def _result(errors, reason, run_id, video, run_dir="."):
    from src.contract import CONTRACT_VERSION

    if isinstance(errors, list):
        clean = [dict(e) for e in errors if isinstance(e, dict)]
    else:
        clean = []
    sentence_reason = str(reason or "undetermined")
    if sentence_reason == "not finished" or sentence_reason.startswith(
            "not finished:"):
        # The loop's own submit (brief §23): the rejection's errors
        # become the reason, in plain words.
        sentence_reason = _not_finished_reason(clean)
        reason_text = sentence_reason
        sentence = "Undetermined: " + sentence_reason.replace(
            "not finished: ", "not finished — ", 1)
    else:
        codes = " / ".join(str(e.get("code", "error"))
                           for e in clean[:3])
        detail = f" (last errors: {codes})" if codes else ""
        reason_text = (sentence_reason + detail).strip()
        sentence = f"Undetermined: {sentence_reason}.{detail}"
    question, wonder = _wonder_for(run_dir)
    if (not isinstance(question, str) or not question.strip()) \
            and isinstance(wonder, dict):
        question = wonder.get("claim")
    if not isinstance(question, str) or not question.strip():
        question = _GENERIC_QUESTION
    return {
        "contract_version": CONTRACT_VERSION,
        "video": video,
        "first_look": {
            "question": question,
            "summary": "The run ended without a measured motion.",
            "scene_card": {"scene": "No measurement was completed.",
                           "place_date": None,
                           "confidence": "low", "objects": []},
            "by_eye": None,
            "views": [],
            "wonder": wonder,
        },
        "references": [],
        "scale": None,
        "segments": [],
        "range_checks": [],
        "calculation_steps": [
            {"id": "verdict", "title": "Verdict", "frame": None,
             "frame_end": None, "segment_id": None,
             "short": [{"type": "text",
                        "text": "The run ended without a measurement."}],
             "full": [{"type": "text",
                       "text": "The synthesis path writes this file."}],
             "caveats": []},
        ],
        "clock": None,
        "clock_absent_reason": None,
        "worlds": {"candidates": [
            {"world": "Moon", "g_m_s2": 1.62, "fits_native": False,
             "delta_sigma": 0.0, "retime_factor": None}],
            "excluded": []},
        "error_budget": {"components": [], "sigma_total": None,
                         "sigma_relative": None},
        "verdict": {
            "kind": "undetermined",
            "world": None,
            "direction": None,
            "factor": None,
            "g_measured": None,
            "sigma_g": None,
            "reason": reason_text,
            "clock_note": None,
            "decided_by": None,
        },
        "sentence": sentence,
        "self_built_tools": [],
        "provenance": {
            "model": _model_name(),
            "run_id": str(run_id or "run"),
            "artifacts": [],
        },
    }


def _model_name() -> str:
    try:
        return str(_config.SPARK_MODEL)
    except AttributeError:
        return "muse-spark-1.3-contributor"


def synthesize_undetermined(run_dir, run_id, reason, *, ledger=None,
                            detail="", errors=None) -> dict:
    """Build the undetermined result; never raise on content (§10)."""
    del ledger, detail
    try:
        video = _video_block(run_dir)
    except (TypeError, ValueError, AttributeError, OSError):
        video = {"coded_width": 352, "coded_height": 240,
                 "sample_aspect": {"num": 1, "den": 1},
                 "measured_fps": 0.0, "frame_count": 0,
                 "duration_s": 0.0}
    try:
        result = _result(errors, reason, run_id, video, run_dir)
    except (TypeError, ValueError, AttributeError):
        try:
            result = _result([], "undetermined", run_id, video,
                             run_dir)
        except (TypeError, ValueError, AttributeError):
            from src.contract import CONTRACT_VERSION

            result = {
                "contract_version": CONTRACT_VERSION,
                "verdict": {"kind": "undetermined",
                            "reason": "undetermined",
                            "decided_by": None},
                "sentence": "Undetermined: undetermined.",
            }
    try:
        base = _run_dir(run_dir)
        base.mkdir(parents=True, exist_ok=True)
        if isinstance(errors, list) and errors:
            logs = base / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            (logs / "validator_last_errors.json").write_text(
                json.dumps([dict(e) for e in errors
                            if isinstance(e, dict)], indent=2) + "\n",
                encoding="utf-8")
    except (TypeError, ValueError, AttributeError, OSError):
        pass
    return result


def write_result(run_dir, result) -> str:
    """Write ``result.json``; return its path (the only writer)."""
    base = _run_dir(run_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / "result.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return str(path)

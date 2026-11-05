# generated from brief/07 · part 07 owns this file
"""Run timing and clip access for the tools (part 07 §§2–3, §10).

Every frame number the tools touch is validated against the measured
report at ``input/timing.json`` — never the container claim. Times
quoted to the agent are per-frame measured timestamps. Part 05's
own tests read this file directly through :func:`load_timing`, so
its return shape is a cross-part contract: ``frame_count``,
``timestamps``, ``measured_fps``, ``confirmed_duplicates`` and
``cuts`` (lists), plus the tool-side ``fps``/``dups`` aliases and
the ``raw`` report.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    "TIMING_FILENAME",
    "find_clip",
    "load_timing",
    "normalise_timing",
]

#: Timing report written by part 05; the only time base the tools use.
TIMING_FILENAME = "timing.json"

#: Recognised anonymised clip names under ``input/``.
_CLIP_GLOBS = ("clip.*",)


def find_clip(run_dir) -> Path:
    """Absolute path of the run's anonymised clip (``input/clip.<ext>``).

    Raises ``FileNotFoundError`` when no clip is present — callers
    turn that into a structured tool error, never a crash.
    """
    input_dir = Path(str(run_dir)) / "input"
    for glob in _CLIP_GLOBS:
        for candidate in sorted(input_dir.glob(glob)):
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(
        f"no anonymised clip in {input_dir} (expected input/clip.<ext>)")


def normalise_timing(timing: dict) -> dict:
    """``{frame_count, timestamps, fps, dups, cuts, ...}`` (key-tolerant).

    Tolerates the part-05 report variants (``fps`` / ``measured_fps``
    dicts, ``duplicate_runs`` / ``duplicates`` / ``confirmed`` runs,
    ``cut_indices`` / ``cuts``). Raises ``ValueError`` naming the
    unusable input.
    """
    if not isinstance(timing, dict):
        raise ValueError("timing report must be an object")
    try:
        frame_count = int(timing["frame_count"])
        stamps = [float(v) for v in timing["timestamps"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"timing timestamps unusable: {exc}") from exc
    if frame_count <= 0 or len(stamps) != frame_count:
        raise ValueError(
            "timing timestamps do not match frame_count")
    measured = timing.get("measured_fps", timing.get("fps"))
    if isinstance(measured, dict):
        for key in ("median", "value", "fps"):
            if key in measured:
                measured = measured[key]
                break
    try:
        fps = float(measured)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"timing measured_fps unusable: {exc}") from exc
    if not fps > 0:
        raise ValueError("timing measured_fps is not positive")
    dups: set = set()

    def _add_runs(runs) -> None:
        for run in runs or []:
            try:
                dups.update(int(i) for i in run)
            except TypeError:
                try:
                    dups.add(int(run))
                except (TypeError, ValueError):
                    continue

    for key in ("duplicate_runs", "confirmed_duplicates",
                "confirmed_duplicate_runs", "confirmed"):
        if isinstance(timing.get(key), list):
            _add_runs(timing[key])
    duplicates = timing.get("duplicates")
    if isinstance(duplicates, dict):
        _add_runs(duplicates.get("confirmed",
                                 duplicates.get("runs", [])))
    elif isinstance(duplicates, list):
        _add_runs(duplicates)
    cuts: set = set()
    for key in ("cut_indices", "cuts", "cut_frames"):
        for value in timing.get(key) or []:
            try:
                cuts.add(int(value))
            except (TypeError, ValueError):
                continue
    return {"frame_count": frame_count, "timestamps": stamps,
            "measured_fps": fps, "fps": fps,
            "confirmed_duplicates": sorted(dups),
            "dups": dups, "cuts": sorted(cuts), "cut_idx": cuts,
            "raw": timing}


def load_timing(run_dir) -> dict:
    """Load and validate ``input/timing.json`` for one run.

    Returns the normalised report (see :func:`normalise_timing`).
    Raises ``ValueError``/``FileNotFoundError`` on a missing or
    malformed report — callers map those to structured tool errors.
    """
    path = Path(str(run_dir)) / "input" / TIMING_FILENAME
    try:
        with open(path, encoding="utf-8") as handle:
            report = json.load(handle)
    except FileNotFoundError:
        raise
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"unreadable timing report at {path}: {exc}") from exc
    try:
        return normalise_timing(report)
    except ValueError as exc:
        raise ValueError(f"timing report at {path}: {exc}") from exc

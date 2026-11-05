# generated from brief/11 · part 11 owns this file
"""Run-context and artifact loading for the validator (part 11 §1).

The validator trusts artifacts and ledgers, not narration: every
number is re-read from the run's own files. All loaders are total —
a missing or unreadable input is reported as ``MISSING_FIELD`` by the
caller, never raised.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from src import config as _config

__all__ = [
    "ROW_FORMAT",
    "artifact_set",
    "clip_frame_size",
    "frame_time",
    "load_json_rel",
    "load_mask_frame",
    "load_object_masks",
    "load_track_rows",
    "load_wonder",
    "mask_frames_for_object",
    "mask_iou_on_frame",
    "masks_on_frame",
    "normalize_context",
    "produced_set",
    "read_timestamps",
    "reference_scale",
    "timing_numbers",
]

#: Expected shape of every ``*_track_artifact`` (brief §7).
ROW_FORMAT = "a JSON list of {frame, x_px, y_px}"


def _run_dir(ctx) -> Path:
    raw = ctx.get("run_dir", ".") if isinstance(ctx, dict) else "."
    try:
        return Path(str(raw))
    except (TypeError, ValueError):
        return Path(".")


def normalize_context(run_context) -> dict:
    """Fill in every context key the checks read, tolerantly."""
    ctx = dict(run_context) if isinstance(run_context, dict) else {}
    ctx.setdefault("run_dir", ".")
    ctx.setdefault("run_id", _run_dir(ctx).name or "run")
    timing = ctx.get("timing")
    if not isinstance(timing, dict):
        timing = {}
        ctx["timing"] = timing
    artifacts = ctx.get("artifacts")
    if isinstance(artifacts, (list, tuple, set)):
        ctx["artifacts"] = sorted(str(a) for a in artifacts)
    else:
        ctx["artifacts"] = []
    produced = ctx.get("produced_files")
    if isinstance(produced, (list, tuple, set)):
        ctx["produced_files"] = sorted(str(a) for a in produced)
    else:
        ctx["produced_files"] = []
    checks = ctx.get("mask_checks")
    if not isinstance(checks, list):
        ctx["mask_checks"] = []
    return ctx


def artifact_set(ctx) -> set:
    """On-disk artifact paths plus the produced-files log, as a set."""
    return set(ctx.get("artifacts", []) or []) | produced_set(ctx)


def produced_set(ctx) -> set:
    return set(ctx.get("produced_files", []) or [])


def created_in_run(rel: str, ctx) -> bool:
    """The ledger shows the file was created in this run (V2)."""
    return str(rel) in artifact_set(ctx)


def _resolve(base: Path, rel: str):
    """A run-relative path that stays inside the run directory."""
    try:
        text = str(rel)
        if not text or text.startswith("/") or ".." in text.split("/"):
            return None
        target = (base / text).resolve()
        if str(target).startswith(str(base.resolve())):
            return target
    except (TypeError, ValueError, OSError):
        return None
    return None


def load_json_rel(rel: str, ctx):
    """Load a run-relative JSON file: ``(ok, value, error_detail)``."""
    base = _run_dir(ctx)
    target = _resolve(base, rel)
    if target is None or not target.is_file():
        return False, None, (
            f"artifact {rel!r} is missing or unreadable: expected "
            f"{ROW_FORMAT}"
        )
    try:
        return True, json.loads(target.read_text(encoding="utf-8")), ""
    except (OSError, ValueError) as exc:
        return False, None, (
            f"invalid JSON in {rel!r} ({exc}): expected {ROW_FORMAT}"
        )


def load_track_rows(rel: str, ctx):
    """Load and validate ``*_track_artifact`` rows (brief §7)."""
    ok, value, detail = load_json_rel(rel, ctx)
    if not ok:
        return False, [], detail
    if not isinstance(value, list) or not value:
        return False, [], (
            f"{rel!r} holds no track rows: expected {ROW_FORMAT}"
        )
    rows = []
    for pos, row in enumerate(value):
        if not isinstance(row, dict):
            return False, [], (
                f"{rel!r} row {pos} is not an object: expected "
                f"{ROW_FORMAT}"
            )
        try:
            frame = int(row["frame"])
            x_px = float(row["x_px"])
            y_px = float(row["y_px"])
        except (KeyError, TypeError, ValueError):
            return False, [], (
                f"{rel!r} row {pos} needs frame, x_px, y_px numbers: "
                f"expected {ROW_FORMAT}"
            )
        if isinstance(frame, bool) or not (
            math.isfinite(x_px) and math.isfinite(y_px)
        ):
            return False, [], (
                f"{rel!r} row {pos} needs frame, x_px, y_px numbers: "
                f"expected {ROW_FORMAT}"
            )
        rows.append({"frame": frame, "x_px": x_px, "y_px": y_px})
    rows.sort(key=lambda r: r["frame"])
    return True, rows, ""


def timing_numbers(ctx):
    """``(fps, frame_count, duration_s, timestamps)`` from timing.json."""
    timing = ctx.get("timing", {}) or {}
    try:
        fps = float(timing.get("measured_fps") or 0.0)
    except (TypeError, ValueError):
        fps = 0.0
    try:
        count = int(timing.get("frame_count") or 0)
    except (TypeError, ValueError):
        count = 0
    try:
        duration = float(timing.get("duration_s") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    stamps = timing.get("timestamps")
    if not isinstance(stamps, list):
        stamps = timing.get("timestamps_s")
    if not isinstance(stamps, list):
        stamps = []
    clean = []
    for stamp in stamps:
        try:
            clean.append(float(stamp))
        except (TypeError, ValueError):
            clean = []
            break
    return fps, count, duration, clean


def frame_time(frame, ctx):
    """Video-second time of a frame, or None when unknown."""
    fps, count, duration, stamps = timing_numbers(ctx)
    try:
        frame = int(frame)
    except (TypeError, ValueError):
        return None
    if 0 <= frame < len(stamps):
        value = stamps[frame]
        return value if math.isfinite(value) else None
    if fps > 0 and frame >= 0:
        return frame / fps
    return None


def timing_sets(ctx):
    """``(confirmed_duplicates, cuts)`` as frame sets / index pairs."""
    timing = ctx.get("timing", {}) or {}
    dups = timing.get("confirmed_duplicates")
    if not isinstance(dups, list):
        dups = []
    dup_frames = set()
    for item in dups:
        try:
            dup_frames.add(int(item))
        except (TypeError, ValueError):
            continue
    cuts = timing.get("cuts")
    if not isinstance(cuts, list):
        cuts = timing.get("cut_indices")
    if not isinstance(cuts, list):
        cuts = []
    return dup_frames, cuts


def reference_scale(ref) -> tuple:
    """``(m_per_px, sigma)`` for one reference (2 px endpoint error)."""
    try:
        size = float(ref["size_m"])
        tol = float(ref.get("size_tolerance_m", 0.0))
        length = float(ref["extent_px"]["length_px"])
    except (KeyError, TypeError, ValueError):
        return None, None
    if not (
        math.isfinite(size) and math.isfinite(tol)
        and math.isfinite(length)
    ):
        return None, None
    if size <= 0 or length <= 0 or tol < 0:
        return None, None
    m_per_px = size / length
    sigma = m_per_px * math.sqrt((2.0 / length) ** 2 + (tol / size) ** 2)
    return float(m_per_px), float(sigma)


def _legacy_bundle(target):
    """``{object_id: {frame: bool array}}`` from a legacy manifest.

    Run artifacts written before the helpers' ``__helpers_index__``
    keep their index under ``__manifest__`` (or ``manifest``) with
    entries ``{key, object_id, frame_index}``. Anything unreadable
    is None, never an exception.
    """
    try:
        import numpy as np  # noqa: PLC0415

        data = np.load(str(target), allow_pickle=True)
    except (OSError, ValueError):
        return None
    except Exception:  # noqa: BLE001
        return None
    try:
        manifest = None
        for key in ("__manifest__", "manifest"):
            if key in data.files:
                manifest = data[key]
                break
        if manifest is None:
            return None
        items = manifest.tolist() if hasattr(manifest, "tolist") else []
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            return None
        out: dict = {}
        for entry in items:
            if not isinstance(entry, dict):
                continue
            object_id = entry.get("object_id", entry.get("oid"))
            if object_id is None:
                continue
            try:
                frame = int(entry.get("frame_index",
                                      entry.get("frame", -1)))
            except (TypeError, ValueError):
                continue
            if isinstance(frame, bool):
                continue
            key = entry.get("key", entry.get("name"))
            if not isinstance(key, str) or key not in data.files:
                continue
            try:
                arr = _as_bool_array(data[key])
            except (TypeError, ValueError, AttributeError):
                continue
            if arr is None:
                continue
            out.setdefault(str(object_id), {})[frame] = arr
        return out or None
    except (TypeError, ValueError, AttributeError):
        return None
    finally:
        try:
            data.close()
        except (AttributeError, ValueError, OSError):  # noqa: BLE001
            pass


def _masks_bundle(artifact: str, ctx):
    """All masks in one artifact, or None.

    Every mask artifact is read first with
    ``src.helpers.masks_io.load_masks``, the same reader the agent
    uses (brief §25). Run artifacts written before the helpers'
    index keep a legacy ``__manifest__`` index instead; those are
    read with the legacy fallback so older runs still validate.
    Anything unreadable is None, never an exception.
    """
    try:
        from src.helpers.masks_io import (  # noqa: PLC0415
            load_masks)
    except ImportError:
        load_masks = None
    base = _run_dir(ctx)
    target = _resolve(base, artifact)
    if target is None or not target.is_file():
        return None
    if load_masks is not None:
        try:
            bundle = load_masks(str(target))
        except Exception:  # noqa: BLE001
            bundle = None
        if isinstance(bundle, dict):
            return bundle
    return _legacy_bundle(target)


def _object_frames(bundle, object_id) -> dict:
    """``{frame: bool array}`` for one object id, or {}.

    The helpers preserve int object ids as int; the evidence may
    carry them as strings, so the int and str spellings are both
    tried (brief §25: masks read the helpers' way).
    """
    out: dict = {}
    if not isinstance(bundle, dict):
        return out
    candidates = []
    for spelling in (object_id, str(object_id)):
        if spelling not in candidates:
            candidates.append(spelling)
    try:
        as_int = int(str(object_id))
    except (TypeError, ValueError):
        as_int = None
    if as_int is not None and as_int not in candidates:
        candidates.append(as_int)
    for key in candidates:
        try:
            frames = bundle.get(key)
        except (TypeError, AttributeError):
            continue
        if not isinstance(frames, dict):
            continue
        for frame, arr in frames.items():
            if isinstance(frame, bool):
                continue
            try:
                index = int(frame)
            except (TypeError, ValueError):
                continue
            if index not in out:
                out[index] = arr
    return out


def _as_bool_array(arr):
    try:
        import numpy as np  # noqa: PLC0415

        canvas = np.asarray(arr).astype(bool)
    except (TypeError, ValueError):
        return None
    if canvas.ndim != 2 or canvas.size == 0:
        return None
    return canvas


def load_mask_frame(artifact: str, object_id, frame, ctx):
    """Boolean mask array for one object on one frame, or None."""
    if isinstance(frame, bool):
        return None
    try:
        index = int(frame)
    except (TypeError, ValueError):
        return None
    frames = _object_frames(_masks_bundle(artifact, ctx), object_id)
    arr = frames.get(index)
    if arr is None:
        return None
    return _as_bool_array(arr)


def mask_iou_on_frame(ref_a, ref_b, ctx):
    """Intersection over union of two reference masks, or None.

    Loads both masks on a common frame (the first reference's frame,
    falling back to the second's). ``None`` means a mask could not be
    loaded — the caller reports it as ``MISSING_FIELD``.
    """
    try:
        frame_a = int(ref_a["mask"]["frame"])
        frame_b = int(ref_b["mask"]["frame"])
    except (KeyError, TypeError, ValueError):
        return None
    for frame in (frame_a, frame_b):
        try:
            mask_a = load_mask_frame(ref_a["mask"]["artifact"],
                                     ref_a["mask"].get("object_id"),
                                     frame, ctx)
            mask_b = load_mask_frame(ref_b["mask"]["artifact"],
                                     ref_b["mask"].get("object_id"),
                                     frame, ctx)
        except (TypeError, ValueError, AttributeError):
            return None
        if mask_a is None or mask_b is None:
            continue
        try:
            if mask_a.shape != mask_b.shape:
                continue
            small = min(int(mask_a.sum()), int(mask_b.sum()))
            import numpy as np  # noqa: PLC0415

            inter_n = int(np.logical_and(mask_a, mask_b).sum())
            union_n = int(np.logical_or(mask_a, mask_b).sum())
        except (TypeError, ValueError):
            return None
        if union_n == 0:
            return None
        return inter_n / union_n, inter_n, small
    return None


def mask_frames_for_object(artifact: str, object_id, ctx):
    """Sorted frames one object mask covers, or None when unreadable.

    Read through the part-09 reader, the same one the agent uses:
    masks written by the ``segment`` tool keep their index under
    ``__helpers_index__`` (brief §25).
    """
    frames = _object_frames(_masks_bundle(artifact, ctx), object_id)
    return sorted(frames) or None


def load_object_masks(artifact: str, object_id, ctx):
    """``{frame: bool array}`` for one object, or None when unreadable.

    Read through the part-09 reader, the same one the agent uses
    (brief §25). Total: never raises; a missing file, an unknown
    object id or an unreadable bundle is None.
    """
    try:
        frames = _object_frames(_masks_bundle(artifact, ctx), object_id)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(frames, dict) or not frames:
        return None
    out: dict = {}
    for frame, arr in frames.items():
        if isinstance(frame, bool):
            continue
        try:
            index = int(frame)
        except (TypeError, ValueError):
            continue
        try:
            canvas = _as_bool_array(arr)
        except Exception:  # noqa: BLE001
            continue
        if canvas is None:
            continue
        out[index] = canvas
    return out or None


def masks_on_frame(ctx, frame):
    """Every object mask in the run covering one frame.

    Returns ``[{"artifact", "object_id", "array"}]`` over the run's
    ``.npz`` artifacts (the ``segment`` tool's products), read with
    the part-09 reader. Empty masks are skipped. Total: never raises.
    """
    if isinstance(frame, bool):
        return []
    try:
        index = int(frame)
    except (TypeError, ValueError):
        return []
    found = []
    try:
        rels = sorted(artifact_set(ctx))
    except Exception:
        return []
    for rel in rels:
        if not str(rel).lower().endswith(".npz"):
            continue
        try:
            bundle = _masks_bundle(rel, ctx)
        except Exception:
            continue
        if not isinstance(bundle, dict):
            continue
        for object_id, frames in bundle.items():
            if not isinstance(frames, dict):
                continue
            try:
                arr = frames.get(index)
            except (TypeError, AttributeError):
                continue
            if arr is None:
                continue
            try:
                canvas = _as_bool_array(arr)
            except Exception:
                continue
            if canvas is None or not bool(canvas.any()):
                continue
            found.append({"artifact": str(rel), "object_id": object_id,
                          "array": canvas})
    return found


def clip_frame_size(ctx):
    """``(width, height)`` of the run's clip, or None.

    Reads ``input/clip.*`` itself (video via frame capture, still
    images directly) — the run's own pixels, never agent-typed
    numbers. Total: None when the clip is missing or unreadable.
    """
    try:
        base = _run_dir(ctx)
        names = sorted(p.name for p in (base / "input").iterdir()
                       if p.is_file())
    except (OSError, ValueError, AttributeError):
        return None
    clips = [n for n in names if n.lower().startswith("clip.")]
    if not clips:
        return None
    target = base / "input" / clips[0]
    try:
        import cv2  # noqa: PLC0415
    except ImportError:
        return None
    try:
        suffix = target.suffix.lower()
        if suffix in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
            img = cv2.imread(str(target))
            if img is None or img.ndim != 3:
                return None
            return int(img.shape[1]), int(img.shape[0])
        cap = cv2.VideoCapture(str(target))
        try:
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        finally:
            cap.release()
        if width > 0 and height > 0:
            return int(width), int(height)
    except Exception:
        return None
    return None


def load_wonder(ctx):
    """The run's Wonder plan from ``artifacts/wonder.json`` (§21).

    Returns ``(question, wonder)``: the copied plan
    (``claim``/``checks``/``realistic_if``/``not_realistic_if``) or
    ``None`` when the file is missing or unreadable. Never raises.
    """
    try:
        base = _run_dir(ctx)
        target = base / "artifacts" / "wonder.json"
        if not target.is_file():
            return None, None
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None, None
    if not isinstance(value, dict):
        return None, None
    try:
        claim = value.get("claim")
        checks = value.get("checks")
        realistic_if = value.get("realistic_if")
        not_realistic_if = value.get("not_realistic_if")
    except AttributeError:
        return None, None
    if not isinstance(claim, str) or not claim.strip():
        return None, None
    if not isinstance(checks, list) or not checks:
        return None, None
    clean = []
    for check in checks:
        if not isinstance(check, dict):
            return None, None
        what = check.get("what")
        why = check.get("why")
        compare_with = check.get("compare_with")
        if not all(isinstance(v, str) and v.strip() for v in
                   (what, why, compare_with)):
            return None, None
        clean.append({"what": what, "why": why,
                      "compare_with": compare_with})
    if not all(isinstance(v, str) and v.strip() for v in
               (realistic_if, not_realistic_if)):
        return None, None
    question = value.get("question")
    if not isinstance(question, str) or not question.strip():
        question = None
    wonder = {"claim": claim, "checks": clean,
              "realistic_if": realistic_if,
              "not_realistic_if": not_realistic_if}
    return question, wonder


def format_g(g: float, sigma: float) -> str:
    """``g ± σ`` with two significant decimals in σ (brief §3)."""
    try:
        sigma = float(sigma)
        g = float(g)
    except (TypeError, ValueError):
        return f"{g} ± {sigma}"
    if not (math.isfinite(g) and math.isfinite(sigma)) or sigma <= 0:
        return f"{g} ± {sigma}"
    decimals = -math.floor(math.log10(sigma)) + 1
    decimals = max(0, int(decimals))
    return f"{g:.{decimals}f} ± {sigma:.{decimals}f}"


def selfbuilt_name_from_path(path: str):
    """Self-built tool name for a provenance path, or None.

    Registry entries carry the full ``sb_``-prefixed stem.
    """
    text = str(path or "")
    marker = "selfbuilt/"
    if marker not in text:
        return None
    tail = text.split(marker, 1)[1]
    stem = tail.split("/", 1)[0].split(".", 1)[0]
    if not stem.startswith("sb_"):
        return None
    return stem or None

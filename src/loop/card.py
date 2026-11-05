# generated from brief/06 · part 06 owns this file
"""The clip card: masks before the plan (part 06 addendum 2026-11-04,
street-jump run 83).

Before deciding what to prove, the run must know from masks which
things move, how they move, where they touch, and how the camera moves.
After Describe and before Wonder — with no Spark call — the loop:

- segments each of Describe's ``moving_things`` phrases over the whole
  clip (part 07's ``segment``; SAM frames ride the ledger and count
  against the SAM budget, as a tool call does);
- runs part 07's ``motion_overview`` on each result;
- computes contacts (frame ranges where two masks overlap or come
  within 3 px, plus the smallest gap over the clip) and the camera's
  movement (part 09's ``find_still_patches`` + ``still_track``);
- writes ``artifacts/card.json`` (card_-prefixed artifacts) and
  ``logs/card.json`` (why anything was left out).

The card adds objects in Describe's order and stops before one that
would take the card past half of the run's SAM frame budget. A phrase
SAM returns empty for, or fails on, is listed with its reason and the
card goes on without it. If every phrase fails, the loop starts as
before (no card quoted) and ``logs/`` records why.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from src import config as _config

__all__ = [
    "CARD_ARTIFACT_PREFIX",
    "CARD_FILENAME",
    "CARD_LOG_FILENAME",
    "CONTACT_PX",
    "MAX_MOVING_THINGS",
    "card_task_lines",
    "describe_moving_things",
    "run_card",
]

#: The clip-card artifact (objects, contacts, camera).
CARD_FILENAME = "artifacts/card.json"

#: Operator-only record of what the card did and why (skips included).
CARD_LOG_FILENAME = "logs/card.json"

#: Every file the card step produces is renamed under this prefix, so
#: the card's masks, charts and strips are recognisable in the run.
CARD_ARTIFACT_PREFIX = "card_"

#: At most this many moving-thing phrases come out of Describe.
MAX_MOVING_THINGS = 4

#: Two masks in contact when they overlap or come within this many px.
CONTACT_PX = 3


def describe_moving_things(describe) -> list:
    """Describe's moving-thing phrases (``[]`` when there are none).

    Up to :data:`MAX_MOVING_THINGS` short noun phrases SAM can
    segment, most important first. Anything else — a missing key, a
    non-list, a blank entry — contributes no phrase; the card is then
    skipped and the loop starts as before.
    """
    if not isinstance(describe, dict):
        return []
    phrases = describe.get("moving_things")
    if not isinstance(phrases, list):
        return []
    out: list = []
    for phrase in phrases:
        if isinstance(phrase, str) and phrase.strip():
            out.append(phrase.strip())
        if len(out) >= MAX_MOVING_THINGS:
            break
    return out


def _card_log_path(run_dir) -> Path:
    return (Path(str(run_dir)) / str(_config.LOGS_DIR_NAME) / "card.json")


def _write_card_log(run_dir, record: dict) -> None:
    try:
        path = _card_log_path(run_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2, sort_keys=True,
                                   ensure_ascii=True, default=str) + "\n",
                        encoding="utf-8")
    except OSError:
        pass


def _rename_for_card(run_dir, rels: list) -> dict:
    """Move card files under the ``card_`` prefix; ``{old: new}``."""
    mapping: dict = {}
    used: set = set()
    counter = 0
    for rel in rels or []:
        if not isinstance(rel, str) or not rel:
            continue
        if rel in mapping:
            continue
        try:
            source = Path(str(run_dir)) / rel
        except (TypeError, ValueError):
            continue
        suffix = source.suffix or ".bin"
        while True:
            candidate = (f"artifacts/{CARD_ARTIFACT_PREFIX}{counter}"
                         f"{suffix}")
            counter += 1
            if candidate not in used and not (
                    Path(str(run_dir)) / candidate).exists():
                break
        try:
            (Path(str(run_dir)) / candidate).parent.mkdir(
                parents=True, exist_ok=True)
            source.rename(Path(str(run_dir)) / candidate)
        except OSError:
            continue
        mapping[rel] = candidate
        used.add(candidate)
    return mapping


def _rewrite_rel(obj, mapping: dict):
    """Replace renamed artifact paths inside a cached tool result."""
    if isinstance(obj, str):
        return mapping.get(obj, obj)
    if isinstance(obj, list):
        return [_rewrite_rel(item, mapping) for item in obj]
    if isinstance(obj, dict):
        return {key: _rewrite_rel(value, mapping)
                for key, value in obj.items()}
    return obj


def _patch_table_artifact(run_dir, table_rel: str, npz_rel: str) -> None:
    """The overview table JSON names its masks file; keep it true."""
    try:
        path = Path(str(run_dir)) / str(table_rel)
        table = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return
    if not isinstance(table, dict):
        return
    table["masks_artifact"] = str(npz_rel)
    try:
        path.write_text(json.dumps(table, indent=2) + "\n",
                        encoding="utf-8")
    except OSError:
        pass


def _segment_phrase(run_dir, phrase: str, frame_count: int, sam_client,
                    ledger, segment_cache) -> dict:
    """One whole-clip ``segment`` call for one card phrase."""
    from src.tools.segment import segment  # noqa: PLC0415 — injection seam
    try:
        return segment(str(run_dir), 0, phrase=phrase, frame_start=0,
                       frame_end=int(frame_count) - 1,
                       confirm_small_range=True, sam_client=sam_client,
                       ledger=ledger, cache=segment_cache)
    except Exception as exc:  # noqa: BLE001 — listed, never raised
        return {"ok": False, "summary": "",
                "files": [], "metrics": {},
                "error": {"code": type(exc).__name__, "detail": str(exc)}}


def _overview_masks(run_dir, npz_rel: str) -> dict:
    """One ``motion_overview`` call on one card masks file."""
    from src.tools.motion_overview import (  # noqa: PLC0415 — same seam
        motion_overview,
    )
    try:
        return motion_overview(str(run_dir), 0, masks_artifact=npz_rel)
    except Exception as exc:  # noqa: BLE001 — listed, never raised
        return {"ok": False, "summary": "",
                "files": [], "metrics": {},
                "error": {"code": type(exc).__name__, "detail": str(exc)}}


def _candidates_of(overview: dict, object_id: str) -> list:
    """The overview's candidates for one object (``[]`` when none)."""
    if not isinstance(overview, dict) or not overview.get("ok"):
        return []
    metrics = overview.get("metrics")
    if not isinstance(metrics, dict):
        return []
    wanted = str(object_id)
    out: list = []
    for candidate in metrics.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("object_id")) != wanted:
            continue
        try:
            start = int(candidate.get("frame_start"))
            end = int(candidate.get("frame_end"))
        except (TypeError, ValueError):
            continue
        try:
            airtime = float(candidate.get("airtime_s", 0.0))
        except (TypeError, ValueError):
            airtime = 0.0
        try:
            rise = float(candidate.get("peak_rise_px", 0.0))
        except (TypeError, ValueError):
            rise = 0.0
        out.append({"id": str(candidate.get("id", "")),
                    "frame_start": start, "frame_end": end,
                    "airtime_s": airtime, "peak_rise_px": rise,
                    "peak_frame": candidate.get("peak_frame")})
    out.sort(key=lambda item: int(item.get("frame_start", 0)))
    return out


def _frame_gap(px_a, px_b) -> float | None:
    """Smallest pixel gap between two bool masks (``None`` if either
    is empty here; 0.0 on overlap). Exact: the distance transform runs
    on the crop covering both masks, which holds every pixel pair."""
    import numpy as np
    from scipy.ndimage import (  # noqa: PLC0415 — heavy, card-only
        distance_transform_edt,
    )
    a = np.asarray(px_a, dtype=bool)
    b = np.asarray(px_b, dtype=bool)
    if a.shape != b.shape or not a.any() or not b.any():
        return None
    if bool((a & b).any()):
        return 0.0
    rows, cols = np.where(a | b)
    y0, y1 = int(rows.min()), int(rows.max()) + 1
    x0, x1 = int(cols.min()), int(cols.max()) + 1
    dist = distance_transform_edt(~b[y0:y1, x0:x1])
    return float(dist[a[y0:y1, x0:x1]].min())


def _pair_contact(entry_a: dict, entry_b: dict,
                  masks: dict) -> dict | None:
    """One pair's contact record (``None`` when never near)."""
    frames_a = set((masks.get(entry_a["key"]) or {}))
    frames_b = set((masks.get(entry_b["key"]) or {}))
    common = sorted(frames_a & frames_b)
    if not common:
        return None
    runs: list = []
    start = None
    prev = None
    smallest: float | None = None
    for frame in common:
        gap = _frame_gap(masks[entry_a["key"]][frame],
                         masks[entry_b["key"]][frame])
        if gap is None:
            gap = float("inf")
        if smallest is None or gap < smallest:
            smallest = gap
        if gap <= float(CONTACT_PX):
            if start is None:
                start, prev = frame, frame
            elif frame == prev + 1:
                prev = frame
            else:
                runs.append([start, prev])
                start, prev = frame, frame
        elif start is not None:
            runs.append([start, prev])
            start, prev = None, None
    if start is not None:
        runs.append([start, prev])
    if not runs:
        return None
    return {
        "a": {"phrase": entry_a["phrase"],
              "object_id": entry_a["object_id"]},
        "b": {"phrase": entry_b["phrase"],
              "object_id": entry_b["object_id"]},
        "ranges": runs,
        "min_gap_px": float(smallest) if smallest is not None else None,
    }


def _contacts(run_dir, objects: list) -> list:
    """Contacts over every pair of card objects (no-Spark, in code)."""
    try:
        from src.helpers import masks_io  # noqa: PLC0415 — card-only
        from src.tools.common import run_path  # noqa: PLC0415 — same
    except Exception:  # noqa: BLE001 — no masks, no contacts
        return []
    masks: dict = {}
    for position, entry in enumerate(objects):
        key = f"card-object-{position}"
        entry["key"] = key
        try:
            loaded = masks_io.load_masks(
                run_path(str(run_dir), str(entry["masks_artifact"])))
        except (OSError, ValueError):
            continue
        own = loaded.get(entry["object_id"])
        if isinstance(entry["object_id"], str):
            for oid, frames in loaded.items():
                if str(oid) == str(entry["object_id"]):
                    own = frames
                    break
        if isinstance(own, dict):
            masks[key] = {int(frame): arr for frame, arr in own.items()}
    found: list = []
    for left in range(len(objects)):
        for right in range(left + 1, len(objects)):
            if objects[left].get("key") not in masks:
                continue
            if objects[right].get("key") not in masks:
                continue
            try:
                contact = _pair_contact(objects[left], objects[right],
                                        masks)
            except Exception:  # noqa: BLE001 — a pair never blocks
                continue
            if contact is not None:
                found.append(contact)
    for entry in objects:
        entry.pop("key", None)
    return found


def _camera(run_dir, avoid: dict, frame_count: int) -> dict:
    """The camera's movement over the whole clip (part 09 helpers).

    Every segmented mask is ``avoid``: the patch must be clear of
    every mover. ``{"status": "no still patch"}`` when nothing
    qualifies or the look fails — the card goes on either way.
    """
    try:
        from src.helpers.tracks import (  # noqa: PLC0415 — card-only
            find_still_patches,
            still_track,
        )
        from src.tools.timing import find_clip  # noqa: PLC0415 — same
        clip = str(find_clip(str(run_dir)))
        frames = list(range(int(frame_count)))
        patches = find_still_patches(clip, frames, avoid=avoid or None)
        if not patches:
            return {"status": "no still patch",
                    "reason": "no patch clear of every mover"}
        box = [float(value) for value in patches[0]]
        rows = still_track(clip, frames, patches[0], avoid=avoid or None)
        if not rows:
            return {"status": "no still patch",
                    "reason": "still track returned no rows"}
        x0 = float(rows[0]["x_px"])
        y0 = float(rows[0]["y_px"])
        peak = 0.0
        for row in rows:
            try:
                peak = max(peak, math.hypot(float(row["x_px"]) - x0,
                                            float(row["y_px"]) - y0))
            except (TypeError, ValueError, KeyError):
                continue
        return {"box": box, "displacement_px": float(peak),
                "frames": len(frames)}
    except Exception as exc:  # noqa: BLE001 — never blocks the card
        return {"status": "no still patch",
                "reason": (f"{type(exc).__name__}: {exc}")[:200]}


def _sam_half_cap() -> float:
    try:
        return float(int(_config.MAX_SAM_FRAMES)) / 2.0
    except (TypeError, ValueError):
        return 750.0


def _sam_spent(ledger) -> int:
    try:
        return int(ledger.sam_frames_billed)
    except (TypeError, ValueError, AttributeError):
        return 0


def _billed_for(frame_count: int) -> int:
    try:
        floor = int(_config.SAM_MIN_BILLED_FRAMES)
    except (TypeError, ValueError):
        floor = 50
    try:
        return max(floor, int(frame_count))
    except (TypeError, ValueError):
        return floor


def run_card(run_dir, describe, *, sam_client=None, ledger=None,
             segment_cache=None) -> dict | None:
    """Build the clip card after Describe, before Wonder.

    Returns the card dict (also written to ``artifacts/card.json``),
    or ``None`` when there is nothing to quote: no moving things, no
    SAM backend, no clip facts, or every phrase failed. Every outcome
    is recorded in ``logs/card.json`` with its reason.
    """
    phrases = describe_moving_things(describe)
    if not phrases:
        _write_card_log(str(run_dir), {"status": "skipped",
                                       "reason": ("describe named no "
                                                  "moving things"),
                                       "objects": []})
        return None
    if not callable(sam_client):
        _write_card_log(str(run_dir), {"status": "skipped",
                                       "reason": "no SAM backend wired",
                                       "objects": []})
        return None
    try:
        from src.tools.timing import load_timing  # noqa: PLC0415
        facts = load_timing(str(run_dir))
        frame_count = int(facts["frame_count"])
    except Exception as exc:  # noqa: BLE001 — no facts, no card
        _write_card_log(str(run_dir), {"status": "skipped",
                                       "reason": (f"no clip facts: "
                                                  f"{type(exc).__name__}"),
                                       "objects": []})
        return None
    if frame_count <= 0:
        _write_card_log(str(run_dir), {"status": "skipped",
                                       "reason": "clip has no frames",
                                       "objects": []})
        return None
    half_cap = _sam_half_cap()
    objects: list = []
    left_out: list = []
    failed: list = []
    cache = segment_cache if isinstance(segment_cache, dict) else {}
    for position, phrase in enumerate(phrases):
        charge = _billed_for(frame_count)
        if _sam_spent(ledger) + charge > half_cap:
            for rest in phrases[position:]:
                left_out.append({
                    "phrase": rest, "status": "left out",
                    "reason": ("would pass half of the run's SAM frame "
                               f"budget ({_sam_spent(ledger)} + {charge} "
                               f"> {half_cap:g})")})
            break
        before = set(cache.keys())
        result = _segment_phrase(str(run_dir), phrase, frame_count,
                                 sam_client, ledger, cache)
        fresh = [key for key in cache if key not in before]
        if not isinstance(result, dict) or not result.get("ok"):
            error = (result.get("error") if isinstance(result, dict)
                     else None) or {}
            detail = str(error.get("detail") or result.get("summary")
                         if isinstance(result, dict) else "") or "failed"
            failed.append({"phrase": phrase, "status": "failed",
                           "reason": detail[:500]})
            continue
        metrics = result.get("metrics") or {}
        npz_rel = metrics.get("masks_artifact")
        if not isinstance(npz_rel, str) or not npz_rel:
            for name in result.get("files") or []:
                if str(name).endswith(".npz"):
                    npz_rel = str(name)
                    break
        if not isinstance(npz_rel, str) or not (
                Path(str(run_dir)) / npz_rel).is_file():
            failed.append({"phrase": phrase, "status": "failed",
                           "reason": "segment wrote no masks file"})
            continue
        overview = _overview_masks(str(run_dir), npz_rel)
        produced = [str(name) for name in (result.get("files") or [])]
        chart_rel: str | None = None
        strip_rels: dict = {}
        table_rel: str | None = None
        if isinstance(overview, dict) and overview.get("ok"):
            produced += [str(name) for name in
                         (overview.get("files") or [])]
            ometrics = overview.get("metrics") or {}
            if isinstance(ometrics.get("chart_artifact"), str):
                chart_rel = ometrics["chart_artifact"]
            strips = ometrics.get("strip_artifacts") or {}
            if isinstance(strips, dict):
                strip_rels = {str(key): str(value)
                              for key, value in strips.items()}
            if isinstance(ometrics.get("table_artifact"), str):
                table_rel = ometrics["table_artifact"]
        mapping = _rename_for_card(str(run_dir), produced)
        for key in fresh:
            try:
                cache[key] = _rewrite_rel(cache[key], mapping)
            except (TypeError, ValueError, AttributeError):
                continue
        npz_rel = mapping.get(npz_rel, npz_rel)
        if chart_rel is not None:
            chart_rel = mapping.get(chart_rel, chart_rel)
        strip_rels = {key: mapping.get(value, value)
                      for key, value in strip_rels.items()}
        if table_rel is not None:
            table_rel = mapping.get(table_rel, table_rel)
            _patch_table_artifact(str(run_dir), table_rel, npz_rel)
        oids = metrics.get("object_ids") or []
        if not oids:
            failed.append({"phrase": phrase, "status": "failed",
                           "reason": "segment returned no objects"})
            continue
        for oid in oids:
            entry = {"phrase": phrase, "masks_artifact": npz_rel,
                     "object_id": str(oid),
                     "candidates": _candidates_of(overview, str(oid)),
                     "chart_artifact": chart_rel,
                     "strip_artifacts": strip_rels,
                     "table_artifact": table_rel}
            if (not isinstance(overview, dict)
                    or not overview.get("ok")):
                error = (overview.get("error")
                         if isinstance(overview, dict) else None) or {}
                entry["overview_error"] = str(
                    error.get("detail") or overview.get("summary")
                    if isinstance(overview, dict) else "")[:200]
            objects.append(entry)
    card: dict = {"status": "ok" if objects else "failed",
                  "objects": objects, "contacts": [],
                  "camera": {"status": "no still patch",
                             "reason": "no objects to avoid"},
                  "left_out": left_out, "failed": failed}
    if objects:
        try:
            card["contacts"] = _contacts(str(run_dir), objects)
        except Exception:  # noqa: BLE001 — contacts never block
            card["contacts"] = []
        avoid: dict = {}
        try:
            from src.helpers import masks_io  # noqa: PLC0415
            from src.tools.common import run_path  # noqa: PLC0415
            for position, entry in enumerate(objects):
                try:
                    loaded = masks_io.load_masks(
                        run_path(str(run_dir),
                                 str(entry["masks_artifact"])))
                except (OSError, ValueError):
                    continue
                for oid, frames in loaded.items():
                    if str(oid) == str(entry["object_id"]):
                        avoid[f"card-object-{position}"] = frames
                        break
        except Exception:  # noqa: BLE001 — camera degrades, not dies
            avoid = {}
        card["camera"] = _camera(str(run_dir), avoid, frame_count)
    if objects:
        try:
            (Path(str(run_dir)) / CARD_FILENAME).write_text(
                json.dumps(card, indent=2, sort_keys=True,
                           ensure_ascii=True, default=str) + "\n",
                encoding="utf-8")
        except OSError:
            pass
    _write_card_log(str(run_dir), {
        "status": card["status"],
        "reason": ("every phrase failed or left out; the loop starts "
                   "without a card" if not objects else ""),
        "objects": [entry["phrase"] for entry in objects],
        "left_out": left_out, "failed": failed})
    if not objects:
        return None
    return card


def card_task_lines(card) -> list:
    """The initial task's clip-card quote (``[]`` with no card)."""
    if not isinstance(card, dict):
        return []
    objects = [entry for entry in (card.get("objects") or [])
               if isinstance(entry, dict)]
    if not objects:
        return []
    lines = ["",
             "CLIP CARD (these masks exist; reuse them — do not "
             "re-segment these objects):"]
    for entry in objects:
        phrase = str(entry.get("phrase", "") or "")
        artifact = str(entry.get("masks_artifact", "") or "")
        oid = str(entry.get("object_id", "") or "")
        lines.append(f'- object "{phrase}": masks {artifact}, object id '
                     f"{oid} (these masks exist; reuse them)")
        candidates = [item for item in (entry.get("candidates") or [])
                      if isinstance(item, dict)]
        if candidates:
            for candidate in candidates:
                lines.append(
                    f'  candidate {candidate.get("id", "?")}: frames '
                    f'{candidate.get("frame_start")}..'
                    f'{candidate.get("frame_end")}, airtime '
                    f'{float(candidate.get("airtime_s", 0.0)):.2f}s, '
                    f'peak rise '
                    f'{float(candidate.get("peak_rise_px", 0.0)):.1f}px')
        else:
            lines.append("  candidates: none decided yet")
    contacts = [item for item in (card.get("contacts") or [])
                if isinstance(item, dict)]
    if contacts:
        for contact in contacts:
            part_a = contact.get("a") or {}
            part_b = contact.get("b") or {}
            name_a = str(part_a.get("phrase", "?")
                         if isinstance(part_a, dict) else "?")
            name_b = str(part_b.get("phrase", "?")
                         if isinstance(part_b, dict) else "?")
            spans = ", ".join(
                f"{span[0]}..{span[1]}"
                for span in (contact.get("ranges") or [])
                if isinstance(span, (list, tuple)) and len(span) == 2)
            gap = contact.get("min_gap_px")
            lines.append(f'- contact "{name_a}" vs "{name_b}": near '
                         f"(within {int(CONTACT_PX)}px) in frames "
                         f"{spans or '?'}; smallest gap {gap}px")
    else:
        lines.append("- contacts: no contact between any two objects")
    camera = card.get("camera") or {}
    if isinstance(camera, dict) and camera.get("status") != "no still patch":
        box = camera.get("box")
        disp = camera.get("displacement_px")
        lines.append(f"- camera: a still patch {box} moved at most "
                     f"{disp}px over the clip")
    else:
        lines.append("- camera: no still patch")
    return lines

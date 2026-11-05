# generated from brief/07 · part 07 owns this file
"""``check_mask`` — the blind second look (part 07 §4).

A separate Spark call with no run context: a fresh conversation
receiving only one overlay image, the mask's pixel extents, and a
neutral question. It returns a structured description of what the
mask covers (never what the object is) plus alternative readings
where coverage is ambiguous.
"""

from __future__ import annotations

import json
from pathlib import Path

from .common import (
    append_produced,
    next_artifact,
    reject_path,
    run_path,
)
from .result import err_result, ok_result

__all__ = [
    "check_mask",
    "mask_checks_path",
    "NEUTRAL_QUESTION",
]

#: The only question the blind call ever asks: coverage, not identity.
#: Part 07 §14: besides what the tinted region covers, the question
#: asks for any separable or stacked parts inside it, and any part of
#: the same object left outside — so a mask over a pack plus its top
#: unit cannot be read as the bare pack without an alternative on the
#: record.
#: Part 07 §16: the one-word kind question (§15) is withdrawn. The
#: question carries no person/animal/object wording and the check
#: record carries no ``kind_answer``: ``subject.kind`` is descriptive
#: only and no rule reads it (R-S6).
NEUTRAL_QUESTION = (
    "An overlay image shows a translucent coloured mask drawn on one "
    "video frame, with one bounding box per masked region. Describe, in "
    "plain words, WHAT THE MASK COVERS: which part of the visible "
    "object or surface the tinted region covers, and which edges it "
    "includes or excludes (for example, whether it covers only part "
    "of an object or extends past it onto the background). Do NOT "
    "name or guess what the object is, where the footage comes from, "
    "or what experiment this is. Where the covering is ambiguous, "
    "list each alternative reading. As alternatives, name any "
    "separable or stacked parts inside the tinted region (for "
    "example a unit mounted on top of another) and any part of the "
    "same object left outside the tinted region."
)

#: Image suffixes accepted as overlays.
_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")


def mask_checks_path(run_dir) -> Path:
    """Registry of blind-check records (read by part 11, ``V3``)."""
    return Path(str(run_dir)) / "workspace" / "mask_checks.json"


def _read_registry(run_dir) -> list:
    try:
        text = mask_checks_path(run_dir).read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        data = json.loads(text)
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def _write_registry(run_dir, records) -> None:
    path = mask_checks_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2) + "\n",
                    encoding="utf-8")


def parse_extents(extents) -> dict:
    """Normalise the mask's pixel extents to a dict (or raise).

    ``None`` means the caller supplied none (the overlay image
    dimensions are used instead); a JSON string is parsed, a mapping
    is copied. Anything else raises ``ValueError``.
    """
    import json as _json

    if extents is None:
        return {}
    if isinstance(extents, str):
        if not extents.strip():
            return {}
        try:
            extents = _json.loads(extents)
        except ValueError as exc:
            raise ValueError(
                f"extents must be a JSON string or object: {exc}") from exc
    if not isinstance(extents, dict):
        raise ValueError(
            f"extents must be a JSON string or object, got "
            f"{type(extents).__name__}")
    return {str(k): extents[k] for k in extents}


def _image_extents(raw: bytes):
    """Pixel extents of the overlay (width/height) via OpenCV."""
    import cv2
    import numpy as np

    grid = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8),
                        cv2.IMREAD_COLOR)
    if grid is None:
        return None
    height, width = grid.shape[:2]
    return {"width_px": int(width), "height_px": int(height)}


def check_mask(run_dir, turn, overlay_artifact=None, extents=None,
               *, spark_client=None, ledger=None) -> dict:
    """Blind coverage verdict on one overlay; record it for submit.

    ``extents`` is the mask's pixel extents (object or JSON string);
    when omitted the overlay image dimensions are sent. The blind
    request carries exactly ``{image, extents, question}`` — no run
    context by construction.
    """
    reason = reject_path(overlay_artifact)
    if reason:
        return err_result("path_rejected", reason,
                          metrics={"overlay_artifact": overlay_artifact})
    if not str(overlay_artifact).startswith("artifacts/"):
        return err_result(
            "path_rejected",
            f"overlay must live under artifacts/, got "
            f"{overlay_artifact!r}",
            metrics={"overlay_artifact": str(overlay_artifact)})
    if str(overlay_artifact).lower().endswith(_IMAGE_SUFFIXES) is False:
        return err_result(
            "bad_overlay",
            f"overlay must be a JPEG/PNG image, got "
            f"{overlay_artifact!r}",
            metrics={"overlay_artifact": str(overlay_artifact)})
    source = run_path(run_dir, str(overlay_artifact))
    if not source.is_file():
        return err_result("missing_overlay",
                          f"overlay not found in this run: "
                          f"{overlay_artifact!r}",
                          metrics={"overlay_artifact":
                                   str(overlay_artifact)})
    if spark_client is None:
        return err_result("blind_unavailable",
                          "no blind-check backend is wired for this run",
                          metrics={"overlay_artifact":
                                   str(overlay_artifact)})
    try:
        raw = source.read_bytes()
    except OSError as exc:
        return err_result("missing_overlay",
                          f"overlay unreadable: {exc}",
                          metrics={"overlay_artifact":
                                   str(overlay_artifact)})
    if not raw:
        return err_result("bad_overlay",
                          f"overlay is empty: {overlay_artifact!r}",
                          metrics={"overlay_artifact": str(overlay_artifact)})
    try:
        extents_dict = parse_extents(extents)
    except ValueError as exc:
        return err_result("bad_arguments", str(exc),
                          metrics={"overlay_artifact":
                                   str(overlay_artifact)})
    decoded = _image_extents(raw)
    if decoded is None and not extents_dict:
        # Not a decodable image and no extents supplied: the blind
        # call still runs with empty extents (the loop's own tests
        # exercise this path with a placeholder file).
        extents_dict = {}
    elif not extents_dict:
        extents_dict = decoded or {}
    try:
        answer = spark_client({"image": raw, "extents": dict(extents_dict),
                               "question": NEUTRAL_QUESTION})
    except Exception as exc:  # noqa: BLE001 — blind death is a tool error
        return err_result("blind_failed",
                          f"{type(exc).__name__}: {exc}",
                          metrics={"overlay_artifact":
                                   str(overlay_artifact)})
    if not isinstance(answer, dict):
        return err_result("blind_malformed",
                          "blind backend returned no structured answer",
                          metrics={"overlay_artifact":
                                   str(overlay_artifact)})
    description = answer.get("description", "")
    if not isinstance(description, str) or not description.strip():
        return err_result("blind_malformed",
                          "blind backend returned an empty description",
                          metrics={"overlay_artifact":
                                   str(overlay_artifact)})
    alternatives = answer.get("alternatives") or []
    if not isinstance(alternatives, list):
        alternatives = [str(alternatives)]
    alternatives = [str(a) for a in alternatives if str(a).strip()]
    record_rel = next_artifact(run_dir, turn, "check_mask", ".json")
    record = {
        "overlay_artifact": str(overlay_artifact),
        "mask_extents_px": extents_dict,
        "question": NEUTRAL_QUESTION,
        "coverage_answer": description.strip(),
        "alternatives": alternatives,
        "confidence": None,
        "turn": int(turn),
    }
    record_path = run_path(run_dir, record_rel)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2) + "\n",
                           encoding="utf-8")
    records = _read_registry(run_dir)
    records.append({"artifact": record_rel,
                    "overlay": str(overlay_artifact),
                    "turn": int(turn)})
    _write_registry(run_dir, records)
    append_produced(run_dir, [record_rel,
                              "workspace/mask_checks.json"])
    usage = answer.get("usage") if isinstance(answer, dict) else None
    if ledger is not None:
        try:
            ledger.record_mask_check(int(turn), usage, artifact=record_rel)
        except (TypeError, ValueError):
            pass
    return ok_result(
        f"blind check: {description.strip()[:280]}"
        + (f" (+{len(alternatives)} alternative reading(s))"
           if alternatives else ""),
        files=[record_rel],
        metrics={"overlay_artifact": str(overlay_artifact),
                 "mask_extents_px": extents_dict,
                 "coverage_answer": description.strip(),
                 "alternatives": alternatives,
                 "record_artifact": record_rel,
                 "blind": True,
                 "context_free": True})

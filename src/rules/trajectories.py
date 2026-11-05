"""Trajectory-first decisions (R-M6/R-M7) and reference placement (R-S11/R-S12)."""

from __future__ import annotations

#: R-M6 (words, 2026-11-03): the only allowed candidate decisions.
CANDIDATE_DECISIONS = ("measured", "not_a_flight", "not_measurable")

#: R-S12: a still thing is segmented on a short range (billed minimum).
STILL_SEGMENT_MAX_FRAMES = 50


def check_rm6_overview(*, overview: dict | None, motions, segments):
    """R-M6: every candidate flight is decided with the listed words."""
    if not overview or "candidates" not in overview:
        return ("MOTION_OVERVIEW_MISSING", "first_look.overview",
                "segment the mover over the whole clip, call "
                "motion_overview, and list every candidate flight")
    seg_ids = {s.get("segment_id") if isinstance(s, dict) else s
               for s in (segments or [])}
    motion_seg_ids = {m.get("segment_id") for m in (motions or [])
                      if isinstance(m, dict) and m.get("segment_id")}
    for i, cand in enumerate(overview["candidates"]):
        decision = cand.get("decision")
        if decision not in CANDIDATE_DECISIONS:
            return ("CANDIDATE_DECISION_WORD", f"first_look.overview.candidates[{i}]",
                    f"decision must be exactly one of {list(CANDIDATE_DECISIONS)}; "
                    f"got {decision!r}")
        if decision == "measured":
            if not cand.get("segment_id"):
                return ("CANDIDATE_DECISION_WORD", f"first_look.overview.candidates[{i}]",
                        "'measured' names its segment_id")
            if cand["segment_id"] not in seg_ids:
                return ("MOTION_NOT_MEASURED", f"first_look.overview.candidates[{i}]",
                        "measured candidate missing from the measured segments")
            if cand["segment_id"] not in motion_seg_ids:
                return ("MOTION_NOT_MEASURED", f"first_look.overview.candidates[{i}]",
                        "measured candidate missing from first_look.motions")
        else:
            if not cand.get("reason"):
                return ("CANDIDATE_DECISION_WORD", f"first_look.overview.candidates[{i}]",
                        f"'{decision}' carries a reason")
    return None


def check_rm7_first_check(*, overview: dict | None, segments):
    """R-M7: one measurement first, the others confirm; choice recorded."""
    if not overview:
        return ("FIRST_CHECK_MISSING", "first_look.overview",
                "record which flight was measured first and why")
    first = overview.get("first_check")
    if not first or not first.get("segment_id") or not first.get("reason"):
        return ("FIRST_CHECK_MISSING", "first_look.overview.first_check",
                "name the first-check segment and why it measures best "
                "(most frames, clean mask, whole body in frame)")
    seg_ids = {s.get("segment_id") if isinstance(s, dict) else s
               for s in (segments or [])}
    if first["segment_id"] not in seg_ids:
        return ("FIRST_CHECK_MISSING", "first_look.overview.first_check",
                "the first check must be a measured segment")
    return None


def check_rs12_short_segment(*, moves: bool, span_frames: int):
    """R-S12: a still thing needs a short segment (≤50 frames)."""
    if moves:
        return None
    if span_frames <= STILL_SEGMENT_MAX_FRAMES:
        return None
    return ("STILL_SEGMENT_TOO_LONG", "references[].segment",
            f"still reference spans {span_frames} frames; segment a short "
            f"range of at most {STILL_SEGMENT_MAX_FRAMES} frames")

# generated from brief/07 · part 07 owns this file
"""``check_line`` — a blind look at a measured line (part 07 §§19–20).

A mask check says what a mask covers. Nothing yet says what a
measured line spans (a short sliver along a mask's edge can pass
every mask check and still scale five times off). This seventh tool
closes that hole with two fresh Spark conversations, spoken in the
blind client's line kinds (part 04 addendum 2026-10-31):

1. **Blind look.** The tool draws each line itself on that frame of
   the run's own clip — numbered, 3 px, a contrasting colour, small
   end caps — and a fresh conversation receives only the overlay
   plus a neutral question. It never sees the claims. The request
   carries ``kind: "line_look"`` with ``n_lines`` and reads
   ``descriptions``.
2. **Text-only match.** A second fresh conversation receives the
   first call's descriptions plus the claims, with no image, and
   answers yes/no per line. This keeps the claim from steering the
   look. The request carries ``kind: "line_match"`` and reads
   ``results``.

A ``FailedCallError`` from the client (a malformed model reply, a
wrong count, an empty string) becomes ``blind_failed`` with its
message — never a crash, and the agent is told not to retry the
identical call. A transport error becomes ``blind_failed`` with an
explicit may-retry-once. Neither failure counts against the cap of
six: only records appended to ``line_checks.jsonl`` count.

The record (``artifacts/t<turn>_check_line_<k>.json``, also
appended to ``artifacts/line_checks.jsonl`` read by part 11) holds
the frame, each line's endpoints, claim, blind description, the
seen side (``view``) and the spanned dimension (``dimension``),
``agrees`` and ``why``. The tool's result returns the descriptions
(plus ``views`` and ``dimensions``) and ``agrees`` to the agent.

Budget and filters: at most 6 calls per run (``MAX_LINE_CHECKS``).
Both Spark calls go on the ledger like ``check_mask``, and the
blindness filter of §17 (answer-seeking pattern screen, plus the
context-free classifier when one is wired) applies to the claims.
``check_line`` checks rather than explores, so it stays open in the
finishing phase (the loop's exploration closing never names it).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.accounting import FailedCallError

from .common import append_produced, next_artifact, run_path
from .result import err_result, ok_result
from .timing import find_clip, load_timing
from .web_search import pattern_hit, run_tokens

__all__ = [
    "check_line",
    "line_checks_path",
    "line_check_count",
    "parse_lines",
    "BLIND_LOOK_QUESTION",
    "MATCH_QUESTION",
    "MAX_LINE_CHECKS",
    "MAX_LINES_PER_CALL",
    "LINE_LOOK_KIND",
    "LINE_MATCH_KIND",
]

#: At most this many ``check_line`` calls per run (§19).
MAX_LINE_CHECKS = 6

#: At most this many lines per call (§19: one to three).
MAX_LINES_PER_CALL = 3

#: Call 1 sees only the overlay image: where each numbered line
#: starts and ends, naming the visible part at each end. It never
#: sees the claims, so the claim cannot steer the look. Part 07
#: §22: the look also names the side the object is seen from and
#: the object's own dimension the line runs along, so a line across
#: a side-seen figure cannot pass as a width.
BLIND_LOOK_QUESTION = (
    "For each numbered line drawn on this video frame, say where it "
    "starts and where it ends, naming the visible part at each end "
    "(for example 'the lower edge of the dark rectangle', 'the tip "
    "of the longest finger'). Do not guess what the video is or what "
    "is being measured. For each line, also say from which side the "
    "object is seen in this frame (front, back, side, top, or "
    "unclear), and along which of its own dimensions the line runs "
    "(height, width, depth, or unclear)."
)

#: Call 2 sees the descriptions and the claims, with no image: one
#: yes/no per line, each with one sentence. Part 07 §22: a claim
#: that names a dimension passes only when the look says the line
#: runs along that same dimension of the object.
MATCH_QUESTION = (
    "Does each description match its claim? For each line answer "
    "yes or no, with one sentence. When a claim names a dimension "
    "(height, tall, width, wide, depth, deep, length, long), answer "
    "yes only if the description says the line runs along that same "
    "dimension of the object."
)

#: Suffixes the tool never accepts from the agent: the overlay is
#: always drawn by the tool itself (§19).
_IMAGE_KEYS = ("image", "overlay", "artifact", "overlay_artifact",
               "image_artifact", "image_path")

#: Blind-client kinds (part 04 addendum 2026-10-31, part 07 §20):
#: the look carries the image only, the match carries descriptions
#: plus claims with no image.
LINE_LOOK_KIND = "line_look"
LINE_MATCH_KIND = "line_match"


def line_checks_path(run_dir) -> Path:
    """Append-only record of line checks (read by part 11, V-line)."""
    return Path(str(run_dir)) / "artifacts" / "line_checks.jsonl"


def line_check_count(run_dir) -> int:
    """How many ``check_line`` records this run already holds."""
    try:
        lines = line_checks_path(run_dir).read_text(
            encoding="utf-8").splitlines()
    except OSError:
        return 0
    return sum(1 for line in lines if line.strip())


def parse_lines(lines) -> list:
    """Validate ``lines`` to ``[{x1, y1, x2, y2, claim}]`` (or raise).

    Exactly one to three items; endpoints are finite numbers and the
    claim is a non-empty plain-words string. Anything carrying an
    agent-supplied image is rejected — the tool draws the overlay
    itself and the agent never supplies the image.
    """
    import math

    if not isinstance(lines, (list, tuple)) or not lines:
        raise ValueError("lines must be a non-empty list of 1 to 3 "
                         f"items, got {lines!r}")
    items = list(lines)
    if len(items) > MAX_LINES_PER_CALL:
        raise ValueError(
            f"lines holds at most {MAX_LINES_PER_CALL} items, got "
            f"{len(items)}")
    clean: list = []
    for position, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"lines[{position}] must be an object with "
                f"x1/y1/x2/y2/claim, got {item!r}")
        for key in _IMAGE_KEYS:
            if key in item:
                raise ValueError(
                    f"lines[{position}] carries {key!r}: the overlay "
                    f"is drawn by the tool itself; the agent never "
                    f"supplies the image")
        try:
            coords = [float(item[name])
                      for name in ("x1", "y1", "x2", "y2")]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"lines[{position}] needs numeric x1/y1/x2/y2, got "
                f"{item!r}: {exc}") from exc
        if not all(math.isfinite(v) for v in coords):
            raise ValueError(
                f"lines[{position}] endpoints must be finite, got "
                f"{item!r}")
        claim = item.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            raise ValueError(
                f"lines[{position}] needs a non-empty claim string, "
                f"got {item!r}")
        x1, y1, x2, y2 = coords
        if x1 == x2 and y1 == y2:
            raise ValueError(
                f"lines[{position}] has zero length: {item!r}")
        clean.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                      "claim": claim.strip()})
    return clean


def _read_frame(run_dir, frame: int):
    """Decode one exact frame of the run's own clip (or raise)."""
    import cv2

    facts = load_timing(run_dir)
    count = int(facts["frame_count"])
    if not 0 <= int(frame) < count:
        raise ValueError(
            f"frame {frame!r} is outside this clip "
            f"(0..{count - 1})")
    try:
        clip = find_clip(run_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(str(exc)) from exc
    capture = cv2.VideoCapture(str(clip))
    if not capture.isOpened():
        raise ValueError(f"cannot open clip {clip.name}")
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, float(int(frame)))
        ok, grid = capture.read()
    finally:
        capture.release()
    if not ok or grid is None:
        raise ValueError(f"frame {int(frame)} failed to decode")
    return grid


def _draw_overlay(grid, items):
    """Numbered 3 px lines in contrasting colours, small end caps."""
    import cv2

    canvas = grid.copy()
    height, width = canvas.shape[:2]
    palette = [(0, 255, 255), (255, 0, 255), (255, 255, 0)]
    for position, item in enumerate(items):
        colour = palette[position % len(palette)]
        x1 = min(max(int(round(item["x1"])), 0), width - 1)
        y1 = min(max(int(round(item["y1"])), 0), height - 1)
        x2 = min(max(int(round(item["x2"])), 0), width - 1)
        y2 = min(max(int(round(item["y2"])), 0), height - 1)
        start, end = (x1, y1), (x2, y2)
        cv2.line(canvas, start, end, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.line(canvas, start, end, colour, 3, cv2.LINE_AA)
        for point in (start, end):
            cv2.circle(canvas, point, 5, (0, 0, 0), -1,
                       cv2.LINE_AA)
            cv2.circle(canvas, point, 3, colour, -1, cv2.LINE_AA)
        label = str(position + 1)
        anchor = ((x1 + x2) // 2 + 6, (y1 + y2) // 2 - 6)
        cv2.putText(canvas, label, anchor,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4,
                    cv2.LINE_AA)
        cv2.putText(canvas, label, anchor,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, colour, 2,
                    cv2.LINE_AA)
    return canvas


def _encode_png(grid) -> bytes:
    import cv2

    ok, buffer = cv2.imencode(".png", grid)
    if not ok:
        raise ValueError("could not encode the line overlay")
    return bytes(buffer)


def _blindness_refusal(run_dir, turn, frame, claim, stage,
                       detail) -> dict:
    return err_result(
        "query_rejected", detail,
        metrics={"frame": frame, "claim": str(claim),
                 "allowed": False, "stage": stage})


def _check_claims(run_dir, turn, frame, items, classifier):
    """Blindness filter (§17) over the claims; refusal or ``None``."""
    import re as _re

    tokens = run_tokens(run_dir)
    for item in items:
        claim = item["claim"]
        hit = pattern_hit(claim, tokens)
        if hit:
            return _blindness_refusal(
                run_dir, turn, frame, claim, "pattern_screen",
                f"pattern screen: the claim seeks the clip or its "
                f"answer ({hit}); describe only what the line spans "
                f"(endpoints in plain words), never the clip, an "
                f"analysis of it, or its answer")
    if classifier is None:
        return None
    for item in items:
        claim = item["claim"]
        try:
            verdict = classifier(claim)
        except Exception as exc:  # noqa: BLE001 — doubt fails closed
            return _blindness_refusal(
                run_dir, turn, frame, claim, "classifier",
                f"blindness classifier failed "
                f"({type(exc).__name__}); the claim is refused "
                f"(fail closed)")
        word = _re.sub(r"[^a-z]", "", str(verdict or "").lower())
        if word != "no":
            return _blindness_refusal(
                run_dir, turn, frame, claim, "classifier",
                f"context-free classifier verdict "
                f"{word or 'empty'!r}: the claim looks like it finds "
                f"a specific video, an analysis of it, or the answer "
                f"to whether its motion is real or what gravity it "
                f"shows; describe only what the line spans")
    return None


def _debit(ledger, turn, usage, artifact) -> None:
    """One Spark call onto the ledger, like ``check_mask``."""
    if ledger is None:
        return
    try:
        ledger.record_mask_check(int(turn), usage, artifact=artifact)
    except (TypeError, ValueError):
        pass


def _normalise_look(entries, count: int) -> tuple:
    """Per-line look answers to ``{description, view, dimension}``.

    Part 07 §22: each per-line answer of the look carries where the
    line starts and ends (``description``), the side the object is
    seen from (``view``) and the object's own dimension the line
    runs along (``dimension``). A bare non-empty string — a look
    that predates §22, which the blind client passes through — names
    no side and no dimension, so both read ``"unclear"``. Anything
    else (wrong count, empty description, non-string fields) raises
    ``ValueError`` and the caller reports ``blind_malformed``.

    Returns ``(looks, match_texts)``: ``looks`` holds the per-line
    dicts written to the result JSON; ``match_texts`` holds what the
    match call judges. A bare string reaches the match unchanged; a
    per-line object reaches it as its description annotated with the
    seen side and the spanned dimension, so the dimension rule in
    ``MATCH_QUESTION`` judges something the look actually said.
    """
    if not isinstance(entries, list) or len(entries) != count:
        have = (len(entries) if isinstance(entries, list)
                else type(entries).__name__)
        raise ValueError(
            f"blind look returned {have} per-line answers for "
            f"{count} lines")
    looks: list = []
    match_texts: list = []
    for position, entry in enumerate(entries, start=1):
        if isinstance(entry, str):
            if not entry.strip():
                raise ValueError(
                    f"blind look returned an empty description "
                    f"for line {position}")
            looks.append({"description": entry.strip(),
                          "view": "unclear",
                          "dimension": "unclear"})
            match_texts.append(entry.strip())
            continue
        if not isinstance(entry, dict):
            raise ValueError(
                f"blind look returned no usable per-line "
                f"description for line {position}: {entry!r}")
        description = entry.get("description")
        if (not isinstance(description, str)
                or not description.strip()):
            raise ValueError(
                f"blind look returned no usable per-line "
                f"description for line {position}: {entry!r}")
        view = entry.get("view")
        dimension = entry.get("dimension")
        view = (view.strip() if isinstance(view, str)
                and view.strip() else "unclear")
        dimension = (dimension.strip()
                     if isinstance(dimension, str)
                     and dimension.strip() else "unclear")
        looks.append({"description": description.strip(),
                      "view": view,
                      "dimension": dimension})
        match_texts.append(
            f"{description.strip()} (seen from the {view}; the "
            f"line runs along the object's {dimension})")
    return looks, match_texts


def _blind_failed(frame, overlay_rel, detail, *, retry_once) -> dict:
    """A blind-call failure as a tool error (§20).

    ``retry_once`` tells the agent whether this call may be retried
    once: yes for a transport error, no for a malformed model reply
    (retrying an identical malformed call only rebills it). Either
    way the failure appends no record, so it never counts against
    the cap of six.
    """
    hint = ("you may retry this call once"
            if retry_once
            else "do not retry the identical call")
    return err_result(
        "blind_failed", f"{detail}; {hint}",
        metrics={"frame": frame,
                 "overlay_artifact": overlay_rel,
                 "retry_once": bool(retry_once)})


def check_line(run_dir, turn, frame=None, lines=None, *,
               spark_client=None, classifier=None, ledger=None,
               **extra) -> dict:
    """Blind two-look verdict on one to three measured lines.

    The tool draws ``lines`` itself on ``frame`` of the run's own
    clip and runs two fresh context-free Spark conversations: the
    first sees only the overlay, the second sees the first call's
    descriptions plus the claims, with no image.
    """
    if extra:
        return err_result(
            "bad_arguments",
            "check_line draws its own overlay: unexpected "
            f"argument(s) {', '.join(sorted(extra))}; the agent "
            "never supplies the image",
            metrics={"frame": frame})
    if isinstance(frame, bool) or not isinstance(frame, int):
        return err_result("bad_frame",
                          f"frame must be an int, got {frame!r}",
                          metrics={"frame": frame})
    try:
        items = parse_lines(lines)
    except ValueError as exc:
        return err_result("bad_lines", str(exc),
                          metrics={"frame": frame})
    try:
        grid = _read_frame(run_dir, frame)
    except ValueError as exc:
        message = str(exc)
        code = ("missing_timing" if "timing" in message
                else "no_clip" if "clip" in message
                else "bad_frame")
        return err_result(code, message, metrics={"frame": frame})
    height, width = grid.shape[:2]
    for position, item in enumerate(items, start=1):
        for name, limit in (("x1", width), ("x2", width),
                            ("y1", height), ("y2", height)):
            if not 0 <= item[name] < limit:
                return err_result(
                    "bad_lines",
                    f"lines[{position}].{name}={item[name]!r} lies "
                    f"outside this {width}x{height} frame",
                    metrics={"frame": frame})
    if spark_client is None:
        return err_result("blind_unavailable",
                          "no blind backend is wired for this run",
                          metrics={"frame": frame})
    if line_check_count(run_dir) >= MAX_LINE_CHECKS:
        return err_result(
            "cap_spent",
            f"check_line allows at most {MAX_LINE_CHECKS} calls per "
            f"run: the cap is spent",
            metrics={"frame": frame,
                     "cap": MAX_LINE_CHECKS})
    refusal = _check_claims(run_dir, turn, frame, items, classifier)
    if refusal is not None:
        return refusal
    overlay = _draw_overlay(grid, items)
    try:
        raw = _encode_png(overlay)
    except ValueError as exc:
        return err_result("write_failed", str(exc),
                          metrics={"frame": frame})
    overlay_rel = next_artifact(run_dir, turn, "check_line", ".png")
    overlay_path = run_path(run_dir, overlay_rel)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        overlay_path.write_bytes(raw)
    except OSError as exc:
        return err_result("write_failed",
                          f"could not write {overlay_rel}: {exc}",
                          metrics={"frame": frame})
    try:
        seen = spark_client({"kind": LINE_LOOK_KIND,
                             "image": raw,
                             "question": BLIND_LOOK_QUESTION,
                             "n_lines": len(items)})
    except FailedCallError as exc:
        # A malformed model reply (wrong count, empty string, no
        # structured answer): visible, not a crash, no retry (§20).
        return _blind_failed(
            frame, overlay_rel, f"blind look failed: {exc}",
            retry_once=False)
    except Exception as exc:  # noqa: BLE001 — blind death is a tool error
        return _blind_failed(
            frame, overlay_rel,
            f"blind look failed on a transport error "
            f"({type(exc).__name__}: {exc})",
            retry_once=True)
    raw_looks = (seen.get("descriptions") if isinstance(
        seen, dict) else None)
    try:
        looks, match_texts = _normalise_look(raw_looks, len(items))
    except ValueError as exc:
        return err_result(
            "blind_malformed", str(exc),
            metrics={"frame": frame,
                     "overlay_artifact": overlay_rel})
    descriptions = [look["description"] for look in looks]
    _debit(ledger, turn,
           seen.get("usage") if isinstance(seen, dict) else None,
           overlay_rel)
    try:
        judged = spark_client(
            {"kind": LINE_MATCH_KIND,
             "descriptions": list(match_texts),
             "claims": [item["claim"] for item in items],
             "question": MATCH_QUESTION})
    except FailedCallError as exc:
        # A malformed model reply: visible, not a crash, no retry.
        return _blind_failed(
            frame, overlay_rel, f"line match failed: {exc}",
            retry_once=False)
    except Exception as exc:  # noqa: BLE001 — blind death is a tool error
        return _blind_failed(
            frame, overlay_rel,
            f"line match failed on a transport error "
            f"({type(exc).__name__}: {exc})",
            retry_once=True)
    results = (judged.get("results") if isinstance(judged, dict)
               else None)
    if (not isinstance(results, list)
            or len(results) != len(items)
            or not all(isinstance(entry, dict)
                       and isinstance(entry.get("agrees"), bool)
                       for entry in results)):
        return err_result(
            "blind_malformed",
            "match call returned no usable per-line yes/no answers",
            metrics={"frame": frame,
                     "overlay_artifact": overlay_rel})
    _debit(ledger, turn,
           judged.get("usage") if isinstance(judged, dict) else None,
           overlay_rel)
    record_lines = []
    for item, look, entry in zip(items, looks, results):
        why = entry.get("why")
        record_lines.append({
            "x1": item["x1"], "y1": item["y1"],
            "x2": item["x2"], "y2": item["y2"],
            "claim": item["claim"],
            "description": look["description"],
            "view": look["view"],
            "dimension": look["dimension"],
            "agrees": bool(entry.get("agrees")),
            "why": str(why).strip() if isinstance(why, str)
            else "",
        })
    record = {"frame": int(frame), "lines": record_lines,
              "overlay_artifact": overlay_rel, "turn": int(turn),
              "blind_question": BLIND_LOOK_QUESTION,
              "match_question": MATCH_QUESTION}
    record_rel = next_artifact(run_dir, turn, "check_line", ".json")
    record_path = run_path(run_dir, record_rel)
    record_path.write_text(json.dumps(record, indent=2) + "\n",
                           encoding="utf-8")
    try:
        journal = line_checks_path(run_dir)
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError as exc:
        return err_result("write_failed",
                          f"could not append line_checks.jsonl: {exc}",
                          metrics={"frame": frame,
                                   "overlay_artifact": overlay_rel})
    append_produced(run_dir, [overlay_rel, record_rel,
                              "artifacts/line_checks.jsonl"])
    agrees = [entry["agrees"] for entry in record_lines]
    confirmed = sum(1 for flag in agrees if flag)
    summary = (f"line check on frame {int(frame)}: {confirmed}/"
               f"{len(agrees)} line(s) confirm the claim(s)")
    if confirmed < len(agrees):
        bad = [str(position) for position, flag in
               enumerate(agrees, start=1) if not flag]
        summary += ("; line(s) " + ",".join(bad)
                    + " do not match — re-measure them")
    return ok_result(
        summary, files=[overlay_rel, record_rel],
        metrics={"frame": int(frame),
                 "overlay_artifact": overlay_rel,
                 "record_artifact": record_rel,
                 "descriptions": descriptions,
                 "views": [look["view"] for look in looks],
                 "dimensions": [look["dimension"] for look in looks],
                 "agrees": agrees,
                 "blind": True,
                 "context_free": True})

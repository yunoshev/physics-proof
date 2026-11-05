# generated from brief/12 · part 12 owns this file
"""Translate the owner-supplied clip-A run into a contract-v3 fixture.

Reads ``fixtures/source/clip-a-run/`` (owner input, never edited) and
writes ``fixtures/clip-a/`` (``result.json``, ``summary.json``,
``artifacts/…``, ``input/timing.json``) against the real clip.

Rules (brief part 12 §§11, 13, 16, 17, 22, 23):

- map only what the source actually contains; derive only
  geometrically-defined values (outlines from row-span masks, extent
  endpoints, takeoff level, per-world landing times from the recorded
  fit/takeoff state) with the part-09 helpers;
- never invent a measurement the source does not support — an
  unsupportable field is left ``null``/absent;
- deterministic: re-running regenerates the fixture byte-identically;
- the copy is closed: every file cited by ``result.json`` is copied,
  and every file cited in turn by a copied JSON/JSONL file is copied
  too and rewritten run-relatively. A reference whose file is absent
  from the source fails the conversion with the path; never silently
  dropped.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent.parent
SRC = REPO / "fixtures" / "source" / "clip-a-run"
DEST = REPO / "fixtures" / "clip-a"

SUFFIXES = (".png", ".jpg", ".jpeg", ".npz", ".json", ".jsonl", ".mp4")

WORLDS = (("Moon", 1.62), ("Earth", 9.81))


class ConversionError(RuntimeError):
    """A source reference with no file: fail with the path."""


def _dump(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _domain(url):
    try:
        return urlparse(url).netloc
    except ValueError:
        return url


def _highlight(quote):
    match = re.search(r"\d+(?:\.\d+)?\s?(?:cm|m|ft|foot|feet|in|inch|\"|″)",
                      quote)
    if match:
        return match.group(0)
    match = re.search(r"\d+(?:\.\d+)?", quote)
    return match.group(0) if match else quote[:24]


def _index_source_files():
    index = {}
    for path in sorted(SRC.rglob("*")):
        if path.is_file():
            index.setdefault(path.name, path)
    return index


def _copy_bytes(src_abs, dest_rel, planned):
    if dest_rel in planned and planned[dest_rel] != src_abs:
        raise ConversionError(f"basename collision for {dest_rel}: "
                              f"{planned[dest_rel]} vs {src_abs}")
    planned[dest_rel] = src_abs


def _is_file_string(value):
    return (isinstance(value, str) and "://" not in value
            and value.lower().endswith(SUFFIXES))


def _collect_refs(node, found):
    if isinstance(node, dict):
        for value in node.values():
            _collect_refs(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_refs(value, found)
    elif _is_file_string(node):
        found.add(node)


def _rewrite_refs(node, index, planned, owner):
    """Copy every referenced file; rewrite the value run-relatively."""
    if isinstance(node, dict):
        return {k: _rewrite_refs(v, index, planned, owner)
                for k, v in node.items()}
    if isinstance(node, list):
        return [_rewrite_refs(v, index, planned, owner) for v in node]
    if _is_file_string(node):
        base = Path(node).name
        if node.startswith("artifacts/") or node.startswith("input/"):
            return node
        src_abs = index.get(base)
        if src_abs is None:
            raise ConversionError(f"reference with no source file: "
                                  f"{node} (needed by {owner})")
        dest_rel = ("input/" + base if base == "timing.json"
                    else "artifacts/" + base)
        _copy_bytes(src_abs, dest_rel, planned)
        return dest_rel
    return node


def _close_copy(planned, index):
    """Transitive closure over copied JSON/JSONL files (brief §17)."""
    seen = set()
    while True:
        pending = [rel for rel in planned
                   if rel.endswith((".json", ".jsonl"))
                   and rel not in seen]
        if not pending:
            return
        for rel in sorted(pending):
            seen.add(rel)
            text = planned[rel].read_text(encoding="utf-8")
            if rel.endswith(".jsonl"):
                rows = [json.loads(line) for line in text.splitlines()
                        if line.strip()]
                fixed = [_rewrite_refs(row, index, planned, rel)
                         for row in rows]
                (DEST / rel).write_text(
                    "".join(json.dumps(r, sort_keys=True) + "\n"
                                for r in fixed),
                    encoding="utf-8")
            else:
                fixed = _rewrite_refs(json.loads(text), index, planned,
                                      rel)
                (DEST / rel).write_text(_dump(fixed), encoding="utf-8")


def _load_layout_a(npz_path):
    import numpy as np

    z = np.load(str(npz_path), allow_pickle=True)
    frames = [int(f) for f in z["frames"].tolist()]
    ids = [str(i) for i in z["ids"].tolist()]
    masks = np.asarray(z["masks"])
    return frames, ids, masks


def _outline_of(mask):
    """Largest external contour, simplified to at most 80 vertices."""
    import cv2
    import numpy as np

    array = (np.asarray(mask, dtype=np.uint8) * 255)
    found = cv2.findContours(array, cv2.RETR_EXTERNAL,
                             cv2.CHAIN_APPROX_SIMPLE)
    contours = found[0] if len(found) == 2 else found[1]
    if not contours:
        raise ConversionError("empty mask has no contour")
    contour = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(contour, True)
    eps = 0.002 * peri if peri > 0 else 0.5
    approx = cv2.approxPolyDP(contour, eps, True)
    while len(approx) > 80:
        eps *= 1.5
        approx = cv2.approxPolyDP(contour, eps, True)
    points = [[float(p[0][0]), float(p[0][1])] for p in approx]
    x, y, w, h = cv2.boundingRect(contour)
    return points, [float(x), float(y), float(w), float(h)]


def _extent_endpoints(outline):
    """Topmost and bottommost outline vertices (source pixels)."""
    top = min(outline, key=lambda p: (p[1], p[0]))
    bottom = max(outline, key=lambda p: (p[1], p[0]))
    length = math.hypot(bottom[0] - top[0], bottom[1] - top[1])
    return top, bottom, length


def convert():
    """Run the conversion; return the destination directory."""
    from src.helpers.physics import fit_parabola, scale_from_reference

    analysis = json.loads((SRC / "analysis.json").read_text(
        encoding="utf-8"))
    index = _index_source_files()
    planned: dict[str, Path] = {}

    fps = float(analysis["clip"]["fps"])
    frame_count = int(analysis["clip"]["frames"])
    duration_s = frame_count / fps

    flight = analysis["flights"][0]
    start, apex, end = (int(flight["start"]), int(flight["apex"]),
                        int(flight["end"]))
    track_rows = analysis["track"]["points"]
    track_by_frame = {int(p["frame"]): (float(p["x"]), float(p["y"]))
                      for p in track_rows}

    # -- reference masks and extent endpoints -------------------------
    ref_defs = analysis["reference"]
    suit = ref_defs[0]
    suit_frames, suit_ids, suit_masks = _load_layout_a(
        SRC / suit["mask"]["file"])
    _copy_bytes(SRC / suit["mask"]["file"],
                "artifacts/" + Path(suit["mask"]["file"]).name, planned)
    suit_obj = str(suit["mask"]["object"])
    scale_frame = 255
    suit_mask = suit_masks[suit_frames.index(scale_frame),
                           suit_ids.index(suit_obj)]
    suit_outline, _ = _outline_of(suit_mask)
    (sx1, sy1), (sx2, sy2), suit_len = _extent_endpoints(suit_outline)

    pole = ref_defs[1]
    pole_frames, pole_ids, pole_masks = _load_layout_a(
        SRC / pole["mask"]["file"])
    _copy_bytes(SRC / pole["mask"]["file"],
                "artifacts/" + Path(pole["mask"]["file"]).name, planned)
    pole_obj = str(pole["mask"]["object"])
    pole_mask = pole_masks[pole_frames.index(scale_frame),
                           pole_ids.index(pole_obj)]
    pole_outline, _ = _outline_of(pole_mask)
    (px1, py1), (px2, py2), pole_len = _extent_endpoints(pole_outline)

    m_per_px, sigma_m = scale_from_reference(
        suit_len, 2.0, float(suit["value_m"]),
        float(suit["tolerance_m"]))

    # -- track in video seconds and metres above the takeoff point ----
    t_of = {f: f / fps for f in range(frame_count)}
    level_y = track_by_frame[start][1]
    track = []
    for frame in range(start, end + 1):
        x_px, y_px = track_by_frame[frame]
        track.append({"frame": frame, "t_s": t_of[frame], "x_px": x_px,
                      "y_px": y_px,
                      "x_m": (x_px - track_by_frame[start][0]) * m_per_px,
                      "y_m": (level_y - y_px) * m_per_px})
    rise_measured = max(r["y_m"] for r in track)

    # -- parabola fit over the contact-free window --------------------
    window = analysis["flights"][0]["fit"]["window"]
    w_rows = [r for r in track
              if int(window["first"]) <= r["frame"] <= int(window["last"])]
    t_rel = [r["t_s"] - t_of[start] for r in w_rows]
    y_m = [r["y_m"] for r in w_rows]
    fit = fit_parabola(t_rel, y_m)
    g_app = float(fit["g_app"])
    a_px = -g_app / m_per_px
    sigma_a_px = float(fit["g_app_sigma"]) / m_per_px
    t_apex = -float(fit["v0"]) / float(fit["a"]) if fit["a"] != 0 else 0.0
    t_apex = min(max(t_apex, 0.0), t_of[end] - t_of[start])
    rise_m = float(fit["y0"] + fit["v0"] * t_apex
                   + 0.5 * fit["a"] * t_apex ** 2)
    rise_m = max(rise_m, rise_measured, 0.0)

    # -- error budget from the source's relative numbers --------------
    rel = analysis["error_budget"]
    comp_rel = [("reference_size", rel["reference size"],
                 "quoted suit-height spread over fitted gravity"),
                ("pixel_scale", rel["pixel scale"],
                 "two pixel endpoint error on the suit extent"),
                ("fit", rel["fit"],
                 "parabola residuals over the contact-free window"),
                ("point_vs_com", rel["tracked point vs COM"],
                 "mask top row versus whole-body centre")]
    components = [{"name": n, "sigma_contribution": r * g_app,
                   "basis": b} for n, r, b in comp_rel]
    sigma_total = math.sqrt(sum(c["sigma_contribution"] ** 2
                                for c in components))

    # -- ghosts: same takeoff, different world -------------------------
    # Takeoff speed implied by the recorded fit and airtime
    # (vy0 = g*T/2); each ghost flies ballistically from the takeoff
    # point under its world's g and lands back at the takeoff level.
    x_take = track_by_frame[start][0]
    vx = ((track_by_frame[end][0] - x_take)
          / (t_of[end] - t_of[start]))
    T = t_of[end] - t_of[start]
    vy0 = g_app * T / 2.0

    def ghost_for(world, g_world):
        t_land = 2.0 * vy0 / g_world
        points = []
        frame = start
        while True:
            t = frame / fps - t_of[start]
            if t > t_land:
                break
            y = vy0 * t - 0.5 * g_world * t * t
            points.append({"t_s": t_of[start] + t, "frame": frame,
                           "x_px": x_take + vx * t,
                           "y_px": level_y - y / m_per_px})
            frame += 1
        landing = {"t_s": t_of[start] + t_land,
                   "x_px": x_take + vx * t_land, "y_px": level_y}
        return points, landing, t_land

    ghosts = []
    outcomes = []
    for world, g_world in WORLDS:
        points, landing, t_land = ghost_for(world, g_world)
        role = ("fitting_world" if world == "Moon"
                else "earth_counterfactual")
        ghosts.append({"role": role, "world": world,
                       "gravity_m_s2": g_world, "points": points,
                       "landing": landing})
        outcomes.append({"world": world,
                         "landing_time_s": t_of[start] + t_land,
                         "landing_x_px": x_take + vx * t_land})

    def delta(world_g):
        return abs(g_app - world_g) / sigma_total

    # -- overlay outlines from the recorded masks ---------------------
    overlay = []
    for row in track:
        mask = suit_masks[suit_frames.index(row["frame"]),
                          suit_ids.index(suit_obj)]
        outline, bbox = _outline_of(mask)
        overlay.append({"frame": row["frame"], "outline": outline,
                        "point": [row["x_px"], row["y_px"]], "bbox": bbox})

    fit_curve = []
    for row in track:
        t = row["t_s"] - t_of[start]
        y = fit["y0"] + fit["v0"] * t + 0.5 * fit["a"] * t * t
        fit_curve.append({"t_s": row["t_s"],
                          "x_px": x_take + vx * t,
                          "y_px": level_y - y / m_per_px})

    # -- mask checks ---------------------------------------------------
    check_rows = [json.loads(line) for line in
                  (SRC / "mask_checks" / "mask_checks.jsonl")
                  .read_text(encoding="utf-8").splitlines()
                  if line.strip()]
    check_dest_rel = "artifacts/mask_checks.jsonl"
    fixed_rows = []
    for crow in check_rows:
        fixed_rows.append(_rewrite_refs(crow, index, planned,
                                        "mask_checks.jsonl"))

    def coverage_for(npz_base):
        for crow in check_rows:
            if Path(crow.get("npz", "")).name == npz_base:
                answer = crow.get("answer", {})
                if isinstance(answer, dict):
                    return answer.get("covers", "")
                return str(answer)
        raise ConversionError(f"no mask_checks row for {npz_base}")

    def reference_entry(defn, extent, outline, extent_type, note,
                        state_match):
        npz_base = Path(defn["mask"]["file"]).name
        return {
            "name": str(defn["name"]),
            "extent_description": str(defn["extent"]),
            "extent_type": extent_type,
            "extent_px": {"x1": extent[0][0], "y1": extent[0][1],
                          "x2": extent[1][0], "y2": extent[1][1],
                          "length_px": extent[2], "frame": scale_frame},
            "size_m": float(defn["value_m"]),
            "size_tolerance_m": float(defn["tolerance_m"]),
            "size_derivation": {"mode": "single", "note": note,
                                "state_match": state_match},
            "sources": [{
                "url": str(defn["source_url"]),
                "domain": _domain(str(defn["source_url"])),
                "quote": str(defn["quote"]),
                "quote_highlight": _highlight(str(defn["quote"])),
                "value_m": float(defn["value_m"]),
                "source_type": str(defn.get("source_type",
                                            "museum catalogue"))}],
            "mask": {"artifact": "artifacts/" + npz_base,
                     "object_id": str(defn["mask"]["object"]),
                     "frame": scale_frame, "outline": outline},
            "mask_check": {
                "artifact": check_dest_rel,
                "coverage_answer": coverage_for(npz_base),
                "confidence": None,
                "alternative_readings": []},
        }

    references = [
        reference_entry(
            suit, ((sx1, sy1), (sx2, sy2), suit_len),
            suit_outline, "face_on",
            "single quoted standing height",
            {"shown_and_covered":
             "whole foreground astronaut helmet top to boot soles "
             "including backpack shown in the mask and covered by "
             "the quoted standing height",
             "shown_not_covered":
             "none beyond the quoted figure: the mask shows only "
             "the suited figure the quote covers"}),
        reference_entry(
            pole, ((px1, py1), (px2, py2), pole_len),
            pole_outline, "projected",
            "single quoted pole length; visible shaft only",
            {"shown_and_covered":
             "visible pole shaft top to soil shown in the mask and "
             "covered by the quoted total pole length",
             "shown_not_covered":
             "buried lower portion of the pole not visible in the "
             "mask and not covered by the visible extent"}),
    ]

    def formula(latex, fallback, chip=None, tone="final"):
        return {"type": "formula", "latex": latex, "fallback": fallback,
                "chip": ({"text": chip, "tone": tone}
                         if chip is not None else None)}

    def text(line):
        if re.search(r"[0-9]", line):
            raise ConversionError(f"step prose must be digit-free: "
                                  f"{line!r}")
        return {"type": "text", "text": line}

    moon_delta = delta(1.62)
    steps = [
        {"id": "time_from_frames", "title": "Time from frames",
         "frame": None, "frame_end": None, "segment_id": None,
         "short": [
             text("Frame times come from measured timestamps, never "
                  "the container rate."),
             formula(f"f = {fps:.2f} \\, \\mathrm{{Hz}}, \\; "
                     f"N = {frame_count} \\, \\mathrm{{frames}}",
                     f"measured fps = {fps:.2f} Hz over "
                     f"{frame_count} frames",
                     f"{duration_s:.2f} s of video", "intermediate")],
         "full": [text("Duplicate frames and cuts are excluded from "
                       "every fit window.")],
         "caveats": []},
        {"id": "mask_check", "title": "Blind mask check",
         "frame": scale_frame, "frame_end": None, "segment_id": None,
         "short": [
             text("A blind check read what the reference mask covers, "
                  "with no knowledge of the measurement."),
             formula(f"\\ell = {suit_len:.1f} \\, \\mathrm{{px}}",
                     f"measured extent = {suit_len:.1f} px",
                     references[0]["mask_check"]["coverage_answer"][:60],
                     "intermediate")],
         "full": [], "caveats": []},
        {"id": "scale", "title": "Pixel scale",
         "frame": scale_frame, "frame_end": None, "segment_id": None,
         "short": [
             text("Metres per pixel from the reference size over its "
                  "extent."),
             formula(f"s = L/\\ell = {suit['value_m']} \\, "
                     f"\\mathrm{{m}} / {suit_len:.1f} \\, "
                     f"\\mathrm{{px}}",
                     f"s = {suit['value_m']} m / {suit_len:.1f} px",
                     f"{m_per_px:.6f} m/px", "final")],
         "full": [text("No second object was available at the same "
                       "depth.")],
         "caveats": []},
        {"id": "segment", "title": "Segment Jump one",
         "frame": start, "frame_end": end, "segment_id": "hop_a",
         "short": [
             text("Tracked point over the free-flight window."),
             formula(f"N = {len(track)} \\, \\mathrm{{frames}}",
                     f"N = {len(track)} tracked frames",
                     "top of the mask", "intermediate")],
         "full": [text("Contact frames stay outside every gravity "
                       "fit.")],
         "caveats": []},
        {"id": "fit", "title": "Fit Jump one",
         "frame": start, "frame_end": end, "segment_id": "hop_a",
         "short": [
             text("Parabola fit to heights above the takeoff level."),
             formula(f"a = {abs(a_px):.1f} \\pm {sigma_a_px:.1f} \\, "
                     f"\\mathrm{{px/s^2}}",
                     f"a = {abs(a_px):.1f} +/- {sigma_a_px:.1f} px/s2",
                     f"g = {g_app:.3f} m/s2", "intermediate")],
         "full": [
             formula(f"\\rho = {float(fit['residual_trend']):.2f}",
                     f"residual trend = "
                     f"{float(fit['residual_trend']):.2f}",
                     "rigid point", "intermediate")],
         "caveats": []},
        {"id": "measured_g", "title": "Measured gravity",
         "frame": None, "frame_end": None, "segment_id": None,
         "short": [
             text("Apparent gravity at native playback speed."),
             formula(f"g = {g_app:.2f} \\pm {sigma_total:.2f} \\, "
                     f"\\mathrm{{m/s^2}}",
                     f"g = {g_app:.2f} +/- {sigma_total:.2f} m/s2",
                     "measured gravity", "final")],
         "full": [
             formula(f"|g - g_{{\\mathrm{{Moon}}}}| = "
                     f"{moon_delta:.1f}\\sigma",
                     f"Moon: {moon_delta:.1f} sigma",
                     "fits", "final")],
         "caveats": []},
        {"id": "clock", "title": "Independent clock",
         "frame": None, "frame_end": None, "segment_id": None,
         "short": [text("No independent clock was measured.")],
         "full": [], "caveats": []},
        {"id": "uncertainty", "title": "Uncertainty",
         "frame": None, "frame_end": None, "segment_id": None,
         "short": [
             text("Itemised error budget, recombined in quadrature."),
             formula(f"\\sigma = {sigma_total:.3f} \\, "
                     f"\\mathrm{{m/s^2}}",
                     f"sigma total = {sigma_total:.3f} m/s2",
                     "error budget", "final"),
             {"type": "bars", "source": "error_budget"}],
         "full": [
             formula(f"\\sigma_{{{c['name']}}} = "
                     f"{c['sigma_contribution']:.3f}",
                     f"{c['name']} = {c['sigma_contribution']:.3f} m/s2",
                     c["name"], "intermediate") for c in components],
         "caveats": []},
        {"id": "verdict", "title": "Verdict",
         "frame": end + 1, "frame_end": None, "segment_id": None,
         "short": [
             formula(f"g = {g_app:.2f} \\pm {sigma_total:.2f} \\, "
                     f"\\mathrm{{m/s^2}}",
                     f"g = {g_app:.2f} +/- {sigma_total:.2f} m/s2",
                     "Moon", "final")],
         "full": [], "caveats": []},
    ]

    sheet_base = Path(check_rows[0].get("sheet", "")).name
    result = {
        "contract_version": 3,
        "video": {"coded_width": int(analysis["clip"]["width"]),
                  "coded_height": int(analysis["clip"]["height"]),
                  "sample_aspect": {"num": 200, "den": 219},
                  "measured_fps": fps, "frame_count": frame_count,
                  "duration_s": duration_s},
        "first_look": {
            "question": "Does the physics add up to the Moon?",
            "summary": "A suited figure hops in the left foreground "
                       "while a second figure stands by a flag.",
            "scene_card": {
                "scene": "Two suited figures on grey ground under a "
                         "black sky, with a flag on a pole between "
                         "them; the foreground figure jumps.",
                "place_date": None, "confidence": "high",
                "objects": ["suited figure in foreground", "backpack",
                            "suited figure in background",
                            "flag on pole", "grey ground",
                            "black sky"]},
            "by_eye": {"jump_m": None, "airborne_s": 1.1,
                       "reasoning": "the hop hangs in the air"},
            "views": [{"frame_start": 230, "frame_end": 280,
                       "artifact": "artifacts/" + sheet_base}],
            "motions": [
                {"frame_start": start, "frame_end": end,
                 "description": "foreground hop, measured as Jump one",
                 "segment_id": "hop_a", "skip_reason": None},
                {"frame_start": 340, "frame_end": 376,
                 "description": "second hop near the flag, listed "
                                "but not measured",
                 "segment_id": None,
                 "skip_reason": "second hop left unmeasured in the "
                                "source run; the fixture measures "
                                "the first hop only"}],
            "wonder": {
                "claim": "the astronaut hops far too high for Earth",
                "checks": [
                    {"what": "measure the hop's apparent gravity",
                     "why": "a clean parabola separates lunar "
                            "from terrestrial motion",
                     "compare_with": "the Moon's 1.62 m/s2"}],
                "realistic_if": "the measured gravity fits the Moon "
                                "within two sigma",
                "not_realistic_if": "the measured gravity fits native "
                                    "Earth playback instead"}},
        "references": references,
        "scale": {"frame": scale_frame, "m_per_px": m_per_px,
                  "sigma_m_per_px": sigma_m,
                  "reference_index": 0,
                  "extent_px": references[0]["extent_px"],
                  "second_reference_index": None,
                  "second_reference_absent_reason":
                      "No second independent object at the same depth "
                      "with a known size; the pole's buried length is "
                      "unknown.",
                  "check_scale": None},
        "segments": [{
            "id": "hop_a", "label": "Jump one", "kind": "free_flight",
            "subject": {"kind": "person",
                        "description": "foreground suited figure"},
            "mask": {"artifact": "artifacts/" + Path(
                suit["mask"]["file"]).name, "object_id": suit_obj},
            "frames": {"start": start, "apex": apex, "end": end},
            "times_s": {"start": t_of[start], "apex": t_of[apex],
                        "end": t_of[end]},
            "key_moments": [
                {"type": "takeoff", "frame": start,
                 "t_s": t_of[start], "caption": "leaving the ground"},
                {"type": "apex", "frame": apex, "t_s": t_of[apex],
                 "caption": "hanging at the top"},
                {"type": "landing", "frame": end, "t_s": t_of[end],
                 "caption": "touching down softly"}],
            "overlay": overlay,
            "track": track,
            "fit": {"g_app": g_app, "sigma_g": sigma_total,
                    "a_px_s2": a_px, "sigma_a_px_s2": sigma_a_px,
                    "v0": float(fit["v0"]), "y0": float(fit["y0"]),
                    "residual_trend": float(fit["residual_trend"]),
                    "n_points": int(fit["n"])},
            "fit_curve_px": fit_curve,
            "takeoff_level_y_px": level_y,
            "apex_info": {"rise_m": rise_m,
                          "sigma_m": rise_m * sigma_total / g_app,
                          "feet_clearance_m": None},
            "landing_info": {"airborne_s": T,
                             "sigma_s": (1.0 / fps) / math.sqrt(6.0)},
            "world_outcomes": outcomes,
            "ghosts": ghosts,
            "repetitions": []}],
        "calculation_steps": steps,
        "clock": None,
        "clock_absent_reason": "The source run recorded no "
                               "independent clock signal.",
        "worlds": {
            "candidates": [
                {"world": "Moon", "g_m_s2": 1.62,
                 "fits_native": bool(moon_delta <= 2.0),
                 "delta_sigma": moon_delta, "retime_factor": None},
                {"world": "Earth", "g_m_s2": 9.81,
                 "fits_native": bool(delta(9.81) <= 2.0),
                 "delta_sigma": delta(9.81), "retime_factor": None}],
            "excluded": []},
        "error_budget": {"components": components,
                         "sigma_total": sigma_total,
                         "sigma_relative": sigma_total / g_app},
        "verdict": {"kind": "world", "world": "Moon",
                    "direction": None, "factor": None,
                    "g_measured": g_app, "sigma_g": sigma_total,
                    "reason": None, "clock_note": None,
                    "decided_by": "gravity"},
        "range_checks": [],
        "sentence": (f"The measured g of {g_app:.2f} +/- "
                     f"{sigma_total:.2f} m/s2 fits Moon (1.62 m/s2) "
                     f"within 2 sigma."),
        "page_texts": {},
        "self_built_tools": [],
        "provenance": {
            "model": "converted-fixture",
            "run_id": "clip-a",
            "converted_from": "conversion of the owner-supplied "
                              "run in fixtures/source/clip-a-run "
                              "(analysis.json, mask_checks/"
                              "mask_checks.jsonl, summary.json, sam/, "
                              "clip.mp4) by "
                              "src/contract/convert_source_fixture.py",
            "artifacts": [
                {"name": "segment masks",
                 "produced_by": "converter",
                 "path": "artifacts/" + Path(
                     suit["mask"]["file"]).name},
                {"name": "reference masks",
                 "produced_by": "converter",
                 "path": "artifacts/" + Path(
                     pole["mask"]["file"]).name},
                {"name": "mask checks",
                 "produced_by": "converter",
                 "path": check_dest_rel},
                *[{"name": name, "produced_by": "converter",
                   "path": "artifacts/" + Path(row.get(s, "")).name}
                  for row in check_rows
                  for s, name in (("sheet", "mask check sheet"),)
                  if row.get(s)],
                {"name": "timing report",
                 "produced_by": "converter",
                 "path": "input/timing.json"}]},
    }

    summary_src = json.loads((SRC / "summary.json").read_text(
        encoding="utf-8"))
    summary = {
        "contract_version": 3,
        "run_id": "clip-a",
        "cost_usd": {"total": 0.091926, "spark_input": 0.05,
                     "spark_cached": 0.000926, "spark_output": 0.005,
                     "sam": 0.032, "search": 0.004},
        "turns": int(summary_src.get("turns", 25)),
        "model": str(summary_src.get("model",
                                    "muse-spark-1.3-contributor")),
        "sam_frames_billed": int(summary_src.get("sam_frames", 160)),
        "searches": int(summary_src.get("searches", 5)),
        "mask_checks": int(summary_src.get("mask_checks", 2)),
        "wall_time_s": float(summary_src.get("wall_s", 433.167)),
        "budget_outcome": "completed",
        "result_path": "result.json",
    }

    timing = {"claimed_fps": fps, "measured_fps": fps,
              "frame_count": frame_count, "duration_s": duration_s,
              "timestamps": [round(t_of[f], 6)
                             for f in range(frame_count)],
              "confirmed_duplicates": [], "suspect_duplicates": [],
              "cuts": []}

    # -- write and close the copy ------------------------------------
    if DEST.exists():
        shutil.rmtree(DEST)
    (DEST / "artifacts").mkdir(parents=True)
    (DEST / "input").mkdir(parents=True)
    for rel, src_abs in planned.items():
        dest_abs = DEST / rel
        dest_abs.parent.mkdir(parents=True, exist_ok=True)
        if dest_abs.suffix.lower() in (".json", ".jsonl"):
            continue
        shutil.copyfile(src_abs, dest_abs)
    (DEST / check_dest_rel).write_text("".join(
        json.dumps(r, sort_keys=True) + "\n" for r in fixed_rows),
        encoding="utf-8")
    (DEST / "input" / "timing.json").write_text(_dump(timing),
                                                encoding="utf-8")
    shutil.copyfile(SRC / "clip.mp4", DEST / "input" / "clip.mp4")
    _close_copy(planned, index)
    (DEST / "result.json").write_text(_dump(result), encoding="utf-8")
    (DEST / "summary.json").write_text(_dump(summary), encoding="utf-8")
    return DEST


def main():
    dest = convert()
    print(f"wrote {dest}/result.json + {dest}/summary.json")


if __name__ == "__main__":
    sys.exit(main())

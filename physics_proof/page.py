"""M10. Frozen-player build: an analysis directory becomes a static page.

``build_page`` reads ``<run_dir>/analysis.json`` (+ ``summary.json`` and the
workspace), recomputes every verdict and overall with the current
``blocks.decide`` and ``schema.combine``, prepares chart/overlay data the
page needs, and writes ``<out>/index.html`` (frozen ``player/`` template
with the JSON embedded) plus ``clip.mp4``, small images and ``meta.json``.
``build_gallery`` turns every built page under ``site/`` into an index.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from PIL import Image

from physics_proof import blocks
from physics_proof.schema import combine, validate
from physics_proof.video import read_frames as _read_frames

__all__ = [
    "DEFAULT_TEXTS",
    "PLAYER_FILES",
    "build_gallery",
    "build_page",
    "flight_chart",
    "headline_and_color",
    "merge_texts",
    "overlay_for_flight",
    "parse_step",
    "prepare_page",
    "recompute_analysis",
    "step_urls",
    "template_hash",
]

#: Frozen template files; build copies them unchanged beside index.html.
PLAYER_FILES = ("index.html", "player.js", "player.css")

#: Hard budget from the M10 probes: the page without the video stays small.
PAGE_BYTES_BUDGET = 1_000_000

#: Every static string on the page, overridable from ``page_texts``.
DEFAULT_TEXTS: dict[str, str] = {
    "app.title": "physics-proof",
    "app.kicker": "video in, proof out",
    "header.measured": "measured g",
    "controls.play": "Play",
    "controls.pause": "Pause",
    "controls.step_back": "-1 frame",
    "controls.step_fwd": "+1 frame",
    "controls.prev_step": "Previous step",
    "controls.next_step": "Next step",
    "controls.step_label": "Steps",
    "steps.firstlook.title": "First look",
    "steps.firstlook.body": "What the agent saw before measuring anything.",
    "steps.reference.title": "Reference",
    "steps.reference.body": "Known sizes the scale rests on.",
    "steps.reference.mask_check": "Mask check",
    "steps.reference.sheet": "Mask-check sheet",
    "steps.scale.title": "Scale",
    "steps.scale.body": "Metres per pixel on the reference frame.",
    "steps.scale.second": "Independent cross-check",
    "steps.scale.agree": "agree",
    "steps.motion.title": "Motion",
    "steps.motion.body": "The tracked point, the fitted curve and the ghost.",
    "steps.clock.title": "Clock",
    "steps.clock.body": "Is the clip running at normal speed?",
    "steps.errors.title": "Error budget",
    "steps.errors.body": "Where the uncertainty comes from.",
    "steps.verdict.title": "Verdict",
    "steps.verdict.body": "Measured gravity against every hypothesis.",
    "steps.howmade.title": "How this was made",
    "steps.howmade.body": "Every number above comes from code the agent ran.",
    "steps.howmade.runlog": "Run log",
    "motion.takeoff": "Takeoff",
    "motion.apex": "Apex",
    "motion.end": "End",
    "motion.measured": "measured",
    "motion.fit": "fit",
    "motion.ghost": "ghost (gravity's path)",
    "motion.height_axis": "height (m)",
    "motion.time_axis": "time (s)",
    "motion.legend_noghost": "no ghost recorded",
    "clock.method": "Method",
    "clock.reading": "Reading",
    "clock.natural": "Natural range",
    "clock.implies": "At the measured pace this implies",
    "errors.term": "Source",
    "errors.share": "Relative error",
    "verdict.measured": "measured",
    "verdict.axis_note": "downward acceleration (m/s^2)",
    "howmade.model": "Model",
    "howmade.turns": "Turns",
    "howmade.sam": "SAM calls / frames",
    "howmade.searches": "Searches",
    "howmade.maskchecks": "Mask checks",
    "howmade.cost": "Cost (USD)",
    "howmade.wall": "Wall time",
    "notice.no_timescale": "No clock check was recorded for this clip.",
    "notice.no_ghost": "No ghost trajectory was recorded for this segment.",
    "notice.no_px": "No pixel positions were recorded for this track, "
    "so it cannot be drawn on the video; the chart shows it in metres.",
    "notice.no_refcurves": "Curves are in reference units and cannot be "
    "drawn on the video without pixel positions.",
    "notice.no_sheet": "No mask-check sheet image was saved for this reference.",
    "notice.no_flight_points": "No tracked points fall inside this segment.",
    "notice.no_summary": "No run summary was found; provenance is unavailable.",
    "gallery.title": "physics-proof gallery",
    "gallery.subtitle": "One page per analysed clip.",
    "gallery.cost": "cost",
    "gallery.open": "Open the proof",
}


def merge_texts(page_texts: Any) -> dict[str, str]:
    """Defaults overridden by the analysis ``page_texts`` (unknown keys kept)."""
    merged = dict(DEFAULT_TEXTS)
    if isinstance(page_texts, dict):
        for key, value in page_texts.items():
            if isinstance(value, str):
                merged[str(key)] = value
    return merged


def _k_sigma_of(stored: Any) -> float:
    """Stored k_sigma threshold, falling back to 2.0 when unusable."""
    if isinstance(stored, dict) and isinstance(stored.get("k_sigma"), (int, float)):
        value = float(stored["k_sigma"])
        if value > 0:
            return value
    return 2.0


def recompute_analysis(analysis: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Recompute flight decides, the verdict and overall; report changes.

    Returns the updated deep copy plus one line per changed field, e.g.
    ``/overall/label: 'none_fits' -> 'impossible'``.
    """
    import copy

    updated = copy.deepcopy(analysis)
    changes: list[str] = []

    def _set(path: str, holder: dict[str, Any], key: str, value: Any) -> None:
        if holder.get(key) != value:
            changes.append(path + "/" + key + ": " + repr(holder.get(key))
                            + " -> " + repr(value))
            holder[key] = value

    for i, flight in enumerate(updated.get("flights") or []):
        hypo = flight.get("hypothesis") or {}
        name, val = hypo.get("name"), hypo.get("value")
        if not isinstance(name, str) or not isinstance(val, (int, float)):
            continue
        fresh = blocks.decide(flight["accel"], flight["accel_err"],
                              {name: float(val)}, k_sigma=_k_sigma_of(flight.get("decide")))
        decide = flight.setdefault("decide", {})
        base = "/flights/" + str(i) + "/decide"
        for key in ("state", "world", "consistent", "sigmas", "nearest", "k", "text"):
            _set(base, decide, key, fresh[key])
    verdict = updated.get("verdict")
    if isinstance(verdict, dict) and isinstance(verdict.get("worlds"), dict):
        fresh = blocks.decide(verdict["g"], verdict["g_err"],
                              {k: float(v) for k, v in verdict["worlds"].items()},
                              k_sigma=_k_sigma_of(verdict))
        for key in ("state", "world", "consistent", "sigmas", "nearest", "k", "text"):
            _set("/verdict", verdict, key, fresh[key])
        overall = updated.get("overall")
        if isinstance(overall, dict):
            fresh_overall = combine(verdict, updated.get("timescale"))
            _set("/overall", overall, "label", fresh_overall["label"])
            _set("/overall", overall, "text", fresh_overall["text"])
    return updated, changes


def headline_and_color(overall: dict[str, Any],
                       verdict: dict[str, Any]) -> tuple[str, str]:
    """Plain-words header and colour for an overall verdict.

    Colours: a fitting world is green, a retimed clip amber, an
    impossible motion red, anything else grey.
    """
    label = str(overall.get("label", ""))
    raw_k = verdict.get("k")
    pace = float(raw_k) if isinstance(raw_k, (int, float)) else 0.0
    if label == "impossible":
        return "Physically impossible", "red"
    if label == "retimed":
        if pace >= 1:
            return "Slowed down ×" + f"{pace:.2f}", "amber"
        if pace > 0:
            return "Sped up ×" + f"{1.0 / pace:.2f}", "amber"
        return "Retimed", "amber"
    if label in ("none_fits", "undetermined"):
        if label == "none_fits" and pace >= 1.01:
            return "No world fits", "grey"
        return "Undetermined" if label == "undetermined" else "No world fits", "grey"
    if label:
        return label + " gravity", "green"
    return "Undetermined", "grey"


def _unit_scale(analysis: dict[str, Any]) -> tuple[float, str]:
    """Metres per track unit and the track unit (``px`` or ``ref``)."""
    scale = analysis["scale"]
    if scale.get("frame_of_reference") == "image":
        return float(scale["m_per_px"]), "px"
    return float(scale["m_per_ref"]), "ref"


def _window_points(analysis: dict[str, Any],
                   flight: dict[str, Any]) -> list[dict[str, Any]]:
    """Track points inside the fit window (falling back to start..end)."""
    window = (flight.get("fit") or {}).get("window") or {}
    first = window.get("first", flight.get("start"))
    last = window.get("last", flight.get("end"))
    return [p for p in (analysis.get("track") or {}).get("points", [])
            if isinstance(p, dict) and first <= p.get("frame", -1) <= last]


def flight_chart(analysis: dict[str, Any],
                 flight: dict[str, Any]) -> dict[str, Any]:
    """Height series in metres for one flight: measured, fit and ghost.

    Returns ``{"notice": ...}`` with a texts key when no tracked points
    fall inside the segment; the ghost series holds None where the
    analysis recorded no ghost point.
    """
    fps = float(analysis["clip"]["fps"])
    m_per, _ = _unit_scale(analysis)
    points = _window_points(analysis, flight)
    if not points:
        return {"notice": "notice.no_flight_points"}
    frames = [int(p["frame"]) for p in points]
    raw = [float(p["y"]) for p in points]
    times = [(f - frames[0]) / fps for f in frames]
    fit = flight.get("fit") or {}
    ave = fit.get("a")
    vel = fit.get("v0")
    fitted = list(raw)
    convention = "none"
    if isinstance(ave, (int, float)) and isinstance(vel, (int, float)):
        # Stored a is the acceleration itself (accel == a * m_per in every
        # real run). Stored v0 is either the velocity at the clip start
        # (blocks.fit_parabola convention) or at the window start; both
        # use the same curve shape, so fit each and keep the one that
        # matches the measured points.
        absolute = [f / fps for f in frames]
        rel = [(f - frames[0]) / fps for f in frames]
        best: list[float] | None = None
        best_rms = float("inf")
        for name, times in (("absolute", absolute), ("relative", rel)):
            base = sum(y - ave * t * t / 2.0 - vel * t
                       for y, t in zip(raw, times)) / len(raw)
            cand = [ave * t * t / 2.0 + vel * t + base for t in times]
            rms = sum((y - c) ** 2 for y, c in zip(raw, cand)) / len(raw)
            if rms < best_rms:
                best, best_rms, convention = cand, rms, name
        assert best is not None
        fitted = best
    ghosts = {int(g["frame"]): float(g["y"])
              for g in (flight.get("ghost") or []) if isinstance(g, dict)}
    zero = raw[0]
    return {
        "t": times,
        "h": [(zero - y) * m_per for y in raw],
        "h_fit": [(zero - y) * m_per for y in fitted],
        "h_ghost": [((zero - ghosts[f]) * m_per if f in ghosts else None)
                    for f in frames],
        "ghost_missing": all(f not in ghosts for f in frames),
        "rise_m": flight.get("rise_m"),
        "v0_convention": convention,
    }


def overlay_for_flight(analysis: dict[str, Any],
                       flight: dict[str, Any]) -> dict[str, Any]:
    """Video-pixel polylines for one flight, or a one-line notice.

    ``px`` tracks draw directly; ``ref`` tracks draw from each point's
    optional ``px`` and note when curves cannot be converted.
    """
    unit = (analysis.get("track") or {}).get("unit", "px")
    points = _window_points(analysis, flight)
    if not points:
        return {"notice": "notice.no_flight_points"}
    if unit == "ref" and not all(isinstance(p.get("px"), list) for p in points):
        return {"notice": "notice.no_px"}
    track_px = [p["px"] if unit == "ref" else [p["x"], p["y"]] for p in points]
    frames = [int(p["frame"]) for p in points]
    chart = flight_chart(analysis, flight)
    out: dict[str, Any] = {"frames": frames, "track": track_px,
                           "fit": None, "ghost": None, "curves_notice": None}
    if "notice" in chart:
        return out
    if unit == "ref":
        out["curves_notice"] = "notice.no_refcurves"
        return out
    zero = float(points[0]["y"])
    raw_fit = [zero - h / _unit_scale(analysis)[0] for h in chart["h_fit"]]
    out["fit"] = [[float(p[0]), float(y)] for p, y in zip(track_px, raw_fit)]
    ghosts = {int(g["frame"]): float(g["y"])
              for g in (flight.get("ghost") or []) if isinstance(g, dict)}
    if ghosts:
        out["ghost"] = [[float(p[0]), float(ghosts[f])]
                        for p, f in zip(track_px, frames) if f in ghosts]
    return out


def sheet_candidates(workspace: Path, mask_file: str,
                     obj: str) -> list[Path]:
    """Mask-check sheet images matching one reference mask, if any."""
    stem = Path(mask_file).name
    if stem.endswith(".npz"):
        stem = stem[:-4]
    return sorted((workspace / "mask_checks").glob(stem + "." + str(obj) + ".*.png"))


def _save_small(src: Path, dst: Path, bound: int) -> None:
    """Copy an image downscaled so its longest side fits ``bound`` px."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = img.convert("RGB")
        img.thumbnail((bound, bound))
        img.save(dst, "JPEG", quality=70)


def parse_step(query: str, n_steps: int) -> dict[str, int | None]:
    """Parse a page query string; mirrors the ``step`` logic in player.js.

    Returns ``{"step": int|None, "frame": int|None}`` with the step
    clamped to ``[0, n_steps)`` and negative frames dropped.
    """
    args = parse_qs(query.lstrip("?"), keep_blank_values=True)
    step: int | None = None
    frame: int | None = None
    try:
        if "step" in args:
            step = max(0, min(n_steps - 1, int(args["step"][0])))
    except (ValueError, TypeError):
        step = None
    try:
        if "frame" in args:
            raw = int(args["frame"][0])
            frame = raw if raw >= 0 else None
    except (ValueError, TypeError):
        frame = None
    return {"step": step, "frame": frame}


def step_urls(base: str, n_steps: int) -> list[str]:
    """One screenshot URL per step; the screens script consumes this."""
    clean = base.rstrip("/")
    return [clean + "?step=" + str(i) for i in range(max(0, n_steps))]


def prepare_page(analysis: dict[str, Any], summary: dict[str, Any],
                 run_tag: str) -> dict[str, Any]:
    """All page-specific data: texts, steps, charts, overlays, provenance."""
    texts = merge_texts(analysis.get("page_texts"))
    headline, color = headline_and_color(analysis["overall"], analysis["verdict"])
    if isinstance(analysis.get("page_texts"), dict) \
            and isinstance(analysis["page_texts"].get("header.verdict"), str):
        headline = analysis["page_texts"]["header.verdict"]
    verdict = analysis["verdict"]
    key_number = (f"{verdict['g']:.2f}" + " ± " + f"{verdict['g_err']:.2f}" + " m/s²")
    flights = analysis.get("flights") or []
    scale = analysis.get("scale") or {}
    steps: list[dict[str, Any]] = [
        {"id": "first-look", "title": texts["steps.firstlook.title"],
         "frame": int(flights[0]["start"]) if flights else 0},
        {"id": "reference", "title": texts["steps.reference.title"],
         "frame": int(scale.get("frame", 0))},
        {"id": "scale", "title": texts["steps.scale.title"],
         "frame": int(scale.get("frame", 0))},
    ]
    for i, flight in enumerate(flights):
        kind = "wall" if flight.get("kind") == "wall" else "flight"
        steps.append({"id": "motion-" + str(i), "flight": i,
                      "title": texts["steps.motion.title"] + " " + str(i + 1)
                      + " · " + kind,
                      "frame": int(flight["start"])})
    last_end = int(flights[-1]["end"]) if flights else 0
    steps += [
        {"id": "clock", "title": texts["steps.clock.title"], "frame": last_end},
        {"id": "errors", "title": texts["steps.errors.title"], "frame": last_end},
        {"id": "verdict", "title": texts["steps.verdict.title"], "frame": last_end},
        {"id": "howmade", "title": texts["steps.howmade.title"], "frame": 0},
    ]
    timescale = analysis.get("timescale")
    prepared_flights = []
    for flight in flights:
        chart = flight_chart(analysis, flight)
        overlay = overlay_for_flight(analysis, flight)
        ghost = flight.get("ghost") or []
        prepared_flights.append({
            "kind": flight.get("kind"), "start": flight.get("start"),
            "apex": flight.get("apex"), "end": flight.get("end"),
            "rise_m": flight.get("rise_m"),
            "duration_s": flight.get("duration_s"),
            "accel": flight.get("accel"), "accel_err": flight.get("accel_err"),
            "hypothesis": flight.get("hypothesis"), "notes": flight.get("notes"),
            "chart": chart, "overlay": overlay,
            "ghost_missing": not ghost or chart.get("ghost_missing", False),
        })
    return {
        "texts": texts,
        "headline": headline,
        "color": color,
        "key_number": key_number,
        "steps": steps,
        "flights": prepared_flights,
        "has_timescale": isinstance(timescale, dict),
        "howmade": {
            "model": summary.get("model", ""),
            "turns": summary.get("turns", 0),
            "sam_calls": summary.get("sam_calls", 0),
            "sam_frames": summary.get("sam_frames", 0),
            "searches": summary.get("searches", 0),
            "mask_checks": summary.get("mask_checks", 0),
            "cost_usd": summary.get("cost_usd", 0.0),
            "wall_s": summary.get("wall_s", 0.0),
        },
        "run_tag": run_tag,
    }


def template_hash(player_dir: Path) -> str:
    """sha256 hex over the frozen template files, in file-name order."""
    digest = hashlib.sha256()
    for name in PLAYER_FILES:
        digest.update(Path(player_dir, name).read_bytes())
    return digest.hexdigest()


def build_page(run_dir: str | Path, out_dir: str | Path | None = None,
               player_dir: str | Path | None = None) -> dict[str, Any]:
    """Build one static page; print verdict changes and return build info."""
    run_path = Path(run_dir)
    tag = run_path.name
    out = Path(out_dir) if out_dir else Path("site") / tag
    player = Path(player_dir) if player_dir else Path("player")
    analysis = json.loads((run_path / "analysis.json").read_text(encoding="utf-8"))
    summary_path = run_path / "summary.json"
    summary: dict[str, Any] = json.loads(summary_path.read_text(encoding="utf-8")) \
        if summary_path.exists() else {}
    analysis, changes = recompute_analysis(analysis)
    for line in changes:
        print("recompute: " + line, flush=True)
    issues = validate(analysis)
    if issues:
        raise RuntimeError("recomputed analysis does not validate: "
                           + "; ".join(i.path + " " + i.message for i in issues))
    page = prepare_page(analysis, summary, tag)
    log = run_path / "conversation.jsonl"
    if summary and log.exists():
        page["howmade"]["runlog_href"] = os.path.relpath(log.resolve(), out.resolve())
    workspace = run_path / "workspace"
    img_dir = out / "img"
    sheets: list[dict[str, Any]] = []
    for ref in analysis.get("reference") or []:
        mask = (ref.get("mask") or {})
        found = sheet_candidates(workspace, str(mask.get("file", "")),
                                 str(mask.get("object", "")))
        if found:
            dst = img_dir / (found[0].stem + ".jpg")
            _save_small(found[0], dst, 960)
            sheets.append({"name": ref.get("name", ""),
                           "sheet": "img/" + dst.name})
        else:
            sheets.append({"name": ref.get("name", ""), "sheet": None})
    page["sheets"] = sheets
    clip_src = workspace / "clip.mp4" if (workspace / "clip.mp4").exists() \
        else run_path / "clip.mp4"
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(clip_src, out / "clip.mp4")
    apex_frame = 0
    if analysis.get("flights"):
        first = analysis["flights"][0]
        apex_frame = first.get("apex") or first.get("start", 0)
    n_frames = int(analysis["clip"]["frames"])
    poster_frame = max(0, min(n_frames - 1, int(apex_frame)))
    frame = _read_frames(clip_src, [poster_frame])[poster_frame]
    _save_small_image(frame, img_dir / "poster.jpg", 480)
    page["images"] = {"poster": "img/poster.jpg"}
    payload = json.dumps(analysis, separators=(",", ":")).replace("</", "<\\/")
    data = json.dumps(page, separators=(",", ":")).replace("</", "<\\/")
    template = (player / "index.html").read_text(encoding="utf-8")
    html = template.replace("__ANALYSIS__", payload).replace("__PAGEDATA__", data)
    (out / "index.html").write_text(html, encoding="utf-8")
    for name in ("player.js", "player.css"):
        shutil.copyfile(player / name, out / name)
    meta = {"slug": out.name, "run": tag, "headline": page["headline"],
            "color": page["color"], "overall_text": analysis["overall"]["text"],
            "cost_usd": page["howmade"]["cost_usd"], "poster": "img/poster.jpg"}
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    page_bytes = (out / "index.html").stat().st_size
    print("built " + str(out) + " page=" + str(page_bytes) + "B "
          + "poster+images=" + str(sum(p.stat().st_size for p in img_dir.glob("*")))
          + "B", flush=True)
    if page_bytes > PAGE_BYTES_BUDGET:
        raise RuntimeError("page exceeds 1 MB without video: " + str(page_bytes))
    return {"out": str(out), "changes": changes, "meta": meta,
            "page_bytes": page_bytes}


def _save_small_image(frame: Any, dst: Path, bound: int) -> None:
    """Save one RGB frame as a small JPEG poster."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(frame)
    img.thumbnail((bound, bound))
    img.save(dst, "JPEG", quality=70)


def build_gallery(site_dir: str | Path = "site") -> dict[str, Any]:
    """Regenerate the gallery index from every built page's meta.json."""
    site = Path(site_dir)
    cards = []
    for meta_path in sorted(site.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        cards.append(meta)
    t = DEFAULT_TEXTS
    items = []
    for meta in cards:
        items.append(
            "<article class=\"card " + meta.get("color", "grey") + "\">"
            + "<a href=\"" + meta["slug"] + "/\">"
            + "<img src=\"" + meta["slug"] + "/" + meta.get("poster", "") + "\""
            + " alt=\"poster frame\" loading=\"lazy\">"
            + "<h2>" + _escape(meta.get("headline", "")) + "</h2>"
            + "<p>" + _escape(meta.get("overall_text", "")) + "</p>"
            + "<p class=\"cost\">" + t["gallery.cost"] + ": $"
            + f"{float(meta.get('cost_usd', 0.0)):.2f}" + "</p>"
            + "<p class=\"open\">" + t["gallery.open"] + " →</p>"
            + "</a></article>")
    html = ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>" + t["gallery.title"] + "</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:60rem;"
            "margin:2rem auto;padding:0 1rem;line-height:1.5}"
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));"
            "gap:1.5rem}img{width:100%;border-radius:.5rem}"
            ".green h2{color:#1a7f37}.amber h2{color:#9a6700}"
            ".red h2{color:#b42318}.grey h2{color:#57606a}"
            "a{color:inherit;text-decoration:none}</style></head><body>"
            "<h1>" + t["gallery.title"] + "</h1>"
            "<p>" + t["gallery.subtitle"] + "</p>"
            "<div class=\"grid\">" + "".join(items) + "</div></body></html>")
    (site / "index.html").write_text(html, encoding="utf-8")
    print("gallery: " + str(len(cards)) + " cards -> " + str(site / "index.html"),
          flush=True)
    return {"cards": len(cards), "slugs": [c["slug"] for c in cards]}


def _escape(text: str) -> str:
    """Minimal HTML escaping for gallery strings."""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

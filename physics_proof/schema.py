"""M9. Analysis schema and validator: the contract between Spark and the page.

`config/analysis.schema.json` (draft 2020-12) is the source of truth for
field names and required fields; this module enforces them plus the
internal-consistency rules from `tasks/M9.md`: frames inside the clip,
positive errors, `duration_s` and `rise_m` matching the track and scale,
every `decide` dict recomputed with `blocks.decide`, and `overall`
recomputed with `combine`. Unknown fields are allowed and ignored.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from physics_proof import blocks

__all__ = ["Issue", "combine", "validate", "schema_doc", "load_schema"]

#: Source of truth for field names and required fields.
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "config" / "analysis.schema.json"

_K_TOL = 1e-6
_RISE_REL_TOL = 0.02
_RISE_ABS_TOL = 0.02


@dataclass(frozen=True)
class Issue:
    """One validation problem; `path` is a JSON-pointer-like location."""

    path: str
    message: str


def load_schema() -> dict[str, Any]:
    """Load the analysis JSON Schema file."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _ptr(base: str, key: Any) -> str:
    """Append one key to a JSON-pointer-like path."""
    text = str(key).replace("~", "~0").replace("/", "~1")
    return base + "/" + text if base else "/" + text


def _is_int(value: Any) -> bool:
    """True for a real int (never a bool)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_num(value: Any) -> bool:
    """True for a finite int or float (never a bool)."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _need(obj: Any, path: str, key: str, issues: list[Issue]) -> bool:
    """Record an issue when a required key is missing; return presence."""
    if not isinstance(obj, dict) or key not in obj:
        issues.append(Issue(_ptr(path, key), "missing required field " + _ptr(path, key)))
        return False
    return True


def _req_str(obj: Any, path: str, key: str, issues: list[Issue]) -> str | None:
    """Required string field; issues on missing or wrong type."""
    if not _need(obj, path, key, issues):
        return None
    value = obj[key]
    if not isinstance(value, str):
        issues.append(Issue(_ptr(path, key), "expected a string"))
        return None
    return value


def _req_num(obj: Any, path: str, key: str, issues: list[Issue]) -> float | None:
    """Required finite-number field; issues on missing or wrong type."""
    if not _need(obj, path, key, issues):
        return None
    value = obj[key]
    if not _is_num(value):
        issues.append(Issue(_ptr(path, key), "expected a finite number"))
        return None
    return float(value)


def _req_int(obj: Any, path: str, key: str, issues: list[Issue]) -> int | None:
    """Required integer field; issues on missing or wrong type."""
    if not _need(obj, path, key, issues):
        return None
    value = obj[key]
    if not _is_int(value):
        issues.append(Issue(_ptr(path, key), "expected an integer"))
        return None
    return int(value)


def _req_list(obj: Any, path: str, key: str, issues: list[Issue]) -> list[Any] | None:
    """Required list field; issues on missing or wrong type."""
    if not _need(obj, path, key, issues):
        return None
    value = obj[key]
    if not isinstance(value, list):
        issues.append(Issue(_ptr(path, key), "expected an array"))
        return None
    return value


def _req_dict(obj: Any, path: str, key: str, issues: list[Issue]) -> dict[str, Any] | None:
    """Required object field; issues on missing or wrong type."""
    if not _need(obj, path, key, issues):
        return None
    value = obj[key]
    if not isinstance(value, dict):
        issues.append(Issue(_ptr(path, key), "expected an object"))
        return None
    return value


def _check_pos(value: float | None, path: str, key: str, issues: list[Issue]) -> None:
    """Error-like values must be strictly positive."""
    if value is not None and value <= 0:
        issues.append(Issue(_ptr(path, key), "must be > 0"))


def _check_frame(value: int | None, path: str, key: str, n_frames: int, issues: list[Issue]) -> None:
    """Frame indices must lie inside the clip."""
    if value is not None and not 0 <= value < n_frames:
        issues.append(
            Issue(_ptr(path, key), "frame " + str(value) + " is outside the clip")
        )


def _k_error(g: float, g_err: float, k: float | None) -> float | None:
    """Error of k = sqrt(world / g) propagated from g_err; None when k is None."""
    if k is None or g <= 0 or g_err <= 0:
        return None
    return abs(k) * g_err / (2.0 * g)


def _retime_consistent(timescale: Any, verdict: dict[str, Any]) -> bool:
    """True when a slow/fast timescale agrees with decide's k within its error."""
    if not isinstance(timescale, dict):
        return False
    mark = timescale.get("verdict")
    if mark not in ("slow", "fast"):
        return False
    k = verdict.get("k")
    if not _is_num(k) or k <= 0 or k == 1:
        return False
    if mark == "slow" and not k > 1:
        return False
    if mark == "fast" and not k < 1:
        return False
    span = timescale.get("expected_range")
    value = timescale.get("value")
    if (
        not isinstance(span, list)
        or len(span) != 2
        or not all(_is_num(v) for v in span)
        or not _is_num(value)
        or value == 0
    ):
        return False
    lo, hi = min(float(span[0]), float(span[1])), max(float(span[0]), float(span[1]))
    observed_lo, observed_hi = lo / float(value), hi / float(value)
    g, g_err = verdict.get("g"), verdict.get("g_err")
    if _is_num(g) and float(g) > 0 and _is_num(g_err) and float(g_err) > 0:
        half = _k_error(float(g), float(g_err), float(k)) or 0.0
    else:
        half = 0.0
    return observed_lo <= float(k) + half + 1e-9 and float(k) - half - 1e-9 <= observed_hi


def _clock_numbers(timescale: Any) -> tuple[float, float, float, float, str] | None:
    """Numeric clock reading (value, err, lo, hi, unit); None when unusable.

    Returns None when the timescale section is missing, not an object, or its
    numbers are missing, non-finite, or meaningless (non-positive value or
    error, or a malformed expected_range), in which case combine falls back
    to the agent's own verdict reading as before.
    """
    if not isinstance(timescale, dict):
        return None
    value = timescale.get("value")
    err = timescale.get("err")
    span = timescale.get("expected_range")
    if not _is_num(value) or not _is_num(err):
        return None
    if float(value) <= 0 or float(err) <= 0:
        return None
    if not isinstance(span, list) or len(span) != 2:
        return None
    if not all(_is_num(v) for v in span):
        return None
    lo, hi = min(float(span[0]), float(span[1])), max(float(span[0]), float(span[1]))
    unit = timescale.get("unit")
    unit_text = unit if isinstance(unit, str) and unit else ""
    return float(value), float(err), lo, hi, unit_text


def combine(verdict: dict[str, Any], timescale: Any) -> dict[str, str]:
    """Overall page verdict from a decide dict and the timescale section.

    For none_fits with a numeric timescale the retime explanation is tested
    against the clock (SPEC section 4 rule 8): at true speed the clock would
    run at value x k with error err x k. Inside the natural range within
    2 sigma gives retimed, outside gives impossible; a clock error whose
    2-sigma band reaches zero carries no usable rate and keeps none_fits.
    The timescale verdict stays the agent's own reading; only the
    numbers decide here.
    """
    state = verdict.get("state") if isinstance(verdict, dict) else None
    k = verdict.get("k") if isinstance(verdict, dict) else None
    if isinstance(state, str) and state.startswith("fits:"):
        world = state.split(":", 1)[1] or verdict.get("world") or "?"
        return {
            "label": str(world),
            "text": "The motion fits " + str(world) + " within the measured error.",
        }
    if state == "undetermined":
        return {
            "label": "undetermined",
            "text": "The motion is consistent with more than one world, "
            "so no single verdict is possible.",
        }
    k_num = float(k) if (_is_num(k) and float(k) > 0) else None
    clock = _clock_numbers(timescale)
    if state == "none_fits" and k_num is not None and clock is not None:
        value, err, lo, hi, unit = clock
        true = value * k_num
        true_err = err * k_num
        with_unit = " " + unit if unit else ""
        band = "[" + f"{lo:g}" + "-" + f"{hi:g}" + "]" + with_unit
        if k_num >= 1:
            pace = "slowed by ×" + f"{k_num:.2f}"
        else:
            pace = "sped up by ×" + f"{1.0 / k_num:.2f}"
        lo_band, hi_band = true - 2.0 * true_err, true + 2.0 * true_err
        if lo_band <= 0:
            if k_num >= 1:
                pace_today = "running slow by a factor of " + f"{k_num:.2f}"
            else:
                pace_today = "running fast by a factor of " + f"{1.0 / k_num:.2f}"
            return {
                "label": "none_fits",
                "text": "The motion fits no listed world; the clip would have to be "
                + pace_today + ".",
            }
        if lo_band <= hi and hi_band >= lo:
            return {
                "label": "retimed",
                "text": "Consistent with a clip " + pace + ": the clock would then run at "
                + f"{true:.2f}" + " ± " + f"{true_err:.2f}" + with_unit
                + ", which is natural (" + band + ").",
            }
        else:
            return {
                "label": "impossible",
                "text": "No playback speed explains it: " + pace + " the clock would run at "
                + f"{true:.2f}" + " ± " + f"{true_err:.2f}" + with_unit
                + ", outside the natural range " + band + ".",
            }
    mark = timescale.get("verdict") if isinstance(timescale, dict) else None
    if mark == "normal":
        return {
            "label": "impossible",
            "text": "The motion ignores gravity at normal speed "
            "and is physically impossible.",
        }
    if mark in ("slow", "fast") and isinstance(verdict, dict) and _retime_consistent(
        timescale, verdict
    ):
        if k is not None and float(k) >= 1:
            paced = "slowed down by a factor of " + f"{float(k):.2f}"
        else:
            paced = "sped up by a factor of " + f"{1.0 / float(k):.2f}"
        return {"label": "retimed", "text": "The motion was " + paced + "."}
    if _is_num(k) and float(k) > 0:
        if float(k) >= 1:
            pace = "running slow by a factor of " + f"{float(k):.2f}"
        else:
            pace = "running fast by a factor of " + f"{1.0 / float(k):.2f}"
        return {
            "label": "none_fits",
            "text": "The motion fits no listed world; the clip would have to be " + pace + ".",
        }
    return {
        "label": "none_fits",
        "text": "The motion fits no listed world, and no playback speed explains it.",
    }


def _check_decide_match(
    stored: Any,
    g: float | None,
    g_err: float | None,
    worlds: dict[str, float] | None,
    path: str,
    issues: list[Issue],
) -> None:
    """Recompute a decide dict with blocks.decide and compare state/consistent/k."""
    if not isinstance(stored, dict):
        issues.append(Issue(path, "expected a decide object"))
        return
    for key in ("state", "world", "consistent", "sigmas", "nearest", "k", "text", "g", "g_err"):
        _need(stored, path, key, issues)
    if g is None or g_err is None or worlds is None:
        return
    k_sigma = stored.get("k_sigma", 2.0)
    if not _is_num(k_sigma) or float(k_sigma) <= 0:
        k_sigma = 2.0
    try:
        expected = blocks.decide(g, g_err, worlds, k_sigma=float(k_sigma))
    except ValueError as exc:
        issues.append(Issue(path, "cannot recompute decide: " + str(exc)))
        return
    if stored.get("state") != expected["state"]:
        issues.append(
            Issue(
                _ptr(path, "state"),
                "state " + repr(stored.get("state")) + " does not match "
                "blocks.decide (" + repr(expected["state"]) + ")",
            )
        )
    got_consistent = stored.get("consistent")
    if not isinstance(got_consistent, list) or sorted(
        str(v) for v in got_consistent
    ) != sorted(expected["consistent"]):
        issues.append(
            Issue(
                _ptr(path, "consistent"),
                "consistent " + repr(got_consistent) + " does not match "
                "blocks.decide (" + repr(expected["consistent"]) + ")",
            )
        )
    got_k, want_k = stored.get("k"), expected["k"]
    if (got_k is None) != (want_k is None) or (
        got_k is not None
        and want_k is not None
        and (not _is_num(got_k) or abs(float(got_k) - want_k) > _K_TOL)
    ):
        issues.append(
            Issue(
                _ptr(path, "k"),
                "k " + repr(got_k) + " does not match blocks.decide (" + repr(want_k) + ")",
            )
        )


def _check_timescale(obj: Any, path: str, issues: list[Issue]) -> Any:
    """Validate the timescale section; return it when it is a usable object."""
    if obj is None:
        return None
    if not isinstance(obj, dict):
        issues.append(Issue(path, "expected an object or null"))
        return None
    _req_str(obj, path, "method", issues)
    _req_num(obj, path, "value", issues)
    err = _req_num(obj, path, "err", issues)
    _check_pos(err, path, "err", issues)
    _req_str(obj, path, "unit", issues)
    span = _req_list(obj, path, "expected_range", issues)
    if span is not None:
        if len(span) != 2 or not all(_is_num(v) for v in span):
            issues.append(Issue(_ptr(path, "expected_range"), "expected [lo, hi] numbers"))
        elif float(span[0]) > float(span[1]):
            issues.append(Issue(_ptr(path, "expected_range"), "expected lo <= hi"))
    mark = obj.get("verdict")
    if "verdict" not in obj:
        issues.append(Issue(_ptr(path, "verdict"), "missing required field " + _ptr(path, "verdict")))
    elif mark not in ("normal", "slow", "fast", "undetermined"):
        issues.append(Issue(_ptr(path, "verdict"), "expected normal|slow|fast|undetermined"))
    return obj


def validate(
    analysis: Any, *, clip_frames: int | None = None, fps: float | None = None
) -> list[Issue]:
    """Validate an analysis dict; return the list of issues (empty means valid)."""
    issues: list[Issue] = []
    if not isinstance(analysis, dict):
        return [Issue("", "expected an analysis object")]
    for key in (
        "type", "schema_version", "clip", "context", "first_look", "reference",
        "scale", "track", "masks", "flights", "timescale", "error_budget",
        "verdict", "overall",
    ):
        _need(analysis, "", key, issues)
    if "type" in analysis and analysis.get("type") != "world-g":
        issues.append(Issue("/type", "expected the constant world-g"))
    if "schema_version" in analysis and analysis.get("schema_version") != 1:
        issues.append(Issue("/schema_version", "expected the constant 1"))
    page_texts = analysis.get("page_texts")
    if page_texts is not None:
        if not isinstance(page_texts, dict):
            issues.append(Issue("/page_texts", "expected an object"))
        else:
            for key, value in page_texts.items():
                if not isinstance(value, str):
                    issues.append(Issue(_ptr("/page_texts", key), "expected a string"))

    clip = _req_dict(analysis, "", "clip", issues)
    clip_file = _req_str(clip, "/clip", "file", issues) if clip is not None else None
    clip_fps = _req_num(clip, "/clip", "fps", issues) if clip is not None else None
    clip_n = _req_int(clip, "/clip", "frames", issues) if clip is not None else None
    if clip is not None:
        width = _req_int(clip, "/clip", "width", issues)
        height = _req_int(clip, "/clip", "height", issues)
        dupes = _req_int(clip, "/clip", "duplicates_found", issues)
        _req_str(clip, "/clip", "notes", issues)
        if width is not None and width < 1:
            issues.append(Issue("/clip/width", "must be >= 1"))
        if height is not None and height < 1:
            issues.append(Issue("/clip/height", "must be >= 1"))
        if dupes is not None and dupes < 0:
            issues.append(Issue("/clip/duplicates_found", "must be >= 0"))
        if clip_fps is not None and clip_fps <= 0:
            issues.append(Issue("/clip/fps", "must be > 0"))
        if clip_n is not None and clip_n < 1:
            issues.append(Issue("/clip/frames", "must be >= 1"))
    del clip_file
    n_frames = clip_n if clip_frames is None else clip_frames
    fps_eff = clip_fps if fps is None else fps
    if clip_frames is not None and (not _is_int(clip_frames) or clip_frames < 1):
        issues.append(Issue("", "clip_frames override must be a positive integer"))
        n_frames = clip_n
    if fps is not None and (not _is_num(fps) or float(fps) <= 0):
        issues.append(Issue("", "fps override must be a positive number"))
        fps_eff = clip_fps
    if not _is_int(n_frames) or int(n_frames) < 1:
        n_frames = None
    else:
        n_frames = int(n_frames)
    if not _is_num(fps_eff) or float(fps_eff) <= 0:
        fps_eff = None
    else:
        fps_eff = float(fps_eff)

    context = _req_dict(analysis, "", "context", issues)
    if context is not None:
        _req_str(context, "/context", "scene", issues)
        _req_str(context, "/context", "claim", issues)
        expected = _req_list(context, "/context", "expected", issues)
        sources = _req_list(context, "/context", "sources", issues)
        if expected is not None:
            for i, item in enumerate(expected):
                base = _ptr("/context/expected", i)
                if not isinstance(item, dict):
                    issues.append(Issue(base, "expected an object"))
                    continue
                _req_str(item, base, "quantity", issues)
                _req_num(item, base, "value", issues)
                _req_str(item, base, "unit", issues)
                _req_str(item, base, "source", issues)
        if sources is not None:
            for i, source in enumerate(sources):
                if not isinstance(source, str):
                    issues.append(Issue(_ptr("/context/sources", i), "expected a string"))

    first = _req_dict(analysis, "", "first_look", issues)
    if first is not None:
        _req_str(first, "/first_look", "what", issues)
        _req_str(first, "/first_look", "where", issues)
        _req_str(first, "/first_look", "when", issues)
        _req_str(first, "/first_look", "source", issues)
        confidence = _req_num(first, "/first_look", "confidence", issues)
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            issues.append(Issue("/first_look/confidence", "must be between 0 and 1"))
        by_eye = _req_dict(first, "/first_look", "by_eye", issues)
        if by_eye is not None:
            _req_str(by_eye, "/first_look/by_eye", "quantity", issues)
            _req_num(by_eye, "/first_look/by_eye", "value", issues)
            _req_str(by_eye, "/first_look/by_eye", "unit", issues)

    reference = _req_list(analysis, "", "reference", issues)
    if reference is not None:
        if len(reference) < 1:
            issues.append(Issue("/reference", "expected at least one reference"))
        for i, item in enumerate(reference):
            base = _ptr("/reference", i)
            if not isinstance(item, dict):
                issues.append(Issue(base, "expected an object"))
                continue
            _req_str(item, base, "name", issues)
            _req_str(item, base, "extent", issues)
            value_m = _req_num(item, base, "value_m", issues)
            tolerance_m = _req_num(item, base, "tolerance_m", issues)
            _check_pos(value_m, base, "value_m", issues)
            _check_pos(tolerance_m, base, "tolerance_m", issues)
            has_url = _need(item, base, "source_url", issues)
            has_quote = _need(item, base, "quote", issues)
            source_type = _req_str(item, base, "source_type", issues)
            if source_type is not None and source_type not in (
                "primary", "secondary", "estimate",
            ):
                issues.append(
                    Issue(_ptr(base, "source_type"), "expected primary|secondary|estimate")
                )
            url = item.get("source_url") if has_url else None
            quote = item.get("quote") if has_quote else None
            for key, val in (("source_url", url), ("quote", quote)):
                if val is not None and not isinstance(val, str):
                    issues.append(Issue(_ptr(base, key), "expected a string or null"))
            if source_type is not None and source_type != "estimate":
                if not isinstance(url, str) or not url:
                    issues.append(
                        Issue(_ptr(base, "source_url"), "required unless source_type is estimate")
                    )
                if not isinstance(quote, str) or not quote:
                    issues.append(
                        Issue(_ptr(base, "quote"), "required unless source_type is estimate")
                    )
            mask = _req_dict(item, base, "mask", issues)
            if mask is not None:
                _req_str(mask, _ptr(base, "mask"), "file", issues)
                _req_str(mask, _ptr(base, "mask"), "object", issues)
            check = _req_dict(item, base, "mask_check", issues)
            if check is not None:
                mark = check.get("verdict")
                if "verdict" not in check:
                    _need(check, _ptr(base, "mask_check"), "verdict", issues)
                elif mark not in (
                    "agrees", "covers_more", "covers_less", "different_object", "cannot_tell",
                ):
                    issues.append(
                        Issue(_ptr(_ptr(base, "mask_check"), "verdict"), "unknown mask-check verdict")
                    )
                _req_str(check, _ptr(base, "mask_check"), "covers", issues)

    scale = _req_dict(analysis, "", "scale", issues)
    m_per: float | None = None
    track_unit_want: str | None = None
    if scale is not None:
        frame = _req_int(scale, "/scale", "frame", issues)
        if frame is not None and n_frames is not None:
            _check_frame(frame, "/scale", "frame", n_frames, issues)
        extent_px = _req_num(scale, "/scale", "extent_px", issues)
        extent_px_err = _req_num(scale, "/scale", "extent_px_err", issues)
        _check_pos(extent_px, "/scale", "extent_px", issues)
        _check_pos(extent_px_err, "/scale", "extent_px_err", issues)
        has_for = _need(scale, "/scale", "frame_of_reference", issues)
        ref = scale.get("frame_of_reference") if has_for else None
        if has_for and ref == "image":
            track_unit_want = "px"
            m_per = _req_num(scale, "/scale", "m_per_px", issues)
            m_per_err = _req_num(scale, "/scale", "m_per_px_err", issues)
            _check_pos(m_per, "/scale", "m_per_px", issues)
            _check_pos(m_per_err, "/scale", "m_per_px_err", issues)
        elif has_for and isinstance(ref, dict):
            track_unit_want = "ref"
            _req_str(ref, "/scale/frame_of_reference", "object", issues)
            anchor = ref.get("anchor")
            if "anchor" not in ref:
                _need(ref, "/scale/frame_of_reference", "anchor", issues)
            elif anchor not in ("top", "bottom"):
                issues.append(
                    Issue("/scale/frame_of_reference/anchor", "expected top|bottom")
                )
            if "size_px_per_frame" not in ref:
                _need(ref, "/scale/frame_of_reference", "size_px_per_frame", issues)
            else:
                sizes = ref["size_px_per_frame"]
                flat = sizes if isinstance(sizes, list) else [sizes]
                if not flat or not all(_is_num(v) and float(v) > 0 for v in flat):
                    issues.append(
                        Issue(
                            "/scale/frame_of_reference/size_px_per_frame",
                            "expected a positive number or array of positives",
                        )
                    )
            m_per = _req_num(scale, "/scale", "m_per_ref", issues)
            m_per_err = _req_num(scale, "/scale", "m_per_ref_err", issues)
            _check_pos(m_per, "/scale", "m_per_ref", issues)
            _check_pos(m_per_err, "/scale", "m_per_ref_err", issues)
        elif has_for:
            issues.append(
                Issue("/scale/frame_of_reference", "expected image or an object")
            )
        has_second = _need(scale, "/scale", "second", issues)
        second = scale.get("second") if has_second else None
        if has_second and second is not None:
            if not isinstance(second, dict):
                issues.append(Issue("/scale/second", "expected an object or null"))
            else:
                _req_str(second, "/scale/second", "name", issues)
                second_m = _req_num(second, "/scale/second", "m_per_px", issues)
                second_err = _req_num(second, "/scale/second", "m_per_px_err", issues)
                _check_pos(second_m, "/scale/second", "m_per_px", issues)
                _check_pos(second_err, "/scale/second", "m_per_px_err", issues)
                agree = _req_num(second, "/scale/second", "agree_sigma", issues)
                if agree is not None and agree < 0:
                    issues.append(Issue("/scale/second/agree_sigma", "must be >= 0"))

    track = _req_dict(analysis, "", "track", issues)
    track_points: dict[int, tuple[float, float]] = {}
    if track is not None:
        _req_str(track, "/track", "what", issues)
        _req_str(track, "/track", "method", issues)
        unit = track.get("unit")
        if "unit" not in track:
            _need(track, "/track", "unit", issues)
        elif unit not in ("px", "ref"):
            issues.append(Issue("/track/unit", "expected px|ref"))
        if track_unit_want is not None and unit in ("px", "ref") and unit != track_unit_want:
            issues.append(
                Issue("/track/unit", "expected " + track_unit_want + " for this frame_of_reference")
            )
        points = _req_list(track, "/track", "points", issues)
        if points is not None:
            if len(points) < 2:
                issues.append(Issue("/track/points", "expected at least two points"))
            for i, point in enumerate(points):
                base = _ptr("/track/points", i)
                if not isinstance(point, dict):
                    issues.append(Issue(base, "expected an object"))
                    continue
                fr = _req_int(point, base, "frame", issues)
                x = _req_num(point, base, "x", issues)
                y = _req_num(point, base, "y", issues)
                if "px" in point:
                    here = point["px"]
                    if (
                        not isinstance(here, list)
                        or len(here) != 2
                        or not all(_is_num(v) for v in here)
                    ):
                        issues.append(Issue(_ptr(base, "px"), "expected [x, y] in px"))
                if fr is not None and n_frames is not None:
                    _check_frame(fr, base, "frame", n_frames, issues)
                if fr is not None and x is not None and y is not None and fr not in track_points:
                    track_points[fr] = (x, y)

    masks = _req_dict(analysis, "", "masks", issues)
    if masks is not None:
        if len(masks) < 1:
            issues.append(Issue("/masks", "expected at least one object"))
        for name, frames_map in masks.items():
            base = _ptr("/masks", name)
            if not isinstance(frames_map, dict):
                issues.append(Issue(base, "expected an object of frame to spans"))
                continue
            for frame_key, spans in frames_map.items():
                entry = _ptr(base, frame_key)
                try:
                    frame_no = int(str(frame_key))
                except ValueError:
                    issues.append(Issue(entry, "expected an integer frame key"))
                    continue
                if n_frames is not None and not 0 <= frame_no < n_frames:
                    issues.append(Issue(entry, "frame is outside the clip"))
                if not isinstance(spans, list) or not spans or any(
                    not isinstance(run, list)
                    or len(run) != 3
                    or not all(_is_int(v) for v in run)
                    or run[2] <= run[1]
                    for run in spans
                ):
                    issues.append(Issue(entry, "expected spans [[y, x0, x1], ...] with x1 > x0"))

    flights = _req_list(analysis, "", "flights", issues)
    if flights is not None:
        if len(flights) < 1:
            issues.append(Issue("/flights", "expected at least one flight"))
        for i, flight in enumerate(flights):
            base = _ptr("/flights", i)
            if not isinstance(flight, dict):
                issues.append(Issue(base, "expected an object"))
                continue
            kind = flight.get("kind")
            if "kind" not in flight:
                _need(flight, base, "kind", issues)
            elif kind not in ("flight", "wall"):
                issues.append(Issue(_ptr(base, "kind"), "expected flight|wall"))
            start = _req_int(flight, base, "start", issues)
            apex = None
            if _need(flight, base, "apex", issues):
                apex = flight["apex"]
                if apex is not None and not _is_int(apex):
                    issues.append(Issue(_ptr(base, "apex"), "expected an integer or null"))
                    apex = None
            end = _req_int(flight, base, "end", issues)
            if n_frames is not None:
                if start is not None:
                    _check_frame(start, base, "start", n_frames, issues)
                if apex is not None:
                    _check_frame(apex, base, "apex", n_frames, issues)
                if end is not None:
                    _check_frame(end, base, "end", n_frames, issues)
            if start is not None and end is not None and end <= start:
                issues.append(Issue(_ptr(base, "end"), "must be after start"))
            if apex is not None and start is not None and end is not None:
                if not start <= apex <= end:
                    issues.append(Issue(_ptr(base, "apex"), "must lie between start and end"))
            rise_m = _req_num(flight, base, "rise_m", issues)
            if rise_m is not None and rise_m < 0:
                issues.append(Issue(_ptr(base, "rise_m"), "must be >= 0"))
            duration_s = _req_num(flight, base, "duration_s", issues)
            if duration_s is not None and duration_s <= 0:
                issues.append(Issue(_ptr(base, "duration_s"), "must be > 0"))
            if (
                duration_s is not None
                and start is not None
                and end is not None
                and fps_eff is not None
                and duration_s > 0
            ):
                want = (end - start) / fps_eff
                if abs(duration_s - want) > 0.5 / fps_eff + 1e-9:
                    issues.append(
                        Issue(
                            _ptr(base, "duration_s"),
                            "duration " + str(duration_s) + "s does not match frames "
                            + str(start) + "-" + str(end) + " at " + str(fps_eff) + " fps",
                        )
                    )
            fit = _req_dict(flight, base, "fit", issues)
            if fit is not None:
                _req_num(fit, _ptr(base, "fit"), "a", issues)
                a_err = _req_num(fit, _ptr(base, "fit"), "a_err", issues)
                _check_pos(a_err, _ptr(base, "fit"), "a_err", issues)
                rms = _req_num(fit, _ptr(base, "fit"), "rms", issues)
                if rms is not None and rms < 0:
                    issues.append(Issue(_ptr(_ptr(base, "fit"), "rms"), "must be >= 0"))
                _req_num(fit, _ptr(base, "fit"), "v0", issues)
                n_fit = _req_int(fit, _ptr(base, "fit"), "n", issues)
                if n_fit is not None and n_fit < 3:
                    issues.append(Issue(_ptr(_ptr(base, "fit"), "n"), "must be >= 3"))
                window = _req_dict(fit, _ptr(base, "fit"), "window", issues)
                if window is not None:
                    first_f = _req_int(window, _ptr(_ptr(base, "fit"), "window"), "first", issues)
                    last_f = _req_int(window, _ptr(_ptr(base, "fit"), "window"), "last", issues)
                    if n_frames is not None:
                        if first_f is not None:
                            _check_frame(
                                first_f, _ptr(_ptr(base, "fit"), "window"), "first", n_frames, issues
                            )
                        if last_f is not None:
                            _check_frame(
                                last_f, _ptr(_ptr(base, "fit"), "window"), "last", n_frames, issues
                            )
            accel = _req_num(flight, base, "accel", issues)
            accel_err = _req_num(flight, base, "accel_err", issues)
            _check_pos(accel_err, base, "accel_err", issues)
            hypo = _req_dict(flight, base, "hypothesis", issues)
            hypo_name, hypo_value = None, None
            if hypo is not None:
                hypo_name = _req_str(hypo, _ptr(base, "hypothesis"), "name", issues)
                hypo_value = _req_num(hypo, _ptr(base, "hypothesis"), "value", issues)
                if hypo_value is not None and hypo_value <= 0:
                    issues.append(
                        Issue(_ptr(_ptr(base, "hypothesis"), "value"), "must be > 0")
                    )
            if "decide" in flight and isinstance(flight.get("decide"), dict):
                worlds = None
                if hypo_name is not None and hypo_value is not None and hypo_value > 0:
                    worlds = {hypo_name: hypo_value}
                _check_decide_match(
                    flight["decide"], accel, accel_err, worlds,
                    _ptr(base, "decide"), issues,
                )
            elif "decide" in flight:
                issues.append(Issue(_ptr(base, "decide"), "expected a decide object"))
            else:
                _need(flight, base, "decide", issues)
            ghost = _req_list(flight, base, "ghost", issues)
            if ghost is not None:
                if len(ghost) < 1:
                    issues.append(Issue(_ptr(base, "ghost"), "expected at least one point"))
                for j, point in enumerate(ghost):
                    gbase = _ptr(_ptr(base, "ghost"), j)
                    if not isinstance(point, dict):
                        issues.append(Issue(gbase, "expected an object"))
                        continue
                    gframe = _req_int(point, gbase, "frame", issues)
                    _req_num(point, gbase, "y", issues)
                    if gframe is not None and n_frames is not None:
                        _check_frame(gframe, gbase, "frame", n_frames, issues)
            _req_str(flight, base, "notes", issues)
            if (
                rise_m is not None
                and start is not None
                and m_per is not None
                and m_per > 0
            ):
                ref_frame = apex if apex is not None else end
                if ref_frame is not None:
                    if start not in track_points or ref_frame not in track_points:
                        issues.append(
                            Issue(
                                _ptr(base, "rise_m"),
                                "track has no point at the flight boundary frames",
                            )
                        )
                    else:
                        rise_units = track_points[start][1] - track_points[ref_frame][1]
                        want_rise = rise_units * m_per
                        tol = max(_RISE_REL_TOL * abs(want_rise), _RISE_ABS_TOL)
                        if abs(rise_m - want_rise) > tol + 1e-9:
                            issues.append(
                                Issue(
                                    _ptr(base, "rise_m"),
                                    "rise " + str(rise_m) + "m does not match the track "
                                    + str(rise_units) + " units",
                                )
                            )

    timescale: Any = None
    if "timescale" in analysis:
        timescale = _check_timescale(analysis["timescale"], "/timescale", issues)
        if analysis["timescale"] is not None and not isinstance(analysis["timescale"], dict):
            timescale = None
    else:
        _need(analysis, "", "timescale", issues)

    budget = analysis.get("error_budget")
    if "error_budget" not in analysis:
        _need(analysis, "", "error_budget", issues)
    elif not isinstance(budget, dict) or len(budget) < 1:
        issues.append(Issue("/error_budget", "expected an object with at least one term"))
    else:
        for term, share in budget.items():
            if not _is_num(share) or float(share) < 0:
                issues.append(
                    Issue(_ptr("/error_budget", term), "expected a relative error >= 0")
                )

    verdict = analysis.get("verdict")
    if "verdict" not in analysis:
        _need(analysis, "", "verdict", issues)
    elif not isinstance(verdict, dict):
        issues.append(Issue("/verdict", "expected an object"))
    else:
        for key in (
            "state", "world", "consistent", "sigmas", "nearest", "k",
            "text", "g", "g_err", "worlds",
        ):
            _need(verdict, "/verdict", key, issues)
        g = verdict.get("g") if _is_num(verdict.get("g")) else None
        g_err = verdict.get("g_err") if _is_num(verdict.get("g_err")) else None
        if verdict.get("g") is not None and g is None:
            issues.append(Issue("/verdict/g", "expected a finite number"))
        if verdict.get("g_err") is not None and (not _is_num(verdict.get("g_err"))):
            issues.append(Issue("/verdict/g_err", "expected a finite number"))
        _check_pos(g_err, "/verdict", "g_err", issues)
        worlds = verdict.get("worlds")
        clean_worlds: dict[str, float] | None = None
        if worlds is not None:
            if not isinstance(worlds, dict) or len(worlds) < 1:
                issues.append(Issue("/verdict/worlds", "expected an object with worlds"))
            else:
                clean_worlds = {}
                for name, val in worlds.items():
                    if not _is_num(val) or float(val) <= 0:
                        issues.append(
                            Issue(_ptr("/verdict/worlds", name), "expected a positive g")
                        )
                    else:
                        clean_worlds[str(name)] = float(val)
        _check_decide_match(
            {k: v for k, v in verdict.items() if k != "worlds"},
            g, g_err, clean_worlds, "/verdict", issues,
        )

    overall = analysis.get("overall")
    if "overall" not in analysis:
        _need(analysis, "", "overall", issues)
    elif not isinstance(overall, dict):
        issues.append(Issue("/overall", "expected an object"))
    else:
        _req_str(overall, "/overall", "label", issues)
        _req_str(overall, "/overall", "text", issues)
        if isinstance(verdict, dict) and isinstance(overall.get("label"), str):
            want_overall = combine(verdict, timescale)
            if overall.get("label") != want_overall["label"]:
                issues.append(
                    Issue(
                        "/overall/label",
                        "label " + repr(overall.get("label")) + " does not match "
                        "combine (" + repr(want_overall["label"]) + ")",
                    )
                )
            elif overall.get("text") != want_overall["text"]:
                issues.append(
                    Issue("/overall/text", "text does not match combine for this verdict")
                )
    seen: set[tuple[str, str]] = set()
    unique: list[Issue] = []
    for issue in issues:
        key = (issue.path, issue.message)
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return unique


def _short_text(text: str, limit: int) -> str:
    """Truncate text at a word boundary; never cut a word in half."""
    words = text.split()
    out: list[str] = []
    size = 0
    for word in words:
        extra = len(word) if not out else len(word) + 1
        if size + extra > limit:
            break
        out.append(word)
        size += extra
    return " ".join(out)


#: Hard character budget for the prompt-ready schema description.
SCHEMA_DOC_LIMIT = 6000


def schema_doc() -> str:
    """Compact prompt-ready description of the schema.

    One compact line per object, listing required then optional fields
    down to the leaves, with enum values and units. Generated from
    ``config/analysis.schema.json`` so the prompt cannot drift from
    the validator; nested field lists are curated from the schema and
    the top-level required set is read from the file.
    """
    schema = load_schema()
    top_required = schema.get("required") or []
    top_optional = [
        name
        for name in (
            "type", "schema_version", "clip", "context", "first_look",
            "reference", "scale", "track", "masks", "flights",
            "timescale", "error_budget", "verdict", "overall",
            "page_texts",
        )
        if name not in top_required
    ]
    header_desc = _short_text(
        str(schema.get("description", "")), 110
    )
    lines = [
        "analysis.json (type world-g, schema version 1): "
        + header_desc
        + " Unknown fields are allowed and ignored.",
        "top-level required: " + ", ".join(str(k) for k in top_required) + ".",
        "top-level optional: " + (
            ", ".join(top_optional) if top_optional else "none"
        ) + ".",
        "type (required const): type=world-g.",
        "schema_version (required const): schema_version=1.",
        "clip (required): file, fps [frames/s], frames, width [px], "
        "height [px], duplicates_found, notes.",
        "context (required): scene, claim, expected[] "
        "{quantity, value, unit, source}, sources[] [URLs].",
        "first_look (required): what, where, when, source, "
        "confidence [0..1], by_eye {quantity, value, unit}.",
        "reference[] (required, at least 1): name, extent, value_m [m], "
        "tolerance_m [m], source_url [URL or null; null only if estimate], "
        "quote [text or null; null only if estimate], "
        "source_type [primary|secondary|estimate], mask {file, object}, "
        "mask_check {verdict "
        "[agrees|covers_more|covers_less|different_object|cannot_tell], "
        "covers [which part of the object the mask covers]}.",
        "scale (required, two forms): frame [frame], extent_px [px], "
        "extent_px_err [px], second [{name, m_per_px [m/px], "
        "m_per_px_err, agree_sigma} or null]; "
        "form image: frame_of_reference=image, m_per_px [m/px], "
        "m_per_px_err; "
        "form moving: frame_of_reference {object, anchor [top|bottom], "
        "size_px_per_frame [px or array of px]}, "
        "m_per_ref [m per reference size], m_per_ref_err. "
        "Track unit must match: image uses px, moving uses ref.",
        "track (required): what, method, unit [px|ref], "
        "points[] {frame, x, y} (at least 2 points, frames inside clip). "
        "Each point may carry px [x, y] in px: the video-pixel position of "
        "the tracked point that frame; write it from now on, so the page "
        "can draw ref-unit tracks on the video without converting.",
        "masks (required, at least 1 object): "
        "{object_name: {frame: spans [[y, x0, x1], ...]}}; "
        "only frames the page draws, spans_of format, x1 > x0.",
        "flights[] (required, at least 1): kind [flight|wall], "
        "start [frame], apex [frame or null], end [frame], rise_m [m], "
        "duration_s [s]=(end-start)/fps, "
        "fit {a [track units/s2, down positive], a_err, rms, v0, "
        "n [at least 3], window {first [frame], last [frame]}}, "
        "accel [m/s2, down positive], accel_err [m/s2], "
        "hypothesis {name, value [m/s2]}, "
        "decide {state, world, consistent[], sigmas{}, nearest, k, "
        "text, g [m/s2], g_err [m/s2]; optional k_sigma} "
        "= blocks.decide(g, g_err, worlds) checked on state/consistent/k, "
        "ghost[] {frame, y}, notes.",
        "timescale (required, null allowed): method, value, err, unit, "
        "expected_range [lo, hi] [same unit as value: the natural range "
        "of the clock rhythm (e.g. the run-up step rate), source in "
        "method/notes], "
        "verdict [normal|slow|fast|undetermined: the agent's own reading; "
        "combine tests value x k against the range].",
        "error_budget (required, at least 1 term): "
        "{term: relative fraction, e.g. 0.05}.",
        "verdict (required) = blocks.decide(g, g_err, worlds) plus "
        "g [m/s2], g_err [m/s2], worlds {name: g [m/s2]}: "
        "state, world, consistent[], sigmas{}, nearest, k, text, "
        "g, g_err, worlds.",
        "overall (required) = combine(verdict, timescale): label, text.",
        "page_texts (optional): {key: replacement string}.",
    ]
    doc = "\n".join(lines)
    assert len(doc) <= SCHEMA_DOC_LIMIT, "schema_doc exceeded 6000 characters"
    return doc


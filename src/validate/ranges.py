# generated from brief/11 · part 11 owns this file
"""Range checks: check, score and combine (brief §20, part 02 §9).

A range check settles one measured quantity against a quoted range.
Every function here is total over schema-valid input: unexpected
shapes become error records, never exceptions.
"""

from __future__ import annotations

import math
import re

__all__ = [
    "RANGE_CODES",
    "check_range_checks",
    "check_range_on_reference",
    "check_reference_sources",
    "combine_parts",
    "format_range_sentence",
    "named_units",
    "normalize_quote",
    "quote_absent_detail",
    "quote_contains_number",
    "quote_in_search",
    "range_calc_steps",
    "range_value_text",
    "score_range",
    "web_search_facts",
    "web_search_urls",
]

#: Hard rejects for range checks (brief §20), dry run included.
#: ``RANGE_LINE_NOT_CONFIRMED`` is the §28 line check: every extent
#: of every range check needs an agreeing ``check_line`` record.
#: ``RANGE_SIGMA_TOO_SMALL`` (brief §33) fires only for a σ that is
#: not a finite positive number; a σ below the endpoint-and-scale
#: floor is raised to the floor instead, with a caveat on the step.
RANGE_CODES = (
    "RANGE_NUMBER_WITHOUT_PROVENANCE",
    "RANGE_FORMULA_MISMATCH",
    "RANGE_SOURCE_MISSING",
    "RANGE_SIGMA_TOO_SMALL",
    "MEASUREMENT_MISSING",
    "RANGE_EXTENT_OFF_FRAME",
    "RANGE_EXTENT_NOT_ON_MASK",
    "RANGE_LINE_NOT_CONFIRMED",
    "RANGE_CHECK_ON_REFERENCE",
)


def _err(code, field, detail) -> dict:
    return {"code": str(code), "field": str(field),
            "detail": str(detail)}


def _missing(field, detail) -> dict:
    return _err("MISSING_FIELD", field, detail)


def _numbers_in_text(text: str) -> list:
    """All plain numbers, fractions and unit-suffixed numbers in text."""
    out = []
    for match in re.finditer(
            r"(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)"
            r"(?:\s*(mm|cm|m|in|inch|inches|ft|feet|%|percent))?",
            str(text)):
        out.append((match.group(1), (match.group(2) or "").strip()))
    return out


def _to_base(number: str, unit: str):
    """A quoted number in the check's unit, or None.

    Unit conversions (brief §20): mm, cm, m, in, ft; percent and
    fraction. A bare number is already in the unit.
    """
    try:
        if "/" in number:
            num, den = number.split("/", 1)
            value = float(num.strip()) / float(den.strip())
        else:
            value = float(number)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    unit = unit.lower()
    if unit in ("mm",):
        return value / 1000.0
    if unit in ("cm",):
        return value / 100.0
    if unit in ("m", ""):
        return value
    if unit in ("in", "inch", "inches"):
        return value * 0.0254
    if unit in ("ft", "feet"):
        return value * 0.3048
    if unit in ("%", "percent"):
        return value / 100.0
    return None


#: Units a quote can name for its bare numbers (brief §24): a label
#: such as "(mm)", "in cm" or "mm:", or the unit suffixed to a number.
_UNIT_WORDS = ("mm", "cm", "m", "in", "inch", "inches", "ft", "feet",
               "percent", "%")

_codes = "|".join(_UNIT_WORDS)

_LABEL_PATTERNS = (
    r"\((%s)\)" % _codes,
    r"\bin\s+(%s)\b" % _codes,
    r"\b(%s)\s*:" % _codes,
)


def named_units(text: str) -> set:
    """Unit words the quote names: label forms plus number suffixes.

    A table names its unit once in a label ("Hand length (mm) ..."),
    as prose does ("in cm"); a suffixed number ("66 cm") names its own
    unit for the same purpose. Used for the §24 unit fallback.
    """
    found = set()
    for _number, unit in _numbers_in_text(str(text or "")):
        if unit:
            found.add(unit.lower())
    for pattern in _LABEL_PATTERNS:
        for match in re.finditer(pattern, str(text or ""),
                                 re.IGNORECASE):
            found.add(match.group(1).lower())
    return found


def _fact_unit(number: str, fact_text: str):
    """The unit following the same number in the search fact's text.

    Tables shorten their quotes; the fact's own text may still carry
    the unit next to that number (brief §24). Returns the unit word,
    or ``""`` when the number is absent or carries none.
    """
    try:
        target = float(number)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(target):
        return ""
    for candidate, unit in _numbers_in_text(str(fact_text or "")):
        try:
            value = float(candidate) if "/" not in candidate else float(
                candidate.split("/", 1)[0]) / float(
                    candidate.split("/", 1)[1])
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if not math.isfinite(value):
            continue
        scale = max(abs(target), 1e-12)
        if abs(value - target) / scale <= 1e-9 and unit:
            return unit
    return ""


def quote_contains_number(quote: str, highlight: str, bound: float,
                          fact_text: str = "") -> bool:
    """The quote carries the bound number, unit conversions allowed.

    A number converts with the unit that follows it or, failing that,
    with the single unit the quote names in a label ("(mm)", "in cm",
    "mm:"). When the quote names no unit, the number converts with the
    unit that follows the same number in the search fact's text. When
    the quote names two different units, there is no fallback: a bare
    number stays unitless (brief §24).
    """
    try:
        target = float(bound)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(target):
        return False
    units = named_units(quote)
    label_unit = next(iter(units)) if len(units) == 1 else None
    candidates = [str(quote or ""), str(highlight or "")]
    for text in candidates:
        for number, unit in _numbers_in_text(text):
            if unit:
                value = _to_base(number, unit)
            elif label_unit is not None:
                value = _to_base(number, label_unit)
            else:
                value = _to_base(
                    number, _fact_unit(number, fact_text))
            if value is None or not math.isfinite(value):
                continue
            scale = max(abs(target), 1e-12)
            if abs(value - target) / scale <= 0.01:
                return True
    return False


def _artifact_text(rel: str, ctx):
    """Text of a run-relative artifact, or None when unreadable."""
    from .io import load_json_rel  # noqa: PLC0415 — avoid a cycle

    base_is_json = str(rel).lower().endswith(".json")
    if base_is_json:
        ok, value, _ = load_json_rel(rel, ctx)
        if not ok:
            return None
        try:
            import json as _json

            return _json.dumps(value)
        except (TypeError, ValueError):
            return None
    try:
        from pathlib import Path  # noqa: PLC0415

        raw = ctx.get("run_dir", ".") if isinstance(ctx, dict) else "."
        target = Path(str(raw)) / str(rel)
        if ".." in str(rel).split("/"):
            return None
        return target.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError, TypeError):
        return None


def _floats_in_text(text: str) -> list:
    return [float(m) for m in
            re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?",
                       str(text))]


def _number_present(text: str, value: float) -> bool:
    try:
        target = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(target):
        return False
    if repr(target) in str(text):
        return True
    for token in _floats_in_text(text):
        scale = max(abs(target), 1e-12)
        if abs(token - target) / scale <= 1e-6:
            return True
    return False


def web_search_facts(ctx) -> dict:
    """Facts the run's filtered ``web_search`` calls returned.

    Maps each URL to its list of ``{"quote", "text"}`` records, in
    file order. Total over any context: unreadable files are skipped.
    """
    out: dict = {}
    artifacts = []
    try:
        artifacts = list((ctx or {}).get("artifacts", []) or [])
    except AttributeError:
        artifacts = []
    from .io import load_json_rel  # noqa: PLC0415 — avoid a cycle

    for rel in artifacts:
        name = str(rel)
        if "web_search" not in name or not name.endswith(".json"):
            continue
        ok, value, _ = load_json_rel(rel, ctx)
        if not ok or not isinstance(value, dict):
            continue
        facts = value.get("facts", [])
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            urls = []
            for key in ("url", "source_url"):
                candidate = fact.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    urls.append(candidate.strip())
            if not urls:
                continue
            record = {}
            for key in ("quote", "text"):
                value_text = fact.get(key)
                record[key] = (value_text if isinstance(value_text, str)
                               else "")
            for url in urls:
                out.setdefault(url, []).append(record)
    return out


def web_search_urls(ctx) -> set:
    """Every URL the run's filtered ``web_search`` calls returned."""
    return set(web_search_facts(ctx))


#: Dash variants normalised to "-" for quote comparison (brief §24).
_DASHES = ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015",
           "\u2212", "\u00ad", "\ufe58", "\ufe63", "\uff0d")


def normalize_quote(text: str) -> str:
    """A quote with spaces and dash variants normalised (brief §24)."""
    collapsed = str(text or "")
    for dash in _DASHES:
        collapsed = collapsed.replace(dash, "-")
    return re.sub(r"[\s\u00a0]+", " ", collapsed).strip()


def quote_in_search(quote: str, url: str, facts_by_url) -> bool:
    """The quote is one the search returned for that URL (brief §24).

    The normalised quote must appear in the normalised ``quote`` or
    ``text`` of one of that URL's facts; it may be shortened at either
    end. An empty quote never passes.
    """
    if not isinstance(quote, str) or not quote.strip():
        return False
    wanted = normalize_quote(quote)
    if not wanted:
        return False
    entries = (facts_by_url.get(url) if isinstance(facts_by_url, dict)
               else None)
    if not entries:
        return False
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        for key in ("quote", "text"):
            text = entry.get(key)
            if isinstance(text, str) and wanted in normalize_quote(
                    text):
                return True
    return False


def quote_absent_detail(url: str) -> str:
    """The §24 detail for a quote the search did not return."""
    return (f"this quote is not in what web_search returned for "
            f"{url}; copy it from the search result")


def _recomputed_value(check, m_per_px):
    """The value recomputed from the extents, or None.

    A ratio recomputes from the two ``length_px``; a metric length
    from ``length_px × m_per_px`` when ``uses_scale`` (brief §20).
    """
    try:
        extents = check.get("extents", [])
        uses_scale = bool(check.get("uses_scale"))
    except AttributeError:
        return None
    if not isinstance(extents, list):
        return None
    try:
        lengths = [float(e["length_px"]) for e in extents
                   if isinstance(e, dict)]
    except (KeyError, TypeError, ValueError):
        return None
    if any(not math.isfinite(v) or v <= 0 for v in lengths):
        return None
    if uses_scale:
        try:
            scale = float(m_per_px)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(scale) or scale <= 0:
            return None
        if len(lengths) != 1:
            return None
        return lengths[0] * scale
    if len(lengths) != 2:
        return None
    return lengths[0] / lengths[1], lengths[1] / lengths[0]


def _required_sigma(check, m_per_px, sigma_m_per_px):
    """Least σ the endpoint error (1 px) and the scale allow (§20)."""
    try:
        value = float(check.get("value", 0.0))
        extents = check.get("extents", [])
        uses_scale = bool(check.get("uses_scale"))
    except (TypeError, ValueError):
        return None
    if not isinstance(extents, list) or not extents:
        return None
    try:
        lengths = [float(e["length_px"]) for e in extents
                   if isinstance(e, dict)]
    except (KeyError, TypeError, ValueError):
        return None
    if any(not math.isfinite(v) or v <= 0 for v in lengths):
        return None
    if not math.isfinite(value) or value == 0:
        return None
    # One pixel per endpoint: σ_length = √2 px, propagated.
    rel_sq = sum((math.sqrt(2.0) / length) ** 2 for length in lengths)
    if uses_scale:
        try:
            scale = float(m_per_px)
            sigma_s = float(sigma_m_per_px)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(scale) or scale <= 0:
            return None
        if not math.isfinite(sigma_s) or sigma_s < 0:
            return None
        rel_sq += (sigma_s / scale) ** 2
    return abs(value) * math.sqrt(rel_sq)


def score_range(check) -> dict:
    """``(outcome, delta_sigma, side)`` for one range check (02 §9).

    ``delta_sigma`` is the distance of the measured value from the
    nearer bound, in σ: ``(value - max) / σ`` above the range,
    ``(min - value) / σ`` below it, and 0 inside (brief §40). The
    outcome rule is unchanged: a check is ``outside`` (or ``below``,
    brief §38) exactly when that distance exceeds 2, that is, when
    the whole 2σ interval lies beyond the bound; otherwise it is
    ``inside`` with ``delta_sigma`` 0. Below (brief §38): falling
    short of a range never decides "not realistic" on its own. A
    check with no measured value or no sourced bound is not
    counted.
    """
    try:
        value = check.get("value")
        sigma = check.get("sigma")
        low = check.get("range", {}).get("min")
        high = check.get("range", {}).get("max")
        value = float(value)
        sigma = float(sigma)
        low = float(low)
        high = float(high)
    except (TypeError, ValueError, AttributeError):
        return {"outcome": "not_counted", "delta_sigma": 0.0,
                "side": None}
    if not all(math.isfinite(v) for v in (value, sigma, low, high)):
        return {"outcome": "not_counted", "delta_sigma": 0.0,
                "side": None}
    if sigma < 0 or high < low:
        return {"outcome": "not_counted", "delta_sigma": 0.0,
                "side": None}
    denom = max(sigma, 1e-12)
    if value < low:
        dist = (low - value) / denom
        if dist > 2:
            return {"outcome": "below", "delta_sigma": float(dist),
                    "side": "below"}
        return {"outcome": "inside", "delta_sigma": 0.0, "side": None}
    if value > high:
        dist = (value - high) / denom
        if dist > 2:
            return {"outcome": "outside", "delta_sigma": float(dist),
                    "side": "above"}
        return {"outcome": "inside", "delta_sigma": 0.0, "side": None}
    return {"outcome": "inside", "delta_sigma": 0.0, "side": None}


def _extent_frame_size(ctx, evidence, frame_masks):
    """``(width, height)`` for the extent checks, or None.

    The run's own pixels first (``input/clip.*``); then the run's
    masks (their array shapes are full-frame); never agent-typed
    numbers. Total: None when nothing measurable is available.
    """
    try:
        from .io import clip_frame_size  # noqa: PLC0415 — avoid a cycle
    except ImportError:
        clip_frame_size = None
    if clip_frame_size is not None:
        try:
            size = clip_frame_size(ctx)
        except Exception:
            size = None
        if size is not None:
            return size
    try:
        timing = (ctx or {}).get("timing", {}) or {}
    except AttributeError:
        timing = {}
    for wide, high in (("coded_width", "coded_height"),
                       ("width", "height")):
        try:
            width = float(timing.get(wide))
            height = float(timing.get(high))
        except (TypeError, ValueError):
            continue
        if width > 0 and height > 0:
            return int(width), int(height)
    try:
        video = (evidence or {}).get("video", {}) or {}
        width = float(video.get("coded_width", 0) or 0)
        height = float(video.get("coded_height", 0) or 0)
    except (TypeError, ValueError, AttributeError):
        width, height = 0.0, 0.0
    if width > 0 and height > 0:
        return int(width), int(height)
    best = None
    for masks in (frame_masks or {}).values():
        for entry in masks or []:
            try:
                shape = entry["array"].shape
            except (KeyError, TypeError, AttributeError):
                continue
            if len(shape) != 2:
                continue
            if best is None or shape[1] * shape[0] > best[1] * best[0]:
                best = (int(shape[1]), int(shape[0]))
    return best


def _dist_to_mask(mask, row, col):
    """Pixel distance from one cell to the nearest True cell."""
    try:
        from scipy.ndimage import (  # noqa: PLC0415
            distance_transform_edt)
    except ImportError:
        distance_transform_edt = None
    if distance_transform_edt is not None:
        try:
            import numpy as np  # noqa: PLC0415

            field = distance_transform_edt(
                np.logical_not(np.asarray(mask, dtype=bool)))
            return float(field[row, col])
        except (TypeError, ValueError, IndexError):
            pass
    try:
        import numpy as np  # noqa: PLC0415

        rows, cols = np.nonzero(np.asarray(mask, dtype=bool))
    except (TypeError, ValueError):
        return float("inf")
    if len(rows) == 0:
        return float("inf")
    gaps = (rows - row) ** 2 + (cols - col) ** 2
    return float(np.sqrt(gaps.min()))


def _mask_covers(mask, points, tol_px) -> bool:
    """Both endpoints on one mask: inside or near its edge (§25)."""
    try:
        height, width = mask.shape
    except (TypeError, ValueError, AttributeError):
        return False
    for x, y in points:
        if not (0 <= x < width and 0 <= y < height):
            return False
        row, col = int(y), int(x)
        try:
            if bool(mask[row, col]):
                continue
        except (TypeError, ValueError, IndexError):
            return False
        if _dist_to_mask(mask, row, col) > tol_px:
            return False
    return True


def _check_extent_geometry(check, pos, ctx, evidence, frame_size,
                           frame_masks):
    """``RANGE_EXTENT_*`` for one range check (brief §25).

    Returns ``(errors, ok)``: every endpoint inside the frame, and
    both endpoints of each extent on one mask from this run's
    ``segment`` artifacts on the extent's frame. A wrong verdict is
    worse than none, so these run before any range check is scored.
    """
    import math as _math  # noqa: PLC0415

    errors = []
    ok = True
    field = f"range_checks[{pos}]"
    try:
        check_frame = int(check.get("frame", 0))
    except (TypeError, ValueError):
        return errors, ok
    extents = check.get("extents", [])
    if not isinstance(extents, list):
        return errors, ok
    for epos, extent in enumerate(extents):
        if not isinstance(extent, dict):
            continue
        efield = f"{field}.extents[{epos}]"
        name = extent.get("name")
        if not isinstance(name, str) or not name.strip():
            name = f"extent {epos}"
        name = name.strip()
        try:
            frame = int(extent.get("frame", check_frame))
        except (TypeError, ValueError):
            continue
        if isinstance(extent.get("frame", check_frame), bool):
            continue
        try:
            x1 = float(extent["x1"])
            y1 = float(extent["y1"])
            x2 = float(extent["x2"])
            y2 = float(extent["y2"])
        except (KeyError, TypeError, ValueError):
            continue
        if frame_size is not None:
            width, height = frame_size
            bad = [f"({x1:g}, {y1:g})"
                   for x1, y1 in ((x1, y1), (x2, y2))
                   if not (0 <= x1 < width and 0 <= y1 < height)]
            if bad:
                ok = False
                errors.append(_err(
                    "RANGE_EXTENT_OFF_FRAME", efield,
                    f"{efield} ({name}) on frame {frame}: endpoint "
                    f"{' and '.join(bad)} lies outside the "
                    f"{width}x{height} frame (0 <= x < {width}, "
                    f"0 <= y < {height}): re-measure the extent "
                    f"inside the picture"))
        masks = (frame_masks or {}).get(frame, [])
        arrays = []
        for entry in masks or []:
            try:
                arrays.append(entry["array"])
            except (KeyError, TypeError):
                continue
        if not arrays:
            ok = False
            errors.append(_err(
                "RANGE_EXTENT_NOT_ON_MASK", efield,
                f"segment {name} on frame {frame}; both ends of the "
                f"line must lie on its mask: no mask from this run "
                f"covers frame {frame}, so segment {name} on frame "
                f"{frame} first"))
            continue
        try:
            diag = _math.hypot(frame_size[0], frame_size[1]) \
                if frame_size is not None else None
        except (TypeError, ValueError):
            diag = None
        if diag is None or not _math.isfinite(diag) or diag <= 0:
            try:
                height, width = arrays[0].shape
                diag = _math.hypot(width, height)
            except (TypeError, ValueError, AttributeError):
                diag = 0.0
        if not any(_mask_covers(mask, ((x1, y1), (x2, y2)),
                               0.02 * diag) for mask in arrays):
            ok = False
            errors.append(_err(
                "RANGE_EXTENT_NOT_ON_MASK", efield,
                f"segment {name} on frame {frame}; both ends of the "
                f"line must lie on its mask: segment {name} on "
                f"frame {frame} so both ends lie on its mask"))
    return errors, ok


#: Endpoints match when each end lies within this many pixels of
#: the extent's own endpoint (brief §28).
_LINE_TOL_PX = 2.0


def _load_line_entries(ctx) -> list:
    """Every measured-line entry of ``artifacts/line_checks.jsonl``.

    Returns ``[(frame, entry)]`` with the raw ``check_line`` line
    dicts (``x1``/``y1``/``x2``/``y2``/``claim``/``description``/
    ``agrees``). Total over any run: a missing or unreadable journal
    simply yields no entries, and each extent then fails with the
    no-record detail (brief §28).
    """
    import json as _json  # noqa: PLC0415

    from pathlib import Path  # noqa: PLC0415

    try:
        raw = ctx.get("run_dir", ".") if isinstance(ctx, dict) else "."
        target = Path(str(raw)) / "artifacts" / "line_checks.jsonl"
        text = target.read_text(encoding="utf-8")
    except (OSError, ValueError, TypeError, AttributeError):
        return []
    entries = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = _json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        lines = record.get("lines")
        if isinstance(lines, list):
            for item in lines:
                if not isinstance(item, dict):
                    continue
                frame = item.get("frame", record.get("frame"))
                entries.append((frame, item))
        elif all(key in record
                 for key in ("x1", "y1", "x2", "y2")):
            entries.append((record.get("frame"), record))
    return entries


def _endpoints_close(first, second, tol=_LINE_TOL_PX) -> bool:
    """Two endpoints within ``tol`` pixels of each other."""
    try:
        gap = math.hypot(float(first[0]) - float(second[0]),
                         float(first[1]) - float(second[1]))
    except (TypeError, ValueError):
        return False
    return gap <= tol + 1e-9


def _line_matches(entry, coords) -> bool:
    """A ``check_line`` entry on the same line as the extent (§28).

    Both endpoints within 2 px of the extent's, in either direction:
    the tool draws the line the agent measured, and the direction the
    agent typed it in carries no meaning.
    """
    try:
        ends = ((float(entry["x1"]), float(entry["y1"])),
                (float(entry["x2"]), float(entry["y2"])))
    except (KeyError, TypeError, ValueError):
        return False
    first, second = coords
    return ((_endpoints_close(ends[0], first)
             and _endpoints_close(ends[1], second))
            or (_endpoints_close(ends[0], second)
                and _endpoints_close(ends[1], first)))


def _check_line_confirmation(check, pos, line_entries) -> list:
    """``RANGE_LINE_NOT_CONFIRMED`` for one range check (brief §28).

    Every extent needs a record in this run's
    ``artifacts/line_checks.jsonl`` on the same frame, with both
    endpoints within 2 px of the extent's and ``agrees: true``.
    References are not line-checked; only range-check extents are.
    Unlike the §25 geometry, a missing confirmation never changes the
    score: it is a hard reject like the other range-code checks.
    """
    errors = []
    field = f"range_checks[{pos}]"
    extents = check.get("extents", [])
    if not isinstance(extents, list):
        return errors
    try:
        check_frame = int(check.get("frame", 0))
    except (TypeError, ValueError):
        check_frame = 0
    for epos, extent in enumerate(extents):
        if not isinstance(extent, dict):
            continue
        efield = f"{field}.extents[{epos}]"
        name = extent.get("name")
        if not isinstance(name, str) or not name.strip():
            name = f"extent {epos}"
        name = name.strip()
        try:
            frame = int(extent.get("frame", check_frame))
        except (TypeError, ValueError):
            continue
        if isinstance(frame, bool):
            continue
        try:
            coords = ((float(extent["x1"]), float(extent["y1"])),
                      (float(extent["x2"]), float(extent["y2"])))
        except (KeyError, TypeError, ValueError):
            continue
        matches = []
        for rec_frame, item in line_entries:
            if isinstance(rec_frame, bool):
                continue
            try:
                if int(rec_frame) != frame:
                    continue
            except (TypeError, ValueError):
                continue
            if not isinstance(item, dict):
                continue
            if _line_matches(item, coords):
                matches.append(item)
        if any(item.get("agrees") is True for item in matches):
            continue
        if matches:
            seen = ""
            for item in matches:
                text = item.get("description")
                if isinstance(text, str) and text.strip():
                    seen = text.strip()
                    break
            errors.append(_err(
                "RANGE_LINE_NOT_CONFIRMED", efield,
                f"{efield} ({name}) on frame {frame}: the second "
                f"look sees '{seen}'; re-measure the line so that "
                f"it runs {name}, then check it again"))
        else:
            x1, y1 = coords[0]
            x2, y2 = coords[1]
            errors.append(_err(
                "RANGE_LINE_NOT_CONFIRMED", efield,
                f"{efield} ({name}) on frame {frame} has no "
                f"confirming check_line record: check this line "
                f"with check_line(frame={frame}, lines=[{{x1: {x1}, "
                f"y1: {y1}, x2: {x2}, y2: {y2}, "
                f"claim: '{name}'}}])"))
    return errors


#: Endpoints match a reference line when each end lies within this
#: many pixels of the reference extent's own endpoint (brief §48):
#: the scale comes from that line, so a range check on it tests
#: nothing.
_REFERENCE_LINE_TOL_PX = 3.0


def _ref_line_coords(extent):
    """``(coords, frame)`` for a reference/scale line, or ``(None, None)``."""
    if not isinstance(extent, dict):
        return None, None
    try:
        coords = ((float(extent["x1"]), float(extent["y1"])),
                  (float(extent["x2"]), float(extent["y2"])))
        frame_raw = extent.get("frame")
        if isinstance(frame_raw, bool):
            return None, None
        frame = int(frame_raw)
    except (KeyError, TypeError, ValueError):
        return None, None
    return coords, frame


def _ref_ends_close(first, second, tol=_REFERENCE_LINE_TOL_PX) -> bool:
    """Two endpoints within the §48 tolerance of each other."""
    try:
        gap = math.hypot(float(first[0]) - float(second[0]),
                         float(first[1]) - float(second[1]))
    except (TypeError, ValueError):
        return False
    return gap <= tol + 1e-9


def _is_same_line(coords, frame, ref_coords, ref_frame) -> bool:
    """A range extent on the same reference line (brief §48).

    The same frame, with both endpoints within 3 px of the reference
    extent's endpoints, in either order: the direction the agent typed
    the line in carries no meaning.
    """
    if frame != ref_frame:
        return False
    (first, second), (ref_first, ref_second) = coords, ref_coords
    return ((_ref_ends_close(first, ref_first)
             and _ref_ends_close(second, ref_second))
            or (_ref_ends_close(first, ref_second)
                and _ref_ends_close(second, ref_first)))


def _reference_lines(evidence) -> list:
    """``(kind, name, coords, frame)`` for every reference/scale line.

    A reference's ``extent_px`` and the scale's ``extent_px`` (the
    player's copy of the headline reference's line); a ``check_scale``
    carrying its own extent endpoints is read too, defensively — the
    contract gives it only ``m_per_px`` and ``sigma`` today.
    """
    lines = []
    references = evidence.get("references", [])
    if isinstance(references, list):
        for pos, ref in enumerate(references):
            if not isinstance(ref, dict):
                continue
            coords, frame = _ref_line_coords(ref.get("extent_px"))
            if coords is None:
                continue
            name = ref.get("name")
            if not isinstance(name, str) or not name.strip():
                name = f"references[{pos}]"
            lines.append(("reference", name.strip(), coords, frame,
                          f"references[{pos}]"))
    scale = evidence.get("scale")
    if isinstance(scale, dict):
        coords, frame = _ref_line_coords(scale.get("extent_px"))
        if coords is not None:
            lines.append(("scale", "the scale", coords, frame,
                          "scale.extent_px"))
        check = scale.get("check_scale")
        if isinstance(check, dict) and all(
                key in check for key in ("x1", "y1", "x2", "y2",
                                         "frame")):
            coords, frame = _ref_line_coords(check)
            if coords is not None:
                lines.append(("scale", "the scale", coords, frame,
                              "scale.check_scale"))
    return lines


#: Endpoints count as re-measuring a reference's object when each
#: lies within this many pixels of it (brief §51).
_OBJECT_TOL_PX = 3.0


def _reference_object_frames(ref, ctx):
    """``{frame: bool array}`` for one reference's object (brief §51).

    The reference's own masks plus every ``t*_segment_*.npz`` whose
    object overlaps the reference's mask object on the measuring
    frame with IoU above ``SAME_OBJECT_IOU`` (the §49 same-object
    rule, §54), each frame counted once with the reference's own
    mask first. Never raises: a reference without a readable mask
    on its measuring frame simply yields no frames.
    """
    try:
        mask = ref.get("mask", {}) if isinstance(ref, dict) else {}
        artifact = mask.get("artifact")
        object_id = mask.get("object_id")
        measure_frame = int((ref.get("extent_px", {}) or {}).get(
            "frame"))
    except (TypeError, ValueError, AttributeError):
        return {}
    if isinstance(measure_frame, bool):
        return {}
    if not isinstance(artifact, str) or not artifact:
        return {}
    try:
        from .io import (load_mask_frame,  # noqa: PLC0415 — same part
                         load_object_masks)
    except ImportError:
        return {}
    try:
        masks = load_object_masks(artifact, object_id, ctx)
    except Exception:  # noqa: BLE001 — total over schema-valid input
        masks = None
    if not masks:
        return {}
    try:
        ref_array = load_mask_frame(artifact, object_id, measure_frame,
                                    ctx)
    except Exception:  # noqa: BLE001
        ref_array = None
    if ref_array is None:
        return {}
    try:
        from .validate import (  # noqa: PLC0415 — the §49 same-object
            _same_object_mask_dicts)
    except ImportError:
        return {}
    try:
        others = _same_object_mask_dicts(artifact, object_id,
                                         measure_frame, ref_array, ctx)
    except Exception:  # noqa: BLE001
        others = []
    combined: dict = {}
    frames_list = [masks]
    if isinstance(others, list):
        frames_list.extend(others)
    for frames in frames_list:
        if not isinstance(frames, dict):
            continue
        for frame, arr in frames.items():
            if isinstance(frame, bool):
                continue
            try:
                index = int(frame)
            except (TypeError, ValueError):
                continue
            if isinstance(index, bool) or index in combined:
                continue
            combined[index] = arr
    return combined


def _endpoints_on_object(frames, frame, coords) -> bool:
    """Both endpoints within 3 px of the reference's object (§51)."""
    try:
        array = frames.get(int(frame))
    except (TypeError, ValueError, AttributeError):
        return False
    if array is None:
        return False
    try:
        height, width = array.shape
    except (TypeError, ValueError, AttributeError):
        return False
    for x, y in coords:
        try:
            inside = (0 <= float(x) < width
                      and 0 <= float(y) < height)
        except (TypeError, ValueError):
            return False
        if not inside:
            return False
        if _dist_to_mask(array, int(float(y)),
                         int(float(x))) > _OBJECT_TOL_PX + 1e-9:
            return False
    return True


def check_range_on_reference(evidence, ctx=None) -> tuple:
    """``RANGE_CHECK_ON_REFERENCE`` for every range check (§48, §51).

    Returns ``(errors, refused)``: ``refused`` holds the positions of
    range checks with an extent on a reference line, or on a
    reference's object. The scale comes from that line or object, so
    the measured length equals the quoted size by construction and
    tests nothing. A hard reject in a dry run and a real submit
    alike; the caller scores refused checks ``not_counted`` so they
    never decide the verdict.
    """
    errors = []
    refused: set = set()
    checks = evidence.get("range_checks", [])
    if not isinstance(checks, list):
        return errors, refused
    lines = _reference_lines(evidence)
    if not lines:
        lines = []
    for pos, check in enumerate(checks):
        if not isinstance(check, dict):
            continue
        field = f"range_checks[{pos}]"
        label = check.get("label", check.get("id", field))
        if not isinstance(label, str) or not label.strip():
            label = field
        label = label.strip()
        try:
            check_frame = int(check.get("frame", 0))
        except (TypeError, ValueError):
            check_frame = 0
        extents = check.get("extents", [])
        if not isinstance(extents, list):
            continue
        for extent in extents:
            if not isinstance(extent, dict):
                continue
            frame_raw = extent.get("frame", check_frame)
            if frame_raw is None:
                frame_raw = check_frame
            coords, frame = _ref_line_coords(
                {**extent, "frame": frame_raw})
            if coords is None:
                continue
            hit = None
            for kind, name, ref_coords, ref_frame, _field in lines:
                if _is_same_line(coords, frame, ref_coords, ref_frame):
                    hit = (kind, name, ref_frame)
                    break
            if hit is None:
                continue
            kind, name, ref_frame = hit
            if kind == "reference":
                detail = (
                    f"range check '{label}' measures the same line as "
                    f"reference '{name}' on frame {ref_frame}. The "
                    f"scale comes from that line, so this check tests "
                    f"nothing. Remove the range check, or measure a "
                    f"different object (R-R).")
            else:
                detail = (
                    f"range check '{label}' measures the same line as "
                    f"the scale on frame {ref_frame}. The scale comes "
                    f"from that line, so this check tests nothing. "
                    f"Remove the range check, or measure a different "
                    f"object (R-R).")
            errors.append(_err("RANGE_CHECK_ON_REFERENCE", field,
                               detail))
            refused.add(pos)
            break
    # A range check never re-measures a reference's object on any
    # frame (brief §51): an extent whose endpoints both lie within
    # 3 px of the reference's object on the range check's frame —
    # read from any mask of the same object (the §49 rule) — tests
    # nothing, since the scale comes from that object. Same-frame
    # overlaps are the §48 line rule's domain above (a same-frame
    # near-miss of the line still passes, as §48's tests pin), so
    # the object rule only looks at other frames.
    if ctx is not None:
        references = evidence.get("references", [])
        if isinstance(references, list):
            objects = []
            for ref in references:
                if not isinstance(ref, dict):
                    continue
                try:
                    measure = int((ref.get("extent_px", {}) or {}).get(
                        "frame"))
                except (TypeError, ValueError, AttributeError):
                    continue
                if isinstance(measure, bool):
                    continue
                name = ref.get("name")
                if not isinstance(name, str) or not name.strip():
                    name = "reference"
                name = name.strip()
                try:
                    frames = _reference_object_frames(ref, ctx)
                except Exception:  # noqa: BLE001 — total over input
                    frames = {}
                if frames:
                    objects.append((name, measure, frames))
            for pos, check in enumerate(checks):
                if pos in refused or not isinstance(check, dict):
                    continue
                field = f"range_checks[{pos}]"
                label = check.get("label", check.get("id", field))
                if not isinstance(label, str) or not label.strip():
                    label = field
                label = label.strip()
                try:
                    check_frame = int(check.get("frame", 0))
                except (TypeError, ValueError):
                    check_frame = 0
                extents = check.get("extents", [])
                if not isinstance(extents, list):
                    continue
                for extent in extents:
                    if not isinstance(extent, dict):
                        continue
                    frame_raw = extent.get("frame", check_frame)
                    if frame_raw is None:
                        frame_raw = check_frame
                    coords, frame = _ref_line_coords(
                        {**extent, "frame": frame_raw})
                    if coords is None:
                        continue
                    hit = None
                    for name, measure, frames in objects:
                        if frame == measure:
                            continue
                        try:
                            if _endpoints_on_object(frames, frame,
                                                    coords):
                                hit = (name, frame)
                                break
                        except Exception:  # noqa: BLE001
                            continue
                    if hit is None:
                        continue
                    name, frame = hit
                    errors.append(_err(
                        "RANGE_CHECK_ON_REFERENCE", field,
                        f"range check '{label}' re-measures the "
                        f"reference '{name}' on frame {frame}. The "
                        f"scale comes from that object, so this check "
                        f"tests nothing. Remove the range check, or "
                        f"measure a different object (R-R)."))
                    refused.add(pos)
                    break
    return errors, refused


def check_range_checks(evidence, ctx, m_per_px, sigma_m_per_px):
    """All range-code checks; returns ``(errors, scored, raises)``.

    ``scored`` holds the evidence item plus ``outcome``,
    ``delta_sigma`` and ``side`` per check, in order. ``raises``
    maps each raised check's position to ``{"from", "to", "unit"}``:
    the submitted σ and the floor it was raised to (brief §33).
    The scored σ is already the raised one, so scoring, the outcome,
    the sentence and the calculation step all use it; the step reads
    ``raises`` for its caveat.
    """
    errors = []
    scored = []
    raises: dict = {}
    checks = evidence.get("range_checks", [])
    if not isinstance(checks, list):
        return errors, scored, raises
    # A wrong verdict is worse than none: the extent geometry runs
    # before any range check is scored (brief §25).
    try:
        from .io import masks_on_frame  # noqa: PLC0415 — avoid a cycle
    except ImportError:
        masks_on_frame = None
    frame_masks: dict = {}
    if masks_on_frame is not None:
        for check in checks:
            if not isinstance(check, dict):
                continue
            for extent in check.get("extents", []) or []:
                if not isinstance(extent, dict):
                    continue
                try:
                    frame = int(extent.get("frame",
                                           check.get("frame", 0)))
                except (TypeError, ValueError):
                    continue
                if isinstance(frame, bool) or frame in frame_masks:
                    continue
                try:
                    frame_masks[frame] = masks_on_frame(ctx, frame)
                except Exception:
                    frame_masks[frame] = []
    extent_failed: set = set()
    frame_size = _extent_frame_size(ctx, evidence, frame_masks)
    for pos, check in enumerate(checks):
        if not isinstance(check, dict):
            continue
        try:
            errs, ok = _check_extent_geometry(
                check, pos, ctx, evidence, frame_size, frame_masks)
        except Exception:
            errs, ok = [], True
        errors.extend(errs)
        if not ok:
            extent_failed.add(pos)
    # A range check's lines are confirmed by ``check_line`` (brief
    # §28): every extent needs an agreeing record in this run's
    # ``artifacts/line_checks.jsonl``. A missing confirmation is a
    # hard reject like the other range-code checks; it never changes
    # the score.
    try:
        line_entries = _load_line_entries(ctx)
    except Exception:
        line_entries = []
    for pos, check in enumerate(checks):
        if not isinstance(check, dict):
            continue
        try:
            errors.extend(_check_line_confirmation(
                check, pos, line_entries))
        except Exception:
            continue
    # A range check never re-measures a reference (brief §48,
    # widened by §51 to the reference's object on any frame): an
    # extent on a reference line, or on the reference's object read
    # from any mask of it, tests nothing — the scale comes from that
    # line or object. A hard reject in a dry run and a real submit
    # alike; the refused check is scored not_counted below, so it
    # never decides the verdict.
    try:
        on_ref_errors, on_reference = check_range_on_reference(
            evidence, ctx)
    except Exception:
        on_ref_errors, on_reference = [], set()
    errors.extend(on_ref_errors)
    facts = web_search_facts(ctx)
    allowed_urls = set(facts)
    for pos, check in enumerate(checks):
        field = f"range_checks[{pos}]"
        if not isinstance(check, dict):
            scored.append(check)
            continue
        # A range check's σ below the floor is raised to the
        # floor (brief §33): the endpoint error plus the validator's
        # own scale σ. The validator uses max(σ, floor) everywhere —
        # scoring, delta_sigma, the outcome, the sentence and the
        # calculation step — and records the raise as a caveat on the
        # range check's step. Raising σ can only weaken a verdict,
        # never strengthen it. A σ that is not a finite positive
        # number is still an error.
        try:
            sigma_raw = float(check.get("sigma", 0.0))
        except (TypeError, ValueError):
            sigma_raw = None
        required = _required_sigma(check, m_per_px, sigma_m_per_px)
        if (sigma_raw is None or not math.isfinite(sigma_raw)
                or sigma_raw <= 0):
            errors.append(_err(
                "RANGE_SIGMA_TOO_SMALL", f"{field}.sigma",
                f"{field}: σ {check.get('sigma')!r} is not a finite "
                f"positive number: state the one-sigma error of the "
                f"measured value"))
            entry = {**check, **score_range(check)}
        elif (required is not None and math.isfinite(required)
                and sigma_raw < required):
            raised = dict(check)
            raised["sigma"] = float(required)
            entry = {**raised, **score_range(raised)}
            unit = check.get("unit", "ratio")
            if not isinstance(unit, str) or not unit:
                unit = "ratio"
            raises[pos] = {"from": float(sigma_raw),
                           "to": float(required), "unit": unit}
        else:
            entry = {**check, **score_range(check)}
        if pos in extent_failed or pos in on_reference:
            # A wrong verdict is worse than none: an extent that
            # leaves the picture or its mask is never scored (§25),
            # and a check re-measuring a reference line never decides
            # anything (§48).
            entry["outcome"] = "not_counted"
            entry["delta_sigma"] = 0.0
            entry["side"] = None
        scored.append(entry)
        # Provenance: value, σ and every extent endpoint in the
        # cited measurement artifact (as V2 does for numbers).
        rel = check.get("measurement_artifact")
        if not isinstance(rel, str) or not rel:
            errors.append(_missing(
                f"{field}.measurement_artifact",
                f"{field}.measurement_artifact is missing: the value, "
                f"σ and extents must be printed by a run_python "
                f"artifact in this run"))
            continue
        text = _artifact_text(rel, ctx)
        if text is None:
            errors.append(_missing(
                f"{field}.measurement_artifact",
                f"{rel!r} is missing or unreadable: the value, σ and "
                f"extents must appear in the cited measurement "
                f"artifact"))
            continue
        from .io import created_in_run  # noqa: PLC0415 — avoid a cycle

        if not created_in_run(rel, ctx):
            errors.append(_err(
                "RANGE_NUMBER_WITHOUT_PROVENANCE",
                f"{field}.measurement_artifact",
                f"{rel!r} was not created in this run: the ledger "
                f"shows no produced file or artifact by that path"))
            continue
        numbers = []
        for key in ("value", "sigma"):
            try:
                numbers.append((key, float(check.get(key))))
            except (TypeError, ValueError):
                pass
        for ext_pos, extent in enumerate(check.get("extents", [])
                                        or []):
            if not isinstance(extent, dict):
                continue
            for key in ("x1", "y1", "x2", "y2", "length_px"):
                try:
                    numbers.append((f"extents[{ext_pos}].{key}",
                                    float(extent.get(key))))
                except (TypeError, ValueError):
                    pass
        for name, number in numbers:
            if not _number_present(text, number):
                errors.append(_err(
                    "RANGE_NUMBER_WITHOUT_PROVENANCE", field,
                    f"{field}: {name} ({number!r}) does not appear in "
                    f"{rel!r}: every measured number cites the "
                    f"artifact that printed it"))
                break
        # Formula: the value recomputes from the extents within 2%.
        recomputed = _recomputed_value(check, m_per_px)
        if recomputed is not None:
            try:
                value = float(check.get("value", 0.0))
            except (TypeError, ValueError):
                value = None
            options = (recomputed if isinstance(recomputed, tuple)
                       else (recomputed,))
            ok = False
            for guess in options:
                if (value is not None and math.isfinite(value)
                        and math.isfinite(guess)
                        and abs(value) > 0):
                    if abs(guess - value) / abs(value) <= 0.02:
                        ok = True
            if not ok:
                shown = (
                    f"{recomputed:.6g}" if not isinstance(
                        recomputed, tuple) else " or ".join(
                            f"{g:.6g}" for g in recomputed))
                errors.append(_err(
                    "RANGE_FORMULA_MISMATCH", f"{field}.value",
                    f"{field}: the value {check.get('value')!r} does "
                    f"not recompute from the extents within 2% "
                    f"(recomputed {shown} from {check.get('formula')!r})"))
        # Sources: min and max each need a sourced quote carrying
        # the number, from this run's filtered web_search.
        ranging = check.get("range", {})
        sources = ranging.get("sources", []) if isinstance(
            ranging, dict) else []
        if isinstance(ranging, dict) and isinstance(sources, list):
            for bound_name in ("min", "max"):
                try:
                    bound = float(ranging.get(bound_name))
                except (TypeError, ValueError):
                    continue
                found = False
                absent_url = None
                for source in sources:
                    if not isinstance(source, dict):
                        continue
                    if source.get("bound") != bound_name:
                        continue
                    url = source.get("url")
                    if not isinstance(url, str) or (
                            url not in allowed_urls):
                        continue
                    quote = source.get("quote", "")
                    texts = [record.get("quote", "") + "\n"
                             + record.get("text", "")
                             for record in facts.get(url, [])
                             if isinstance(record, dict)] or [""]
                    if not any(quote_contains_number(
                            quote,
                            source.get("quote_highlight", ""), bound,
                            fact_text=text) for text in texts):
                        continue
                    if not quote_in_search(quote, url, facts):
                        absent_url = url
                        continue
                    found = True
                    break
                if not found:
                    if absent_url is not None:
                        errors.append(_err(
                            "RANGE_SOURCE_MISSING",
                            f"{field}.range.sources",
                            quote_absent_detail(absent_url)))
                    else:
                        errors.append(_err(
                            "RANGE_SOURCE_MISSING",
                            f"{field}.range.sources",
                            f"{field}: no source quotes the {bound_name} "
                            f"bound ({bound!r}) with that number in its "
                            f"quote and a URL from this run's filtered "
                            f"web_search"))
        # The σ floor itself is applied above (brief §33): a σ
        # below the floor is raised, never an error. Only a σ that
        # is not a finite positive number is refused there.
    return errors, scored, raises


def check_reference_sources(evidence, ctx) -> list:
    """Each reference source's quote is one the search returned.

    A reference size rests on its sources (R-S6, R-R2 "as for reference
    sizes"): a source passes only when its ``quote`` appears in that
    URL's fact of this run's ``web_search`` records, in the fact's
    ``quote`` or ``text`` (brief §24). A quote not found fails with
    the §24 detail. A run with no ``web_search`` records at all has
    nothing to check a quote against, so the rule bites once the run
    searched (as every run that sources sizes does).
    """
    errors = []
    facts = web_search_facts(ctx)
    if not facts:
        return errors
    references = evidence.get("references", [])
    if not isinstance(references, list):
        return errors
    for pos, ref in enumerate(references):
        if not isinstance(ref, dict):
            continue
        sources = ref.get("sources", [])
        if not isinstance(sources, list):
            continue
        for spos, source in enumerate(sources):
            if not isinstance(source, dict):
                continue
            url = source.get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            url = url.strip()
            quote = source.get("quote", "")
            if quote_in_search(quote, url, facts):
                continue
            errors.append(_err(
                "RANGE_SOURCE_MISSING",
                f"references[{pos}].sources[{spos}].quote",
                quote_absent_detail(url)))
    return errors


def _pct(value) -> str:
    """A ratio as percent with one decimal, trailing zeros cut."""
    try:
        text = f"{float(value) * 100.0:.1f}"
    except (TypeError, ValueError):
        return str(value)
    return text.rstrip("0").rstrip(".")


def range_value_text(value, sigma, unit) -> str:
    """``value ± σ`` in display units for a range number."""
    if unit == "ratio":
        return (f"{_pct(value)} % ± {_pct(sigma)} %")
    if unit == "m":
        try:
            number = float(value)
            spread = float(sigma)
        except (TypeError, ValueError):
            return f"{value} ± {sigma} m"
        if 0.01 <= abs(number) < 10.0:
            return (f"{number * 100.0:.1f} ± {spread * 100.0:.1f} cm")
        if 0 < abs(number) < 0.01:
            return (f"{number * 1000.0:.1f} ± "
                    f"{spread * 1000.0:.1f} mm")
        return f"{number:.3f} ± {spread:.3f} m"
    if unit == "s":
        try:
            return f"{float(value):.2f} ± {float(sigma):.2f} s"
        except (TypeError, ValueError):
            return f"{value} ± {sigma} s"
    try:
        return f"{float(value):.2f} ± {float(sigma):.2f} {unit}"
    except (TypeError, ValueError):
        return f"{value} ± {sigma} {unit}"


def _bound_text(bound, unit) -> str:
    if unit == "ratio":
        return f"{_pct(bound)} %"
    if unit == "m":
        try:
            number = float(bound)
        except (TypeError, ValueError):
            return f"{bound} m"
        if 0.01 <= abs(number) < 10.0:
            text = f"{number * 100.0:.1f}"
            return f"{text.rstrip('0').rstrip('.')} cm"
        if 0 < abs(number) < 0.01:
            text = f"{number * 1000.0:.1f}"
            return f"{text.rstrip('0').rstrip('.')} mm"
        return f"{number:.3f} m"
    try:
        return f"{float(bound):.2f} {unit}"
    except (TypeError, ValueError):
        return f"{bound} {unit}"


def _range_span_text(check) -> str:
    try:
        ranging = check.get("range", {})
        unit = check.get("unit", "ratio")
        return (f"{_bound_text(ranging.get('min'), unit)}–"
                f"{_bound_text(ranging.get('max'), unit)}")
    except (TypeError, ValueError, AttributeError):
        return ""


def format_range_sentence(kind, place, check, scored) -> str:
    """Display sentence for a range-decided verdict (brief §20)."""
    label = check.get("label", check.get("id", "range check"))
    numbers = range_value_text(check.get("value"), check.get("sigma"),
                              check.get("unit", "ratio"))
    what = (check.get("range", {}) or {}).get("what", "quoted range")
    if kind == "impossible":
        side = scored.get("side")
        word = "below" if side == "below" else "above"
        edge = "minimum" if side == "below" else "maximum"
        bound_name = "min" if side == "below" else "max"
        try:
            bound = float((check.get("range", {}) or {}).get(bound_name))
        except (TypeError, ValueError):
            bound = 0.0
        try:
            delta = float(scored.get("delta_sigma", 0.0))
        except (TypeError, ValueError):
            delta = 0.0
        return (f"Not realistic on {place}: {label} {numbers} is "
                f"{delta:.1f}σ {word} the {what} {edge} of "
                f"{_bound_text(bound, check.get('unit', 'ratio'))}.")
    span = _range_span_text(check)
    return (f"Realistic on {place}: {label} {numbers} is inside the "
            f"{what} range {span}.")


def combine_parts(gravity, scored, candidates):
    """Combine the gravity part with the range parts (part 02 §9).

    ``gravity`` is ``(status, preview)`` with status one of
    ``realistic``, ``not_realistic``, ``retimed``, ``undetermined``
    or ``absent``. Returns ``(kind, world, decided_by, reason)``.
    """
    status, _preview = gravity
    scene = candidates[0] if candidates else "Earth"
    scored = [s for s in scored if isinstance(s, dict)]
    live = [s for s in scored
            if s.get("outcome") in ("inside", "outside")]
    outside = [s for s in live if s.get("outcome") == "outside"]
    inside = [s for s in live if s.get("outcome") == "inside"]
    # Below the minimum is reported, never decisive (brief §38):
    # it cannot make the verdict "not realistic" on its own, and
    # the verdict comes from the other checks above.
    below = [s for s in scored if s.get("outcome") == "below"]
    if status == "not_realistic" or outside:
        if outside:
            first = outside[0]
            side = first.get("side")
            word = "below" if side == "below" else "above"
            return ("impossible", scene, first.get("id"),
                    f"{first.get('label', first.get('id'))} is "
                    f"{float(first.get('delta_sigma', 0.0)):.1f}σ "
                    f"{word} its range")
        return ("impossible", scene, "gravity", None)
    if status == "retimed":
        return ("retimed", None, "gravity", None)
    if status == "realistic" or inside:
        if status == "realistic":
            return ("world", None, "gravity", None)
        return ("world", scene, inside[0].get("id"), None)
    if below:
        first = below[0]
        return ("undetermined", None, first.get("id"),
                f"{first.get('label', first.get('id'))} is below "
                f"the typical range")
    # Otherwise undetermined, with the first undetermined part's
    # reason.
    if status == "undetermined":
        return ("undetermined", None, "gravity", None)
    return ("undetermined", None, None, None)


def range_calc_steps(scored, m_per_px=None, raises=None) -> list:
    """One calculation step per range check (brief §§20, 29).

    The step-id vocabulary (part 12 §6) has no range-check id, and
    part 12 owns it, so range steps reuse ``scale`` with the title
    ``Range check <name>``: ``<measured> = <length_px> px × <s>
    m/px`` against the quoted range ``[lo, hi]``, with in or out as
    a chip. The vocabulary stays that of part 12. ``raises`` is the
    ``check_range_checks`` raise map: a raised σ is recorded as a
    caveat on its step (brief §33).
    """
    steps = []
    if not isinstance(raises, dict):
        raises = {}
    for pos, entry in enumerate(scored):
        if not isinstance(entry, dict):
            continue
        outcome = entry.get("outcome", "not_counted")
        numbers = range_value_text(entry.get("value"),
                                  entry.get("sigma"),
                                  entry.get("unit", "ratio"))
        label = str(entry.get("label", entry.get("id", "range")))
        what = (entry.get("range", {}) or {}).get("what",
                                                  "quoted range")
        span = _range_span_text(entry)
        # A check below the minimum reads "below the typical
        # range" (brief §38), never "outside".
        outcome_text = ("below the typical range"
                        if outcome == "below" else outcome)
        full = (f"{entry.get('id', 'range')}: "
                f"{label}: {numbers} "
                f"against the {what} range {span}: {outcome_text}.")
        try:
            frame = entry.get("frame")
            frame = int(frame) if frame is not None else None
        except (TypeError, ValueError):
            frame = None
        formula_text = _range_formula_text(entry, numbers, m_per_px)
        if outcome == "inside":
            chip = {"text": "inside", "tone": "intermediate"}
        elif outcome == "outside":
            chip = {"text": "outside", "tone": "final"}
        elif outcome == "below":
            chip = {"text": "below", "tone": "intermediate"}
        else:
            chip = None
        # A raised σ is recorded as a caveat on the step (brief
        # §33): "σ raised from ... (endpoint and scale floor)".
        caveats = []
        record = raises.get(pos)
        if isinstance(record, dict):
            try:
                raised_from = float(record.get("from"))
                raised_to = float(record.get("to"))
            except (TypeError, ValueError):
                raised_from, raised_to = None, None
            unit = record.get("unit")
            if not isinstance(unit, str) or not unit:
                unit = "ratio"
            if (raised_from is not None and raised_to is not None
                    and math.isfinite(raised_from)
                    and math.isfinite(raised_to)):
                caveats.append({
                    "text": (f"σ raised from {raised_from:g} {unit} "
                             f"to {raised_to:g} {unit} (endpoint and "
                             f"scale floor)"),
                    "artifact": None})
        steps.append({
            "id": "scale",
            "title": f"Range check {label}",
            "frame": frame,
            "frame_end": None,
            "segment_id": None,
            "short": [
                {"type": "text",
                 "text": f"Measured {label} against its quoted range."},
                {"type": "formula", "latex": formula_text,
                 "fallback": formula_text, "chip": chip},
            ],
            "full": [{"type": "text", "text": full}],
            "caveats": caveats,
        })
    return steps


def _range_formula_text(entry, numbers, m_per_px=None) -> str:
    """The substituted formula for one range-check step (§29)."""
    label = str(entry.get("label", entry.get("id", "range")))
    ranging = entry.get("range", {}) if isinstance(
        entry.get("range"), dict) else {}
    unit = entry.get("unit", "ratio")
    try:
        lo = _bound_text(ranging.get("min"), unit)
        hi = _bound_text(ranging.get("max"), unit)
    except (TypeError, ValueError):
        lo, hi = "?", "?"
    outcome = entry.get("outcome", "not_counted")
    if outcome == "below":
        outcome = "below the typical range"
    extents = entry.get("extents", [])
    lengths = []
    if isinstance(extents, list):
        for extent in extents:
            if not isinstance(extent, dict):
                continue
            try:
                lengths.append(float(extent.get("length_px")))
            except (TypeError, ValueError):
                continue
    if (bool(entry.get("uses_scale")) and len(lengths) == 1
            and m_per_px):
        try:
            scale = float(m_per_px)
        except (TypeError, ValueError):
            scale = 0.0
        if scale > 0:
            return (f"{label} = {lengths[0]:.1f} px x "
                    f"{scale:.6f} m/px = {numbers} against "
                    f"[{lo}, {hi}]: {outcome}")
    return (f"{label} = {entry.get('formula', '')} = {numbers} "
            f"against [{lo}, {hi}]: {outcome}")

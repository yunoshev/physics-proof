# generated from brief/11 · part 11 owns this file
"""Submit-time checks V2–V12, verdict computation and assembly (§§2–3).

Every check is a comparison, a mask-overlap computation, or a
recompute with a part-09 helper. There is no second model and no
judgement call here. All functions are total over schema-valid input:
unexpected shapes become error records, never exceptions.
"""

from __future__ import annotations

import math
import re

from src import config as _config
from src.helpers.physics import fit_parabola, ghost

from .checks import (
    PUSH_CODES,
    REQUIRED_COMPONENTS,
    SAME_OBJECT_IOU,
    WORLD_G,
)
from .io import (
    ROW_FORMAT,
    artifact_set,
    created_in_run,
    format_g,
    frame_time,
    load_json_rel,
    load_mask_frame,
    load_object_masks,
    load_track_rows,
    load_wonder,
    mask_frames_for_object,
    mask_iou_on_frame,
    normalize_context,
    reference_scale,
    selfbuilt_name_from_path,
    timing_numbers,
    timing_sets,
)
from .ranges import (_to_base, check_range_checks,
                     check_reference_sources, named_units,
                     range_calc_steps)
from .v1 import check_v1

__all__ = [
    "DRY_RUN_HARD_HEADER",
    "DRY_RUN_PUSH_HEADER",
    "assemble_result",
    "decide_verdict",
    "format_dry_run_reply",
    "run_checks",
    "validate",
]


def _err(code, field, detail) -> dict:
    return {"code": str(code), "field": str(field),
            "detail": str(detail)}


def _missing(field, detail) -> dict:
    return _err("MISSING_FIELD", field, detail)


# --- small structured helpers ---------------------------------------------

def _norm_text(value) -> str:
    return str(value or "").strip()


def _words(text: str) -> set:
    import re

    return {w for w in re.split(r"[^a-z0-9]+", str(text).lower())
            if len(w) > 3}


_STOP = {"with", "from", "that", "this", "inside", "same", "left",
        "tinted", "square", "region", "figure", "mass", "part"}


def _blind_answered(alt_text: str, readings) -> bool:
    """A blind-check alternative is answered by an evidence reading."""
    words = _words(alt_text) - _STOP
    if not words:
        return True
    for reading in readings or []:
        if not isinstance(reading, dict):
            continue
        got = _words(reading.get("description", "")) - _STOP
        if len(words & got) >= 2:
            return True
    return False


def _alt_content_words(text: str) -> set:
    """Content words for §27 derivation matching (keeps 3-letter words).

    ``_words`` drops 3-letter words (``cap``, ``box``), which would make
    a copied alternative such as ``cap-like`` versus ``cap`` never
    match. Here a word counts when it has at least 3 letters, so the
    agent copying the alternative's own words always matches.
    """
    import re

    return {w for w in re.split(r"[^a-z0-9]+", str(text).lower())
            if len(w) >= 3}


_JUSTIFY_CUES = (
    "does not",
    "doesn't",
    "do not",
    "don't",
    "outside",
    "exclud",
    "irrelevant",
    "because",
    "since",
    "instead",
    "without",
)


def _derivation_texts(ref) -> list:
    """Every display string inside ``size_derivation`` (no schema change)."""
    try:
        derivation = ref.get("size_derivation")
    except AttributeError:
        return []
    out: list = []

    def _collect(value):
        if isinstance(value, str):
            if value.strip():
                out.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                _collect(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                _collect(item)

    _collect(derivation)
    return out


def _answered_by_derivation(alt_text: str, ref) -> bool:
    """A blind-check alternative answered by a ``size_derivation`` sentence.

    The sentence quotes the alternative (at least three of its content
    words, matched on the alternative's own words so hyphen variants
    such as ``cap-like`` versus ``cap`` never block) and says why it
    does not change the size (brief §27).
    """
    words = _alt_content_words(alt_text) - _STOP
    # Generic words alone never force a match: without content words
    # there is nothing to quote.
    words = {w for w in words if w not in ("the", "and", "with")}
    if len(words) < 3:
        return False
    for text in _derivation_texts(ref):
        lowered = text.lower()
        got = _alt_content_words(text) - _STOP
        if len(words & got) < 3:
            continue
        if any(cue in lowered for cue in _JUSTIFY_CUES):
            return True
        # A bare negation word ("not", "no", "never") as a whole word
        # also states a reason.
        import re

        tokens = set(re.split(r"[^a-z0-9']+", lowered))
        if tokens & {"not", "no", "never", "nobody", "none"}:
            return True
    return False


def _weighted_mean(pairs):
    """Inverse-variance weighted mean of ``[(value, sigma)]``."""
    total_w = 0.0
    total = 0.0
    for value, sigma in pairs:
        if not (math.isfinite(value) and math.isfinite(sigma)):
            return None, None
        if sigma <= 0:
            return None, None
        weight = 1.0 / (sigma * sigma)
        total_w += weight
        total += weight * value
    if total_w <= 0:
        return None, None
    mean = total / total_w
    sigma_mean = math.sqrt(1.0 / total_w)
    values = [v for v, _ in pairs]
    spread = (max(values) - min(values)) / 2.0 if len(values) > 1 else 0.0
    return float(mean), float(max(sigma_mean, spread))


def _clock_interval(clock):
    """Clock-only stretch interval ``(lo, hi, centre)`` (brief §9.2)."""
    try:
        rate = float(clock["measured_rate_hz"])
        rsig = float(clock.get("measured_rate_sigma_hz", 0.0))
        lo_nat = float(clock["natural_range_hz"][0])
        hi_nat = float(clock["natural_range_hz"][1])
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    if not (math.isfinite(rate) and rate > 0):
        return None
    if not (math.isfinite(rsig) and rsig >= 0):
        return None
    if not (math.isfinite(lo_nat) and math.isfinite(hi_nat)):
        return None
    if hi_nat < lo_nat:
        return None
    mult = 2.0 if clock.get("interpretation") == "stride" else 1.0
    eff = rate * mult
    esig = rsig * mult
    hi_rate = eff + 2.0 * esig
    lo_rate = eff - 2.0 * esig
    if hi_rate <= 0:
        return None
    lo = lo_nat / hi_rate
    hi = float("inf") if lo_rate <= 0 else hi_nat / lo_rate
    if not math.isfinite(hi):
        centre = lo * 2.0 if lo > 0 else 0.0
    else:
        centre = (lo + hi) / 2.0
    return lo, hi, centre


# --- EXAMPLE_VALUE_COPIED (§23) --------------------------------------------

def _example_values():
    """Reference names and source URLs from the two example evidences."""
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent.parent
    names: set = set()
    urls: set = set()
    for rel in ("src/contract/evidence.example.json",
                "fixtures/still-range/evidence.json"):
        try:
            import json as _json

            evidence = _json.loads(
                (repo / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(evidence, dict):
            continue
        for ref in evidence.get("references", []) or []:
            if not isinstance(ref, dict):
                continue
            name = ref.get("name")
            if isinstance(name, str) and name.strip():
                names.add(name.strip())
            for source in ref.get("sources", []) or []:
                if not isinstance(source, dict):
                    continue
                url = source.get("url")
                if isinstance(url, str) and url.strip():
                    urls.add(url.strip())
        for check in evidence.get("range_checks", []) or []:
            if not isinstance(check, dict):
                continue
            ranging = check.get("range", {})
            sources = ranging.get("sources", []) if isinstance(
                ranging, dict) else []
            for source in sources or []:
                if not isinstance(source, dict):
                    continue
                url = source.get("url")
                if isinstance(url, str) and url.strip():
                    urls.add(url.strip())
    return names, urls


def _own_records_text(ctx) -> str:
    """Clip's own words: web_search results + run_python artifacts."""
    from pathlib import Path

    parts = []
    artifacts = []
    try:
        artifacts = list((ctx or {}).get("artifacts", []) or [])
    except AttributeError:
        artifacts = []
    from .io import load_json_rel as _load

    for rel in artifacts:
        name = str(rel)
        if "web_search" not in name or not name.endswith(".json"):
            continue
        ok, value, _ = _load(rel, ctx)
        if not ok or not isinstance(value, dict):
            continue
        facts = value.get("facts", [])
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            for key in ("text", "quote"):
                text = fact.get(key)
                if isinstance(text, str):
                    parts.append(text)
    produced = []
    try:
        produced = list((ctx or {}).get("produced_files", []) or [])
    except AttributeError:
        produced = []
    try:
        base = Path(str((ctx or {}).get("run_dir", ".") or "."))
    except (TypeError, ValueError):
        return "\n".join(parts)
    for rel in produced:
        name = str(rel)
        lower = name.lower()
        # Evidence, submit and check artifacts carry the agent's own
        # words back: only run_python products count here.
        if "run_python" not in lower:
            continue
        if not lower.endswith((".py", ".txt", ".json")):
            continue
        if ".." in name.split("/"):
            continue
        try:
            target = base / name
            if not target.is_file() or target.stat().st_size > 1 << 20:
                continue
            parts.append(target.read_text(encoding="utf-8",
                                          errors="replace"))
        except (OSError, ValueError):
            continue
    return "\n".join(parts)


def _check_example_copied(evidence, ctx):
    """A reference name or source URL from the examples (§23)."""
    from .ranges import web_search_urls

    names, urls = _example_values()
    if not names and not urls:
        return []
    own_text = _own_records_text(ctx).lower()
    allowed_urls = web_search_urls(ctx)
    errors = []
    for pos, ref in enumerate(evidence.get("references", []) or []):
        if not isinstance(ref, dict):
            continue
        name = ref.get("name")
        if (isinstance(name, str) and name.strip() in names
                and name.strip().lower() not in own_text):
            errors.append(_err(
                "EXAMPLE_VALUE_COPIED",
                f"references[{pos}].name",
                f"references[{pos}].name {name.strip()!r}: this comes "
                f"from the example, not from your clip; measure your "
                f"own object and search its size"))
        for spos, source in enumerate(ref.get("sources", []) or []):
            if not isinstance(source, dict):
                continue
            url = source.get("url")
            if (isinstance(url, str) and url.strip() in urls
                    and url.strip() not in allowed_urls):
                errors.append(_err(
                    "EXAMPLE_VALUE_COPIED",
                    f"references[{pos}].sources[{spos}].url",
                    f"references[{pos}].sources[{spos}].url "
                    f"{url.strip()!r}: this comes from the example, "
                    f"not from your clip; measure your own object "
                    f"and search its size"))
    for pos, check in enumerate(evidence.get("range_checks", [])
                                or []):
        if not isinstance(check, dict):
            continue
        ranging = check.get("range", {})
        sources = ranging.get("sources", []) if isinstance(
            ranging, dict) else []
        for spos, source in enumerate(sources or []):
            if not isinstance(source, dict):
                continue
            url = source.get("url")
            if (isinstance(url, str) and url.strip() in urls
                    and url.strip() not in allowed_urls):
                errors.append(_err(
                    "EXAMPLE_VALUE_COPIED",
                    f"range_checks[{pos}].range.sources[{spos}].url",
                    f"range_checks[{pos}].range.sources[{spos}].url "
                    f"{url.strip()!r}: this comes from the example, "
                    f"not from your clip; measure your own object "
                    f"and search its size"))
    clock = evidence.get("clock")
    if isinstance(clock, dict):
        natural = clock.get("natural_range_source", {})
        url = natural.get("url") if isinstance(natural, dict) else None
        if (isinstance(url, str) and url.strip() in urls
                and url.strip() not in allowed_urls):
            errors.append(_err(
                "EXAMPLE_VALUE_COPIED", "clock.natural_range_source.url",
                f"clock.natural_range_source.url {url.strip()!r}: "
                f"this comes from the example, not from your clip; "
                f"measure your own object and search its size"))
    return errors


# --- V2/V8 track loading and fitting --------------------------------------

def _segment_window(segment):
    try:
        frames = segment["frames"]
        return (int(frames["start"]), int(frames["apex"]),
                int(frames["end"]))
    except (KeyError, TypeError, ValueError):
        return None


def _load_segment_track(segment, index, ctx):
    field = f"segments[{index}].track_artifact"
    rel = segment.get("track_artifact") if isinstance(segment, dict) else None
    if not isinstance(rel, str) or not rel:
        return None, [_missing(field, f"{field} is missing: expected "
                                      f"{ROW_FORMAT}")]
    ok, rows, detail = load_track_rows(rel, ctx)
    if not ok:
        return None, [_missing(field, detail)]
    if not created_in_run(rel, ctx):
        return None, [_err(
            "NUMBER_WITHOUT_PROVENANCE", field,
            f"{rel!r} was not created in this run: the ledger shows "
            f"no produced file or artifact by that path")]
    return rows, []


def _fit_segment(rows, level_y_px, m_per_px, ctx):
    """Refit one track: ``(result, error)`` in metres, y up."""
    times = []
    heights = []
    for row in rows:
        moment = frame_time(row["frame"], ctx)
        if moment is None:
            return None, "no video time for frame %d" % row["frame"]
        times.append(moment)
        heights.append((level_y_px - row["y_px"]) * m_per_px)
    try:
        return fit_parabola(times, heights), ""
    except ValueError as exc:
        return None, str(exc)


def _takeoff_level(rows, start_frame):
    for row in rows:
        if row["frame"] == start_frame:
            return row["y_px"], row["x_px"]
    return rows[0]["y_px"], rows[0]["x_px"]


# --- dropped references (§26) ---------------------------------------------

def _significant_words(name: str) -> set:
    words = _words(name or "") - _STOP
    return {w for w in words if len(w) > 3}


def _covers_something_else(ref_name, coverage) -> bool:
    """The blind check recorded that the mask covers something else."""
    if not isinstance(coverage, str) or not coverage.strip():
        return False
    lowered = coverage.lower()
    if "something else" in lowered:
        return True
    if "different" in lowered or " other " in f" {lowered} ":
        return True
    words = _significant_words(ref_name or "")
    if not words:
        return False
    return all(w not in _words(lowered) for w in words)


def _mask_frame_of(ref):
    """The measuring frame of a reference, or None (brief §46)."""
    try:
        mask = ref.get("mask", {}) if isinstance(ref, dict) else {}
        frame = mask.get("frame", None)
        return int(frame) if not isinstance(frame, bool) else None
    except (TypeError, ValueError, AttributeError):
        pass
    try:
        extent = ref.get("extent_px", {}) if isinstance(ref, dict) else {}
        frame = extent.get("frame", None)
        return int(frame) if not isinstance(frame, bool) else None
    except (TypeError, ValueError, AttributeError):
        return None


def _same_reference_object(early, final, ctx) -> bool:
    """Same measured object in two evidences (brief §46).

    The same mask artifact and object id, or masks that overlap by
    more than 50 % of the smaller mask on the measuring frame.
    Total: never raises.
    """
    try:
        early_mask = early.get("mask", {}) if isinstance(
            early, dict) else {}
        final_mask = final.get("mask", {}) if isinstance(
            final, dict) else {}
        early_art = early_mask.get("artifact")
        final_art = final_mask.get("artifact")
        if (isinstance(early_art, str) and early_art
                and early_art == final_art
                and str(early_mask.get("object_id"))
                == str(final_mask.get("object_id"))):
            return True
    except AttributeError:
        pass
    try:
        from .io import load_mask_frame as _load
    except ImportError:
        return False
    frame = _mask_frame_of(final)
    if frame is None:
        frame = _mask_frame_of(early)
    if frame is None:
        return False
    try:
        early_art = early.get("mask", {}).get("artifact")
        early_oid = early.get("mask", {}).get("object_id")
        final_art = final.get("mask", {}).get("artifact")
        final_oid = final.get("mask", {}).get("object_id")
        mask_e = _load(early_art, early_oid, frame, ctx)
        mask_f = _load(final_art, final_oid, frame, ctx)
    except (TypeError, ValueError, AttributeError):
        return False
    if mask_e is None or mask_f is None:
        return False
    try:
        if mask_e.shape != mask_f.shape:
            return False
        import numpy as _np

        small = min(int(mask_e.sum()), int(mask_f.sum()))
        if small <= 0:
            return False
        inter = int(_np.logical_and(mask_e, mask_f).sum())
    except (TypeError, ValueError):
        return False
    return inter / small > 0.5


def _reference_settled(early, final, ctx) -> bool:
    """A dry-run reference corrected, not dropped (brief §46).

    The final evidence carries a reference on the same object (the
    same mask artifact and object id, or masks overlapping by more
    than 50 % on the measuring frame) and either its
    ``size_derivation`` is a ``sum`` whose sources include the
    earlier quoted value (R-S15), or it has the same size measured
    on another frame (R-S14). Total: never raises.
    """
    try:
        if not _same_reference_object(early, final, ctx):
            return False
    except (TypeError, ValueError, AttributeError):
        return False
    try:
        early_size = float(early.get("size_m"))
        final_size = float(final.get("size_m"))
    except (TypeError, ValueError, AttributeError):
        return False
    if not (math.isfinite(early_size) and early_size > 0
            and math.isfinite(final_size) and final_size > 0):
        return False
    # Same size measured on another frame (R-S14).
    try:
        early_frame = _mask_frame_of(early)
        final_frame = _mask_frame_of(final)
    except (TypeError, ValueError, AttributeError):
        early_frame = final_frame = None
    if (early_frame is not None and final_frame is not None
            and early_frame != final_frame
            and abs(final_size - early_size) / early_size <= 0.01):
        return True
    # A part/whole correction (R-S15): the final size is a ``sum``
    # whose sources include the earlier quoted value.
    try:
        derivation = final.get("size_derivation", {})
        mode = derivation.get("mode") if isinstance(
            derivation, dict) else None
    except AttributeError:
        return False
    if mode != "sum":
        return False
    final_quoted = [value for _, value in _quoted_values(final)]
    early_quoted = [value for _, value in _quoted_values(early)]
    early_quoted.append(early_size)
    for old in early_quoted:
        try:
            old_f = float(old)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(old_f) and old_f > 0):
            continue
        for new in final_quoted:
            try:
                new_f = float(new)
            except (TypeError, ValueError):
                continue
            if (math.isfinite(new_f) and new_f > 0
                    and abs(new_f - old_f) / old_f <= 0.01):
                return True
    return False


def _final_refs_agree(final_refs) -> bool:
    """Every final reference pair agrees (brief §46 clearing rule).

    Pairwise 2σ agreement plus the §15/§39 gap rule: a pair more
    than 5 % apart needs a tight third reference within 2σ of both.
    Total: never raises.
    """
    infos = []
    for ref in final_refs or []:
        if not isinstance(ref, dict):
            return False
        try:
            m_per_px, sigma = reference_scale(ref)
        except (TypeError, ValueError, AttributeError):
            return False
        if m_per_px is None or sigma is None:
            return False
        try:
            if not (math.isfinite(m_per_px) and math.isfinite(sigma)
                    and sigma > 0):
                return False
        except TypeError:
            return False
        infos.append((m_per_px, sigma))
    for left in range(len(infos)):
        for right in range(left + 1, len(infos)):
            ma, sa = infos[left]
            mb, sb = infos[right]
            try:
                combined = math.sqrt(sa * sa + sb * sb)
            except (TypeError, ValueError):
                return False
            if combined <= 0 or abs(ma - mb) > 2.0 * combined:
                return False
            mean = (ma + mb) / 2.0
            if mean > 0 and abs(ma - mb) / mean > 0.05:
                settled = False
                for pos, (mo, so) in enumerate(infos):
                    if pos == left or pos == right:
                        continue
                    try:
                        rel = so / mo if mo > 0 else float("inf")
                    except (TypeError, ZeroDivisionError):
                        continue
                    if not math.isfinite(rel) or rel > 0.05:
                        continue
                    try:
                        near_a = (abs(mo - ma) <= 2.0 * math.sqrt(
                            so * so + sa * sa))
                        near_b = (abs(mo - mb) <= 2.0 * math.sqrt(
                            so * so + sb * sb))
                    except (TypeError, ValueError):
                        continue
                    if near_a and near_b:
                        settled = True
                        break
                if not settled:
                    return False
    return True


def _earlier_evidences(ctx):
    """Every ``artifacts/t*_evidence.json`` in the run, in order."""
    from pathlib import Path

    try:
        base = Path(str(ctx.get("run_dir", ".") or "."))
    except (TypeError, ValueError):
        return []
    try:
        paths = sorted((base / "artifacts").glob("t*_evidence.json"))
    except OSError:
        return []
    out = []
    for path in paths:
        try:
            import json as _json

            value = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def _dropped_disagreement(evidence, ctx, mean_m, sigma_mean):
    """A run-measured reference the final evidence dropped (§26).

    Returns ``(name_d, m_d, s_d, name_k, m_k)`` for the first dropped
    reference that disagrees with the kept scale beyond 2σ, or None.
    A dropped reference stops counting only when the final evidence's
    ``second_reference_absent_reason`` names it and its blind mask
    check recorded that it covers something else.
    """
    try:
        final_refs = evidence.get("references", []) or []
    except AttributeError:
        return None
    if not isinstance(final_refs, list):
        return None
    final_names = set()
    for ref in final_refs:
        if isinstance(ref, dict) and isinstance(ref.get("name"), str):
            final_names.add(ref["name"].strip().lower())
    try:
        scale = evidence.get("scale", {}) if isinstance(
            evidence.get("scale"), dict) else {}
        absent = scale.get("second_reference_absent_reason")
    except AttributeError:
        absent = None
    absent_text = absent.lower() if isinstance(absent, str) else ""
    kept_name = None
    kept_m = mean_m
    try:
        if len(final_refs) == 1 and isinstance(final_refs[0], dict):
            kept_name = final_refs[0].get("name", "kept scale")
            if not isinstance(kept_name, str) or not kept_name.strip():
                kept_name = "kept scale"
    except (TypeError, AttributeError):
        kept_name = "kept scale"
    if kept_name is None:
        kept_name = "kept scale"
    if mean_m is None or sigma_mean is None:
        return None
    try:
        if not (math.isfinite(mean_m) and math.isfinite(sigma_mean)):
            return None
    except TypeError:
        return None
    seen: dict = {}
    for earlier in _earlier_evidences(ctx):
        refs = earlier.get("references", [])
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            name = ref.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            key = name.strip().lower()
            if key in final_names:
                continue
            seen[key] = ref
    for key, ref in seen.items():
        name = ref.get("name", key)
        # A part/whole correction settles the disagreement (brief
        # §46): the final evidence carries the same object with a
        # ``sum`` size that includes the earlier quoted value, or
        # the same size on another frame. A settled reference stops
        # counting, like a present one.
        try:
            settled = any(
                _reference_settled(ref, kept, ctx)
                for kept in (final_refs or [])
                if isinstance(kept, dict))
        except (TypeError, ValueError, AttributeError):
            settled = False
        if settled:
            continue
        # Excused only when the absent reason names it and its own
        # blind check says it covers something else.
        names_it = (
            isinstance(absent_text, str) and absent_text
            and (key in absent_text
                 or any(w in absent_text
                        for w in _significant_words(name))))
        if names_it:
            check = ref.get("mask_check", {}) if isinstance(
                ref.get("mask_check"), dict) else {}
            artifact = check.get("artifact")
            coverage = None
            if isinstance(artifact, str) and artifact:
                from .io import load_json_rel as _load

                ok, value, _ = _load(artifact, ctx)
                if ok and isinstance(value, dict):
                    coverage = value.get("coverage_answer", "")
            if _covers_something_else(name, coverage):
                continue
        m_per_px, sigma = reference_scale(ref)
        if m_per_px is None or sigma is None:
            continue
        try:
            combined = math.sqrt(sigma * sigma
                                 + sigma_mean * sigma_mean)
        except (TypeError, ValueError):
            continue
        if combined <= 0:
            continue
        if abs(m_per_px - mean_m) > 2.0 * combined:
            return (name, m_per_px, sigma, kept_name, mean_m)
    return None


def _earlier_dry_run_evidences(ctx):
    """``{turn: (rel, evidence)}`` for ``artifacts/t*_evidence.json``.

    The validator reads this run's earlier dry runs: the evidence
    files, plus the ``t*_submit_errors.json`` lists below (brief
    §37). Anything unreadable is skipped, never an exception.
    """
    import re
    from pathlib import Path

    out = {}
    try:
        base = Path(str(ctx.get("run_dir", ".") or "."))
    except (TypeError, ValueError, AttributeError):
        return out
    try:
        paths = sorted((base / "artifacts").glob("t*_evidence.json"))
    except OSError:
        return out
    for path in paths:
        match = re.fullmatch(r"t(\d+)_evidence\.json", path.name)
        if match is None:
            continue
        try:
            import json as _json

            value = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict):
            out[int(match.group(1))] = (
                f"artifacts/{path.name}", value)
    return out


def _disagreement_report_turns(ctx):
    """Turns whose dry run reported a scale disagreement (§37).

    A dry run that told the agent to settle a scale disagreement
    leaves its error list in ``artifacts/t*_submit_errors.json``.
    Returns ``{turn: [codes]}`` for the disagreement codes
    ``REFERENCES_DISAGREE`` and ``THIRD_REFERENCE_REQUIRED``.
    """
    import re
    from pathlib import Path

    out = {}
    try:
        base = Path(str(ctx.get("run_dir", ".") or "."))
    except (TypeError, ValueError, AttributeError):
        return out
    try:
        paths = sorted(
            (base / "artifacts").glob("t*_submit_errors.json"))
    except OSError:
        return out
    for path in paths:
        match = re.fullmatch(r"t(\d+)_submit_errors\.json", path.name)
        if match is None:
            continue
        try:
            import json as _json

            value = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(value, list):
            continue
        codes = {error.get("code") for error in value
                 if isinstance(error, dict)}
        hit = sorted(codes & {"REFERENCES_DISAGREE",
                              "THIRD_REFERENCE_REQUIRED"})
        if hit:
            out[int(match.group(1))] = hit
    return out


def _dropped_reference_refusal(evidence, ctx):
    """``REFERENCE_DROPPED``: a reference dropped to escape a
    reported disagreement (brief §37).

    When an earlier dry run carried two or more references and a
    dry run reported ``REFERENCES_DISAGREE`` or
    ``THIRD_REFERENCE_REQUIRED``, the final evidence may not rest
    on one reference with a ``second_reference_absent_reason``:
    removing a reference never clears the disagreement. A run that
    never measured a second reference may still state an absence
    reason, as before.
    """
    references = evidence.get("references", [])
    if not isinstance(references, list) or len(references) != 1:
        return None
    scale = evidence.get("scale")
    if not isinstance(scale, dict):
        return None
    absent = scale.get("second_reference_absent_reason")
    if not isinstance(absent, str) or not absent.strip():
        return None
    earlier = _earlier_dry_run_evidences(ctx)
    carried = {turn: pair for turn, pair in earlier.items()
               if isinstance(pair[1].get("references"), list)
               and len(pair[1]["references"]) >= 2}
    if not carried:
        return None
    reports = _disagreement_report_turns(ctx)
    if not reports:
        return None
    # A part/whole correction settles a disagreement (brief §46): a
    # disagreement from a dry run is cleared when every reference in
    # it is settled or present in the final evidence (the same
    # object, corrected or not), and the final references agree
    # pairwise. Only a reference that leaves the evidence entirely
    # still needs §37's third reference.
    try:
        final_refs = evidence.get("references", [])
        cleared_all = _final_refs_agree(final_refs) and all(
            all(any(_same_reference_object(early_ref, kept_ref, ctx)
                    for kept_ref in (final_refs or [])
                    if isinstance(kept_ref, dict))
                for early_ref in (pair[1].get("references", []) or [])
                if isinstance(early_ref, dict))
            for pair in carried.values())
    except (TypeError, ValueError, AttributeError):
        cleared_all = False
    if cleared_all:
        return None
    kept = references[0].get("name") if isinstance(
        references[0], dict) else ""
    kept = kept.strip() if isinstance(kept, str) else ""
    kept_key = kept.lower()
    turn = min(carried)
    rel, early = carried[turn]
    dropped = None
    for ref in early.get("references", []):
        if not isinstance(ref, dict):
            continue
        name = ref.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if name.strip().lower() != kept_key:
            dropped = name.strip()
            break
    if dropped is None:
        dropped = "a second reference"
    codes = sorted({code for hits in reports.values()
                    for code in hits})
    return _err(
        "REFERENCE_DROPPED", "references",
        f"references: the run measured two references in {rel} "
        f"(dry run turn {turn}), but the final evidence rests on one "
        f"reference ({kept or 'kept scale'}) with a "
        f"second_reference_absent_reason, after a dry run reported "
        f"{' and '.join(codes)}: removing a reference never clears "
        f"the disagreement: settle it with three references, two of "
        f"which agree (R-S6). The dropped reference was "
        f"{dropped!r}.")


# --- a measured line is not hidden (brief §45) ----------------------------

#: Endpoints match when each end lies within this many pixels of the
#: evidence line's own endpoint (brief §45): a confirmed line is
#: reported when an evidence extent sits on the same line.
_HIDDEN_LINE_TOL_PX = 3.0


def _run_line_check_records(ctx):
    """``{turn: [lines]}`` for ``artifacts/t*_check_line_*.json``.

    Each line is ``{"frame", "coords", "claim"}`` with ``agrees``
    true: a line the second look confirmed. Anything unreadable is
    skipped, never an exception.
    """
    import json as _json
    import re
    from pathlib import Path

    out = {}
    try:
        base = Path(str(ctx.get("run_dir", ".") or "."))
    except (TypeError, ValueError, AttributeError):
        return out
    try:
        paths = sorted((base / "artifacts").glob("t*_check_line_*.json"))
    except OSError:
        return out
    for path in paths:
        match = re.fullmatch(r"t(\d+)_check_line_\d+\.json", path.name)
        if match is None:
            continue
        try:
            record = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        try:
            frame = int(record.get("frame"))
        except (TypeError, ValueError):
            continue
        if isinstance(frame, bool):
            continue
        lines = record.get("lines")
        if not isinstance(lines, list):
            continue
        kept = []
        for item in lines:
            if not isinstance(item, dict):
                continue
            if item.get("agrees") is not True:
                continue
            try:
                coords = ((float(item["x1"]), float(item["y1"])),
                          (float(item["x2"]), float(item["y2"])))
            except (KeyError, TypeError, ValueError):
                continue
            claim = item.get("claim")
            claim = claim.strip() if isinstance(claim, str) else ""
            kept.append({"frame": frame, "coords": coords,
                         "claim": claim})
        if kept:
            out.setdefault(int(match.group(1)), []).extend(kept)
    return out


def _ends_close_3(first, second) -> bool:
    """Two endpoints within 3 px of each other (brief §45)."""
    try:
        gap = math.hypot(float(first[0]) - float(second[0]),
                         float(first[1]) - float(second[1]))
    except (TypeError, ValueError):
        return False
    return gap <= _HIDDEN_LINE_TOL_PX + 1e-9


def _same_line_3(left, right) -> bool:
    """Two measured lines on the same line, either direction (§45)."""
    try:
        first_l, second_l = left
        first_r, second_r = right
    except (TypeError, ValueError):
        return False
    return ((_ends_close_3(first_l, first_r)
             and _ends_close_3(second_l, second_r))
            or (_ends_close_3(first_l, second_r)
                and _ends_close_3(second_l, first_r)))


def _evidence_lines(evidence):
    """``[(frame, coords)]`` for every measured line in the evidence.

    A reference's ``extent_px``, the scale's ``extent_px`` and every
    range-check extent: a confirmed ``check_line`` record on the same
    frame within 3 px of any of these is reported (brief §45).
    """
    out = []
    references = evidence.get("references", [])
    if isinstance(references, list):
        for ref in references:
            if not isinstance(ref, dict):
                continue
            coords, frame = _extent_line(ref.get("extent_px"))
            if coords is not None:
                out.append((frame, coords))
    scale = evidence.get("scale")
    if isinstance(scale, dict):
        coords, frame = _extent_line(scale.get("extent_px"))
        if coords is not None:
            out.append((frame, coords))
    checks = evidence.get("range_checks", [])
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict):
                continue
            try:
                check_frame = int(check.get("frame", 0))
            except (TypeError, ValueError):
                continue
            if isinstance(check_frame, bool):
                continue
            extents = check.get("extents", [])
            if not isinstance(extents, list):
                continue
            for extent in extents:
                if not isinstance(extent, dict):
                    continue
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
                out.append((frame, coords))
    return out


def _hidden_confirmed_line_refusal(evidence, ctx):
    """``REFERENCE_DROPPED``: a measured line left out (brief §45).

    A confirmed line (``agrees: true`` in one of this run's
    ``artifacts/t*_check_line_*.json`` records) is reported when an
    extent in the evidence — a reference, the scale, a range check —
    sits on the same frame with both endpoints within 3 px of it.
    When the evidence rests on one reference with a
    ``second_reference_absent_reason`` and an unreported confirmed
    line exists, the submit is refused: a reference the run measured
    is reported, and a disagreement is settled, not hidden. A run
    whose confirmed lines are all reported may still state an
    absence reason, as before.
    """
    references = evidence.get("references", [])
    if not isinstance(references, list) or len(references) != 1:
        return None
    scale = evidence.get("scale")
    if not isinstance(scale, dict):
        return None
    absent = scale.get("second_reference_absent_reason")
    if not isinstance(absent, str) or not absent.strip():
        return None
    try:
        records = _run_line_check_records(ctx)
    except (TypeError, ValueError, AttributeError):
        return None
    if not records:
        return None
    try:
        lines = _evidence_lines(evidence)
    except (TypeError, ValueError, AttributeError):
        lines = []
    for turn in sorted(records):
        for entry in records[turn]:
            try:
                reported = any(
                    entry["frame"] == frame
                    and _same_line_3(entry["coords"], coords)
                    for frame, coords in lines)
            except (TypeError, ValueError, AttributeError):
                continue
            if reported:
                continue
            first, second = entry["coords"]
            try:
                length = math.hypot(first[0] - second[0],
                                    first[1] - second[1])
            except (TypeError, ValueError):
                continue
            claim = entry.get("claim", "")
            if not isinstance(claim, str):
                claim = ""
            claim = claim.strip()
            if len(claim) > 60:
                claim = claim[:60].rstrip() + " …"
            return _err(
                "REFERENCE_DROPPED", "references",
                f"turn {turn}, frame {entry['frame']}: {claim!r}, "
                f"{int(length)} px, confirmed and not reported. A "
                f"reference you measured is reported; a disagreement "
                f"is settled, not hidden.{_PART_WHOLE_SENTENCE}")
    return None


# --- the checks ------------------------------------------------------------

def run_checks(evidence, ctx, dry_run=False):
    """All post-V1 checks. Returns ``(errors, computed)``.

    ``computed`` carries the refits, the scale and the verdict preview
    for assembly. Push codes (brief §16.2) are included only when
    ``dry_run`` is true; a real submit never reports them.
    """
    errors = []
    computed = {"segments": [], "scale_pairs": [], "fits_ok": True}
    segments = evidence.get("segments", [])
    references = evidence.get("references", [])

    # -- scale pairs first: every later metre conversion needs them ----
    pairs = []
    scales_ok = True
    for pos, ref in enumerate(references):
        if not isinstance(ref, dict):
            scales_ok = False
            continue
        m_per_px, sigma = reference_scale(ref)
        if m_per_px is None:
            errors.append(_missing(
                f"references[{pos}].extent_px",
                f"references[{pos}]: size over extent is not a positive "
                f"finite number"))
            scales_ok = False
            continue
        pairs.append((m_per_px, sigma))
    computed["scale_pairs"] = pairs
    if len(references) >= 2 and pairs and len(pairs) == len(references):
        mean_m, _ = _weighted_mean(pairs)
    else:
        mean_m = pairs[0][0] if pairs else None
    computed["m_per_px"] = mean_m
    computed["sigma_m_per_px"] = (
        _weighted_mean(pairs)[1] if pairs and len(pairs)
        == len(references) and len(pairs) > 1 else (
            pairs[0][1] if pairs else None))

    # -- §23: the example is not the clip --------------------------------
    errors.extend(_check_example_copied(evidence, ctx))

    # -- §20: at least one measurement ------------------------------------
    has_segments = any(isinstance(s, dict) for s in segments)
    has_ranges = any(isinstance(c, dict)
                     for c in (evidence.get("range_checks", []) or []))
    if not has_segments and not has_ranges:
        errors.append(_err(
            "MEASUREMENT_MISSING", "segments",
            "segments: neither a segment nor a range check: measure "
            "the motion or check a quantity against a sourced range"))

    # -- V2: recompute each headline fit from the track artifact -------
    seg_fits = []
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            seg_fits.append(None)
            continue
        window = _segment_window(segment)
        if window is None or mean_m is None:
            seg_fits.append(None)
            continue
        start, apex, end = window
        rows, track_errors = _load_segment_track(segment, index, ctx)
        errors.extend(track_errors)
        if rows is None:
            computed["fits_ok"] = False
            seg_fits.append(None)
            continue
        level_y, _ = _takeoff_level(rows, start)
        fit, problem = _fit_segment(rows, level_y, mean_m, ctx)
        if fit is None:
            errors.append(_missing(
                f"segments[{index}].track_artifact",
                f"segments[{index}]: the track cannot be refit "
                f"({problem}): expected {ROW_FORMAT}"))
            computed["fits_ok"] = False
            seg_fits.append(None)
            continue
        seg_fits.append({
            "rows": rows, "fit": fit, "level_y": level_y,
            "start": start, "apex": apex, "end": end,
        })
        errors.extend(_check_fit_curve(segment, index, rows, level_y,
                                       mean_m, fit, ctx))
    computed["segments"] = seg_fits

    # -- V6: contact/duplicate/cut exclusion -----------------------------
    dup_frames, cuts = timing_sets(ctx)
    for index, info in enumerate(seg_fits):
        if info is None:
            continue
        frames = {r["frame"] for r in info["rows"]}
        window = set(range(info["start"], info["end"] + 1))
        if not frames <= window:
            errors.append(_err(
                "FIT_INCLUDES_CONTACT_OR_DUP",
                f"segments[{index}].track_artifact",
                f"segments[{index}]: fitted frames "
                f"{sorted(frames - window)[:5]} lie outside the "
                f"[{info['start']}, {info['end']}] window"))
        hit = sorted(frames & set(dup_frames))
        if hit:
            errors.append(_err(
                "FIT_INCLUDES_CONTACT_OR_DUP",
                f"segments[{index}].track_artifact",
                f"segments[{index}]: fitted frames {hit[:5]} are "
                f"confirmed duplicates in timing.json"))
        crossed = _crossed_cuts(frames, cuts)
        if crossed:
            errors.append(_err(
                "FIT_INCLUDES_CONTACT_OR_DUP",
                f"segments[{index}].track_artifact",
                f"segments[{index}]: the fit window crosses a cut "
                f"{crossed}"))

    # -- V7: residual trend ----------------------------------------------
    for index, info in enumerate(seg_fits):
        if info is None:
            continue
        z_value = info["fit"].get("residual_trend_z", 0.0)
        try:
            z_value = float(z_value)
        except (TypeError, ValueError):
            z_value = 0.0
        if z_value > 3.0:
            errors.append(_err(
                "RESIDUAL_TREND", f"segments[{index}].track_artifact",
                f"segments[{index}]: residual_trend_z is {z_value:.2f} "
                f"(above 3.0): the window is not one stretch of "
                f"constant acceleration: it mixes phases (support, a "
                f"change of surface, a turn) or the point deforms; "
                f"fit one phase (R-M1, R-M5)"))

    # -- V8: camera accounting --------------------------------------------
    errors.extend(_check_camera(evidence, ctx, seg_fits))

    # -- V3: mask-check gate ----------------------------------------------
    for pos, ref in enumerate(references):
        field = f"references[{pos}].mask_check"
        if not isinstance(ref, dict):
            continue
        check = ref.get("mask_check", {})
        artifact = check.get("artifact") if isinstance(check, dict) else None
        if not isinstance(artifact, str) or not artifact:
            errors.append(_err("MASK_CHECK_MISSING", field,
                               f"{field}: no check_mask artifact: the "
                               f"reference mask needs a blind check "
                               f"(part 07 §4)"))
            continue
        if artifact not in artifact_set(ctx):
            errors.append(_err("MASK_CHECK_MISSING", field + ".artifact",
                               f"{artifact!r} is not in the run ledger: "
                               f"the reference mask needs a recorded "
                               f"check_mask artifact"))
            continue
        # The artifact must be a real check_mask product, not a file
        # the agent pointed at itself (brief §30): a segment preview
        # or any other non-check file carries no blind coverage
        # reading, so the gate cannot pass on the quoted answer
        # alone.
        ok_check, check_value, _ = load_json_rel(artifact, ctx)
        blind_reading = ""
        if ok_check and isinstance(check_value, dict):
            for key in ("coverage_answer", "answer"):
                text = check_value.get(key)
                if isinstance(text, str) and text.strip():
                    blind_reading = text.strip()
                    break
        if not blind_reading:
            errors.append(_err(
                "MASK_CHECK_MISSING", field + ".artifact",
                f"{artifact!r} is not a check_mask artifact: run "
                f"check_mask on the reference mask and quote its "
                f"coverage answer (part 07 §4)"))
            continue
        answer = check.get("coverage_answer") if isinstance(check,
                                                             dict) else None
        if not isinstance(answer, str) or not answer.strip():
            errors.append(_err("MASK_CHECK_MISSING", field,
                               f"{field}: the submission must quote the "
                               f"blind check's coverage answer"))

    # -- V4 + scale agreement (§§9, 13, 15) --------------------------------
    errors.extend(_check_references(evidence, ctx))

    # -- §36: a line the second look rejected is never used -------
    # A reference or scale line with a check_line record needs a
    # confirming one; a line with no record passes as before. Range
    # extents keep §28's stronger rule inside check_range_checks.
    errors.extend(_check_measured_lines(evidence, ctx))

    # -- §50: every reference line is confirmed blind ----------------
    # A reference's extent_px needs an agreeing check_line record
    # with a named dimension; a line with no record is refused in a
    # dry run and a real submit alike (§30: the other
    # per-reference checks still run).
    try:
        errors.extend(_check_reference_lines_confirmed(evidence, ctx))
    except (TypeError, ValueError, AttributeError):
        pass

    # -- §24: each reference source's quote is one the search returned
    errors.extend(check_reference_sources(evidence, ctx))

    # -- V5: priced alternative readings -----------------------------------
    errors.extend(_check_readings(evidence, ctx))

    # -- §44: a reference keeps its shape on the measuring frame ----
    try:
        shape_errors, shape_skipped = _check_reference_shapes(
            evidence, ctx)
    except (TypeError, ValueError, AttributeError):
        shape_errors, shape_skipped = [], []
    errors.extend(shape_errors)
    computed["reference_shape_skipped"] = shape_skipped

    # -- repetition spread from the segments' g values (§14) -------------
    values = _segment_g_values(computed)
    if len(values) > 1:
        import statistics

        mean = sum(values) / len(values)
        if mean > 0:
            spread = (statistics.pstdev(values) / math.sqrt(len(values))
                      / mean) * mean
            floors = []
            for info in computed.get("segments", []):
                if info is None:
                    continue
                try:
                    floors.append(abs(float(
                        info["fit"].get("g_app_sigma", 0.0))))
                except (TypeError, ValueError):
                    continue
            floor = min(floors) if floors else 0.0
            computed["repetition_spread_extra"] = max(spread, floor)
    # -- V9: error budget ---------------------------------------------------
    errors.extend(_check_budget(evidence, computed))

    # -- §57: the point-versus-centre allowance is at least what masks show
    try:
        errors.extend(_check_shape_terms(evidence, ctx, computed))
    except (TypeError, ValueError, AttributeError):
        pass

    # -- §20: range checks (checked, then scored) --------------------------
    range_errors, scored, raises = check_range_checks(
        evidence, ctx, computed.get("m_per_px"),
        computed.get("sigma_m_per_px"))
    errors.extend(range_errors)
    computed["range_scored"] = scored
    computed["range_sigma_raises"] = raises

    # -- V10: candidate-only worlds ------------------------------------------
    errors.extend(_check_worlds(evidence))

    # -- V11: clock logic (also the verdict preview) -------------------------
    verdict_preview = decide_verdict(evidence, computed, ctx)
    computed["verdict_preview"] = verdict_preview
    errors.extend(_check_clock(evidence, computed, ctx))

    # -- §26: a dropped reference still counts --------------------------------
    try:
        dropped = _dropped_disagreement(
            evidence, ctx, computed.get("m_per_px"),
            computed.get("sigma_m_per_px"))
    except (TypeError, ValueError, AttributeError):
        dropped = None
    computed["dropped_disagreement"] = dropped
    if dropped is not None:
        name_d, m_d, _s_d, name_k, m_k = dropped
        reason = (f"the references disagree: {name_d} at "
                  f"{m_d:.6f} m/px and {name_k} at {m_k:.6f} m/px "
                  f"differ by more than 2 combined sigma")
        preview = dict(computed.get("verdict_preview", {}) or {})
        preview.update(kind="undetermined", world=None,
                       reason=reason, clock_note=None)
        computed["verdict_preview"] = preview
        if dry_run:
            errors.append({
                "code": "REFERENCES_DISAGREE",
                "field": "references",
                "detail": f"references: {reason}: reconcile them "
                f"before the final submit.{_PART_WHOLE_SENTENCE}",
                "push": True})

    # -- §37: a reference is not dropped to escape a disagreement -----
    # A reported disagreement (REFERENCES_DISAGREE or
    # THIRD_REFERENCE_REQUIRED in an earlier dry run) cannot be
    # cleared by resting the final evidence on one reference.
    # Unlike §26's verdict path, this is a hard refusal in a dry
    # run and a real submit alike.
    refusal = _dropped_reference_refusal(evidence, ctx)
    if refusal is not None:
        errors.append(refusal)

    # -- §45: a confirmed line counts as a measured reference -------
    # A confirmed check_line record no evidence extent sits on is an
    # unreported measured reference: one reference plus an absence
    # reason cannot stand next to it. Like §37, a hard refusal in a
    # dry run and a real submit alike.
    try:
        hidden = _hidden_confirmed_line_refusal(evidence, ctx)
    except (TypeError, ValueError, AttributeError):
        hidden = None
    if hidden is not None:
        errors.append(hidden)

    # -- §43: every candidate flight is decided -------------------------
    # The overview is recomputed read-only (dry runs never write).
    # Decision mismatches are hard errors; a missing or partial
    # survey, or a recomputed flight without a decision, forces an
    # undetermined verdict on a real submit (a push in a dry run).
    # The survey requirement only guards results that measure a
    # motion; range-only evidence needs no overview.
    overview = None
    if has_segments:
        try:
            overview = _survey_overview(evidence, ctx)
        except (TypeError, ValueError, AttributeError):
            overview = {"present": False, "span": None, "runs": None,
                        "unconsidered": [], "partial": None,
                        "missing": True,
                        "force": _NOT_SURVEYED, "far": []}
    computed["overview"] = overview
    computed["overview_force"] = (
        overview.get("force") if isinstance(overview, dict) else None)
    try:
        errors.extend(_check_overview_decisions(evidence))
    except (TypeError, ValueError, AttributeError):
        pass
    # -- §45: a candidate flight follows one parabola ------------------
    # A measured candidate whose recomputed centroid track fits one
    # parabola with R² below 0.8 is refused, in a dry run and a real
    # submit alike; a run that ends with it is undetermined with the
    # detail as its reason.
    try:
        errors.extend(_check_flight_parabolic(evidence, ctx))
    except (TypeError, ValueError, AttributeError):
        pass
    try:
        _far_pushes, far_refs, _far_hard = _check_reference_far(
            evidence, ctx)
    except (TypeError, ValueError, AttributeError):
        _far_pushes, far_refs, _far_hard = [], [], []
    computed["reference_far"] = far_refs
    computed["reference_far_pushes"] = _far_pushes
    # Tightened refusals (brief §44) are hard errors in a dry run
    # and a real submit alike.
    errors.extend(_far_hard)

    # -- V12: digit-free prose + registered self-built tools ------------------
    errors.extend(_check_text(evidence, ctx))

    # -- §14: every listed motion is measured or explained ---------------------
    errors.extend(_check_motions(evidence))

    # -- §56: a named free flight is measured, not replaced -----------
    # No segments plus an 8-frame motion needs a checkable skip
    # reason; with a segment, free-text reasons stand as before.
    try:
        errors.extend(_check_motion_skip_reasons(
            evidence, ctx, dry_run=dry_run))
    except (TypeError, ValueError, AttributeError):
        pass

    # -- push codes: dry run only ----------------------------------------------
    if dry_run:
        errors.extend(_push_codes(evidence, computed, ctx))
        # Hard errors first, pushes after: a rejected dry run hid
        # hard errors behind a push code, so the run chased the push
        # and never fixed what blocks acceptance. Each push item
        # carries "push": true (§25). A dropped-reference disagreement
        # is dry-run-only too: it arrives with push already set (§26).
        # A tightened far refusal carries "push": false: it is a
        # hard error even though its code is a push code (§44).
        for error in errors:
            if (isinstance(error, dict)
                    and error.get("code") in PUSH_CODES
                    and error.get("push") is not False):
                error["push"] = True
        def _is_push(error):
            return (isinstance(error, dict)
                    and ((error.get("code") in PUSH_CODES
                          and error.get("push") is not False)
                         or error.get("push") is True))
        hard = [e for e in errors if not _is_push(e)]
        push = [e for e in errors if _is_push(e)]
        errors = hard + push

    return errors, computed


#: The dry-run reply lists hard errors under this line: the run
#: cannot be accepted until they are gone (brief §25).
DRY_RUN_HARD_HEADER = ("Fix these first; the run cannot be accepted "
                       "until they are gone")

#: The dry-run reply lists push codes under this line, after the
#: hard errors (brief §25).
DRY_RUN_PUSH_HEADER = "Then, only if time allows"


def format_dry_run_reply(errors) -> str:
    """The dry-run reply text: hard errors, then pushes (§§25–26).

    Hard errors come first under :data:`DRY_RUN_HARD_HEADER`; push
    codes (each carrying ``"push": True``) come after under
    :data:`DRY_RUN_PUSH_HEADER`. A dropped-reference disagreement
    carries ``push`` too, so it counts as a push (§26). A tightened
    far refusal carries ``"push": False``: it is a hard error even
    though its code is a push code (§44).
    """
    def _is_push(error):
        if not isinstance(error, dict):
            return False
        if error.get("push") is False:
            return False
        return (error.get("code") in PUSH_CODES
                or error.get("push") is True)
    hard = [e for e in (errors or []) if not _is_push(e)]
    push = [e for e in (errors or []) if _is_push(e)]
    lines = []
    if hard:
        lines.append(DRY_RUN_HARD_HEADER)
        for error in hard:
            if isinstance(error, dict):
                lines.append(f"{error.get('code', 'error')} "
                             f"{error.get('field', '?')}: "
                             f"{error.get('detail', '')}")
            else:
                lines.append(str(error))
    if push:
        lines.append(DRY_RUN_PUSH_HEADER)
        for error in push:
            lines.append(f"{error.get('code', 'error')} "
                         f"{error.get('field', '?')}: "
                         f"{error.get('detail', '')}")
    return "\n".join(lines)


def _crossed_cuts(frames, cuts):
    for cut in cuts or []:
        lo = hi = None
        if isinstance(cut, dict):
            for key in ("start", "frame", "index"):
                if cut.get(key) is not None:
                    try:
                        lo = hi = int(cut[key])
                        break
                    except (TypeError, ValueError):
                        continue
            if lo is None:
                try:
                    lo = int(cut.get("frame_start",
                                     cut.get("from", -1)))
                    hi = int(cut.get("frame_end", cut.get("to", -1)))
                except (TypeError, ValueError):
                    continue
        elif isinstance(cut, (list, tuple)) and len(cut) == 2:
            try:
                lo, hi = int(cut[0]), int(cut[1])
            except (TypeError, ValueError):
                continue
        elif isinstance(cut, (int, float)) and not isinstance(cut, bool):
            lo = hi = int(cut)
        else:
            continue
        if lo is None or hi is None:
            continue
        if any(lo <= frame < hi or frame == hi for frame in frames
               if lo != hi) or (lo == hi and lo in frames):
            return [lo, hi] if lo != hi else [lo]
    return []


def _check_fit_curve(segment, index, rows, level_y, m_per_px, fit, ctx):
    """The fit-curve check gives numbers (brief §8)."""
    field = f"segments[{index}].fit_curve_px"
    curve = segment.get("fit_curve_px", [])
    if not isinstance(curve, list) or len(curve) < 4:
        count = len(curve) if isinstance(curve, list) else 0
        return [_err("NUMBER_WITHOUT_PROVENANCE", field,
                     f"{field}: the fit curve holds {count} samples: "
                     f"at least 4 samples are required to check the "
                     f"curve against the track")]
    samples = []
    for pos, sample in enumerate(curve):
        if not isinstance(sample, dict):
            return [_err("NUMBER_WITHOUT_PROVENANCE", field,
                         f"{field}[{pos}]: not an object: expected "
                         f"{ROW_FORMAT}")]
        try:
            moment = float(sample["t_s"])
            y_px = float(sample["y_px"])
        except (KeyError, TypeError, ValueError):
            return [_err("NUMBER_WITHOUT_PROVENANCE", field,
                         f"{field}[{pos}]: needs t_s and y_px numbers: "
                         f"expected {ROW_FORMAT}")]
        if not (math.isfinite(moment) and math.isfinite(y_px)):
            return [_err("NUMBER_WITHOUT_PROVENANCE", field,
                         f"{field}[{pos}]: needs finite t_s and y_px")]
        samples.append((moment, y_px))
    # Implied gravity of the submitted curve, in the same metres.
    curve_t = [s[0] for s in samples]
    curve_y = [(level_y - s[1]) * m_per_px for s in samples]
    try:
        curve_fit = fit_parabola(curve_t, curve_y)
    except ValueError as exc:
        return [_err("NUMBER_WITHOUT_PROVENANCE", field,
                     f"{field}: the submitted curve cannot be refit "
                     f"({exc})")]
    g_track = abs(fit.get("a", 0.0))
    g_curve = abs(curve_fit.get("a", 0.0))
    a_px_track = g_track / m_per_px if m_per_px else 0.0
    a_px_curve = g_curve / m_per_px if m_per_px else 0.0
    # Per-sample deviations of the curve from the track parabola.
    # The refit used absolute video times, so the parabola is
    # evaluated at the sample's absolute time.
    devs = []
    for moment, y_px in samples:
        try:
            predicted_m = (float(fit["y0"]) + float(fit["v0"]) * moment
                           + 0.5 * float(fit["a"]) * moment * moment)
        except (KeyError, TypeError, ValueError):
            continue
        predicted_px = level_y - predicted_m / m_per_px
        devs.append((moment, y_px, predicted_px, abs(y_px - predicted_px)))
    if not devs:
        return []
    rmse_m = float(fit.get("rmse", 0.0) or 0.0)
    rmse_px = rmse_m / m_per_px if m_per_px else 0.0
    tol = max(2.0, 3.0 * rmse_px)
    worst = max(devs, key=lambda d: d[3])
    out = []
    denom = max(g_track, 1e-12)
    if denom and abs(g_curve - g_track) / denom > 0.05:
        frames = sorted(r["frame"] for r in rows)
        out.append(_err(
            "NUMBER_WITHOUT_PROVENANCE", field,
            f"{field}: the fit curve implies g={g_curve:.4f} m/s² "
            f"({a_px_curve:.2f} px/s²) but the track recomputes to "
            f"g={g_track:.4f} m/s² ({a_px_track:.2f} px/s²) at "
            f"m_per_px={m_per_px:.6f} over frames "
            f"{frames[0]}–{frames[-1]} ({len(rows)} samples); "
            f"worst sample t_s={worst[0]:.4f}: y_px={worst[1]:.2f} "
            f"against the track parabola y_px={worst[2]:.2f}"))
    for moment, y_px, predicted_px, dev in devs:
        if dev > tol:
            out.append(_err(
                "NUMBER_WITHOUT_PROVENANCE", field,
                f"{field}: sample t_s={moment:.4f} lies {dev:.2f} px "
                f"off the track parabola (y_px={y_px:.2f} against "
                f"{predicted_px:.2f}; tolerance {tol:.2f} px): the "
                f"fit curve implies g={g_curve:.4f} m/s² but the "
                f"track recomputes to g={g_track:.4f} m/s²"))
            break
    return out


def _fit_base_time(rows, ctx):
    """Video time of the first fitted frame (the fit's t origin)."""
    if not rows:
        return None
    return frame_time(rows[0]["frame"], ctx)


def _check_camera(evidence, ctx, seg_fits):
    camera = evidence.get("camera", {})
    if not isinstance(camera, dict):
        return []
    if "still" in camera and camera["still"] is not None:
        still = camera["still"] or {}
        rel = still.get("reference_track_artifact")
        field = "camera.still.reference_track_artifact"
        if not isinstance(rel, str) or not rel:
            return []
        ok, rows, detail = load_track_rows(rel, ctx)
        if not ok:
            return [_missing(field, detail)]
        if not created_in_run(rel, ctx):
            return [_missing(field, f"{rel!r} was not created in this "
                                    f"run")]
        window_frames = set()
        for info in seg_fits:
            if info is None:
                continue
            window_frames.update(range(info["start"], info["end"] + 1))
        points = [(r["frame"], r["x_px"], r["y_px"]) for r in rows
                  if not window_frames or r["frame"] in window_frames]
        if not points:
            points = [(r["frame"], r["x_px"], r["y_px"]) for r in rows]
        if not points:
            return [_missing(field, f"{rel!r} holds no track rows: "
                                    f"expected {ROW_FORMAT}")]
        x0, y0 = points[0][1], points[0][2]
        peak = max(math.hypot(x - x0, y - y0) for _, x, y in points)
        try:
            threshold = float(_config.CAMERA_STILL_PX_THRESHOLD)
        except (TypeError, ValueError, AttributeError):
            threshold = 2.0
        if peak > threshold:
            return [_err("CAMERA_UNACCOUNTED", "camera",
                         f"camera: the scene reference moves {peak:.2f} "
                         f"px over the fit window (threshold "
                         f"{threshold:.2f} px): a screen-pixel track "
                         f"from a moving camera cannot become a "
                         f"verdict; use the relative_track artifact "
                         f"(R-M3). replace camera with "
                         f'{{"relative_track_artifact": "<path>"}}: a '
                         f"JSON list of {{frame, x_px, y_px}} rows of "
                         f"the subject's track minus the scene "
                         f"reference's track "
                         f"(helpers.tracks.relative_track), and fit "
                         f"that track")]
        return []
    rel = camera.get("relative_track_artifact")
    field = "camera.relative_track_artifact"
    if not isinstance(rel, str) or not rel:
        return []
    ok, rows, detail = load_track_rows(rel, ctx)
    if not ok:
        return [_missing(field, detail)]
    if not created_in_run(rel, ctx):
        return [_missing(field, f"{rel!r} was not created in this run")]
    return []


def _cover_text(ref, ctx):
    """``artifact covers frames lo–hi`` for one reference mask."""
    mask = ref.get("mask", {}) if isinstance(ref, dict) else {}
    artifact = mask.get("artifact") if isinstance(mask, dict) else None
    if not isinstance(artifact, str) or not artifact:
        return "no mask artifact"
    frames = mask_frames_for_object(
        artifact, mask.get("object_id"), ctx)
    if not frames:
        return f"{artifact} (unreadable or empty)"
    if len(frames) == 1:
        return f"{artifact} covers frame {frames[0]}"
    return f"{artifact} covers frames {frames[0]}–{frames[-1]}"


def _common_frame_error(pos_a, ref_a, pos_b, ref_b, ctx):
    """The two masks share no frame: name both covers, say the fix."""
    cover_a = _cover_text(ref_a, ctx)
    cover_b = _cover_text(ref_b, ctx)
    return _missing(
        f"references[{pos_b}].mask",
        f"references[{pos_a}].mask {cover_a}, "
        f"references[{pos_b}].mask {cover_b}; the two masks cannot "
        f"be loaded on a common frame: segment one of them again "
        f"on frames that overlap the other")


def _extent_line(extent):
    """``(coords, frame)`` for a measured line, or ``(None, None)``."""
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


def _check_measured_lines(evidence, ctx):
    """``LINE_NOT_CONFIRMED`` for rejected reference/scale lines (§36).

    Every measured line in the evidence that has a ``check_line``
    record must have a confirming record: a reference's
    ``extent_px``, the scale's ``extent_px``, and every range check
    extent (range extents keep §28's stronger rule — they need a
    confirming record even when none was made — so they are not
    rechecked here). A matching record has the same frame and both
    endpoints within 2 px. When the latest matching record says
    ``agrees: false``, the evidence is refused, naming the line and
    quoting what the second look saw. A line with no record at all
    passes, as before.
    """
    from .ranges import _line_matches, _load_line_entries

    try:
        entries = _load_line_entries(ctx)
    except Exception:  # noqa: BLE001 — a broken journal is no records
        return []
    if not entries:
        return []
    lines = []
    references = evidence.get("references", [])
    if isinstance(references, list):
        for pos, ref in enumerate(references):
            if not isinstance(ref, dict):
                continue
            field = f"references[{pos}].extent_px"
            name = ref.get("name")
            if not isinstance(name, str) or not name.strip():
                name = field
            runs = ref.get("extent_description")
            if not isinstance(runs, str) or not runs.strip():
                runs = name
            lines.append((field, name.strip(), runs.strip(),
                          ref.get("extent_px")))
    scale = evidence.get("scale")
    if isinstance(scale, dict) and isinstance(
            scale.get("extent_px"), dict):
        try:
            index = int(scale.get("reference_index", 0))
        except (TypeError, ValueError):
            index = 0
        lines.append(("scale.extent_px",
                      f"scale.extent_px (copy of "
                      f"references[{index}])",
                      f"references[{index}]",
                      scale.get("extent_px")))
    errors = []
    for field, name, runs, extent in lines:
        coords, frame = _extent_line(extent)
        if coords is None:
            continue
        matches = []
        for rec_frame, item in entries:
            if isinstance(rec_frame, bool) or not isinstance(
                    item, dict):
                continue
            try:
                if int(rec_frame) != frame:
                    continue
            except (TypeError, ValueError):
                continue
            try:
                if _line_matches(item, coords):
                    matches.append(item)
            except (TypeError, ValueError):
                continue
        if not matches:
            continue
        latest = matches[-1]
        if latest.get("agrees") is True:
            continue
        seen = latest.get("description")
        if not isinstance(seen, str) or not seen.strip():
            seen = latest.get("why")
        if not isinstance(seen, str) or not seen.strip():
            seen = "nothing usable"
        errors.append(_err(
            "LINE_NOT_CONFIRMED", field,
            f"{field} ({name}) on frame {frame}: the second look "
            f"sees '{seen.strip()}'; re-measure the line so that it "
            f"runs {runs}, then check it again"))
    return errors


def _check_reference_lines_confirmed(evidence, ctx):
    """``REFERENCE_LINE_NOT_CONFIRMED``: every reference line is confirmed blind (§50).

    Every reference's ``extent_px`` needs a ``check_line`` record of
    this run matching it as §28 says (the same frame, both endpoints
    within 2 px) with ``agrees: true`` and a ``dimension`` other than
    ``"unclear"`` (part 07 §22). A dry run lists this error for each
    reference that lacks a record; the other per-reference checks
    still run (§30). Total over schema-valid input: never raises.
    """
    from .ranges import _line_matches, _load_line_entries

    try:
        references = evidence.get("references", [])
    except AttributeError:
        return []
    if not isinstance(references, list) or not references:
        return []
    try:
        entries = _load_line_entries(ctx)
    except Exception:  # noqa: BLE001 — a broken journal is no records
        entries = []
    errors = []
    for pos, ref in enumerate(references):
        if not isinstance(ref, dict):
            continue
        try:
            extent = ref.get("extent_px")
        except AttributeError:
            continue
        coords, frame = _extent_line(extent)
        if coords is None:
            continue
        try:
            name = ref.get("name")
        except AttributeError:
            name = None
        if not isinstance(name, str) or not name.strip():
            name = f"references[{pos}]"
        else:
            name = name.strip()
        field = f"references[{pos}].extent_px"
        hint = (f"run check_line on this line with a claim that names "
                f"its dimension, for example 'height of the {name}' "
                f"(R-S17)")
        matches = []
        for rec_frame, item in entries or []:
            if isinstance(rec_frame, bool) or not isinstance(item, dict):
                continue
            try:
                if int(rec_frame) != frame:
                    continue
            except (TypeError, ValueError):
                continue
            try:
                if _line_matches(item, coords):
                    matches.append(item)
            except (TypeError, ValueError):
                continue
        if not matches:
            errors.append(_err(
                "REFERENCE_LINE_NOT_CONFIRMED", field,
                f"{field} ({name}) on frame {frame}: no confirming "
                f"check_line record with agrees: true and a named "
                f"dimension; {hint}"))
            continue
        latest = matches[-1]
        dimension = latest.get("dimension")
        dimension_ok = (isinstance(dimension, str)
                        and dimension.strip()
                        and dimension.strip().lower() != "unclear")
        if latest.get("agrees") is True and dimension_ok:
            continue
        if latest.get("agrees") is not True:
            seen = latest.get("description")
            if not isinstance(seen, str) or not seen.strip():
                seen = latest.get("why")
            if not isinstance(seen, str) or not seen.strip():
                seen = "nothing usable"
            errors.append(_err(
                "REFERENCE_LINE_NOT_CONFIRMED", field,
                f"{field} ({name}) on frame {frame}: the second look "
                f"does not confirm it ('{seen.strip()}'); re-measure "
                f"the line, then {hint}"))
        else:
            errors.append(_err(
                "REFERENCE_LINE_NOT_CONFIRMED", field,
                f"{field} ({name}) on frame {frame}: its check_line "
                f"record leaves the dimension 'unclear'; {hint}"))
    return errors


# --- quoted sizes and part/whole gaps (brief §44, R-S13/R-S15) ----------

#: Appended to the REFERENCES_DISAGREE and THIRD_REFERENCE_REQUIRED
#: details (brief §44, R-S15): before searching for another
#: reference, each reference is checked for a part/whole mismatch —
#: a mounted unit, a lid, a base needs its own quoted size (mode
#: sum), or a shorter line on the quoted part.
_PART_WHOLE_SENTENCE = (
    " First check each reference for a part/whole mismatch: list "
    "what its mask and line cover; a unit mounted on it, a lid or "
    "a base needs its own quoted size (mode sum), or a shorter line "
    "(R-S15).")


def _quoted_values(ref):
    """``[(url, value_m)]`` usable quoted sizes, in order (R-S13).

    Only non-null finite positive numbers count: a source with a
    null ``value_m`` backs a reading qualitatively and carries no
    number. Total: never raises.
    """
    try:
        sources = ref.get("sources", [])
    except AttributeError:
        return []
    out = []
    if not isinstance(sources, list):
        return out
    for source in sources:
        if not isinstance(source, dict):
            continue
        try:
            value = float(source.get("value_m"))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(value) and value > 0):
            continue
        try:
            url = str(source.get("url", "") or "").strip()
        except (TypeError, ValueError):
            url = ""
        out.append((url, value))
    return out


def _distinct_values(quoted):
    """Quoted values with exact ``(url, value)`` duplicates removed.

    The same page quoted twice still states one number; two
    different pages quoting the same number are two sources and
    both count.
    """
    out = []
    seen = set()
    for url, value in quoted:
        key = (url, round(value, 9))
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _check_reference_size(pos, ref):
    """``SIZE_NOT_AS_QUOTED``: a size is used as quoted (R-S13).

    ``size_m`` is one source's value (``single``), the sum of the
    values of distinct sources (``sum``), or their mean (``mean``),
    within 1 %. An estimate layered on a quote — a crouch
    reduction, a guessed subtraction — is refused with the quoted
    numbers named. Total: schema-valid input never raises; an
    unreadable size or mode is None (the schema already reported
    it).
    """
    try:
        size = float(ref.get("size_m"))
    except (TypeError, ValueError, AttributeError):
        return None
    if not (math.isfinite(size) and size > 0):
        return None
    try:
        derivation = ref.get("size_derivation", {})
    except AttributeError:
        return None
    mode = derivation.get("mode") if isinstance(derivation, dict) else None
    quoted = _quoted_values(ref)
    values = _distinct_values(quoted)
    if mode == "single":
        ok = any(abs(size - value) / value <= 0.01 for value in values)
    elif mode == "sum":
        total = sum(values)
        ok = bool(values) and total > 0 and (
            abs(size - total) / total <= 0.01)
    elif mode == "mean":
        mean = sum(values) / len(values) if values else 0.0
        ok = bool(values) and mean > 0 and (
            abs(size - mean) / mean <= 0.01)
    else:
        return None
    if ok:
        return None
    try:
        name = ref.get("name", "")
    except AttributeError:
        name = ""
    if not isinstance(name, str) or not name.strip():
        name = f"references[{pos}]"
    else:
        name = name.strip()
    if quoted:
        sources_text = ", ".join(f"{value:g}"
                                 for _, value in quoted)
    else:
        sources_text = "no usable value"
    return _err(
        "SIZE_NOT_AS_QUOTED", f"references[{pos}].size_m",
        f"{name}: {size:g} m ({mode}) is not a quoted value; the "
        f"sources quote {sources_text} m. Use the size as quoted; "
        f"if the figure is not in the quoted state on this frame, "
        f"measure it on another frame (R-S13).")


# --- a size comes from a named dimension (brief §47, R-S13) --------

#: Words that name which number of a dimension list is which
#: (brief §47): "high", "tall", "height", "wide", "width", "deep",
#: "depth", "long", "length", "diameter".
_DIMENSION_WORD_RE = re.compile(
    r"\b(?:high|tall|height|wide|width|deep|depth|long|length"
    r"|diameter)\b",
    re.IGNORECASE)

#: How far around a matched number a dimension word still counts as
#: naming it (brief §47 "next to that number"): the same breath of
#: the quote, wide enough for a parallel imperial/metric dimension
#: list such as "5 ft. 6 15/16 in. tall x ... (170.02 x 82 x 27.9cm)".
_DIMENSION_WINDOW = 40

#: One quoted number with an optional unit suffix, as in part 12 §24
#: quote parsing (see ``_numbers_in_text`` in ``ranges.py``).
_DIMENSION_NUMBER_RE = re.compile(
    r"(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)"
    r"(?:\s*(mm|cm|m|in|inch|inches|ft|feet|%|percent))?")

#: A run of three or more numbers joined by "×" or "x" (brief §47).
#: A unit may sit between a number and the separator, but any other
#: word between two numbers breaks the run, so a labelled list such
#: as "5 ft. 6 15/16 in. tall x 2 ft. 8 5/16 in. wide x 11 in. deep"
#: never counts as one.
_DIMENSION_RUN_RE = re.compile(
    r"\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?"
    r"(?:\s*(?:mm|cm|m|in|inch|inches|ft|feet)\.?)?"
    r"(?:\s*[×xX]\s*\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?"
    r"(?:\s*(?:mm|cm|m|in|inch|inches|ft|feet)\.?)?){2,}")

#: A compound imperial measurement ("5 ft. 6 15/16 in."): feet plus
#: inches, the inches whole, decimal or mixed. It states one size in
#: words outside any dimension run.
_DIMENSION_COMPOUND_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:ft|feet|foot)\.?\s+"
    r"(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
    r"\s*(?:in|inch|inches)\.?",
    re.IGNORECASE)


def _dimension_runs(quote):
    """``[(start, end, text)]`` dimension runs in the quote (R-S13).

    Total: never raises.
    """
    out = []
    try:
        text = str(quote or "")
    except (TypeError, ValueError):
        return out
    try:
        for match in _DIMENSION_RUN_RE.finditer(text):
            out.append((match.start(), match.end(), match.group(0)))
    except (TypeError, ValueError):
        return out
    return out


def _run_trailing_unit(run_text):
    """Unit suffix of the run's last number ("cm" for "... x 27.9cm").

    A bare list such as "(170 × 82 × 28cm)" states every element in
    that unit. Total: never raises.
    """
    unit = ""
    try:
        for match in _DIMENSION_NUMBER_RE.finditer(str(run_text or "")):
            suffix = (match.group(2) or "").strip().lower()
            if suffix:
                unit = suffix
    except (TypeError, ValueError):
        return ""
    return unit


def _compound_inches(text):
    """Inches part of a compound measurement in inches, or None."""
    try:
        part = str(text or "").strip()
    except (TypeError, ValueError):
        return None
    try:
        if "/" in part:
            if " " in part.strip():
                whole, _, frac = part.strip().partition(" ")
                num, _, den = frac.partition("/")
                return float(whole) + float(num) / float(den)
            num, _, den = part.partition("/")
            return float(num) / float(den)
        return float(part)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _dimension_occurrences(quote, value_m):
    """``[(start, end)]`` spans where the quote states this many metres.

    Compound imperial ("5 ft. 6 15/16 in."), unit-suffixed numbers,
    run-inherited units ("170" of "(170 × 82 × 28cm)" is centimetres)
    and the single-label fallback of part 12 §24 all count, within 1 %
    like ``SIZE_NOT_AS_QUOTED``. A compound match covers its inches
    number, so one statement is one hit. Total: never raises.
    """
    try:
        target = float(value_m)
    except (TypeError, ValueError):
        return []
    if not (math.isfinite(target) and target > 0):
        return []
    try:
        text = str(quote or "")
    except (TypeError, ValueError):
        return []
    if not text:
        return []
    runs = _dimension_runs(text)
    try:
        label_units = named_units(text)
    except (TypeError, ValueError):
        label_units = set()
    label_unit = next(iter(label_units)) if len(label_units) == 1 else None
    out = []
    covered = []

    def _close(metres):
        try:
            value = float(metres)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(value):
            return False
        return abs(value - target) / target <= 0.01

    try:
        for match in _DIMENSION_COMPOUND_RE.finditer(text):
            inches = _compound_inches(match.group(2))
            try:
                feet = float(match.group(1))
            except (TypeError, ValueError):
                continue
            if inches is None or not math.isfinite(inches):
                continue
            if _close(feet * 0.3048 + inches * 0.0254):
                out.append((match.start(), match.end()))
                covered.append((match.start(), match.end()))
    except (TypeError, ValueError):
        pass
    run_unit = {}
    for start, end, run_text in runs:
        unit = _run_trailing_unit(run_text)
        if unit:
            run_unit[(start, end)] = unit
    try:
        numbered = list(_DIMENSION_NUMBER_RE.finditer(text))
    except (TypeError, ValueError):
        numbered = []
    for match in numbered:
        if any(match.start() >= cstart and match.end() <= cend
               for cstart, cend in covered):
            continue
        number, suffix = match.group(1), (match.group(2) or "").strip()
        unit = suffix.lower()
        if not unit:
            for (start, end), inherited in run_unit.items():
                if match.start() >= start and match.end() <= end:
                    unit = inherited
                    break
        if not unit:
            unit = label_unit or ""
        if _close(_to_base(number, unit)):
            out.append((match.start(), match.end()))
    return out


def _check_reference_dimensions(pos, ref):
    """``SIZE_DIMENSION_UNLABELLED``: a size from a named dimension.

    For each ``sources[]`` entry: when its value appears in the quote
    only inside a run of three or more numbers joined by "×" or "x"
    with no dimension word next to that number (R-S13), the submit is
    refused: the line does not say which number is the height. A value
    the quote also states outside any run — a compound imperial
    measurement, a labelled number — is used as quoted. Total over
    schema-valid input: unreadable entries are skipped (the schema
    already reported them).
    """
    if not isinstance(ref, dict):
        return []
    try:
        name = ref.get("name", "")
    except AttributeError:
        return []
    if not isinstance(name, str) or not name.strip():
        name = f"references[{pos}]"
    else:
        name = name.strip()
    sources = ref.get("sources", [])
    if not isinstance(sources, list):
        return []
    errors = []
    for spos, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        try:
            value = float(source.get("value_m"))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(value) and value > 0):
            continue
        quote = source.get("quote", "")
        if not isinstance(quote, str) or not quote:
            continue
        runs = _dimension_runs(quote)
        if not runs:
            continue
        hits = _dimension_occurrences(quote, value)
        if not hits:
            continue
        inside = []
        outside = False
        for start, end in hits:
            run_text = None
            for run_start, run_end, text in runs:
                if start >= run_start and end <= run_end:
                    run_text = text
                    break
            if run_text is None:
                outside = True
                break
            inside.append((start, end, run_text))
        if outside or not inside:
            # The quote states the size outside the dimension list.
            continue
        named = False
        for start, end, _run_text in inside:
            window = quote[max(0, start - _DIMENSION_WINDOW):
                           end + _DIMENSION_WINDOW]
            if _DIMENSION_WORD_RE.search(window):
                named = True
                break
        if named:
            continue
        run_text = inside[0][2]
        errors.append(_err(
            "SIZE_DIMENSION_UNLABELLED",
            f"references[{pos}].sources[{spos}].quote",
            f"{name}: {value:g} m comes from '{run_text}', which "
            f"does not name its dimensions. Use a source that says "
            f"which number is the height (R-S13)."))
    return errors


def _source_urls(ref) -> set:
    """The ``sources[].url`` set of one reference (brief §53)."""
    try:
        sources = ref.get("sources", [])
    except AttributeError:
        return set()
    urls = set()
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict):
                continue
            try:
                url = source.get("url")
            except AttributeError:
                continue
            if isinstance(url, str) and url.strip():
                urls.add(url.strip())
    return urls


def _check_same_thing(evidence):
    """``REFERENCE_SAME_THING``: one quoted thing measured twice.

    Two references whose ``size_m`` values are within 1 % of each
    other and whose ``sources[].url`` sets are equal are one quoted
    thing measured twice, not two references (brief §53, R-S6b,
    R-S16). Total: never raises.
    """
    errors = []
    try:
        references = evidence.get("references", [])
    except AttributeError:
        return errors
    if not isinstance(references, list):
        return errors
    for left in range(len(references)):
        for right in range(left + 1, len(references)):
            try:
                ref_a = references[left]
                ref_b = references[right]
                if not isinstance(ref_a, dict) or not isinstance(
                        ref_b, dict):
                    continue
                size_a = float(ref_a.get("size_m"))
                size_b = float(ref_b.get("size_m"))
            except (TypeError, ValueError, AttributeError):
                continue
            if not (math.isfinite(size_a) and math.isfinite(size_b)):
                continue
            denom = max(abs(size_a), abs(size_b))
            if not math.isfinite(denom) or denom <= 0:
                continue
            if abs(size_a - size_b) / denom > 0.01:
                continue
            if _source_urls(ref_a) != _source_urls(ref_b):
                continue
            try:
                name_a = ref_a.get("name") or f"references[{left}]"
                name_b = ref_b.get("name") or f"references[{right}]"
            except AttributeError:
                name_a, name_b = (
                    f"references[{left}]", f"references[{right}]")
            errors.append(_err(
                "REFERENCE_SAME_THING", "references",
                f"references[{left}] ({name_a}) and "
                f"references[{right}] ({name_b}) quote the same size "
                f"from the same sources: one thing measured twice is "
                f"one reference. A second reference is a different "
                f"thing: the moving thing itself, something it wears "
                f"or carries, or a fixed thing beside it (R-S6b, "
                f"R-S16)."))
    return errors


def _check_references(evidence, ctx):
    """V4 plus the §§9/13/15/44/53 scale agreement rules."""
    errors = []
    references = evidence.get("references", [])
    scale = evidence.get("scale", {}) if isinstance(
        evidence.get("scale", {}), dict) else {}
    errors.extend(_check_same_thing(evidence))
    for pos, ref in enumerate(references):
        if not isinstance(ref, dict):
            continue
        error = _check_reference_size(pos, ref)
        if error is not None:
            errors.append(error)
        errors.extend(_check_reference_dimensions(pos, ref))
    if len(references) < 2:
        if scale.get("second_reference_index") is not None:
            errors.append(_err(
                "SECOND_REFERENCE_SAME_OBJECT",
                "scale.second_reference_index",
                "scale.second_reference_index names a second reference "
                "but only one reference is listed"))
            return errors
        reason = scale.get("second_reference_absent_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(_err(
                "SECOND_REFERENCE_ABSENT_UNEXPLAINED",
                "scale.second_reference_absent_reason",
                "scale rests on one reference with no reason: name "
                "second_reference_absent_reason, or add a second "
                "reference of a different thing"))
        for pos, ref in enumerate(references):
            if not isinstance(ref, dict):
                continue
            match = ((ref.get("size_derivation") or {})
                     .get("state_match") if isinstance(
                         ref.get("size_derivation"), dict) else None)
            if not isinstance(match, dict) or not _norm_text(
                    match.get("shown_and_covered")) or not _norm_text(
                    match.get("shown_not_covered")):
                errors.append(_err(
                    "STATE_MATCH_MISSING",
                    f"references[{pos}].size_derivation.state_match",
                    f"references[{pos}]: state_match needs "
                    f"shown_and_covered and shown_not_covered "
                    f"(R-S7)"))
        return errors
    # Two or more references: state_match, pairwise masks, agreement.
    infos = []
    for pos, ref in enumerate(references):
        if not isinstance(ref, dict):
            continue
        match = ((ref.get("size_derivation") or {})
                 .get("state_match") if isinstance(
                     ref.get("size_derivation"), dict) else None)
        if not isinstance(match, dict) or not _norm_text(
                match.get("shown_and_covered")) or not _norm_text(
                match.get("shown_not_covered")):
            errors.append(_err(
                "STATE_MATCH_MISSING",
                f"references[{pos}].size_derivation.state_match",
                f"references[{pos}]: state_match needs "
                f"shown_and_covered and shown_not_covered (R-S7)"))
        m_per_px, sigma = reference_scale(ref)
        infos.append((pos, ref, m_per_px, sigma))
    # V4: near-identical masks (IoU above 0.8) are fakery.
    for left in range(len(infos)):
        for right in range(left + 1, len(infos)):
            pos_a, ref_a, _, _ = infos[left]
            pos_b, ref_b, _, _ = infos[right]
            try:
                result = mask_iou_on_frame(ref_a, ref_b, ctx)
            except (TypeError, ValueError):
                result = None
            if result is None:
                errors.append(_common_frame_error(
                    pos_a, ref_a, pos_b, ref_b, ctx))
                continue
            iou, _inter, _small = result
            if iou > 0.8:
                name_a = ref_a.get("name", pos_a)
                name_b = ref_b.get("name", pos_b)
                errors.append(_err(
                    "SECOND_REFERENCE_SAME_OBJECT",
                    f"references[{pos_b}].mask",
                    f"references[{pos_a}] ({name_a}) and "
                    f"references[{pos_b}] ({name_b}) overlap with "
                    f"IoU {iou:.2f} above 0.8 on a common frame: "
                    f"they are the same object, not two references "
                    f"(R-S3)"))
    # Gap rule (§§15/39): any pair differing by more than 5% of its
    # mean needs a settler — another reference tight enough to tell
    # the two sides apart (relative σ at most 5%) that lies within
    # 2σ of both. A loose reference agrees with almost any scale, so
    # it never settles a gap (it still counts in the weighted scale
    # and in the pairwise check below).
    good = [(p, r, m, s) for p, r, m, s in infos
            if m is not None and s is not None and s > 0]
    n_before_gap = len(errors)
    for left in range(len(good)):
        for right in range(left + 1, len(good)):
            pa, ra, ma, sa = good[left]
            pb, rb, mb, sb = good[right]
            mean = (ma + mb) / 2.0
            if mean <= 0 or abs(ma - mb) / mean <= 0.05:
                continue
            gap = abs(ma - mb) / mean * 100.0
            settled = False
            loose = []
            for pos, ro, mo, so in good:
                if pos == pa or pos == pb:
                    continue
                rel = so / mo if mo > 0 else float("inf")
                if not math.isfinite(rel) or rel > 0.05:
                    loose.append((pos, ro, rel))
                    continue
                near_a = (abs(mo - ma)
                          <= 2.0 * math.sqrt(so * so + sa * sa))
                near_b = (abs(mo - mb)
                          <= 2.0 * math.sqrt(so * so + sb * sb))
                if near_a and near_b:
                    settled = True
                    break
            if settled:
                continue
            detail = (
                f"references[{pa}] ({ra.get('name')}: "
                f"{ma:.6f} m/px) and references[{pb}] "
                f"({rb.get('name')}: {mb:.6f} m/px) differ by "
                f"{gap:.1f}% of their mean: add a third reference "
                f"with relative σ at most 5% that lies within 2σ "
                f"of both")
            for pos, ro, rel in loose:
                if math.isfinite(rel):
                    rel_text = (f"relative σ {rel * 100.0:.1f}%")
                else:
                    rel_text = "relative σ not finite"
                detail += (
                    f"; references[{pos}] ({ro.get('name')}) is too "
                    f"loose to settle the gap ({rel_text}, above "
                    f"the 5% threshold)")
            errors.append(_err(
                "THIRD_REFERENCE_REQUIRED", "references",
                detail + "." + _PART_WHOLE_SENTENCE))
    if len(good) == 2 and len(errors) > n_before_gap:
        return errors
    for left in range(len(good)):
        for right in range(left + 1, len(good)):
            pa, ra, ma, sa = good[left]
            pb, rb, mb, sb = good[right]
            combined = math.sqrt(sa * sa + sb * sb)
            if abs(ma - mb) > 2.0 * combined:
                ratio = (max(ma, mb) / min(ma, mb)
                         if min(ma, mb) > 0 else float("inf"))
                errors.append(_err(
                    "REFERENCES_DISAGREE",
                    f"references[{pb}].size_m",
                    f"references[{pa}] ({ra.get('name')}: "
                    f"{ma:.6f} ± {sa:.6f} m/px) and references[{pb}] "
                    f"({rb.get('name')}: {mb:.6f} ± {sb:.6f} m/px) "
                    f"differ by more than 2 combined σ (ratio "
                    f"{ratio:.3f}): reconcile the readings, never "
                    f"average them away."
                    f"{_PART_WHOLE_SENTENCE}"))
    return errors


def _alt_sizes(ref):
    """``[(description, size_m)]`` differing from the headline size."""
    try:
        size = float(ref.get("size_m"))
    except (TypeError, ValueError):
        return []
    out = []
    check = ref.get("mask_check", {})
    alts = check.get("alternative_readings", []) if isinstance(
        check, dict) else []
    for alt in alts or []:
        if not isinstance(alt, dict):
            continue
        try:
            size_alt = float(alt.get("size_m"))
        except (TypeError, ValueError):
            continue
        if size_alt != size:
            out.append((alt.get("description", ""), size_alt))
    return out


def _excused_by_second_reading(ref_pos, ref, size_alt, evidence):
    """Another reference agrees under the headline, not the alt (§13.5)."""
    try:
        size = float(ref.get("size_m"))
        tol = float(ref.get("size_tolerance_m", 0.0))
        length = float(ref["extent_px"]["length_px"])
    except (KeyError, TypeError, ValueError):
        return False
    references = evidence.get("references", [])
    for pos, other in enumerate(references):
        if pos == ref_pos or not isinstance(other, dict):
            continue
        m_o, s_o = reference_scale(other)
        if m_o is None:
            continue
        m_h = size / length
        s_h = m_h * math.sqrt((2.0 / length) ** 2 + (tol / size) ** 2) \
            if size > 0 and length > 0 else None
        m_a = size_alt / length
        s_a = m_a * math.sqrt((2.0 / length) ** 2 + (tol / size_alt) ** 2) \
            if size_alt > 0 and length > 0 else None
        if s_h is None or s_a is None or s_h <= 0 or s_a <= 0:
            continue
        agrees_headline = (abs(m_h - m_o)
                           <= 2.0 * math.sqrt(s_h * s_h + s_o * s_o))
        disagrees_alt = (abs(m_a - m_o)
                         > 2.0 * math.sqrt(s_a * s_a + s_o * s_o))
        if agrees_headline and disagrees_alt:
            return True
    return False


def _reading_spread_given(evidence):
    for comp in (evidence.get("error_budget", {}) or {}).get(
            "components", []) or []:
        if isinstance(comp, dict) and comp.get("name") == "reading_spread":
            try:
                return float(comp.get("sigma_contribution", 0.0))
            except (TypeError, ValueError):
                return 0.0
    return None


def _blind_alternatives(ref, ctx):
    """Free-text alternatives from the blind check artifact, if any."""
    check = ref.get("mask_check", {}) if isinstance(ref, dict) else {}
    artifact = check.get("artifact") if isinstance(check, dict) else None
    if not isinstance(artifact, str) or not artifact:
        return []
    ok, value, _ = load_json_rel(artifact, ctx)
    if not ok or not isinstance(value, dict):
        return []
    alts = value.get("alternative_readings", value.get("alternatives", []))
    out = []
    if isinstance(alts, list):
        for alt in alts:
            if isinstance(alt, str) and alt.strip():
                out.append(alt.strip())
            elif isinstance(alt, dict):
                text = alt.get("description", alt.get("reading",
                                                     alt.get("text", "")))
                if isinstance(text, str) and text.strip():
                    out.append(text.strip())
    return out


# --- steady reference shapes (brief §44, R-S14) ------------------------------

#: Rest half-window for the shape check, in seconds (brief §44,
#: R-S14): the reference keeps its shape on a frame whose mask
#: height matches the median over the frames within ±1 s that lie
#: outside every flight candidate.
_SHAPE_REST_S = 1.0
#: Rest margin around each recomputed flight candidate (brief §44).
_SHAPE_FLIGHT_MARGIN_S = 0.3
#: Minimum rest frames for the shape check (brief §44).
_SHAPE_MIN_FRAMES = 5
#: Largest steady-shape deviation, relative (brief §44, R-S14).
_SHAPE_TOLERANCE = 0.05


def _frame_ranges_text(frames):
    """``[41, 42, 43, 50]`` as ``"41–43, 50"`` for error details."""
    runs = []
    for frame in sorted(set(frames)):
        if runs and frame == runs[-1][-1] + 1:
            runs[-1].append(frame)
        else:
            runs.append([frame])
    parts = []
    for run in runs:
        if len(run) > 1:
            parts.append(f"{run[0]}–{run[-1]}")
        else:
            parts.append(str(run[0]))
    return ", ".join(parts)


def _extent_direction(ref):
    """Unit vector of the reference's ``extent_px`` line, or None.

    A line of zero length gives None, and the shape check then
    measures the mask height, as before (brief §52).
    """
    try:
        extent = ref.get("extent_px", {})
        x1 = float(extent["x1"])
        y1 = float(extent["y1"])
        x2 = float(extent["x2"])
        y2 = float(extent["y2"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    dx = x2 - x1
    dy = y2 - y1
    norm = math.hypot(dx, dy)
    if not math.isfinite(norm) or norm <= 0:
        return None
    return (dx / norm, dy / norm)


def _mask_spread_along(masks, frame, direction):
    """Mask size on one frame along ``direction``, or None.

    The spread of the mask pixels' projection on the unit vector
    ``direction`` (largest minus smallest projection of the pixel
    centres), plus 1 px. With ``direction`` None the mask height
    is measured, as before: a vertical line gives the mask height
    (brief §52). An empty frame is None, never zero. Total.
    """
    if not isinstance(masks, dict):
        return None
    arr = masks.get(frame)
    if arr is None:
        return None
    try:
        import numpy as np  # noqa: PLC0415

        canvas = np.asarray(arr, dtype=bool)
        if not bool(canvas.any()):
            return None
        if direction is None:
            from src.helpers import tracks  # noqa: PLC0415

            return int(tracks.mask_stats(
                tracks.largest_component(canvas))["height"])
        rows, cols = np.nonzero(canvas)
        proj = cols * direction[0] + rows * direction[1]
        return float(proj.max() - proj.min()) + 1.0
    except (ValueError, TypeError, AttributeError):
        return None


def _shape_rest_frames(masks, measure_time, candidates, ctx, direction):
    """Rest frames for the shape check (brief §§44, 52, R-S14).

    Frames of the same mask within ±1 s of the measuring frame
    that lie outside every recomputed flight candidate ±0.3 s.
    Every frame is measured along ``direction``, the reference's
    own line. Returns ``(rest, sizes)``: the eligible frames and
    their ``{frame: size}`` (non-empty masks only). Total.
    """
    rest = []
    heights = {}
    for frame in masks:
        if isinstance(frame, bool):
            continue
        try:
            moment = frame_time(frame, ctx)
        except (TypeError, ValueError, AttributeError):
            continue
        try:
            moment = float(moment)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(moment):
            continue
        if abs(moment - measure_time) > _SHAPE_REST_S + 1e-9:
            continue
        inside = False
        for start, end in candidates:
            try:
                low = frame_time(start, ctx)
                high = frame_time(end, ctx)
                low = float(low) - _SHAPE_FLIGHT_MARGIN_S
                high = float(high) + _SHAPE_FLIGHT_MARGIN_S
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(low) and math.isfinite(high)):
                continue
            if low <= moment <= high:
                inside = True
                break
        if inside:
            continue
        size = _mask_spread_along(masks, frame, direction)
        if size is None:
            continue
        rest.append(frame)
        heights[frame] = size
    return sorted(rest), heights


def _mask_iou_arrays(arr_a, arr_b) -> float | None:
    """Intersection over union of two mask arrays, or None."""
    try:
        import numpy as np  # noqa: PLC0415

        a = np.asarray(arr_a, dtype=bool)
        b = np.asarray(arr_b, dtype=bool)
    except (TypeError, ValueError):
        return None
    try:
        if a.shape != b.shape:
            return None
        union_n = int((a | b).sum())
    except (TypeError, ValueError):
        return None
    if union_n == 0:
        return None
    try:
        inter_n = int((a & b).sum())
    except (TypeError, ValueError):
        return None
    return inter_n / union_n


def _same_object_mask_dicts(artifact, object_id, measure_frame,
                            ref_array, ctx):
    """Every ``t*_segment_*.npz`` mask of the same object (brief §49).

    Each ``artifacts/t*_segment_*.npz`` whose object overlaps the
    reference's mask object on the measuring frame with IoU above
    ``SAME_OBJECT_IOU`` (brief §54) contributes its
    ``{frame: array}`` dict. Total: never raises; unreadable files
    simply do not count.
    """
    from pathlib import Path as _Path

    out = []
    if ref_array is None:
        return out
    try:
        base = _Path(str((ctx or {}).get("run_dir", ".") or "."))
    except (TypeError, ValueError):
        return out
    try:
        paths = sorted((base / "artifacts").glob("t*_segment_*.npz"))
    except (OSError, ValueError):
        return out
    try:
        from .io import _masks_bundle as _bundle  # noqa: PLC0415
    except ImportError:
        return out
    try:
        own_rel = str(artifact)
    except (TypeError, ValueError):
        own_rel = ""
    for path in paths:
        try:
            rel = str(path.relative_to(base))
        except (ValueError, OSError):
            continue
        if rel == own_rel:
            continue
        try:
            bundle = _bundle(rel, ctx)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(bundle, dict):
            continue
        for frames in bundle.values():
            if not isinstance(frames, dict):
                continue
            cand = None
            for key in (measure_frame, str(measure_frame)):
                try:
                    if key in frames:
                        cand = frames[key]
                        break
                except (TypeError, AttributeError):
                    continue
            if cand is None:
                continue
            try:
                iou = _mask_iou_arrays(ref_array, cand)
            except (TypeError, ValueError, AttributeError):
                continue
            if (iou is None or not math.isfinite(iou)
                    or iou <= SAME_OBJECT_IOU):
                continue
            cleaned: dict = {}
            for frame, arr in frames.items():
                if isinstance(frame, bool):
                    continue
                try:
                    index = int(frame)
                except (TypeError, ValueError):
                    continue
                if isinstance(index, bool):
                    continue
                cleaned[index] = arr
            if cleaned:
                out.append(cleaned)
            break
    return out


def _eligible_clip_frames(measure_time, candidates, ctx):
    """Clip frames within ±1 s outside every flight candidate ±0.3 s."""
    try:
        _fps, count, _duration, _stamps = timing_numbers(ctx)
        count = int(count or 0)
    except (TypeError, ValueError, AttributeError):
        return []
    if isinstance(count, bool) or count <= 0:
        return []
    eligible = []
    for frame in range(count):
        try:
            moment = float(frame_time(frame, ctx))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(moment):
            continue
        if abs(moment - measure_time) > _SHAPE_REST_S + 1e-9:
            continue
        inside = False
        for start, end in candidates:
            try:
                low = float(frame_time(start, ctx)) - _SHAPE_FLIGHT_MARGIN_S
                high = float(frame_time(end, ctx)) + _SHAPE_FLIGHT_MARGIN_S
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(low) and math.isfinite(high)):
                continue
            if low <= moment <= high:
                inside = True
                break
        if inside:
            continue
        eligible.append(frame)
    return sorted(eligible)


def _check_reference_shapes(evidence, ctx):
    """``REFERENCE_SHAPE_UNSTABLE``: measure where the thing keeps
    its shape (brief §44, R-S14); ``REFERENCE_SHAPE_UNCHECKED``
    when no mask covers its rest frames (brief §49).

    For each reference with a mask: the mask height on the
    measuring frame against the median mask height over the
    rest frames within ±1 s of it that lie outside every
    recomputed flight candidate ±0.3 s. The rest frames come
    from every ``artifacts/t*_segment_*.npz`` of this run whose
    object overlaps the reference's mask object on the measuring
    frame with IoU above ``SAME_OBJECT_IOU`` (brief §54), each
    frame counting once with the
    reference's own mask first. With 5 or more such frames and a
    difference above 5 %, the evidence is refused.

    Returns ``(errors, skipped)``: ``skipped`` lists ``(pos, name,
    n)`` for references with fewer than 5 rest frames when the
    clip itself has fewer than 5 eligible frames (a still or a
    very short clip), so the scale step can say the check was
    skipped. A mask that cannot be read is skipped silently
    (other checks report it).

    The size of a mask on a frame is the spread of its pixels
    along the direction of the reference's ``extent_px`` line
    (brief §52, R-S14): a vertical line gives the mask height, as
    before. A line of zero length gives the mask height too.
    """
    errors = []
    skipped = []
    references = evidence.get("references", [])
    if not isinstance(references, list):
        return errors, skipped
    try:
        overview = (evidence.get("first_look", {}) or {}).get("overview")
    except AttributeError:
        overview = None
    if isinstance(overview, dict):
        _span, runs = _overview_recompute(overview.get("artifact"),
                                          overview.get("object_id"), ctx)
    else:
        runs = None
    candidates = list(runs) if isinstance(runs, list) else []
    for pos, ref in enumerate(references):
        if not isinstance(ref, dict):
            continue
        mask = ref.get("mask", {})
        artifact = mask.get("artifact") if isinstance(mask, dict) else None
        object_id = mask.get("object_id") if isinstance(
            mask, dict) else None
        if not isinstance(artifact, str) or not artifact:
            continue
        try:
            measure_frame = int((ref.get("extent_px", {}) or {}).get(
                "frame"))
        except (TypeError, ValueError, AttributeError):
            continue
        if isinstance(measure_frame, bool):
            continue
        try:
            masks = load_object_masks(artifact, object_id, ctx)
        except (TypeError, ValueError, AttributeError):
            continue
        if not masks:
            continue
        try:
            measure_time = frame_time(measure_frame, ctx)
            measure_time = float(measure_time)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(measure_time):
            continue
        try:
            ref_array = load_mask_frame(artifact, object_id,
                                        measure_frame, ctx)
        except (TypeError, ValueError, AttributeError):
            ref_array = None
        try:
            others = _same_object_mask_dicts(
                artifact, object_id, measure_frame, ref_array, ctx)
        except (TypeError, ValueError, AttributeError):
            others = []
        combined: dict = {}
        for frames in [masks, *list(others or [])]:
            if not isinstance(frames, dict):
                continue
            for frame, arr in frames.items():
                if isinstance(frame, bool):
                    continue
                try:
                    index = int(frame)
                except (TypeError, ValueError):
                    continue
                if isinstance(index, bool):
                    continue
                if index not in combined:
                    combined[index] = arr
        try:
            direction = _extent_direction(ref)
        except (TypeError, ValueError, AttributeError):
            direction = None
        rest, heights = _shape_rest_frames(
            combined, measure_time, candidates, ctx, direction)
        if len(rest) < _SHAPE_MIN_FRAMES:
            try:
                name = ref.get("name", "")
            except AttributeError:
                name = ""
            if not isinstance(name, str) or not name.strip():
                name = f"references[{pos}]"
            else:
                name = name.strip()
            try:
                from pathlib import Path as _Path

                _seg_paths = sorted(
                    (_Path(str((ctx or {}).get("run_dir", ".") or "."))
                     / "artifacts").glob("t*_segment_*.npz"))
                _has_segments = len(_seg_paths) > 0
            except (TypeError, ValueError, OSError, AttributeError):
                _has_segments = False
            if not _has_segments:
                skipped.append((pos, name, len(rest)))
                continue
            try:
                eligible = _eligible_clip_frames(
                    measure_time, candidates, ctx)
            except (TypeError, ValueError, AttributeError):
                eligible = []
            if len(eligible) >= _SHAPE_MIN_FRAMES:
                lo, hi = min(eligible), max(eligible)
                errors.append(_err(
                    "REFERENCE_SHAPE_UNCHECKED",
                    f"references[{pos}].extent_px",
                    f"{name}: its shape on frame {measure_frame} "
                    f"cannot be checked; segment it over frames "
                    f"{lo}–{hi} (its rest frames near the motion) "
                    f"or measure it on one of them (R-S14)"))
            else:
                skipped.append((pos, name, len(rest)))
            continue
        height = heights.get(measure_frame)
        if height is None:
            height = _mask_spread_along(combined, measure_frame,
                                        direction)
        if height is None:
            try:
                name = ref.get("name", "")
            except AttributeError:
                name = ""
            if not isinstance(name, str) or not name.strip():
                name = f"references[{pos}]"
            else:
                name = name.strip()
            skipped.append((pos, name, len(rest)))
            continue
        import statistics

        try:
            median = float(statistics.median(
                heights[frame] for frame in rest))
        except (TypeError, ValueError, AttributeError):
            continue
        if not (math.isfinite(median) and median > 0):
            continue
        if abs(height - median) / median <= _SHAPE_TOLERANCE:
            continue
        try:
            name = ref.get("name", "")
        except AttributeError:
            name = ""
        if not isinstance(name, str) or not name.strip():
            name = f"references[{pos}]"
        else:
            name = name.strip()
        pct = abs(height - median) / median * 100.0
        up_down = "above" if height > median else "below"
        errors.append(_err(
            "REFERENCE_SHAPE_UNSTABLE",
            f"references[{pos}].extent_px",
            f"{name} on frame {measure_frame}: mask {height:g} px "
            f"along the measured line, {pct:.0f} % {up_down} its "
            f"median {median:g} px on frames "
            f"{_frame_ranges_text(rest)} at rest; measure it on a "
            f"frame where it keeps its shape along this line "
            f"(R-S14)."))
    return errors, skipped


def _check_readings(evidence, ctx):
    errors = []
    references = evidence.get("references", [])
    for pos, ref in enumerate(references):
        if not isinstance(ref, dict):
            continue
        # Every blind-check alternative is answered (§9, §46): one
        # error per reference lists every unanswered alternative,
        # numbered, with a ready-to-paste block.
        check = ref.get("mask_check", {})
        readings = check.get("alternative_readings", []) if isinstance(
            check, dict) else []
        missing = [alt_text for alt_text in _blind_alternatives(ref, ctx)
                   if not _blind_answered(alt_text, readings)
                   and not _answered_by_derivation(alt_text, ref)]
        if missing:
            numbered = "\n".join(
                f"{num}. {alt_text!r}"
                for num, alt_text in enumerate(missing, 1))
            paste = "\n".join(
                f"{alt_text!r}: does not apply because ..."
                for alt_text in missing)
            errors.append(_err(
                "ALTERNATIVE_NOT_ADDRESSED",
                f"references[{pos}].mask_check.alternative_readings",
                f"references[{pos}] ({ref.get('name')}): the blind "
                f"check lists {len(missing)} alternatives that are "
                f"not answered:\n{numbered}\nAdd one line per "
                f"alternative to size_derivation:\n{paste}\nIf an "
                f"alternative is another size of this reference, add "
                f"{{\"description\": <alternative>, \"size_m\": <size>}} "
                f"to mask_check.alternative_readings with its size_m "
                f"instead."))
        # A sized alternative is priced in full (§12.2).
        try:
            size = float(ref.get("size_m"))
        except (TypeError, ValueError):
            continue
        if size <= 0:
            continue
        for alt_pos, (description, size_alt) in enumerate(
                _alt_sizes(ref)):
            required = abs(size_alt - size) / (2.0 * size)
            if _excused_by_second_reading(pos, ref, size_alt, evidence):
                continue
            given = _reading_spread_given(evidence)
            field = (f"references[{pos}].mask_check."
                     f"alternative_readings[{alt_pos}]")
            if given is None:
                errors.append(_err(
                    "REFERENCE_READING_UNPRICED", field,
                    f"references[{pos}] ({ref.get('name')}): "
                    f"alternative reading {description!r} at "
                    f"{size_alt:.4f} m differs from the headline "
                    f"{size:.4f} m and no reading_spread component "
                    f"prices it (required at least {required:.3f})"))
            elif given + 1e-12 < required:
                errors.append(_err(
                    "READING_SPREAD_TOO_SMALL", field,
                    f"references[{pos}] ({ref.get('name')}): "
                    f"alternative reading {description!r} at "
                    f"{size_alt:.4f} m against the headline "
                    f"{size:.4f} m requires reading_spread at least "
                    f"{required:.3f}, given {given:.3f}"))
    return errors


def _check_budget(evidence, computed):
    errors = []
    has_segments = any(isinstance(s, dict)
                       for s in (evidence.get("segments", []) or []))
    if not has_segments:
        # A result without segments assembles (§20): there is no
        # gravity σ to recompute, so the budget lists only what the
        # range checks need.
        computed["sigma_total"] = None
        computed["sigma_norep"] = None
        computed["g_head"] = None
        return errors
    budget = evidence.get("error_budget", {})
    components = budget.get("components", []) if isinstance(
        budget, dict) else []
    by_name = {}
    if isinstance(components, list):
        for comp in components:
            if isinstance(comp, dict) and comp.get("name"):
                try:
                    by_name[str(comp["name"])] = float(
                        comp.get("sigma_contribution", 0.0))
                except (TypeError, ValueError):
                    by_name[str(comp["name"])] = None
    for name in REQUIRED_COMPONENTS:
        if name not in by_name:
            errors.append(_err(
                "ERROR_BUDGET_INCOMPLETE", "error_budget.components",
                f"error_budget: required component {name!r} is missing "
                f"(R-E1)"))
        elif by_name[name] is None or by_name[name] < 0:
            errors.append(_err(
                "ERROR_BUDGET_INCOMPLETE", "error_budget.components",
                f"error_budget: component {name!r} is not a "
                f"non-negative number"))
    # Repetition fits must not have identical residuals (R-E2): the
    # evidence carries no residual series, so identical (g, σ) pairs
    # are the observable signature of a copied fit.
    seen = {}
    for index, segment in enumerate(evidence.get("segments", [])):
        if not isinstance(segment, dict):
            continue
        for rep_pos, rep in enumerate(segment.get("repetitions",
                                                  []) or []):
            if not isinstance(rep, dict):
                continue
            try:
                key = (float(rep.get("g_app")),
                       float(rep.get("sigma_g")))
            except (TypeError, ValueError):
                continue
            field = (f"segments[{index}].repetitions"
                     f"[{rep_pos}]")
            if key in seen:
                errors.append(_err(
                    "ERROR_BUDGET_INCOMPLETE", field,
                    f"{field}: repetition fit repeats g_app and "
                    f"sigma_g of {seen[key]} exactly: repetition fits "
                    f"must not have identical residuals (R-E2)"))
            else:
                seen[key] = field
    # Recompute σ_total: quadrature sum, 2% relative tolerance (§18).
    quad = 0.0
    worst = 0.0
    for name, value in by_name.items():
        if value is None or value < 0:
            continue
        quad += value * value
        worst = max(worst, value)
    rep_extra = computed.get("repetition_spread_extra", 0.0) or 0.0
    if rep_extra > 0 and "repetition_spread" not in by_name:
        quad += rep_extra * rep_extra
        worst = max(worst, rep_extra)
    total = math.sqrt(quad)
    computed["sigma_total"] = total
    # The contradiction gate (§3.5) judges the segments against the
    # measurement budget, never against a spread they inflate
    # themselves: a rep-driven σ would hide every contradiction.
    norep = quad - (rep_extra * rep_extra
                    if rep_extra > 0 and "repetition_spread"
                    not in by_name else 0.0)
    computed["sigma_norep"] = math.sqrt(max(norep, 0.0))
    try:
        sigma_relative = float(budget.get("sigma_relative", 0.0))
    except (TypeError, ValueError):
        sigma_relative = None
    g_values = _segment_g_values(computed)
    g_head = _weighted_g_head(computed)
    if g_head is None and g_values:
        g_head = sum(g_values) / len(g_values)
    computed["g_head"] = g_head
    if sigma_relative is None or g_head is None:
        return errors
    submitted = sigma_relative * g_head
    if submitted + 1e-12 < total * 0.98:
        errors.append(_err(
            "ERROR_BUDGET_INCOMPLETE", "error_budget.sigma_relative",
            f"error_budget: submitted sigma {submitted:.4f} is smaller "
            f"than the recomputed quadrature total {total:.4f}"))
    elif submitted + 1e-12 < worst * 0.98:
        errors.append(_err(
            "ERROR_BUDGET_INCOMPLETE", "error_budget.sigma_relative",
            f"error_budget: submitted sigma {submitted:.4f} is smaller "
            f"than its largest component {worst:.4f}"))
    return errors


def _mask_centroid_median(arr):
    """``(centroid_y, median_y, height)`` for one mask array, or None.

    The area centroid y is the mean row of the mask pixels; the
    median row is the row with half of the mask's pixels above it
    (the upper median of the pixel rows); the height is the
    bounding-box height. Total: never raises.
    """
    try:
        import numpy as np  # noqa: PLC0415

        canvas = np.asarray(arr, dtype=bool)
        if canvas.ndim != 2 or not bool(canvas.any()):
            return None
        rows, _cols = np.nonzero(canvas)
        if len(rows) == 0:
            return None
        centroid = float(rows.mean())
        ordered = np.sort(rows)
        median = float(ordered[len(ordered) // 2])
        height = int(rows.max() - rows.min()) + 1
        if not (math.isfinite(centroid) and math.isfinite(median)
                and height > 0):
            return None
        return centroid, median, height
    except (TypeError, ValueError, AttributeError):
        return None


def _point_vs_com_value(evidence):
    """The ``point_vs_com`` budget component, or None."""
    try:
        budget = evidence.get("error_budget", {})
        components = budget.get("components", []) if isinstance(
            budget, dict) else []
    except AttributeError:
        return None
    if not isinstance(components, list):
        return None
    for comp in components:
        if not isinstance(comp, dict):
            continue
        if comp.get("name") != "point_vs_com":
            continue
        try:
            value = float(comp.get("sigma_contribution", 0.0))
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value) or value < 0:
            return None
        return value
    return None


def _check_shape_terms(evidence, ctx, computed):
    """The point-versus-centre allowance is at least what masks show.

    For each measured segment, from its own masks
    (``segment.mask.artifact``, ``object_id``) over the frames of its
    fit: per frame the mask's area centroid y and its median row,
    one parabola for each series on the measured timestamps
    (part-09's fit, unweighted); the shape term is ``|g from the
    centroid - g from the median row|`` in m/s² at the segment's
    pixel scale. Both series carry the same camera offset in every
    frame, so the difference needs no camera correction.

    The error budget's ``point_vs_com`` must be at least the largest
    shape term (2 % tolerance, as §18). A segment whose masks cannot
    be read gives ``MISSING_FIELD`` naming the input, never a shape
    term of 0. Total: never raises.
    """
    errors = []
    try:
        segments = evidence.get("segments", [])
    except AttributeError:
        return errors
    if not isinstance(segments, list) or not any(
            isinstance(s, dict) for s in segments):
        return errors
    try:
        m_per_px = float(computed.get("m_per_px", 0.0) or 0.0)
    except (TypeError, ValueError):
        return errors
    if not math.isfinite(m_per_px) or m_per_px <= 0:
        return errors
    point_vs_com = _point_vs_com_value(evidence)
    if point_vs_com is None:
        return errors
    try:
        seg_fits = computed.get("segments", [])
    except AttributeError:
        return errors
    if not isinstance(seg_fits, list):
        return errors
    best = None
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            continue
        try:
            info = seg_fits[index] if index < len(seg_fits) else None
        except (TypeError, IndexError):
            info = None
        if not isinstance(info, dict):
            continue
        rows = info.get("rows", [])
        if not isinstance(rows, list) or not rows:
            continue
        fit_frames = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                frame = int(row.get("frame", -1))
            except (TypeError, ValueError):
                continue
            if isinstance(frame, bool):
                continue
            fit_frames.append(frame)
        if len(fit_frames) < 4:
            continue
        try:
            mask = segment.get("mask", {})
        except AttributeError:
            mask = {}
        artifact = mask.get("artifact") if isinstance(mask, dict) else None
        object_id = mask.get("object_id") if isinstance(
            mask, dict) else None
        field = f"segments[{index}].mask"
        if not isinstance(artifact, str) or not artifact:
            errors.append(_missing(
                field, f"{field}: the segment needs its mask "
                f"artifact and object id to check the body's change "
                f"of shape"))
            continue
        try:
            masks = load_object_masks(artifact, object_id, ctx)
        except (TypeError, ValueError, AttributeError):
            masks = None
        if masks is None:
            try:
                from pathlib import Path as _Path

                base = _Path(str((ctx or {}).get("run_dir", ".")
                                 or "."))
                target = base / str(artifact)
                exists = target.is_file()
            except (TypeError, ValueError, OSError, AttributeError):
                exists = False
            if not exists:
                errors.append(_missing(
                    field, f"{field}: {artifact!r} is missing or "
                    f"unreadable: the segment's masks cannot be "
                    f"read"))
            continue
        times = []
        cent_px = []
        med_px = []
        heights = []
        for frame in fit_frames:
            try:
                arr = masks.get(frame)
            except (TypeError, AttributeError):
                continue
            if arr is None:
                continue
            try:
                moment = frame_time(frame, ctx)
            except (TypeError, ValueError, AttributeError):
                continue
            if moment is None:
                continue
            try:
                moment = float(moment)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(moment):
                continue
            triple = _mask_centroid_median(arr)
            if triple is None:
                continue
            centroid, median, height = triple
            times.append(moment)
            cent_px.append(centroid)
            med_px.append(median)
            heights.append(height)
        if len(times) < 4:
            continue
        try:
            y_cent = [-y * m_per_px for y in cent_px]
            y_med = [-y * m_per_px for y in med_px]
            fit_cent = fit_parabola(times, y_cent)
            fit_med = fit_parabola(times, y_med)
            g_cent = abs(float(fit_cent.get("a", 0.0)))
            g_med = abs(float(fit_med.get("a", 0.0)))
        except (ValueError, TypeError, AttributeError):
            continue
        if not (math.isfinite(g_cent) and math.isfinite(g_med)):
            continue
        term = abs(g_cent - g_med)
        if not math.isfinite(term):
            continue
        try:
            seg_id = segment.get("id", "")
        except AttributeError:
            seg_id = ""
        if not isinstance(seg_id, str) or not seg_id.strip():
            seg_id = f"segments[{index}]"
        else:
            seg_id = seg_id.strip()
        hmin = min(heights) if heights else 0
        hmax = max(heights) if heights else 0
        if best is None or term > best[0]:
            best = (term, seg_id, g_cent, g_med, hmin, hmax)
    if best is None:
        return errors
    term, seg_id, g_cent, g_med, hmin, hmax = best
    if point_vs_com + 1e-12 < term * 0.98:
        errors.append(_err(
            "ERROR_BUDGET_INCOMPLETE", "error_budget.components",
            f"point_vs_com {point_vs_com:.4f} is smaller than the "
            f"shape term {term:.4f} m/s² of segment {seg_id}: the "
            f"body changes shape in the fit (mask height "
            f"{hmin}–{hmax} px); the area centroid gives g = "
            f"{g_cent:.4f}, the median row gives g = {g_med:.4f}. "
            f"Set point_vs_com to at least {term:.4f} and recompute "
            f"sigma_relative."))
    return errors


def _check_worlds(evidence):
    errors = []
    worlds = evidence.get("worlds", {})
    if not isinstance(worlds, dict):
        return [_missing("worlds", "worlds: no worlds listing: "
                                   "candidates come from the scene")]
    candidates = worlds.get("candidates", [])
    if not isinstance(candidates, list):
        return [_missing("worlds.candidates",
                         "worlds.candidates: must be a list")]
    names = []
    for pos, entry in enumerate(candidates):
        if not isinstance(entry, dict):
            errors.append(_missing(
                f"worlds.candidates[{pos}]",
                f"worlds.candidates[{pos}]: not an object"))
            continue
        world = entry.get("world")
        if not isinstance(world, str) or not world:
            errors.append(_missing(
                f"worlds.candidates[{pos}].world",
                f"worlds.candidates[{pos}]: needs a world name"))
            continue
        names.append(world)
        if world not in WORLD_G:
            errors.append(_err(
                "WORLD_NOT_FROM_SCENE",
                f"worlds.candidates[{pos}].world",
                f"worlds.candidates[{pos}]: unknown world {world!r}: "
                f"candidates come from the scene (R-W1)"))
    excluded = worlds.get("excluded", [])
    if not isinstance(excluded, list):
        errors.append(_missing("worlds.excluded",
                               "worlds.excluded: must be a list"))
        excluded = []
    for pos, entry in enumerate(excluded):
        field = f"worlds.excluded[{pos}]"
        if not isinstance(entry, dict):
            errors.append(_err("WORLD_NOT_FROM_SCENE", field,
                               f"{field}: exclusion is not an object "
                               f"(R-W1)"))
            continue
        frames = entry.get("evidence_frames", [])
        artifact = str(entry.get("evidence_artifact", "") or "").strip()
        if (not artifact or not isinstance(frames, list)
                or not frames):
            errors.append(_err(
                "WORLD_NOT_FROM_SCENE", field,
                f"{field}: every exclusion needs frame-referenced "
                f"visual evidence (artifact + frame indices) (R-W1)"))
        if entry.get("world") in names:
            errors.append(_err(
                "WORLD_NOT_FROM_SCENE", field,
                f"{field}: {entry.get('world')!r} is both a candidate "
                f"and excluded: fits run only over candidates (R-W1)"))
    return errors


def _segment_g_values(computed):
    values = []
    for info in computed.get("segments", []):
        if info is None:
            continue
        try:
            values.append(float(info["fit"]["g_app"]))
        except (KeyError, TypeError, ValueError):
            continue
    return values


def _weighted_g_head(computed):
    """Inverse-variance weighted mean of the segments' recomputed g.

    Weights come from each fit's own ``g_app_sigma`` (brief §43).
    Segments with a non-positive, non-finite or dust-level fit sigma
    carry no weight; when no segment has a usable sigma, the plain
    mean is used. ``None`` when there is no recomputed g at all.
    """
    pairs = []
    for info in computed.get("segments", []) or []:
        if not isinstance(info, dict):
            continue
        fit = info.get("fit", {})
        if not isinstance(fit, dict):
            continue
        try:
            value = float(fit.get("g_app"))
            sigma = float(fit.get("g_app_sigma", 0.0))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        pairs.append((value, sigma))
    if not pairs:
        return None
    if len(pairs) == 1:
        # One flight: its own recomputed g, exactly (no reordering
        # of the arithmetic).
        return pairs[0][0]
    # Fit sigmas at floating-point dust (below 1e-9 m/s²) are the
    # signature of an exact synthetic track, not a measurement: they
    # carry no weight. Any real fit sigma is orders of magnitude
    # above this floor.
    weighted = [(g, s) for g, s in pairs
                if math.isfinite(s) and s > 1e-9]
    if not weighted:
        return sum(g for g, _ in pairs) / len(pairs)
    total = sum(1.0 / (s * s) for _, s in weighted)
    if not math.isfinite(total) or total <= 0:
        return sum(g for g, _ in pairs) / len(pairs)
    return sum(g / (s * s) for g, s in weighted) / total


def decide_verdict(evidence, computed, ctx):
    """Deterministic verdict from the evidence (brief §3).

    Returns a preview dict with ``kind`` (``world``, ``retimed``,
    ``impossible``, ``undetermined``), ``world``, ``direction``,
    ``factor``, ``g_measured``, ``sigma_g``, ``reason`` and
    ``clock_note``. Never raises on content.
    """
    preview = {"kind": "undetermined", "world": None, "direction": None,
               "factor": None, "g_measured": None, "sigma_g": None,
               "reason": "no measurable segment", "clock_note": None,
               "clock_interval": None, "native": []}
    try:
        return _decide_inner(evidence, computed, preview)
    except (TypeError, ValueError, AttributeError, KeyError,
            ZeroDivisionError):
        return preview


def _decide_inner(evidence, computed, preview):
    from src.helpers.physics import worlds_fit

    values = _segment_g_values(computed)
    sigma_total = computed.get("sigma_total")
    if sigma_total is None or sigma_total <= 0 or not values:
        return preview
    # Several flights give one g: the inverse-variance weighted mean
    # of the segments' recomputed g (brief §43).
    g_head = _weighted_g_head(computed)
    if g_head is None:
        g_head = sum(values) / len(values)
    # Contradictory segments cannot be reconciled (§3.5), judged
    # against the uninflated measurement budget.
    sigma_gate = computed.get("sigma_norep") or sigma_total
    if len(values) > 1:
        for left in range(len(values)):
            for right in range(left + 1, len(values)):
                combined = math.sqrt(2.0) * sigma_gate
                if abs(values[left] - values[right]) > 2.0 * combined:
                    preview.update(
                        g_measured=g_head, sigma_g=sigma_total,
                        reason="undetermined (conflicting segments)")
                    return preview
    candidates = []
    if isinstance(evidence.get("worlds"), dict):
        for entry in evidence["worlds"].get("candidates", []) or []:
            if isinstance(entry, dict) and entry.get("world") in WORLD_G:
                candidates.append(entry["world"])
    native = []
    for world in candidates:
        delta = abs(WORLD_G[world] - g_head) / sigma_total
        native.append({"world": world, "delta_sigma": delta,
                       "fits_native": bool(delta <= 2.0)})
    preview["native"] = native
    preview["g_measured"] = g_head
    preview["sigma_g"] = sigma_total
    fitting = sorted(native, key=lambda e: e["delta_sigma"])
    if sum(1 for e in native if e["fits_native"]) == 1:
        winner = [e for e in native if e["fits_native"]][0]
        preview.update(kind="world", world=winner["world"],
                       reason=None)
        return preview
    if sum(1 for e in native if e["fits_native"]) > 1:
        preview.update(reason="multiple worlds fit natively")
        return preview
    clock = evidence.get("clock")
    if clock is None:
        if len(candidates) == 1:
            preview.update(kind="retimed", world=candidates[0],
                           direction=None, factor=None,
                           clock_note="clock: none, scene-pinned",
                           reason=None)
            stretch = math.sqrt(WORLD_G[candidates[0]] / g_head) \
                if g_head > 0 else None
            if stretch is not None and math.isfinite(stretch):
                preview["factor"] = display_factor(stretch)
                preview["direction"] = ("slowed" if stretch >= 1.0
                                        else "sped")
            return preview
        preview.update(
            reason="cannot separate retiming from impossibility")
        return preview
    if not isinstance(clock, dict):
        preview.update(
            reason="cannot separate retiming from impossibility")
        return preview
    interval = _clock_interval(clock)
    preview["clock_interval"] = interval
    if interval is None:
        preview.update(
            reason="cannot separate retiming from impossibility")
        return preview
    lo, hi, centre = interval
    reads_normal = bool(lo <= 1.0 <= hi)
    scored = []
    for entry in native:
        world = entry["world"]
        if g_head <= 0:
            continue
        s_grav = math.sqrt(WORLD_G[world] / g_head)
        sigma_s = (s_grav * 0.5 * sigma_total / g_head
                   if g_head > 0 else 0.0)
        overlap = not (s_grav + 2.0 * sigma_s < lo
                       or s_grav - 2.0 * sigma_s > hi)
        scored.append((entry, s_grav, sigma_s, overlap))
    agreeing = [s for s in scored if s[3]]
    if agreeing:
        best_entry, s_grav, _sigma_s, _ = min(
            agreeing, key=lambda s: abs(s[1] - centre))
        if not reads_normal:
            preview.update(
                kind="retimed", world=best_entry["world"],
                direction="slowed" if s_grav >= 1.0 else "sped",
                factor=display_factor(s_grav),
                clock_note="clock agrees", reason=None)
            return preview
        preview.update(
            reason="the clock cannot separate retiming from a "
                   "measurement error")
        return preview
    if reads_normal:
        preview.update(kind="impossible", world=None,
                       clock_note="clock reads normal",
                       reason="the clock reads normal but no candidate "
                              "world fits the measured gravity")
        return preview
    preview.update(reason="the clock cannot separate retiming from a "
                          "measurement error")
    return preview


def _check_clock(evidence, computed, ctx):
    """V11: the honest-clock rules (brief §§2, 9)."""
    errors = []
    clock = evidence.get("clock")
    if clock is None:
        return errors
    if not isinstance(clock, dict):
        return [_missing("clock", "clock: must be an object or null")]
    try:
        rate = float(clock.get("measured_rate_hz", 0.0))
        band = clock.get("band_hz", [])
        band_lo, band_hi = float(band[0]), float(band[1])
    except (TypeError, ValueError, IndexError, KeyError,
            AttributeError):
        return [_err("CLOCK_LOGIC", "clock.measured_rate_hz",
                     "clock: the rate and band must be numbers (R-C2)")]
    if not band_lo < rate < band_hi:
        errors.append(_err(
            "CLOCK_LOGIC", "clock.measured_rate_hz",
            f"clock: rate {rate:.3f} Hz is not strictly inside the "
            f"stated band [{band_lo:.3f}, {band_hi:.3f}]: a peak at "
            f"the band edge is no reliable clock (R-C2)"))
    # Step/stride ambiguity that would change the verdict (R-C3).
    if clock.get("ambiguous"):
        preview = computed.get("verdict_preview", {})
        if preview.get("kind") in ("retimed", "impossible", "world"):
            computed["verdict_forced_undetermined"] = True
    return errors


def _check_text(evidence, ctx):
    errors = []
    import re

    digit = re.compile(r"[0-9]")
    for index, segment in enumerate(evidence.get("segments", [])):
        if not isinstance(segment, dict):
            continue
        for pos, moment in enumerate(segment.get("key_moments",
                                                 []) or []):
            if not isinstance(moment, dict):
                continue
            caption = moment.get("caption", "")
            if isinstance(caption, str) and digit.search(caption):
                errors.append(_err(
                    "UNMEASURED_NUMBER_IN_TEXT",
                    f"segments[{index}].key_moments[{pos}].caption",
                    f"segments[{index}].key_moments[{pos}]: the "
                    f"caption carries a digit: agent-authored display "
                    f"text must be digit-free"))
    page_texts = evidence.get("page_texts", {})
    if isinstance(page_texts, dict):
        for key, value in page_texts.items():
            if isinstance(value, str) and digit.search(value):
                errors.append(_err(
                    "UNMEASURED_NUMBER_IN_TEXT",
                    f"page_texts.{key}",
                    f"page_texts.{key}: the value carries a digit: "
                    f"agent-authored display text must be digit-free"))
    # Self-built tools named in provenance must be registered, passed,
    # hash-matching (part 10 §4).
    try:
        from src.selfbuilt.registry import find_tool, load_registry
    except ImportError:
        return errors
    try:
        registry = load_registry(str(ctx.get("run_dir", ".")))
    except (ValueError, OSError):
        registry = {"tools": []}
    provenance = evidence.get("provenance", {})
    artifacts = provenance.get("artifacts", []) if isinstance(
        provenance, dict) else []
    if not isinstance(artifacts, list):
        return errors
    for pos, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            continue
        name = selfbuilt_name_from_path(artifact.get("path", ""))
        if name is None:
            continue
        entry = find_tool(registry, name)
        field = f"provenance.artifacts[{pos}].path"
        if entry is None:
            errors.append(_err(
                "UNMEASURED_NUMBER_IN_TEXT", field,
                f"{field}: self-built tool {name!r} is not in the "
                f"run registry (part 10 §4)"))
            continue
        if entry.get("status") != "passed":
            errors.append(_err(
                "UNMEASURED_NUMBER_IN_TEXT", field,
                f"{field}: self-built tool {name!r} has not passed "
                f"its synthetic test (part 10 §4)"))
            continue
        try:
            from src.selfbuilt.registry import sha256_file
            digest = sha256_file(
                str(ctx.get("run_dir", ".")) + "/workspace/selfbuilt/"
                f"{name}.py")
        except (OSError, ValueError):
            digest = None
        if digest is None or digest != entry.get("module_sha256"):
            errors.append(_err(
                "UNMEASURED_NUMBER_IN_TEXT", field,
                f"{field}: self-built tool {name!r} no longer "
                f"matches its registered hash (part 10 §4)"))
    return errors


def _check_motions(evidence):
    errors = []
    first_look = evidence.get("first_look", {})
    motions = first_look.get("motions", []) if isinstance(
        first_look, dict) else []
    segments = evidence.get("segments", [])
    ids = [s.get("id") for s in segments
           if isinstance(s, dict) and isinstance(s.get("id"), str)]
    if not isinstance(motions, list):
        return errors
    seen: dict = {}
    for pos, entry in enumerate(motions):
        field = f"first_look.motions[{pos}]"
        if not isinstance(entry, dict):
            errors.append(_err("MOTION_NOT_MEASURED", field,
                               f"{field}: not an object"))
            continue
        seg_id = entry.get("segment_id")
        reason = entry.get("skip_reason")
        if isinstance(seg_id, str) and seg_id and seg_id in ids:
            seen[seg_id] = seen.get(seg_id, 0) + 1
        elif not (isinstance(reason, str) and reason.strip()):
            errors.append(_err(
                "MOTION_NOT_MEASURED", field,
                f"{field}: the entry names no existing segment and "
                f"carries no skip_reason: every listed motion is "
                f"measured or explained (R-M4)"))
    for seg_id in ids:
        if seen.get(seg_id, 0) == 0:
            errors.append(_err(
                "MOTION_NOT_MEASURED", "first_look.motions",
                f"segment {seg_id!r} appears in no motions entry: "
                f"every segment appears in exactly one entry (R-M4)"))
        elif seen.get(seg_id, 0) > 1:
            errors.append(_err(
                "MOTION_NOT_MEASURED", "first_look.motions",
                f"segment {seg_id!r} is listed "
                f"{seen.get(seg_id, 0)} times: every segment appears "
                f"in exactly one entry (R-M4)"))
    return errors


#: Skip-reason prefixes for an unmeasured motion when the evidence
#: has no measured segment (brief §56, R-M4): a range check goes
#: beside a measured motion, never in its place.
_SKIP_PREFIXES = ("cut:", "too short:", "no flight:", "out of frame:",
                  "hidden:")
_SKIP_STARTERS = ("cut:, too short:, no flight:, out of frame: or "
                  "hidden:")


def _motion_span(entry):
    """``(start, end, count)`` for a motions entry, or ``None``."""
    try:
        start = int(entry.get("frame_start"))
        end = int(entry.get("frame_end"))
    except (TypeError, ValueError, AttributeError):
        return None
    if isinstance(start, bool) or isinstance(end, bool):
        return None
    if end < start:
        return (start, end, 0)
    return (start, end, end - start + 1)


def _has_cut_inside(start, end, ctx) -> bool:
    """A part-05 cut inside ``[start, end]`` (brief §56, ``cut:``)."""
    try:
        _dups, cuts = timing_sets(ctx)
    except (TypeError, ValueError, AttributeError):
        return False
    for cut in cuts or []:
        lo = hi = None
        try:
            if isinstance(cut, dict):
                for key in ("start", "frame", "index"):
                    if cut.get(key) is not None:
                        lo = hi = int(cut[key])
                        break
                if lo is None:
                    lo = int(cut.get("frame_start",
                                     cut.get("from", -1)))
                    hi = int(cut.get("frame_end", cut.get("to", -1)))
            elif isinstance(cut, (list, tuple)) and len(cut) == 2:
                lo, hi = int(cut[0]), int(cut[1])
            elif (isinstance(cut, (int, float))
                    and not isinstance(cut, bool)):
                lo = hi = int(cut)
            else:
                continue
        except (TypeError, ValueError):
            continue
        if lo is None or hi is None:
            continue
        if hi < lo:
            lo, hi = hi, lo
        if hi < start or lo > end:
            continue
        return True
    return False


def _skip_reason_prefix(reason) -> str | None:
    """The §56 prefix a skip reason starts with, or ``None``."""
    if not isinstance(reason, str):
        return None
    lowered = reason.strip().lower()
    for prefix in _SKIP_PREFIXES:
        if lowered.startswith(prefix):
            return prefix
    return None


def _check_motion_skip_reasons(evidence, ctx, dry_run=False):
    """A named free flight is measured, not replaced (§56, R-M4).

    Applies only when the evidence has no measured segment and some
    motions entry spans 8 frames or more; results with a segment
    keep free-text skip reasons. Every such entry's ``skip_reason``
    then starts with ``cut:``, ``too short:``, ``no flight:``,
    ``out of frame:`` or ``hidden:``; the checkable ones are
    checked, and anything else is refused with
    ``MOTION_SKIP_REASON``. Total: never raises.
    """
    try:
        segments = evidence.get("segments", [])
        has_segments = any(isinstance(s, dict) for s in segments or [])
        if has_segments:
            return []
        first_look = evidence.get("first_look", {})
        motions = first_look.get("motions", []) if isinstance(
            first_look, dict) else []
        if not isinstance(motions, list) or not motions:
            return []
        spans = []
        for pos, entry in enumerate(motions):
            if not isinstance(entry, dict):
                continue
            span = _motion_span(entry)
            if span is None:
                continue
            spans.append((pos, entry, span))
        if not any(count >= 8 for _p, _e, (_a, _b, count) in spans):
            return []
        errors = []
        for pos, entry, (start, end, count) in spans:
            field = f"first_look.motions[{pos}]"
            try:
                desc = entry.get("description")
            except AttributeError:
                desc = ""
            if not isinstance(desc, str):
                desc = ""
            try:
                seg_id = entry.get("segment_id")
            except AttributeError:
                seg_id = None
            if isinstance(seg_id, str) and seg_id.strip():
                continue
            try:
                reason = entry.get("skip_reason")
            except AttributeError:
                reason = None
            prefix = _skip_reason_prefix(reason)
            head = (f"{field} (frames {start}\u2013{end}, "
                    f"'{desc}'): a named motion is measured as a "
                    f"segment, a free flight against the world's "
                    f"gravity, unless it cannot be. Start skip_reason "
                    f"with {_SKIP_STARTERS} A range check goes beside "
                    f"a measured motion, never in its place.")
            if prefix is None:
                errors.append(_err("MOTION_SKIP_REASON", field, head))
                continue
            if prefix == "cut:":
                try:
                    inside = _has_cut_inside(start, end, ctx)
                except (TypeError, ValueError, AttributeError):
                    inside = False
                if not inside:
                    errors.append(_err(
                        "MOTION_SKIP_REASON", field,
                        head + f" Got 'cut:' but the part-05 cut list "
                        f"has no cut inside frames {start}\u2013{end}."))
            elif prefix == "too short:":
                if count >= 8:
                    errors.append(_err(
                        "MOTION_SKIP_REASON", field,
                        head + f" Got 'too short:' but the entry "
                        f"covers {count} frames (\u22658)."))
            elif prefix == "no flight:":
                try:
                    overview = _overview_block(evidence)
                except (TypeError, ValueError, AttributeError):
                    overview = None
                if overview is None:
                    if dry_run:
                        errors.append(_err(
                            "MOTION_OVERVIEW_MISSING",
                            "first_look.overview",
                            f"first_look.overview: no motion overview "
                            f"while the result leaves a named motion "
                            f"unmeasured (frames {start}\u2013{end}): "
                            f"segment the moving body over the whole "
                            f"clip and run motion_overview"))
                    continue
                try:
                    artifact = overview.get("artifact")
                    object_id = overview.get("object_id")
                except AttributeError:
                    artifact, object_id = None, None
                try:
                    _span, runs = _overview_recompute(
                        artifact, object_id, ctx)
                except (TypeError, ValueError, AttributeError):
                    runs = None
                if runs is None:
                    if dry_run:
                        errors.append(_err(
                            "MOTION_OVERVIEW_MISSING",
                            "first_look.overview",
                            f"first_look.overview: no motion overview "
                            f"while the result leaves a named motion "
                            f"unmeasured (frames {start}\u2013{end}): "
                            f"segment the moving body over the whole "
                            f"clip and run motion_overview"))
                    continue
                hit = None
                for run_start, run_end in runs:
                    try:
                        if _ranges_match(start, end, run_start,
                                         run_end):
                            hit = (run_start, run_end)
                            break
                    except (TypeError, ValueError):
                        continue
                if hit is not None:
                    run_start, run_end = hit
                    errors.append(_err(
                        "MOTION_SKIP_REASON", field,
                        head + f" Got 'no flight:' but the recomputed "
                        f"overview has a candidate at frames "
                        f"{run_start}\u2013{run_end} overlapping "
                        f"frames {start}\u2013{end}."))
            else:
                continue
        return errors
    except (TypeError, ValueError, AttributeError):
        return []


# --- motion survey: every candidate flight is decided (brief §43) ----

#: Support half-window for the overview recompute, in seconds: the
#: documented ``motion_overview`` rule (part 07 §21).
_OVERVIEW_SUPPORT_S = 1.0
#: Rise thresholds for the overview recompute: ``max(3 px, 4 % of the
#: median mask height)`` (part 07 §21).
_OVERVIEW_RISE_PX = 3.0
_OVERVIEW_RISE_FRAC = 0.04
#: Minimum consecutive frames for an overview candidate (part 07 §21).
_OVERVIEW_MIN_FRAMES = 4
#: A reference measuring frame more than this far (in seconds) from
#: the first-check takeoff is pushed in a dry run, and refused when
#: its own mask holds it next to the motion (brief §§43–44, R-S11).
_FAR_GAP_S = 2.0
#: Minimum in-window mask frames for the tightened far refusal: the
#: reference's own mask holds its object on this many frames within
#: 2 s before the first-check takeoff (brief §44, R-S11).
_FAR_MIN_PRESENT = 5
#: Whole-clip coverage margins: the overview masks must start at or
#: before frame 2 and end at or after frame N − 3 (brief §43).
_COVER_FIRST_MAX = 2
_COVER_LAST_MARGIN = 3
#: Forced-undetermined reason when the clip's motions were not
#: surveyed (brief §43).
_NOT_SURVEYED = "the motions in the clip were not surveyed"


def _overview_block(evidence):
    """The evidence's ``first_look.overview``, or None (total)."""
    try:
        first_look = evidence.get("first_look", {})
        overview = first_look.get("overview")
    except AttributeError:
        return None
    return overview if isinstance(overview, dict) else None


def _overview_rows(artifact, object_id, ctx):
    """Per-frame overview rows, or None when the masks cannot be read.

    One row per non-empty mask frame: ``frame``, ``t_s``,
    ``bottom_y``, ``height_px`` and ``centroid_y`` (the largest
    piece's centroid, mirroring part 07's ``motion_overview`` rows).
    Total: never raises, never writes.
    """
    try:
        from src.helpers import tracks
    except ImportError:
        return None
    try:
        masks = load_object_masks(artifact, object_id, ctx)
    except (TypeError, ValueError, AttributeError):
        return None
    if not masks:
        return None
    try:
        _fps, _count, _duration, stamps = timing_numbers(ctx)
    except (TypeError, ValueError, AttributeError):
        return None
    rows = []
    for frame in sorted(masks):
        if isinstance(frame, bool):
            continue
        try:
            import numpy as np  # noqa: PLC0415

            canvas = np.asarray(masks[frame], dtype=bool)
            if not bool(canvas.any()):
                continue
            big = tracks.largest_component(canvas)
            stats = tracks.mask_stats(big)
            moment = float(stamps[int(frame)])
            centroid_y = float(stats["centroid"]["y"])
        except (ValueError, IndexError, TypeError, AttributeError,
                KeyError):
            continue
        rows.append({"frame": int(frame), "t_s": moment,
                     "bottom_y": int(stats["bottom"]),
                     "height_px": int(stats["height"]),
                     "centroid_y": centroid_y})
    return rows or None


def _parabola_r2(xs, ys):
    """``R²`` of ``y = a t² + b t + c`` over the track.

    The same fit part 07's ``motion_overview`` reports as
    ``centroid_r_squared``: least squares on centred times,
    ``1 − SSres/SStot`` (1.0 on a perfectly flat track, 0.0 when
    the fit explains nothing of a spread). Total over input.
    """
    try:
        import numpy as np  # noqa: PLC0415

        t = np.asarray([float(v) for v in xs], dtype=float)
        y = np.asarray([float(v) for v in ys], dtype=float)
    except (TypeError, ValueError):
        return 0.0
    try:
        span = float(t.max() - t.min()) if len(t) else 0.0
    except (TypeError, ValueError):
        return 0.0
    if len(t) < 3 or not math.isfinite(span) or span <= 0.0:
        return 0.0
    centre = float(t.mean())
    tc = t - centre
    try:
        a, _b, _c = np.polyfit(tc, y, 2)
    except (TypeError, ValueError):
        return 0.0
    try:
        fitted = a * tc * tc + _b * tc + _c
        residual = float(np.sum((y - fitted) ** 2))
        spread = float(np.sum((y - float(y.mean())) ** 2))
    except (TypeError, ValueError):
        return 0.0
    if not (math.isfinite(residual) and math.isfinite(spread)):
        return 0.0
    if spread <= 0.0:
        return 1.0 if residual <= 0.0 else 0.0
    return max(0.0, min(1.0, 1.0 - residual / spread))


def _overview_runs_with_r2(artifact, object_id, ctx):
    """``(span, runs)`` with each run's centroid parabola ``R²``.

    ``runs`` is ``[(start, end, r_squared)]``: the recomputed
    candidate ranges of :func:`_overview_recompute` plus the R² of a
    parabola fitted to the centroid-y track over the run — the same
    number part 07's ``motion_overview`` reports as
    ``centroid_r_squared``. ``(None, None)`` when the masks cannot
    be read. Total: never raises, never writes.
    """
    rows = _overview_rows(artifact, object_id, ctx)
    if not rows:
        return None, None
    span, ranges = _ranges_from_rows(rows)
    by_frame = {row["frame"]: row for row in rows}
    runs = []
    for start, end in ranges:
        xs = []
        ys = []
        for frame in range(start, end + 1):
            row = by_frame.get(frame)
            if row is None:
                continue
            xs.append(row["t_s"])
            ys.append(row["centroid_y"])
        runs.append((start, end, _parabola_r2(xs, ys)))
    return span, runs


def _ranges_from_rows(rows):
    """``(span, ranges)`` from overview rows (part 07 §21).

    Rise is the support level (lowest bottom within ±1 s) minus the
    bottom, the threshold is ``max(3 px, 4 % of the median mask
    height)``, and a candidate is a maximal run of at least 4
    consecutive frames above it.
    """
    import statistics

    span = (rows[0]["frame"], rows[-1]["frame"])
    try:
        median_h = float(statistics.median(
            r["height_px"] for r in rows))
    except (TypeError, ValueError, AttributeError):
        return span, []
    threshold = max(_OVERVIEW_RISE_PX, _OVERVIEW_RISE_FRAC * median_h)
    for row in rows:
        level = row["bottom_y"]
        for other in rows:
            try:
                near = abs(float(other["t_s"]) - float(row["t_s"]))
            except (TypeError, ValueError):
                continue
            if near <= _OVERVIEW_SUPPORT_S and (
                    other["bottom_y"] > level):
                level = other["bottom_y"]
        row["rise_px"] = float(level - row["bottom_y"])
    runs: list = []
    current: list = []
    for row in rows:
        if float(row["rise_px"]) >= threshold:
            if current and row["frame"] != current[-1] + 1:
                runs.append(list(current))
                current = []
            current.append(row["frame"])
        elif current:
            runs.append(list(current))
            current = []
    if current:
        runs.append(list(current))
    ranges = [(run[0], run[-1]) for run in runs
              if len(run) >= _OVERVIEW_MIN_FRAMES]
    return span, ranges


def _overview_recompute(artifact, object_id, ctx):
    """Recompute part 07's ``motion_overview`` candidates, read-only.

    Returns ``(span, runs)``: ``span`` is ``(first, last)`` mask
    frames, ``runs`` the ``(start, end)`` candidate frame ranges.
    ``(None, None)`` when the masks cannot be read. The computation
    mirrors the tool's documented rule (part 07 §21): rise is the
    support level (lowest bottom within ±1 s) minus the bottom, the
    threshold is ``max(3 px, 4 % of the median mask height)``, and a
    candidate is a maximal run of at least 4 consecutive frames above
    it. Masks are read with the part-09 reader, the same one the
    agent uses. Total: never raises, never writes.
    """
    try:
        rows = _overview_rows(artifact, object_id, ctx)
    except (TypeError, ValueError, AttributeError):
        return None, None
    if not rows:
        return None, None
    try:
        return _ranges_from_rows(rows)
    except (TypeError, ValueError, AttributeError):
        return None, None
    if current:
        runs.append(list(current))
    ranges = [(run[0], run[-1]) for run in runs
              if len(run) >= _OVERVIEW_MIN_FRAMES]
    return span, ranges


def _ranges_match(start_a, end_a, start_b, end_b) -> bool:
    """Frame ranges overlap by at least half of the shorter (brief §43)."""
    try:
        start_a, end_a = int(start_a), int(end_a)
        start_b, end_b = int(start_b), int(end_b)
    except (TypeError, ValueError):
        return False
    if end_a < start_a or end_b < start_b:
        return False
    overlap = max(0, min(end_a, end_b) - max(start_a, start_b) + 1)
    shorter = min(end_a - start_a + 1, end_b - start_b + 1)
    if shorter <= 0:
        return False
    return overlap * 2 >= shorter


def _evidence_segments_by_id(evidence) -> dict:
    out = {}
    segments = evidence.get("segments", [])
    if not isinstance(segments, list):
        return out
    for index, segment in enumerate(segments):
        if isinstance(segment, dict):
            seg_id = segment.get("id")
            if isinstance(seg_id, str) and seg_id:
                out[seg_id] = (index, segment)
    return out


def _overview_first_takeoff(evidence, ctx):
    """``(frame, time_s)`` of the first-check takeoff, or ``(None, None)``."""
    overview = _overview_block(evidence)
    if overview is None:
        return None, None
    try:
        first = overview.get("first_check", {})
        seg_id = first.get("segment_id") if isinstance(
            first, dict) else None
    except AttributeError:
        return None, None
    if not isinstance(seg_id, str) or not seg_id:
        return None, None
    found = _evidence_segments_by_id(evidence).get(seg_id)
    if found is None:
        return None, None
    _index, segment = found
    try:
        start = int(segment.get("frames", {}).get("start"))
    except (TypeError, ValueError, AttributeError):
        return None, None
    if isinstance(start, bool):
        return None, None
    return start, frame_time(start, ctx)


def _run_has_survey_masks(ctx) -> bool:
    """Any mask object in the run spanning a candidate-length run.

    Compatibility for runs predating the overview survey (brief §43):
    part 07's default-valid-run mirror carries only single-frame
    reference masks and no whole-clip survey, so there is nothing the
    overview recompute could judge. Such runs are judged as before
    §43; once any object spans ``_OVERVIEW_MIN_FRAMES`` frames the
    survey is possible and a missing overview is pushed/forced as
    the spec says. Total: never raises; unreadable bundles simply
    do not count.
    """
    try:
        from .io import _masks_bundle  # noqa: PLC0415
    except ImportError:
        return True
    try:
        rels = sorted(artifact_set(ctx))
    except Exception:  # noqa: BLE001
        return True
    for rel in rels:
        if not str(rel).lower().endswith(".npz"):
            continue
        try:
            bundle = _masks_bundle(rel, ctx)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(bundle, dict):
            continue
        for frames in bundle.values():
            if not isinstance(frames, dict):
                continue
            try:
                count = sum(1 for f in frames
                            if not isinstance(f, bool))
            except Exception:  # noqa: BLE001
                continue
            if count >= _OVERVIEW_MIN_FRAMES:
                return True
    return False


def _survey_overview(evidence, ctx):
    """Recompute the overview and compare it with the decisions.

    Returns a status dict with ``present`` (a usable overview block),
    ``span``, ``runs`` (``None`` when the masks cannot be read),
    ``unconsidered`` recomputed ranges, ``partial`` detail (or None),
    ``missing`` (no survey to judge by), ``force`` (the
    forced-undetermined reason for a real submit, or None) and
    ``far`` references. Total: never raises.
    """
    status = {"present": False, "span": None, "runs": None,
              "unconsidered": [], "partial": None, "missing": True,
              "force": None, "far": []}
    overview = _overview_block(evidence)
    if overview is None:
        try:
            has_survey = _run_has_survey_masks(ctx)
        except Exception:  # noqa: BLE001
            has_survey = True
        if not has_survey:
            status["missing"] = False
            status["force"] = None
            return status
        status["force"] = _NOT_SURVEYED
        return status
    try:
        candidates = overview.get("candidates", [])
    except AttributeError:
        candidates = []
    if not isinstance(candidates, list):
        candidates = []
    try:
        artifact = overview.get("artifact")
        object_id = overview.get("object_id")
    except AttributeError:
        artifact, object_id = None, None
    span, runs = _overview_recompute(artifact, object_id, ctx)
    if runs is None:
        status["force"] = _NOT_SURVEYED
        return status
    status.update(present=True, missing=False, span=span, runs=runs)
    try:
        _fps, count, _duration, _stamps = timing_numbers(ctx)
    except (TypeError, ValueError, AttributeError):
        count = 0
    if isinstance(count, bool):
        count = 0
    try:
        count = int(count or 0)
    except (TypeError, ValueError):
        count = 0
    if count > 0 and span is not None:
        first, last = span
        if first > _COVER_FIRST_MAX or last < count - _COVER_LAST_MARGIN:
            status["partial"] = (
                f"the overview masks cover frames {first}-{last} "
                f"of a {count}-frame clip: segment the moving body "
                f"over the whole clip (first frame 2 or earlier, "
                f"last frame {count - _COVER_LAST_MARGIN} or later) "
                f"and run motion_overview")
            status["force"] = _NOT_SURVEYED
            return status
    listed = []
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        try:
            listed.append((int(entry.get("frame_start")),
                           int(entry.get("frame_end"))))
        except (TypeError, ValueError):
            continue
    unconsidered = []
    for start, end in runs:
        if not any(_ranges_match(start, end, first, last)
                   for first, last in listed):
            unconsidered.append((start, end))
    status["unconsidered"] = sorted(unconsidered)
    if unconsidered:
        if len(unconsidered) == 1:
            start, end = unconsidered[0]
            status["force"] = (
                f"a possible flight at frames {start}-{end} was "
                f"not considered")
        else:
            spans = ", ".join(f"{a}-{b}" for a, b in unconsidered)
            status["force"] = (
                f"possible flights at frames {spans} were not "
                f"considered")
    return status


def _check_overview_decisions(evidence):
    """Overview decisions against the evidence segments (brief §§14, 43).

    A ``measured`` candidate whose segment does not exist, or a
    segment that is in no candidate, is ``MOTION_NOT_MEASURED``.
    """
    errors = []
    overview = _overview_block(evidence)
    if overview is None:
        return errors
    try:
        candidates = overview.get("candidates", [])
    except AttributeError:
        return errors
    if not isinstance(candidates, list):
        return errors
    by_id = _evidence_segments_by_id(evidence)
    measured: set = set()
    for pos, entry in enumerate(candidates):
        if not isinstance(entry, dict):
            continue
        try:
            start = int(entry.get("frame_start"))
            end = int(entry.get("frame_end"))
        except (TypeError, ValueError):
            start, end = "?", "?"
        if entry.get("decision") != "measured":
            continue
        seg_id = entry.get("segment_id")
        field = f"first_look.overview.candidates[{pos}].segment_id"
        if not isinstance(seg_id, str) or seg_id not in by_id:
            errors.append(_err(
                "MOTION_NOT_MEASURED", field,
                f"first_look.overview.candidates[{pos}] (frames "
                f"{start}-{end}) is decided measured but names no "
                f"evidence segment: every measured flight is measured "
                f"as its own segment (R-M4)"))
        else:
            measured.add(seg_id)
    segments = evidence.get("segments", [])
    if not isinstance(segments, list):
        return errors
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            continue
        seg_id = segment.get("id")
        if (isinstance(seg_id, str) and seg_id
                and seg_id not in measured):
            errors.append(_err(
                "MOTION_NOT_MEASURED", f"segments[{index}].id",
                f"segment {seg_id!r} is measured but appears in no "
                f"overview candidate decision: every segment appears "
                f"in exactly one measured candidate (R-M4)"))
    return errors


#: A measured flight follows one parabola: the recomputed overview
#: candidate's centroid-track R² below this is not a free flight
#: (brief §45).
_PARABOLIC_R2_MIN = 0.8


def _check_flight_parabolic(evidence, ctx):
    """``FLIGHT_NOT_PARABOLIC``: a measured flight follows one parabola.

    A candidate decided ``measured`` whose recomputed overview
    candidate (§43) has ``centroid_r_squared`` below 0.8 mixed phases
    into one window — a free flight follows one parabola, so the
    candidate is decided ``not_a_flight`` with the reason instead.
    The detail names the candidate, its R² and the R² of the other
    candidates. A measured segment inside a longer candidate is
    judged on its own frames (§55): when the candidate's
    ``segment_id`` names a segment strictly inside the run, the
    centroid R² over the segment's frames decides instead. Total:
    never raises.
    """
    try:
        overview = _overview_block(evidence)
    except (TypeError, ValueError, AttributeError):
        return []
    if overview is None:
        return []
    try:
        candidates = overview.get("candidates", [])
    except AttributeError:
        return []
    if not isinstance(candidates, list):
        return []
    try:
        _span, runs = _overview_runs_with_r2(
            overview.get("artifact"), overview.get("object_id"), ctx)
    except (TypeError, ValueError, AttributeError):
        return []
    if not runs:
        return []
    try:
        _rows = _overview_rows(
            overview.get("artifact"), overview.get("object_id"), ctx)
    except (TypeError, ValueError, AttributeError):
        _rows = None
    _by_frame = {}
    if _rows:
        try:
            for _row in _rows:
                _by_frame[int(_row["frame"])] = _row
        except (TypeError, ValueError, AttributeError, KeyError):
            _by_frame = {}
    try:
        _segments = _evidence_segments_by_id(evidence)
    except (TypeError, ValueError, AttributeError):
        _segments = {}
    labels = [f"F{pos + 1}" for pos in range(len(runs))]
    errors = []
    for (start, end, r2), label in zip(runs, labels):
        try:
            r2 = float(r2)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(r2) or r2 >= _PARABOLIC_R2_MIN:
            continue
        for pos, entry in enumerate(candidates):
            if not isinstance(entry, dict):
                continue
            if entry.get("decision") != "measured":
                continue
            try:
                first = int(entry.get("frame_start"))
                last = int(entry.get("frame_end"))
            except (TypeError, ValueError):
                continue
            if isinstance(first, bool) or isinstance(last, bool):
                continue
            if not _ranges_match(start, end, first, last):
                continue
            _seg_extra = ""
            try:
                _seg_id = entry.get("segment_id")
                _found = _segments.get(_seg_id) if isinstance(
                    _seg_id, str) else None
                if _found is not None:
                    _seg = _found[1]
                    _s_start = int(_seg.get("frames", {}).get("start"))
                    _s_end = int(_seg.get("frames", {}).get("end"))
                    if (not isinstance(_s_start, bool)
                            and not isinstance(_s_end, bool)
                            and _s_start >= start and _s_end <= end
                            and (_s_end - _s_start + 1) < (end - start + 1)
                            and _by_frame):
                        _xs = []
                        _ys = []
                        for _frame in range(_s_start, _s_end + 1):
                            _row = _by_frame.get(_frame)
                            if _row is None:
                                continue
                            _xs.append(_row["t_s"])
                            _ys.append(_row["centroid_y"])
                        _sub_r2 = _parabola_r2(_xs, _ys)
                        try:
                            _sub_r2 = float(_sub_r2)
                        except (TypeError, ValueError):
                            _sub_r2 = 0.0
                        if (math.isfinite(_sub_r2)
                                and _sub_r2 >= _PARABOLIC_R2_MIN):
                            break
                        _seg_extra = (
                            f" Segment {_seg_id} frames "
                            f"{_s_start}-{_s_end}: r² {_sub_r2:.2f} "
                            f"on its own frames.")
            except (TypeError, ValueError, AttributeError, KeyError):
                _seg_extra = ""
            rest = ", ".join(
                f"{other} {other_r2:.2f}"
                for other, (_s, _e, other_r2) in zip(labels, runs)
                if other != label)
            if rest:
                rest = f" ({rest})"
            errors.append(_err(
                "FLIGHT_NOT_PARABOLIC",
                f"first_look.overview.candidates[{pos}]",
                f"{label} frames {start}-{end}: the centroid track "
                f"fits one parabola with r² {r2:.2f}{rest}. A "
                f"free flight follows one parabola; decide it "
                f"not_a_flight with the reason.{_seg_extra}"))
            break
    return errors


def _mask_presence_in_window(artifact, object_id, window_start_s,
                               window_end_s, ctx):
    """Frames holding the object inside a time window (brief §44).

    The reference's own mask frames with a non-empty mask whose
    frame time lies in ``[window_start_s, window_end_s]``. Read
    with the part-09 reader. Total: never raises.
    """
    try:
        masks = load_object_masks(artifact, object_id, ctx)
    except (TypeError, ValueError, AttributeError):
        return []
    if not isinstance(masks, dict):
        return []
    present = []
    for frame, arr in masks.items():
        if isinstance(frame, bool):
            continue
        try:
            moment = float(frame_time(frame, ctx))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(moment):
            continue
        if not (window_start_s - 1e-9 <= moment <= window_end_s + 1e-9):
            continue
        try:
            import numpy as np  # noqa: PLC0415

            if not bool(np.asarray(arr, dtype=bool).any()):
                continue
        except (TypeError, ValueError):
            continue
        try:
            present.append(int(frame))
        except (TypeError, ValueError):
            continue
    return sorted(present)


def _check_reference_far(evidence, ctx):
    """References far from the first-check takeoff (§§43–44, R-S11).

    When the reference's own mask holds its object on 5 or more
    frames within 2 s before the first-check takeoff and the
    measuring frame is outside that window, the submit is refused
    with ``REFERENCE_FAR_FROM_MOTION``, whatever the note says
    (brief §44, tightened R-S11): the reference was there to be
    measured next to the motion. Otherwise a far measuring frame
    is a dry-run push ``REFERENCE_FAR_FROM_MOTION`` (brief §43);
    a real submit accepts it and the scale step carries a caveat.

    Returns ``(pushes, far, hard)``: ``pushes`` for the dry run,
    ``far`` listing ``(index, name, frame)`` for the caveat, and
    ``hard`` with the refusal errors (each carrying
    ``"push": False`` so the dry-run reply lists them under the
    hard errors, not the pushes).
    """
    pushes: list = []
    far: list = []
    hard: list = []
    takeoff_frame, takeoff_time = _overview_first_takeoff(
        evidence, ctx)
    if takeoff_frame is None or takeoff_time is None:
        return pushes, far, hard
    try:
        takeoff_time = float(takeoff_time)
    except (TypeError, ValueError):
        return pushes, far, hard
    if not math.isfinite(takeoff_time):
        return pushes, far, hard
    references = evidence.get("references", [])
    if not isinstance(references, list):
        return pushes, far, hard
    for pos, ref in enumerate(references):
        if not isinstance(ref, dict):
            continue
        try:
            frame = int((ref.get("extent_px", {}) or {}).get("frame"))
        except (TypeError, ValueError, AttributeError):
            continue
        if isinstance(frame, bool):
            continue
        moment = frame_time(frame, ctx)
        try:
            moment = float(moment)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(moment):
            continue
        if abs(moment - takeoff_time) <= _FAR_GAP_S:
            continue
        name = ref.get("name") if isinstance(
            ref.get("name"), str) and ref.get("name").strip() else (
                f"references[{pos}]")
        # Tightened R-S11 (§44): the reference's own mask decides.
        # Measured outside the 2 s window while its mask holds the
        # object on 5 or more frames inside it is a refusal,
        # whatever the note says.
        try:
            mask = ref.get("mask", {})
            artifact = mask.get("artifact") if isinstance(
                mask, dict) else None
            object_id = mask.get("object_id") if isinstance(
                mask, dict) else None
        except AttributeError:
            artifact, object_id = None, None
        present: list = []
        if isinstance(artifact, str) and artifact:
            try:
                present = _mask_presence_in_window(
                    artifact, object_id, takeoff_time - _FAR_GAP_S,
                    takeoff_time, ctx)
            except (TypeError, ValueError, AttributeError):
                present = []
        far.append((pos, name, frame))
        if (len(present) >= _FAR_MIN_PRESENT
                and (moment < takeoff_time - _FAR_GAP_S
                     or moment > takeoff_time)):
            try:
                fps, _count, _duration, _stamps = timing_numbers(ctx)
            except (TypeError, ValueError, AttributeError):
                fps = 0.0
            try:
                fps = float(fps)
            except (TypeError, ValueError):
                fps = 0.0
            if fps > 0:
                first = max(0, takeoff_frame - int(
                    round(_FAR_GAP_S * fps)))
                window = f"frames {first}–{takeoff_frame}"
            else:
                window = (f"{_FAR_GAP_S:g} s before the first-check "
                          f"takeoff")
            error = _err(
                "REFERENCE_FAR_FROM_MOTION", f"references[{pos}]",
                f"references[{pos}] ({name}) is measured at frame "
                f"{frame}, but its own mask holds the object on "
                f"{len(present)} frames within 2 s before the "
                f"first-check takeoff at frame {takeoff_frame} "
                f"({window}): {_frame_ranges_text(present)}; measure "
                f"the reference there (R-S11).")
            error["push"] = False
            hard.append(error)
            continue
        pushes.append(_err(
            "REFERENCE_FAR_FROM_MOTION", f"references[{pos}]",
            f"references[{pos}] ({name}) is measured at frame "
            f"{frame} ({moment:.2f} s), more than 2 s from the "
            f"first-check takeoff at frame {takeoff_frame} "
            f"({takeoff_time:.2f} s): add why in "
            f"size_derivation.note (R-S11)"))
    return pushes, far, hard


def _reference_on_moving_thing(ref, overview_artifact,
                                overview_object_id, ctx) -> bool:
    """One reference overlaps the moving thing's mask (brief §53).

    The reference counts as on the moving thing when its mask on
    its measuring frame overlaps the motion overview object's mask
    on the same frame with IoU above ``SAME_OBJECT_IOU``
    (brief §54). The overview's mask and
    every mask of the same object count (§49): both sides gather
    their same-object siblings, and any pair above the limit decides.
    Total: never raises; unreadable masks decide False.
    """
    try:
        mask = ref.get("mask", {})
        artifact = mask.get("artifact") if isinstance(
            mask, dict) else None
        object_id = mask.get("object_id") if isinstance(
            mask, dict) else None
        extent = ref.get("extent_px", {}) or {}
        measure_frame = int(extent.get("frame"))
    except (TypeError, ValueError, AttributeError):
        return False
    if isinstance(measure_frame, bool):
        return False
    if not isinstance(artifact, str) or not artifact:
        return False
    try:
        ref_array = load_mask_frame(artifact, object_id,
                                    measure_frame, ctx)
    except (TypeError, ValueError, AttributeError):
        return False
    if ref_array is None:
        return False
    ref_arrays = [ref_array]
    try:
        siblings = _same_object_mask_dicts(
            artifact, object_id, measure_frame, ref_array, ctx)
    except (TypeError, ValueError, AttributeError):
        siblings = []
    for frames in siblings or []:
        if not isinstance(frames, dict):
            continue
        arr = frames.get(measure_frame)
        if arr is not None:
            ref_arrays.append(arr)
    over_arrays = []
    try:
        over_array = load_mask_frame(overview_artifact,
                                     overview_object_id,
                                     measure_frame, ctx)
    except (TypeError, ValueError, AttributeError):
        over_array = None
    if over_array is not None:
        over_arrays.append(over_array)
        try:
            over_siblings = _same_object_mask_dicts(
                overview_artifact, overview_object_id,
                measure_frame, over_array, ctx)
        except (TypeError, ValueError, AttributeError):
            over_siblings = []
        for frames in over_siblings or []:
            if not isinstance(frames, dict):
                continue
            arr = frames.get(measure_frame)
            if arr is not None:
                over_arrays.append(arr)
    for left in ref_arrays:
        for right in over_arrays:
            try:
                iou = _mask_iou_arrays(left, right)
            except (TypeError, ValueError, AttributeError):
                continue
            if iou is not None and iou > SAME_OBJECT_IOU:
                return True
    return False


def _self_reference_push(evidence, ctx):
    """``SELF_REFERENCE_REQUIRED``: a reference on the moving thing.

    Dry-run push only (brief §53, R-S16): when
    ``first_look.overview`` names the moving thing and no reference
    overlaps that object's mask on its measuring frame with IoU
    above ``SAME_OBJECT_IOU`` (brief §54), the dry run asks for
    the moving thing's own quoted
    size. A real submit is never refused for it, and evidence
    without an overview never lists it. Total: never raises.
    """
    try:
        first_look = evidence.get("first_look", {})
        overview = first_look.get("overview") if isinstance(
            first_look, dict) else None
        artifact = overview.get("artifact") if isinstance(
            overview, dict) else None
        object_id = overview.get("object_id") if isinstance(
            overview, dict) else None
        references = evidence.get("references", [])
    except AttributeError:
        return []
    if not isinstance(artifact, str) or not artifact:
        return []
    if not isinstance(references, list) or not references:
        return []
    try:
        for ref in references:
            if not isinstance(ref, dict):
                continue
            if _reference_on_moving_thing(ref, artifact, object_id,
                                          ctx):
                return []
    except (TypeError, ValueError, AttributeError):
        return []
    return [_err(
        "SELF_REFERENCE_REQUIRED", "references",
        f"references: none of them is the moving thing (object "
        f"{object_id} of {artifact}); measure its own quoted size "
        f"on a rest frame along the dimension its source names, "
        f"and keep the others (R-S16). Skip this only when the "
        f"moving thing has no quoted size.")]


def _push_codes(evidence, computed, ctx):
    """Dry-run-only push codes (brief §16.2)."""
    out = []
    references = evidence.get("references", [])
    if len(references) < 2:
        out.append(_err(
            "SECOND_REFERENCE_REQUIRED", "references",
            "references: measure a second thing of independently "
            "known size at the depth of the motion: the moving thing "
            "itself, something it wears or carries, or a fixed "
            "thing beside it (R-S6)"))
    try:
        out.extend(_self_reference_push(evidence, ctx))
    except (TypeError, ValueError, AttributeError):
        pass
    preview = computed.get("verdict_preview", {}) or {}
    if evidence.get("clock") is None and preview.get("kind") == (
            "undetermined") and "cannot separate" in str(
                preview.get("reason", "")):
        # The verdict would be undetermined only because no clock
        # was measured: the measured g fits no candidate world.
        if not any(e.get("fits_native")
                   for e in preview.get("native", [])):
            out.append(_err(
                "CLOCK_REQUIRED", "clock",
                "clock: any repeating motion in the clip is a clock "
                "(steps, swings, wing beats, turning wheels): "
                "measure its rate (R-C1), or name in "
                "clock_absent_reason each repeating motion you "
                "checked and why it fails"))
    out.extend(_scan_push(evidence, ctx))
    out.extend(_overview_pushes(evidence, computed))
    return out


def _overview_pushes(evidence, computed):
    """Motion-survey pushes for a dry run (brief §43)."""
    out = []
    overview = computed.get("overview")
    if not isinstance(overview, dict):
        return out
    has_segments = any(isinstance(s, dict)
                       for s in (evidence.get("segments", []) or []))
    if not has_segments:
        return out
    if overview.get("missing"):
        out.append(_err(
            "MOTION_OVERVIEW_MISSING", "first_look.overview",
            "first_look.overview: no motion overview while the "
            "result measures a motion: segment the moving body over "
            "the whole clip and run motion_overview"))
        return out
    if overview.get("partial"):
        out.append(_err(
            "MOTION_OVERVIEW_PARTIAL", "first_look.overview",
            f"first_look.overview: {overview.get('partial')}"))
        return out
    for start, end in overview.get("unconsidered", []) or []:
        out.append(_err(
            "FLIGHT_NOT_CONSIDERED",
            "first_look.overview.candidates",
            f"first_look.overview.candidates: a possible flight at "
            f"frames {start}-{end} was not considered: decide it "
            f"(measured with its segment, or not a flight / not "
            f"measurable with a reason) (R-M4)"))
    for item in computed.get("reference_far_pushes", []) or []:
        if isinstance(item, dict):
            out.append(item)
    return out


def _scan_push(evidence, ctx):
    """MOTIONS_SCAN_MISSING from the turn logs (brief §16.2)."""
    import glob
    import json as _json
    import os

    run_dir = str(ctx.get("run_dir", ".") or ".")
    logs_dir = os.path.join(run_dir, "logs")
    try:
        paths = sorted(glob.glob(os.path.join(logs_dir, "turn_*.json")))
    except OSError:
        return []
    if not paths:
        return []
    covered: set = set()
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                record = _json.load(handle)
        except (OSError, ValueError):
            continue
        calls = record.get("tool_calls", record.get("calls", []))
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            name = call.get("tool", call.get("name", ""))
            args = call.get("arguments", call.get("args", {}))
            if name != "view_frames" or not isinstance(args, dict):
                continue
            try:
                if isinstance(args.get("frame_indices"), list):
                    for frame in args["frame_indices"]:
                        covered.add(int(frame))
                    continue
                start = int(args.get("frame_start", -1))
                end = int(args.get("frame_end", -1))
                stride = int(args.get("stride", 1) or 1)
            except (TypeError, ValueError):
                continue
            if start < 0 or end < start or stride <= 0:
                continue
            covered.update(range(start, end + 1, stride))
    if not covered:
        return []
    fps, count, _duration, _stamps = timing_numbers(ctx)
    if fps <= 0 or count <= 0:
        return []
    ordered = sorted(f for f in covered if 0 <= f < count)
    if not ordered:
        return []
    gaps = [ordered[0]]
    gaps.extend(b - a for a, b in zip(ordered, ordered[1:]))
    gaps.append(count - 1 - ordered[-1])
    max_gap_frames = max(gaps)
    if max_gap_frames / fps > 0.25:
        return [_err(
            "MOTIONS_SCAN_MISSING", "first_look.motions",
            "first_look.motions: view the whole clip at a spacing "
            "of at most 0.25 s and list every motion in "
            "first_look.motions (R-M4)")]
    return []


# --- validate ---------------------------------------------------------------

def validate(evidence, run_context=None, dry_run=False):
    """Validate agent evidence; on accept, compute and write the result.

    Returns ``{"accepted", "errors", ["result", "result_path"]}``.
    V1 gates the rest. A dry run returns the errors without assembling
    or writing anything. A validator fault ends the run as
    undetermined with reason ``validator_fault`` — never returned to
    the agent and never counted as an attempt.
    """
    from .synthesis import synthesize_undetermined, write_result

    ctx = normalize_context(run_context)
    if not isinstance(evidence, dict):
        return {"accepted": False,
                "errors": [_missing(
                    "evidence", "evidence: must be a JSON object")]}
    v1_errors = check_v1(evidence)
    if v1_errors:
        if dry_run:
            return {"accepted": False, "errors": v1_errors,
                    "reply": format_dry_run_reply(v1_errors)}
        return {"accepted": False, "errors": v1_errors}
    if dry_run:
        try:
            errors, _computed = run_checks(evidence, ctx, dry_run=True)
        except (TypeError, ValueError, AttributeError, KeyError,
                ZeroDivisionError, ArithmeticError):
            fault = [_err(
                "VALIDATOR_FAULT", "evidence",
                "the validator hit an internal fault")]
            return {"accepted": False, "errors": fault,
                    "reply": format_dry_run_reply(fault)}
        return {"accepted": not errors, "errors": errors,
                "reply": format_dry_run_reply(errors)}
    try:
        errors, computed = run_checks(evidence, ctx, dry_run=False)
    except (TypeError, ValueError, AttributeError, KeyError,
            ZeroDivisionError, ArithmeticError) as exc:
        return _fault(ctx, exc, synthesize_undetermined, write_result)
    # A single scale reference (or any residual error set) is judged
    # as now: errors reject; no errors accept, even when the verdict
    # is undetermined.
    if errors:
        return {"accepted": False, "errors": errors}
    try:
        result = assemble_result(evidence, ctx, computed)
    except (TypeError, ValueError, AttributeError, KeyError,
            ZeroDivisionError, ArithmeticError) as exc:
        return _fault(ctx, exc, synthesize_undetermined, write_result)
    try:
        path = write_result(str(ctx.get("run_dir", ".")) or ".", result)
    except (TypeError, ValueError, AttributeError, KeyError, OSError,
            ZeroDivisionError, ArithmeticError) as exc:
        return _fault(ctx, exc, synthesize_undetermined, write_result)
    return {"accepted": True, "errors": [],
            "result": result, "result_path": path}


def _fault(ctx, exc, synthesize_undetermined, write_result):
    """Our bug, not the agent's attempt (brief §6.2)."""
    import traceback
    from pathlib import Path

    run_dir = str(ctx.get("run_dir", ".") or ".")
    run_id = str(ctx.get("run_id", "run") or "run")
    try:
        logs = Path(run_dir) / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "validator_fault.txt").write_text(
            "".join(traceback.format_exception(exc)), encoding="utf-8")
    except OSError:
        pass
    try:
        result = synthesize_undetermined(run_dir, run_id,
                                         "validator_fault")
        path = write_result(run_dir, result)
    except (TypeError, ValueError, AttributeError, KeyError, OSError,
            ZeroDivisionError, ArithmeticError):
        return {"accepted": True, "errors": [], "result": None,
                "result_path": None}
    return {"accepted": True, "errors": [], "result": result,
            "result_path": path}


# --- assembly ------------------------------------------------------------------

def _assemble_scale(evidence, computed):
    references = evidence.get("references", [])
    pairs = computed.get("scale_pairs", [])
    if pairs and len(pairs) == len(references) and len(pairs) > 1:
        mean_m, sigma_m = _weighted_mean(pairs)
    elif pairs:
        mean_m, sigma_m = pairs[0]
    else:
        mean_m, sigma_m = (computed.get("m_per_px"),
                           computed.get("sigma_m_per_px"))
    scale_ev = evidence.get("scale", {}) if isinstance(
        evidence.get("scale"), dict) else {}
    headline = scale_ev.get("reference_index", 0)
    try:
        headline = int(headline)
    except (TypeError, ValueError):
        headline = 0
    if not 0 <= headline < max(len(references), 1):
        headline = 0
    indices = list(range(len(references)))
    second = indices[1] if len(indices) > 1 else None
    extent = None
    if 0 <= headline < len(references):
        extent = (references[headline] or {}).get("extent_px")
    try:
        frame = int(scale_ev.get("frame",
                                 (extent or {}).get("frame", 0)))
    except (TypeError, ValueError):
        frame = 0
    return {
        "frame": frame,
        "m_per_px": float(mean_m or 0.0),
        "sigma_m_per_px": float(sigma_m or 0.0),
        "reference_index": headline,
        "reference_indices": indices,
        "extent_px": dict(extent or {"x1": 0.0, "y1": 0.0, "x2": 0.0,
                                     "y2": 0.0, "length_px": 1.0,
                                     "frame": frame}),
        "second_reference_index": second,
        "second_reference_absent_reason": scale_ev.get(
            "second_reference_absent_reason"),
        "check_scale": scale_ev.get("check_scale"),
    }


def _display_track(rows, start, end, ctx):
    """Track rows with the takeoff/landing frames present (brief §9.3)."""
    by_frame = {r["frame"]: dict(r) for r in rows}
    frames = sorted(by_frame)
    if start not in by_frame and len(frames) >= 2:
        before = [f for f in frames if f < start]
        after = [f for f in frames if f > start]
        if before and after:
            first, second = before[-1], after[0]
            if second != first:
                frac = (start - first) / (second - first)
                row_a, row_b = by_frame[first], by_frame[second]
                by_frame[start] = {
                    "frame": start,
                    "x_px": row_a["x_px"] + frac * (
                        row_b["x_px"] - row_a["x_px"]),
                    "y_px": row_a["y_px"] + frac * (
                        row_b["y_px"] - row_a["y_px"])}
        elif after:
            by_frame[start] = dict(by_frame[after[0]])
            by_frame[start]["frame"] = start
    if end not in by_frame and len(frames) >= 2:
        last = max(f for f in by_frame)
        if last != end and end > last:
            f0 = sorted(by_frame)[-2]
            row_a, row_b = by_frame[f0], by_frame[last]
            if last != f0:
                frac = (end - f0) / (last - f0)
                by_frame[end] = {
                    "frame": end,
                    "x_px": row_a["x_px"] + frac * (
                        row_b["x_px"] - row_a["x_px"]),
                    "y_px": row_a["y_px"] + frac * (
                        row_b["y_px"] - row_a["y_px"])}
    return [by_frame[f] for f in sorted(by_frame)]


def _assemble_segment(evidence_segment, info, index, ctx, scale,
                      verdict_world, fitting_world, candidates=()):
    """One result segment from its refit (brief §§3, 9.3)."""
    rows = _display_track(info["rows"], info["start"], info["end"], ctx)
    m_per_px = scale["m_per_px"]
    level_y = info["level_y"]
    # Takeoff frame level: the tracked point at takeoff.
    for row in rows:
        if row["frame"] == info["start"]:
            level_y = row["y_px"]
            break
    t_start = frame_time(info["start"], ctx) or 0.0
    _t_apex = frame_time(info["apex"], ctx)
    t_end = frame_time(info["end"], ctx) or 0.0
    track = []
    for row in rows:
        moment = frame_time(row["frame"], ctx)
        if moment is None:
            moment = t_start
        track.append({
            "frame": int(row["frame"]),
            "t_s": float(moment),
            "x_px": float(row["x_px"]),
            "y_px": float(row["y_px"]),
            "x_m": float((row["x_px"] - _takeoff_x(rows, info)) 
                         * m_per_px),
            "y_m": float((level_y - row["y_px"]) * m_per_px),
        })
    fit = info["fit"]
    sigma_total = info.get("sigma_total", 0.0) or 0.0
    g_app = abs(float(fit.get("a", 0.0)))
    a_px = g_app / m_per_px if m_per_px else 0.0
    sigma_a_px = (sigma_total / m_per_px) if m_per_px else 0.0
    try:
        residual_trend = float(fit.get("residual_trend", 0.0))
    except (TypeError, ValueError):
        residual_trend = 0.0
    try:
        n_points = int(fit.get("n", len(rows)))
    except (TypeError, ValueError):
        n_points = len(rows)
    try:
        v0 = float(fit.get("v0", 0.0))
        y0 = float(fit.get("y0", 0.0))
    except (TypeError, ValueError):
        v0, y0 = 0.0, 0.0
    # The refit used absolute video times: velocity at takeoff is
    # v(t_start) on that absolute base.
    vy = v0 + float(fit.get("a", 0.0)) * t_start
    vx, x0 = _x_takeoff(info["rows"], ctx, t_start, m_per_px)
    rise = (vy * vy / (2.0 * g_app)) if g_app > 0 and vy > 0 else 0.0
    airborne = max(t_end - t_start, 1e-9)
    fps, _count, _duration, stamps = timing_numbers(ctx)
    sigma_s = (math.sqrt(2.0) / fps) if fps > 0 else 0.01
    key_moments = []
    for moment in evidence_segment.get("key_moments", []) or []:
        if not isinstance(moment, dict):
            continue
        try:
            frame = int(moment.get("frame", info["start"]))
        except (TypeError, ValueError):
            frame = info["start"]
        key_moments.append({
            "type": moment.get("type", "takeoff"),
            "frame": frame,
            "t_s": float(frame_time(frame, ctx) or t_start),
            "caption": moment.get("caption", ""),
        })
    overlay = []
    by_frame = {r["frame"]: r for r in track}
    for frame in (info["start"], info["apex"], info["end"]):
        row = by_frame.get(frame)
        if row is None:
            continue
        x_px, y_px = row["x_px"], row["y_px"]
        overlay.append({
            "frame": int(frame),
            "outline": [[x_px - 4.0, y_px - 4.0],
                        [x_px + 4.0, y_px - 4.0],
                        [x_px + 4.0, y_px + 4.0],
                        [x_px - 4.0, y_px + 4.0]],
            "point": [x_px, y_px],
            "bbox": [x_px - 4.0, y_px - 4.0, 8.0, 8.0],
        })
    # The landing level of a free-flight segment (brief §31): the
    # track's y_m at the landing (end) frame, relative to takeoff.
    # Every ghost and world outcome lands at this level, answering
    # "in that world, when would this body touch the same ground?"
    land_y_m = 0.0
    for row in track:
        if row["frame"] == info["end"]:
            try:
                land_y_m = float(row["y_m"])
            except (TypeError, ValueError):
                land_y_m = 0.0
            break
    if evidence_segment.get("kind") == "wall":
        ghosts = []
    else:
        ghosts = _assemble_ghosts(track, t_start, level_y, m_per_px,
                                  verdict_world, fitting_world, fps,
                                  stamps, takeoff_vy=vy,
                                  takeoff_vx=vx, land_y_m=land_y_m)
    world_outcomes = []
    for world in candidates:
        gravity = WORLD_G.get(world)
        if not gravity or vy <= 0:
            continue
        discriminant = vy * vy - 2.0 * gravity * land_y_m
        if discriminant < 0.0:
            t_land = 2.0 * vy / gravity
        else:
            t_land = (vy + math.sqrt(discriminant)) / gravity
        world_outcomes.append({
            "world": world,
            "landing_time_s": float(t_land),
            "landing_x_px": float(
                _takeoff_x_px(rows, info) + (vx / m_per_px) * t_land
                if m_per_px else 0.0),
        })
    return {
        "id": evidence_segment.get("id", f"seg_{index}"),
        "label": evidence_segment.get("label", f"segment {index}"),
        "kind": evidence_segment.get("kind", "free_flight"),
        "mask": dict(evidence_segment.get("mask", {})),
        "frames": {"start": info["start"], "apex": info["apex"],
                   "end": info["end"]},
        "times_s": {"start": float(t_start),
                    "apex": float(_t_apex or t_start),
                    "end": float(t_end)},
        "key_moments": key_moments,
        "overlay": overlay,
        "track": track,
        "fit": {"g_app": float(g_app),
                "sigma_g": float(max(sigma_total, 1e-9)),
                "a_px_s2": float(a_px),
                "sigma_a_px_s2": float(max(sigma_a_px, 0.0)),
                "v0": float(v0), "y0": float(y0),
                "residual_trend": float(residual_trend),
                "n_points": int(n_points)},
        "fit_curve_px": [dict(s) for s in
                         evidence_segment.get("fit_curve_px", []) or []],
        "takeoff_level_y_px": float(level_y),
        "apex_info": {
            "rise_m": float(max(rise, 0.0)),
            "sigma_m": float(max(
                rise * sigma_total / g_app, 0.0) if g_app > 0 else 0.0),
            "feet_clearance_m": None},
        "landing_info": {"airborne_s": float(airborne),
                         "sigma_s": float(max(sigma_s, 0.0))},
        "world_outcomes": world_outcomes,
        "ghosts": ghosts,
        "repetitions": [dict(r) for r in
                        evidence_segment.get("repetitions", []) or []],
    }


def _takeoff_x(rows, info):
    for row in rows:
        if row["frame"] == info["start"]:
            return row["x_px"]
    return rows[0]["x_px"] if rows else 0.0


def _takeoff_x_px(rows, info):
    return _takeoff_x(rows, info)


def _x_takeoff(rows, ctx, t_start, m_per_px):
    """Linear x(t) at takeoff: ``(vx, x0)`` in metres."""
    times = []
    xs_m = []
    x_takeoff = rows[0]["x_px"] if rows else 0.0
    for row in rows:
        moment = frame_time(row["frame"], ctx)
        if moment is None:
            continue
        times.append(moment - t_start)
        xs_m.append((row["x_px"] - x_takeoff) * m_per_px)
    if len(times) < 2:
        return 0.0, 0.0
    n_points = len(times)
    mean_t = sum(times) / n_points
    mean_x = sum(xs_m) / n_points
    denom = sum((t - mean_t) ** 2 for t in times)
    if denom <= 0:
        return 0.0, 0.0
    vx = sum((t - mean_t) * (x - mean_x)
             for t, x in zip(times, xs_m)) / denom
    return float(vx), 0.0


def _frame_for_time(moment, stamps, fps):
    if stamps:
        best = 0
        best_dist = None
        for pos, stamp in enumerate(stamps):
            try:
                dist = abs(float(stamp) - moment)
            except (TypeError, ValueError):
                continue
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = pos
        return best
    if fps > 0:
        return max(0, int(round(moment * fps)))
    return 0


def _assemble_ghosts(track, t_start, level_y, m_per_px, verdict_world,
                     fitting_world, fps, stamps, takeoff_vy=0.0,
                     takeoff_vx=0.0, land_y_m=0.0):
    """Display counterfactuals from the fitted takeoff state (§§3, 31).

    Every ghost lands at the clip's landing level ``land_y_m`` (the
    track's height at the landing frame, relative to takeoff), not at
    takeoff height: ``ghost(..., land_y_m=...)`` (part 09 §8). With
    ``land_y_m`` at zero this is today's return-to-takeoff path.
    """
    if verdict_world == "Earth":
        return []
    if not track:
        return []
    first = track[0]
    try:
        vy = float(takeoff_vy)
        vx = float(takeoff_vx)
    except (TypeError, ValueError):
        return []
    if not (vy > 0):
        return []
    try:
        landing_level = float(land_y_m)
    except (TypeError, ValueError):
        landing_level = 0.0
    ghosts = []
    takeoff_state = {"x0": 0.0, "y0": 0.0, "vx": vx, "vy": vy}
    grid = sorted({r["t_s"] - t_start for r in track
                   if r["t_s"] >= t_start})
    if not grid:
        return []
    if verdict_world != "Earth":
        entry = _ghost_entry(
            "earth_counterfactual", "Earth", WORLD_G["Earth"],
            takeoff_state, m_per_px, grid, t_start, level_y,
            first["x_px"], stamps, fps, land_y_m=landing_level)
        if entry is not None:
            ghosts.append(entry)
    if (fitting_world is not None and fitting_world != "Earth"
            and fitting_world in WORLD_G):
        entry = _ghost_entry(
            "fitting_world", fitting_world,
            WORLD_G[fitting_world], takeoff_state, m_per_px, grid,
            t_start, level_y, first["x_px"], stamps, fps,
            land_y_m=landing_level)
        if entry is not None:
            ghosts.append(entry)
    return ghosts


def _ghost_vx(track):
    if len(track) < 2:
        return 0.0
    first, second = track[0], track[1]
    dt = second["t_s"] - first["t_s"]
    if dt <= 0:
        return 0.0
    return (second["x_m"] - first["x_m"]) / dt


def _ghost_entry(role, world, gravity, takeoff_state, m_per_px, grid,
                 t_start, level_y, x_takeoff_px, stamps, fps,
                 land_y_m=0.0):
    try:
        result = ghost(takeoff_state, gravity, m_per_px, grid,
                       land_y_m=land_y_m)
    except ValueError:
        return None
    points = []
    for sample in result.get("path", []):
        moment = t_start + sample["t"]
        points.append({
            "t_s": float(moment),
            "frame": int(_frame_for_time(moment, stamps, fps)),
            "x_px": float(x_takeoff_px + sample["x_px"]),
            "y_px": float(level_y - sample["y_px"]),
        })
    landing = result.get("landing", {})
    t_land = t_start + landing.get("t", 0.0)
    return {
        "role": role,
        "world": world,
        "gravity_m_s2": float(gravity),
        "points": points,
        "landing": {
            "t_s": float(t_land),
            "x_px": float(x_takeoff_px + landing.get("x_px", 0.0)),
            "y_px": float(level_y - landing.get("y_px", 0.0)),
        },
    }


def _candidate_worlds(evidence):
    worlds = evidence.get("worlds", {})
    if not isinstance(worlds, dict):
        return []
    return [e.get("world") for e in worlds.get("candidates", []) or []
            if isinstance(e, dict) and e.get("world") in WORLD_G]


def _worlds_result(evidence, computed):
    preview = computed.get("verdict_preview", {}) or {}
    native = {e["world"]: e for e in preview.get("native", []) or []}
    candidates = []
    for world in _candidate_worlds(evidence):
        gravity = WORLD_G[world]
        entry = native.get(world, {})
        g_head = preview.get("g_measured")
        sigma = preview.get("sigma_g")
        if g_head is not None and sigma:
            retime = math.sqrt(gravity / g_head) if g_head > 0 else None
        else:
            retime = None
        candidates.append({
            "world": world,
            "g_m_s2": float(gravity),
            "fits_native": bool(entry.get("fits_native", False)),
            "delta_sigma": float(entry.get("delta_sigma", 0.0)),
            "retime_factor": (float(retime) if retime is not None
                              and math.isfinite(retime) else None),
        })
    # Brief §41: Earth is always weighed. The evidence may name Earth
    # neither as a candidate nor as an excluded world; for a result
    # with a measured g the validator then adds Earth, with
    # delta_sigma, fits_native and retime_factor computed exactly as
    # for every other candidate. The verdict is decided over the
    # agent's candidates before this, so it does not change; the added
    # entry only gives the page a chip.
    g_head = preview.get("g_measured")
    sigma = preview.get("sigma_g")
    names = {c["world"] for c in candidates
             if isinstance(c, dict)}
    excluded_names = set()
    worlds = evidence.get("worlds", {})
    if isinstance(worlds, dict):
        for entry in worlds.get("excluded", []) or []:
            if isinstance(entry, dict):
                excluded_names.add(entry.get("world"))
    if (g_head is not None and sigma and "Earth" not in names
            and "Earth" not in excluded_names):
        try:
            delta = abs(WORLD_G["Earth"] - g_head) / sigma
        except (TypeError, ValueError, ZeroDivisionError,
                ArithmeticError):
            delta = None
        try:
            retime = math.sqrt(WORLD_G["Earth"] / g_head) \
                if g_head and g_head > 0 else None
        except (TypeError, ValueError, ZeroDivisionError,
                ArithmeticError):
            retime = None
        if delta is not None and math.isfinite(delta):
            candidates.append({
                "world": "Earth",
                "g_m_s2": float(WORLD_G["Earth"]),
                "fits_native": bool(delta <= 2.0),
                "delta_sigma": float(delta),
                "retime_factor": (float(retime)
                                  if retime is not None
                                  and math.isfinite(retime) else None),
            })
    excluded = []
    worlds = evidence.get("worlds", {})
    if isinstance(worlds, dict):
        for entry in worlds.get("excluded", []) or []:
            if not isinstance(entry, dict):
                continue
            excluded.append({
                "world": entry.get("world", ""),
                "evidence_text": entry.get("evidence_text", ""),
                "evidence_frames": list(
                    entry.get("evidence_frames", []) or []),
                "evidence_artifact": entry.get("evidence_artifact",
                                               ""),
            })
    return {"candidates": candidates, "excluded": excluded}


def _clock_result(evidence, computed):
    clock = evidence.get("clock")
    if clock is None:
        return None
    if not isinstance(clock, dict):
        return None
    try:
        interval = computed.get("verdict_preview", {}).get(
            "clock_interval")
    except (TypeError, AttributeError):
        interval = None
    if interval is None:
        try:
            interval = _clock_interval(clock)
        except (TypeError, ValueError, AttributeError, KeyError):
            interval = None
    if interval is None:
        lo, hi, centre = 0.0, 0.0, 0.0
    else:
        try:
            lo, hi, centre = interval
        except (TypeError, ValueError):
            lo, hi, centre = 0.0, 0.0, 0.0
    try:
        hi = hi if math.isfinite(hi) else centre * 2.0 if centre else 1.0
    except (TypeError, ValueError):
        hi = 1.0
    try:
        reads_normal = bool(lo <= 1.0 <= hi)
    except (TypeError, ValueError):
        reads_normal = False
    try:
        rate = float(clock.get("measured_rate_hz", 0.0))
    except (TypeError, ValueError):
        rate = 0.0
    try:
        rsig = float(clock.get("measured_rate_sigma_hz", 0.0))
    except (TypeError, ValueError):
        rsig = 0.0
    def _pair(raw):
        try:
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                return [float(raw[0]), float(raw[1])]
        except (TypeError, ValueError):
            pass
        return [0.0, 0.0]
    return {
        "signal_description": clock.get("signal_description", "")
        if isinstance(clock.get("signal_description", ""), str) else "",
        "measured_rate_hz": rate,
        "measured_rate_sigma_hz": max(rsig, 0.0),
        "interpretation": clock.get("interpretation", "step")
        if isinstance(clock.get("interpretation", "step"), str)
        else "step",
        "band_hz": _pair(clock.get("band_hz")),
        "natural_range_hz": _pair(clock.get("natural_range_hz")),
        "natural_range_source": {
            "url": (clock.get("natural_range_source", {}) or {}).get(
                "url", ""),
            "quote": (clock.get("natural_range_source", {}) or {}).get(
                "quote", ""),
        },
        "implied_stretch": float(centre),
        "implied_stretch_sigma": float(max((hi - lo) / 2.0, 0.0)),
        "reads_normal": reads_normal,
    }


def _gravity_status(preview, has_segments):
    """The gravity part's standing for the parts combine (02 §9)."""
    if not has_segments:
        return "absent"
    kind = preview.get("kind", "undetermined")
    if kind == "world":
        return "realistic"
    if kind == "impossible":
        return "not_realistic"
    if kind == "retimed":
        return "retimed"
    return "undetermined"


def _verdict_result(preview, single_reference, scored=(), candidates=(),
                   has_segments=True, overview_force=None):
    """Assembled verdict, with the motion-survey veto (brief §43).

    An unsurveyed clip cannot carry a deciding verdict: when the
    survey is missing, partial or leaves a flight undecided, a
    ``world``, ``retimed`` or ``impossible`` verdict becomes
    ``undetermined`` with the survey reason (the measured g and σ
    stay in the result for the page). An already-undetermined
    verdict stays honest with its own reason.
    """
    out = _verdict_combined(
        preview, single_reference, scored=scored,
        candidates=candidates, has_segments=has_segments)
    if (has_segments and overview_force
            and out.get("kind") in ("world", "retimed", "impossible")):
        return {"kind": "undetermined", "world": None,
                "direction": None, "factor": None,
                "g_measured": out.get("g_measured"),
                "sigma_g": out.get("sigma_g"),
                "reason": overview_force,
                "clock_note": out.get("clock_note"),
                "decided_by": "gravity"}
    return out


def _verdict_combined(preview, single_reference, scored=(), candidates=(),
                      has_segments=True):
    from .ranges import combine_parts

    kind = preview.get("kind", "undetermined")
    g_measured = preview.get("g_measured")
    sigma_g = preview.get("sigma_g")
    scored = [s for s in (scored or []) if isinstance(s, dict)]
    candidates = list(candidates or [])
    scene = candidates[0] if candidates else "Earth"
    # One scale reference downgrades the gravity part, never the
    # range parts (§13.1, §20, §46): with one reference, every
    # gravity verdict (world, impossible, retimed, with or without a
    # clock) becomes undetermined. No part of the spec makes an
    # exception for a scene-pinned retimed verdict.
    gravity = dict(preview)
    if single_reference and has_segments and kind in (
            "world", "impossible", "retimed"):
        gravity = dict(preview, kind="undetermined", world=None,
                       reason="scale rests on one reference",
                       clock_note=None)
    status = _gravity_status(gravity, has_segments)
    # One reference gives no verdict from range checks either (§51,
    # R-S6a): every range check that uses the scale is reported with
    # its value but decides nothing — the scale it rests on is the
    # single reference. A check that does not use the scale (a
    # ratio, a clock) still decides as before.
    deciding = scored
    if single_reference:
        deciding = [s for s in scored
                    if isinstance(s, dict) and not s.get("uses_scale")]
    combined, world, decided_by, reason = combine_parts(
        (status, gravity), deciding, candidates)
    if combined == "world" and decided_by == "gravity":
        return {
            "kind": "world", "world": gravity.get("world"),
            "direction": None, "factor": None,
            "g_measured": g_measured, "sigma_g": sigma_g,
            "reason": None, "clock_note": None,
            "decided_by": "gravity"}
    if combined == "world":
        return {
            "kind": "world", "world": scene, "direction": None,
            "factor": None, "g_measured": g_measured,
            "sigma_g": sigma_g, "reason": None, "clock_note": None,
            "decided_by": decided_by}
    if combined == "retimed":
        return {
            "kind": "retimed", "world": gravity.get("world"),
            "direction": gravity.get("direction"),
            "factor": gravity.get("factor"),
            "g_measured": g_measured, "sigma_g": sigma_g,
            "reason": None, "clock_note": gravity.get("clock_note"),
            "decided_by": "gravity"}
    if combined == "impossible" and decided_by == "gravity":
        return {
            "kind": "impossible", "world": gravity.get("world"),
            "direction": None, "factor": None,
            "g_measured": g_measured, "sigma_g": sigma_g,
            "reason": gravity.get("reason"),
            "clock_note": gravity.get("clock_note"),
            "decided_by": "gravity"}
    if combined == "impossible":
        return {
            "kind": "impossible", "world": scene, "direction": None,
            "factor": None, "g_measured": g_measured,
            "sigma_g": sigma_g, "reason": reason,
            "clock_note": None, "decided_by": decided_by}
    final_reason = gravity.get("reason") or "undetermined"
    # A below-minimum range check names the undetermined reason
    # (§38): with no other deciding check, the verdict says what
    # fell short rather than the generic gravity reason. A gravity
    # part that already says why (conflicting segments, no way to
    # separate retiming from error) keeps its own reason.
    if (decided_by not in (None, "gravity") and reason
            and final_reason in ("undetermined",
                                 "no measurable segment")):
        final_reason = reason
    # One reference gives no verdict from range checks either (§51):
    # when the scale rests on one reference, a scale-based check is
    # reported but never decisive — the verdict says so, as for
    # gravity. A below-minimum naming from a scale check yields to
    # the same reason; a deciding check that does not use the scale
    # returns above and never reaches this line.
    if single_reference and any(
            isinstance(s, dict) and s.get("uses_scale")
            for s in scored):
        final_reason = "scale rests on one reference"
    if status == "absent" and not scored:
        final_reason = "no measurable segment"
    return {"kind": "undetermined", "world": None, "direction": None,
            "factor": None, "g_measured": g_measured,
            "sigma_g": sigma_g, "reason": final_reason,
            "clock_note": gravity.get("clock_note"),
            "decided_by": decided_by}


#: Display place per world (brief §19): "on the Moon", "on Earth",
#: "on Mars".
_PLACE = {"Moon": "the Moon", "Earth": "Earth", "Mars": "Mars"}

#: Possessive per world for the fit distance (brief §19):
#: "0.2σ from the Moon's 1.62".
_OWNER = {"Moon": "the Moon's", "Earth": "Earth's", "Mars": "Mars's"}


def display_factor(stretch):
    """Display speed factor ``k`` (brief §42, part 02 §1).

    The stored stretch ``s`` is presented ÷ real. Display factors
    are above 1 in both directions: ``k = s`` when slowed
    (``s >= 1``), ``k = 1/s`` when sped up (``s < 1``). Returns
    ``None`` for a missing or non-finite stretch.
    """
    try:
        value = float(stretch)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return value if value >= 1.0 else 1.0 / value


def _impossible_world(verdict, preview):
    """The world an impossible sentence is stated against (§19)."""
    world = verdict.get("world")
    if isinstance(world, str) and world in WORLD_G:
        return world
    best = None
    for entry in preview.get("native", []) or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("world") not in WORLD_G:
            continue
        try:
            delta = float(entry.get("delta_sigma", 1e18))
        except (TypeError, ValueError):
            continue
        if best is None or delta < best[1]:
            best = (entry["world"], delta)
    if best is not None:
        return best[0]
    return "Earth"


def _sentence(verdict, preview, scored=()):
    """Display wording: realistic or not (§19, part 02 §8, §20)."""
    from .ranges import format_range_sentence

    scored = [s for s in (scored or []) if isinstance(s, dict)]
    decided_by = verdict.get("decided_by")
    # Only a deciding check makes the sentence: a below-minimum
    # check never decides "not realistic" (§38), so an undetermined
    # verdict always reads the undetermined sentence, whatever
    # check the reason names.
    if (decided_by not in (None, "gravity")
            and verdict.get("kind") in ("world", "impossible")):
        match = [s for s in scored if s.get("id") == decided_by]
        if match:
            entry = match[0]
            check = {k: entry.get(k) for k in (
                "id", "label", "value", "sigma", "unit", "range")}
            world = verdict.get("world") or "Earth"
            place = _PLACE.get(world, world)
            return format_range_sentence(
                verdict.get("kind"), place, check, entry)
    g_measured = verdict.get("g_measured")
    sigma_g = verdict.get("sigma_g")
    numbers = ""
    if isinstance(g_measured, (int, float)) and isinstance(
            sigma_g, (int, float)) and sigma_g > 0:
        numbers = f"Measured g = {format_g(g_measured, sigma_g)} m/s²."
    if verdict.get("kind") == "world":
        world = verdict.get("world")
        native = {e["world"]: e for e in preview.get("native", [])
                  or []}
        delta = native.get(world, {}).get("delta_sigma", 0.0)
        gravity = WORLD_G.get(world, 0.0)
        place = _PLACE.get(world, world)
        owner = _OWNER.get(world, f"{world}'s")
        return (f"Realistic on {place}: measured g = "
                f"{format_g(g_measured, sigma_g)} m/s², "
                f"{delta:.1f}σ from {owner} {gravity}.")
    if verdict.get("kind") == "retimed":
        factor = verdict.get("factor") or 0.0
        word = ("slowed down" if verdict.get("direction") == "slowed"
                else "sped up")
        world = verdict.get("world")
        place = _PLACE.get(world, world)
        note = verdict.get("clock_note")
        if note == "clock agrees":
            parenthetical = " (clock agrees)"
        elif note == "clock: none, scene-pinned":
            parenthetical = " (no independent clock; scene-pinned)"
        elif isinstance(note, str) and note:
            parenthetical = f" ({note})"
        else:
            parenthetical = ""
        base = (f"Not realistic at this speed: {word} ×{factor:.2f}; "
                f"at real speed it fits {place}{parenthetical}.")
        return f"{base} {numbers}" if numbers else base
    if verdict.get("kind") == "impossible":
        world = _impossible_world(verdict, preview)
        place = _PLACE.get(world, world)
        base = (f"Not realistic on {place}: "
                f"{verdict.get('reason') or 'the motion cannot fit'}.")
        return f"{base} {numbers}" if numbers else base
    base = f"Undetermined: {verdict.get('reason') or 'no result'}."
    return f"{base} {numbers}" if numbers else base


def assemble_result(evidence, ctx, computed):
    """Build the part-12 result from evidence plus run records (§3)."""
    from src.contract import CONTRACT_VERSION

    preview = dict(computed.get("verdict_preview", {}) or {})
    if computed.get("verdict_forced_undetermined"):
        preview = dict(preview)
        preview["kind"] = "undetermined"
        preview["world"] = None
        preview["reason"] = ("the clock cannot separate retiming from "
                             "a measurement error")
    single_reference = len(evidence.get("references", []) or []) < 2
    has_segments = any(isinstance(s, dict)
                       for s in (evidence.get("segments", []) or []))
    # The one-reference rule downgrades the gravity part (only with
    # segments) and every scale-based range check, with or without
    # segments (§13.1, §20, §46, §51). A scale-free check (a ratio, a
    # clock) still decides as before.
    scale = _assemble_scale(evidence, computed)
    scored = [s for s in (computed.get("range_scored", []) or [])
              if isinstance(s, dict)]
    # The scored entries may carry the validator's private raise
    # note (brief §33); the result keeps the part-12 fields only.
    result_ranges = []
    for entry in scored:
        cleaned = {key: entry[key] for key in (
            "id", "label", "answers", "unit", "frame", "extents",
            "value", "sigma", "formula", "uses_scale",
            "measurement_artifact", "range", "outcome", "delta_sigma",
            "side") if key in entry}
        result_ranges.append(cleaned)
    # Per-segment σ_total: quadrature already includes the computed
    # repetition spread for multi-segment evidence (§14). Without
    # segments there is no gravity σ: the budget lists only what the
    # range checks need (§20).
    g_values = _segment_g_values(computed)
    if has_segments:
        sigma_total = max(computed.get("sigma_total", 0.0) or 0.0,
                          1e-9)
    else:
        sigma_total = None
    rep_extra = computed.get("repetition_spread_extra", 0.0) or 0.0
    by_name = {}
    for comp in (evidence.get("error_budget", {}) or {}).get(
            "components", []) or []:
        if isinstance(comp, dict) and comp.get("name"):
            by_name[str(comp["name"])] = dict(comp)
    if has_segments and rep_extra > 0 and "repetition_spread" \
            not in by_name:
        by_name["repetition_spread"] = {
            "name": "repetition_spread",
            "sigma_contribution": float(rep_extra),
            "basis": "spread of the segment g values over √n, never "
                     "below the per-segment fit σ",
        }
        quad = sum(float(c.get("sigma_contribution", 0.0)) ** 2
                   for c in by_name.values())
        sigma_total = max(math.sqrt(quad), 1e-9)
    computed["sigma_total"] = sigma_total
    verdict = _verdict_result(
        {**preview, "g_measured": preview.get("g_measured"),
         "sigma_g": sigma_total}, single_reference,
        scored=scored, candidates=_candidate_worlds(evidence),
        has_segments=has_segments,
        overview_force=computed.get("overview_force"))
    if verdict.get("g_measured") is None and g_values:
        weighted = _weighted_g_head(computed)
        verdict["g_measured"] = (
            weighted if weighted is not None
            else sum(g_values) / len(g_values))
    if verdict.get("sigma_g") is None and has_segments:
        verdict["sigma_g"] = sigma_total
    # The result uses the recomputed total (§18).
    fitting_world = None
    if verdict.get("kind") in ("world", "retimed"):
        fitting_world = verdict.get("world")
    elif verdict.get("kind") == "impossible":
        native = preview.get("native", []) or []
        if native:
            fitting_world = min(
                native, key=lambda e: e.get("delta_sigma", 1e18)).get(
                    "world")
    result_segments = []
    for index, segment in enumerate(evidence.get("segments", [])):
        info = (computed.get("segments", []) or [None] * len(
            evidence.get("segments", [])))[index] \
            if index < len(computed.get("segments", [])) else None
        if info is None or not isinstance(segment, dict):
            continue
        info = dict(info)
        info["sigma_total"] = sigma_total
        result_segments.append(_assemble_segment(
            segment, info, index, ctx, scale,
            verdict.get("world"), fitting_world,
            candidates=_candidate_worlds(evidence)))
    fps, count, duration, _stamps = timing_numbers(ctx)
    video = {"coded_width": 352, "coded_height": 240,
             "sample_aspect": {"num": 1, "den": 1},
             "measured_fps": float(fps or 0.0),
             "frame_count": int(count or 0),
             "duration_s": float(duration or 0.0)}
    evidence_video = evidence.get("video")
    if isinstance(evidence_video, dict):
        for key in ("coded_width", "coded_height", "measured_fps",
                    "frame_count", "duration_s"):
            if evidence_video.get(key) is not None:
                try:
                    video[key] = evidence_video[key]
                except (TypeError, ValueError):
                    pass
        aspect = evidence_video.get("sample_aspect")
        if isinstance(aspect, dict):
            video["sample_aspect"] = aspect
    first_look = evidence.get("first_look", {})
    if not isinstance(first_look, dict):
        first_look = {}
    result_first_look = {
        "question": first_look.get("question", ""),
        "summary": first_look.get("summary", ""),
        "scene_card": first_look.get("scene_card", {}),
        "by_eye": first_look.get("by_eye"),
        "views": first_look.get("views", []),
    }
    if "motions" in first_look:
        result_first_look["motions"] = first_look.get("motions", [])
    # The plan is shown, never used to decide the verdict (§21).
    _wonder_question, wonder = load_wonder(ctx)
    result_first_look["wonder"] = wonder
    references = []
    for ref in evidence.get("references", []) or []:
        references.append(dict(ref) if isinstance(ref, dict) else ref)
    components = []
    for name in list(by_name):
        components.append(by_name[name])
    if has_segments:
        error_budget = {
            "components": components,
            "sigma_total": float(sigma_total or 0.0),
            "sigma_relative": float(
                sigma_total / verdict["g_measured"]
                if verdict.get("g_measured") and sigma_total
                else 0.0),
        }
    else:
        error_budget = {
            "components": components,
            "sigma_total": None,
            "sigma_relative": None,
        }
    provenance = _assemble_provenance(evidence, ctx)
    clock_res = _clock_result(evidence, computed)
    result = {
        "contract_version": CONTRACT_VERSION,
        "video": video,
        "first_look": result_first_look,
        "references": references,
        "scale": scale,
        "segments": result_segments,
        "range_checks": result_ranges,
        "calculation_steps": _calculation_steps(
            evidence, ctx, computed, scale, result_segments, verdict,
            preview, sigma_total, scored, components,
            clock=clock_res, has_segments=has_segments),
        "clock": clock_res,
        "clock_absent_reason": evidence.get("clock_absent_reason"),
        "worlds": _worlds_result(evidence, computed),
        "error_budget": error_budget,
        "verdict": verdict,
        "sentence": _sentence(verdict, preview, scored),
        "page_texts": (dict(evidence.get("page_texts", {}))
                       if isinstance(evidence.get("page_texts"),
                                    dict) else {}),
        "self_built_tools": _selfbuilt_result(ctx),
        "provenance": provenance,
    }
    return result


def _text_block(text) -> dict:
    return {"type": "text", "text": str(text)}


def _formula_block(fallback, latex=None, chip=None) -> dict:
    return {"type": "formula",
            "latex": str(latex if latex is not None else fallback),
            "fallback": str(fallback), "chip": chip}


def _make_chip(text, tone):
    return {"text": str(text), "tone": tone}


def _domain_of(url) -> str:
    """The source domain for a clock step (brief §32)."""
    try:
        from urllib.parse import urlparse

        host = urlparse(str(url or "")).netloc
        if host:
            return host
    except (TypeError, ValueError, AttributeError):
        pass
    return str(url or "")


def _clock_frames(evidence):
    """The clock step's frame range (brief §32).

    The clock's frames — the motion the rate was measured on — when
    the evidence clock carries them as ``[start, end]``; ``(None,
    None)`` otherwise. Total over schema-valid input: the clock
    schema carries no frames, so this is usually absent.
    """
    try:
        clock = evidence.get("clock", None)
    except AttributeError:
        return None, None
    if not isinstance(clock, dict):
        return None, None
    frames = clock.get("frames", None)
    try:
        raw_start, raw_end = frames[0], frames[1]
    except (TypeError, ValueError, IndexError, KeyError):
        return None, None
    if isinstance(raw_start, bool) or isinstance(raw_end, bool):
        return None, None
    try:
        start, end = int(raw_start), int(raw_end)
    except (TypeError, ValueError):
        return None, None
    if start < 0 or end < start:
        return None, None
    return start, end


def _jumps_agree_step(evidence, computed, ordered_segments,
                       g_measured, sig_g):
    """The "Jumps agree" step for multi-flight results (brief §43).

    Each jump's g with its sigma, and the inverse-variance weighted
    mean. Total over schema-valid input: missing numbers fall back
    to text-only formulas, never exceptions.
    """
    per_jump: dict = {}
    try:
        ev_segments = evidence.get("segments", [])
    except AttributeError:
        ev_segments = []
    if not isinstance(ev_segments, list):
        ev_segments = []
    try:
        seg_infos = computed.get("segments", [])
    except AttributeError:
        seg_infos = []
    if not isinstance(seg_infos, list):
        seg_infos = []
    for ev_pos, ev_seg in enumerate(ev_segments):
        if not isinstance(ev_seg, dict):
            continue
        seg_id = ev_seg.get("id")
        if not isinstance(seg_id, str):
            continue
        info = seg_infos[ev_pos] if ev_pos < len(seg_infos) else None
        fit = info.get("fit", {}) if isinstance(info, dict) else {}
        if not isinstance(fit, dict):
            fit = {}
        try:
            value = float(fit.get("g_app"))
            sigma = float(fit.get("g_app_sigma", 0.0))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and math.isfinite(sigma) and sigma > 0:
            per_jump[seg_id] = (value, sigma)
    short = [_text_block("Each measured flight gives its own "
                         "gravity; they agree within the budget.")]
    for number, result_seg in enumerate(ordered_segments, start=1):
        if not isinstance(result_seg, dict):
            continue
        seg_id = result_seg.get("id")
        pair = per_jump.get(seg_id)
        if pair is None:
            continue
        value, sigma = pair
        short.append(_formula_block(
            f"Jump {number}: g = {value:.3f} +/- {sigma:.3f} m/s2",
            f"g_{{{number}}} = {value:.3f} \\pm {sigma:.3f} \\, "
            f"\\mathrm{{m/s^2}}",
            _make_chip(f"Jump {number}", "intermediate")))
    try:
        numbers = format_g(g_measured, sig_g).replace("±", "+/-")
        latex_numbers = format_g(g_measured, sig_g).replace(
            "±", "\\pm")
    except (TypeError, ValueError):
        numbers = f"{g_measured} +/- {sig_g}"
        latex_numbers = numbers
    short.append(_formula_block(
        f"combined g = {numbers} m/s2",
        f"g = {latex_numbers} \\, \\mathrm{{m/s^2}}",
        _make_chip("combined gravity", "final")))
    full = [_formula_block(
        "inverse-variance weighted mean of the jumps",
        "g = \\sum g_i/\\sigma_i^2 / \\sum 1/\\sigma_i^2", None)]
    return {
        "id": "measured_g",
        "title": "Jumps agree",
        "frame": None,
        "frame_end": None,
        "segment_id": None,
        "short": short,
        "full": full,
        "caveats": [],
    }


def _calculation_steps(evidence, ctx, computed, scale, result_segments,
                       verdict, preview, sigma_total, scored=(),
                       components=(), clock=None, has_segments=True):
    """Every step the evidence supports, in display order (§29).

    Ids follow part 12 §6: ``time_from_frames``, one ``mask_check``
    per reference, one combined ``scale``, per-segment ``segment``
    and ``fit``, ``measured_g``, ``clock``, ``uncertainty`` and
    ``verdict``; each range check adds a ``scale`` step titled
    ``Range check <name>`` before ``uncertainty``. Motions that were
    not measured stay in ``first_look.motions`` only: they are never
    steps. Every number in a formula is the result's own value at
    the printed precision. Total over schema-valid input: missing
    numbers fall back to text-only steps, never exceptions.
    """
    steps = []
    try:
        return _calculation_steps_inner(
            evidence, ctx, computed, scale, result_segments, verdict,
            preview, sigma_total, scored, components, clock,
            has_segments)
    except (TypeError, ValueError, AttributeError, KeyError,
            ZeroDivisionError):
        steps.append({
            "id": "verdict",
            "title": "Verdict",
            "frame": None,
            "frame_end": None,
            "segment_id": None,
            "short": [_text_block(
                "The verdict was computed from the evidence.")],
            "full": [],
            "caveats": [],
        })
        return steps


def _calculation_steps_inner(evidence, ctx, computed, scale,
                             result_segments, verdict, preview,
                             sigma_total, scored, components, clock,
                             has_segments):
    steps = []
    # 1. Time from frames: measured fps over the frame count, and
    # the video length as a chip.
    fps, count, duration, _stamps = timing_numbers(ctx)
    try:
        fps_f = float(fps)
    except (TypeError, ValueError):
        fps_f = 0.0
    try:
        count_i = int(count)
    except (TypeError, ValueError):
        count_i = 0
    try:
        dur_f = float(duration)
    except (TypeError, ValueError):
        dur_f = 0.0
    steps.append({
        "id": "time_from_frames",
        "title": "Time from frames",
        "frame": None,
        "frame_end": None,
        "segment_id": None,
        "short": [
            _text_block("Frame times come from measured timestamps, "
                        "never the container rate."),
            _formula_block(
                f"measured fps = {fps_f:.2f} Hz over "
                f"{count_i} frames",
                f"f = {fps_f:.2f} \\, \\mathrm{{Hz}}, \\; "
                f"N = {count_i} \\, \\mathrm{{frames}}",
                _make_chip(f"{dur_f:.2f} s of video",
                           "intermediate")),
        ],
        "full": [_text_block("Duplicate frames and cuts are excluded "
                             "from every fit window.")],
        "caveats": [],
    })
    # 2. One mask_check step per reference, chipped with the blind
    # check's description.
    references = evidence.get("references", [])
    if not isinstance(references, list):
        references = []
    for ref in references:
        if not isinstance(ref, dict):
            continue
        extent = ref.get("extent_px", {})
        if not isinstance(extent, dict):
            extent = {}
        try:
            length = float(extent.get("length_px", 0.0) or 0.0)
        except (TypeError, ValueError):
            length = 0.0
        try:
            frame = extent.get("frame")
            frame = int(frame) if frame is not None else None
        except (TypeError, ValueError):
            frame = None
        if isinstance(frame, bool):
            frame = None
        check = ref.get("mask_check", {})
        coverage = ""
        if isinstance(check, dict):
            answer = check.get("coverage_answer")
            if isinstance(answer, str) and answer.strip():
                coverage = answer.strip()
        if not coverage:
            coverage = "blind check"
        steps.append({
            "id": "mask_check",
            "title": "Blind mask check",
            "frame": frame,
            "frame_end": None,
            "segment_id": None,
            "short": [
                _text_block("A blind check read what the reference "
                            "mask covers, with no knowledge of the "
                            "measurement."),
                _formula_block(
                    f"measured extent = {length:.1f} px",
                    f"\\ell = {length:.1f} \\, \\mathrm{{px}}",
                    _make_chip(coverage, "intermediate")),
            ],
            "full": [],
            "caveats": [],
        })
    # 3. One combined scale step: s = L/l per reference, with the
    # weighted mean as a chip; two references show both and their
    # agreement.
    try:
        mean_m = float(scale.get("m_per_px", 0.0) or 0.0)
    except (TypeError, ValueError, AttributeError):
        mean_m = 0.0
    try:
        scale_frame = scale.get("frame")
        scale_frame = int(scale_frame) \
            if scale_frame is not None else None
    except (TypeError, ValueError):
        scale_frame = None
    if isinstance(scale_frame, bool):
        scale_frame = None
    per_ref = []
    for ref in references:
        if not isinstance(ref, dict):
            continue
        try:
            size = float(ref.get("size_m", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        extent = ref.get("extent_px", {})
        try:
            length = float((extent or {}).get("length_px", 0.0)
                           or 0.0)
        except (TypeError, ValueError, AttributeError):
            length = 0.0
        if size > 0 and length > 0:
            per_ref.append((ref.get("name", "?"), size, length))
    if len(per_ref) == 1:
        _name, size, length = per_ref[0]
        short_formula = _formula_block(
            f"s = {size} m / {length} px",
            f"s = L/\\ell = {size} \\, \\mathrm{{m}} / "
            f"{length} \\, \\mathrm{{px}}",
            _make_chip(f"{mean_m:.6f} m/px", "final"))
        full = []
    elif per_ref:
        values = [size / length for _n, size, length in per_ref]
        denom = min(values) if min(values) > 0 else 1.0
        ratio = max(values) / denom
        shown = ", ".join(f"{v:.6f} m/px" for v in values)
        short_formula = _formula_block(
            f"s = {mean_m:.6f} m/px from {len(per_ref)} references "
            f"({shown}; max ratio {ratio:.3f})",
            f"s = {mean_m:.6f} \\, \\mathrm{{m/px}}",
            _make_chip(f"{mean_m:.6f} m/px", "final"))
        full = [_formula_block(
            f"{name}: s = {size} m / {length} px",
            f"s = {size} \\, \\mathrm{{m}} / {length} \\, "
            f"\\mathrm{{px}}", None) for name, size, length in per_ref]
    else:
        short_formula = _formula_block(
            f"s = {mean_m:.6f} m/px",
            f"s = {mean_m:.6f} \\, \\mathrm{{m/px}}",
            _make_chip(f"{mean_m:.6f} m/px", "final"))
        full = []
    # A reference far from the first-check takeoff is accepted with
    # a caveat on the scale step (brief §43). A reference whose
    # shape check was skipped says so here too (brief §44, R-S14).
    scale_caveats = []
    try:
        far_refs = computed.get("reference_far", [])
    except AttributeError:
        far_refs = []
    if isinstance(far_refs, list):
        for item in far_refs:
            if (isinstance(item, (list, tuple)) and len(item) == 3
                    and isinstance(item[1], str)):
                _pos, name, frame = item
                try:
                    _pos = int(_pos)
                    frame = int(frame)
                except (TypeError, ValueError):
                    continue
                note = ""
                try:
                    refs = evidence.get("references", [])
                    if isinstance(refs, list) and 0 <= _pos < len(
                            refs) and isinstance(refs[_pos], dict):
                        maybe = (refs[_pos].get(
                            "size_derivation", {}) or {}).get("note")
                        if isinstance(maybe, str) and maybe.strip():
                            note = maybe.strip()
                except (TypeError, ValueError, AttributeError):
                    note = ""
                if note:
                    scale_caveats.append({
                        "text": f"reference {name!r} is measured at "
                        f"frame {frame}, more than 2 s from the "
                        f"first-check takeoff: accepted with note: "
                        f"{note}",
                        "artifact": None})
                else:
                    scale_caveats.append({
                        "text": f"reference {name!r} is measured at "
                        f"frame {frame}, more than 2 s from the "
                        f"first-check takeoff: accepted with no "
                        f"timing reason",
                        "artifact": None})
    try:
        shape_skipped = computed.get("reference_shape_skipped", [])
    except AttributeError:
        shape_skipped = []
    if isinstance(shape_skipped, list):
        for item in shape_skipped:
            if (isinstance(item, (list, tuple)) and len(item) == 3
                    and isinstance(item[1], str)):
                _pos, name, count = item
                try:
                    count = int(count)
                except (TypeError, ValueError):
                    continue
                scale_caveats.append({
                    "text": f"reference {name!r}: shape check "
                    f"skipped, only {count} rest frames within ±1 s "
                    f"to compare against (R-S14)",
                    "artifact": None})
    steps.append({
        "id": "scale",
        "title": "Pixel scale",
        "frame": scale_frame,
        "frame_end": None,
        "segment_id": None,
        "short": [
            _text_block("Metres per pixel from the reference size "
                        "over its extent."),
            short_formula,
        ],
        "full": full,
        "caveats": scale_caveats,
    })
    # 4. Per measured segment: a segment step (N and the tracked
    # point) and a fit step (a ± σa with that segment's g). With
    # two or more flights the pairs run in frame order (brief §43).
    seg_infos = computed.get("segments", []) \
        if isinstance(computed, dict) else []
    if not isinstance(seg_infos, list):
        seg_infos = []
    ordered_segments = [seg for seg in (result_segments or [])
                        if isinstance(seg, dict)]
    if len(ordered_segments) >= 2:
        def _step_start(item):
            frames = item.get("frames", {})
            if not isinstance(frames, dict):
                return 0
            try:
                return int(frames.get("start", 0))
            except (TypeError, ValueError):
                return 0
        ordered_segments = sorted(ordered_segments, key=_step_start)
    for index, result_seg in enumerate(ordered_segments):
        if not isinstance(result_seg, dict):
            continue
        seg_id = result_seg.get("id")
        label = result_seg.get("label", seg_id or f"segment {index}")
        frames = result_seg.get("frames", {}) \
            if isinstance(result_seg.get("frames"), dict) else {}
        try:
            start = int(frames.get("start", 0))
        except (TypeError, ValueError):
            start = 0
        try:
            end = int(frames.get("end", start))
        except (TypeError, ValueError):
            end = start
        track = result_seg.get("track", []) \
            if isinstance(result_seg.get("track"), list) else []
        n_points = len(track) or (end - start + 1)
        ev_segments = evidence.get("segments", []) \
            if isinstance(evidence.get("segments"), list) else []
        ev_seg = {}
        for candidate_seg in ev_segments:
            if isinstance(candidate_seg, dict) and candidate_seg.get(
                    "id") == seg_id:
                ev_seg = candidate_seg
                break
        if not ev_seg and index < len(ev_segments) and isinstance(
                ev_segments[index], dict):
            ev_seg = ev_segments[index]
        point = ev_seg.get("tracked_point")
        if not isinstance(point, str) or not point.strip():
            point = "tracked point"
        steps.append({
            "id": "segment",
            "title": f"Segment {label}",
            "frame": start,
            "frame_end": end,
            "segment_id": seg_id,
            "short": [
                _text_block("Tracked point over the free-flight "
                            "window."),
                _formula_block(
                    f"N = {n_points} tracked frames",
                    f"N = {n_points} \\, \\mathrm{{frames}}",
                    _make_chip(point.strip(), "intermediate")),
            ],
            "full": [_text_block("Contact frames stay outside every "
                                 "gravity fit.")],
            "caveats": [],
        })
        fit = result_seg.get("fit", {}) \
            if isinstance(result_seg.get("fit"), dict) else {}
        try:
            a_px = float(fit.get("a_px_s2", 0.0) or 0.0)
        except (TypeError, ValueError):
            a_px = 0.0
        try:
            sig_a = float(fit.get("sigma_a_px_s2", 0.0) or 0.0)
        except (TypeError, ValueError):
            sig_a = 0.0
        try:
            seg_g = float(fit.get("g_app", 0.0) or 0.0)
        except (TypeError, ValueError):
            seg_g = 0.0
        trend_z = 0.0
        raw_fit = {}
        for ev_pos, candidate_seg in enumerate(ev_segments):
            if (isinstance(candidate_seg, dict)
                    and candidate_seg.get("id") == seg_id
                    and ev_pos < len(seg_infos)
                    and isinstance(seg_infos[ev_pos], dict)):
                maybe_fit = seg_infos[ev_pos].get("fit", {})
                if isinstance(maybe_fit, dict):
                    raw_fit = maybe_fit
                break
        if isinstance(raw_fit, dict):
            try:
                trend_z = float(
                    raw_fit.get("residual_trend_z", 0.0) or 0.0)
            except (TypeError, ValueError):
                trend_z = 0.0
        steps.append({
            "id": "fit",
            "title": f"Fit {label}",
            "frame": start,
            "frame_end": end,
            "segment_id": seg_id,
            "short": [
                _text_block("Parabola fit to heights above the "
                            "takeoff level."),
                _formula_block(
                    f"a = {a_px:.1f} +/- {sig_a:.1f} px/s2",
                    f"a = {a_px:.1f} \\pm {sig_a:.1f} \\, "
                    f"\\mathrm{{px/s^2}}",
                    _make_chip(f"g = {seg_g:.3f} m/s2",
                               "intermediate")),
            ],
            "full": [_formula_block(
                f"residual trend z = {trend_z:.2f}",
                f"\\rho_z = {trend_z:.2f}", None)],
            "caveats": [],
        })
    # 5. Measured g at native playback speed. With two or more
    # flights a "Jumps agree" step carries each jump's g with its
    # sigma and the weighted mean instead (brief §43); its id stays
    # in the controlled vocabulary (part 12 §6).
    g_measured = verdict.get("g_measured")
    sig_g = verdict.get("sigma_g")
    if has_segments and len(ordered_segments) >= 2 and isinstance(
            g_measured, (int, float)) and isinstance(
                sig_g, (int, float)) and sig_g > 0:
        steps.append(_jumps_agree_step(
            evidence, computed, ordered_segments, g_measured, sig_g))
    elif has_segments and isinstance(g_measured, (int, float)) and \
            isinstance(sig_g, (int, float)) and sig_g > 0:
        numbers = format_g(g_measured, sig_g).replace("±", "+/-")
        latex_numbers = format_g(g_measured, sig_g).replace(
            "±", "\\pm")
        full = []
        for entry in preview.get("native", []) or []:
            if not isinstance(entry, dict):
                continue
            world = entry.get("world")
            try:
                delta = float(entry.get("delta_sigma", 0.0))
            except (TypeError, ValueError):
                continue
            full.append(_formula_block(
                f"{world}: {delta:.1f} sigma",
                f"{world}: {delta:.1f}\\sigma",
                _make_chip(str(world), "intermediate")))
        steps.append({
            "id": "measured_g",
            "title": "Measured gravity",
            "frame": None,
            "frame_end": None,
            "segment_id": None,
            "short": [
                _text_block("Apparent gravity at native playback "
                            "speed."),
                _formula_block(
                    f"g = {numbers} m/s2",
                    f"g = {latex_numbers} \\, \\mathrm{{m/s^2}}",
                    _make_chip("measured gravity", "final")),
            ],
            "full": full,
            "caveats": [],
        })
    # 6. The clock's implied stretch, or its absence (brief §32:
    # titled "Clock: <interpretation> rate", showing the measured
    # rate with its σ, the natural range and its source, the implied
    # stretch with its σ, and the reading). The step is built
    # whenever the result has a clock, with or without segments
    # (brief §35); a result with neither a clock nor segments has no
    # clock step.
    if isinstance(clock, dict) and clock.get("measured_rate_hz"):
        try:
            stretch = float(clock.get("implied_stretch", 0.0)
                            or 0.0)
        except (TypeError, ValueError):
            stretch = 0.0
        try:
            stretch_sig = float(
                clock.get("implied_stretch_sigma", 0.0) or 0.0)
        except (TypeError, ValueError):
            stretch_sig = 0.0
        try:
            rate = float(clock.get("measured_rate_hz", 0.0)
                         or 0.0)
        except (TypeError, ValueError):
            rate = 0.0
        try:
            rate_sig = float(
                clock.get("measured_rate_sigma_hz", 0.0) or 0.0)
        except (TypeError, ValueError):
            rate_sig = 0.0
        natural = clock.get("natural_range_hz", [0.0, 0.0])
        try:
            nat_lo, nat_hi = float(natural[0]), float(natural[1])
        except (TypeError, ValueError, IndexError):
            nat_lo, nat_hi = 0.0, 0.0
        source = clock.get("natural_range_source", {})
        url = source.get("url", "") if isinstance(
            source, dict) else ""
        domain = _domain_of(url)
        try:
            reads_normal = bool(clock.get("reads_normal", False))
        except (TypeError, ValueError):
            reads_normal = False
        interpretation = clock.get("interpretation", "step")
        if not isinstance(interpretation, str) or \
                not interpretation.strip():
            interpretation = "step"
        # Brief §42: the printed factor is k, above 1 in both
        # directions, with its σ propagated to first order.
        shown = display_factor(stretch)
        if shown is None:
            shown = 0.0
        try:
            shown_sig = float(stretch_sig)
        except (TypeError, ValueError):
            shown_sig = 0.0
        if not math.isfinite(shown_sig):
            shown_sig = 0.0
        elif stretch > 0 and stretch < 1.0:
            shown_sig = shown_sig / (stretch ** 2)
        if reads_normal:
            reading = "plays at real speed"
        elif stretch >= 1.0:
            reading = (f"implies slowed down x{shown:.2f}: "
                       f"at real speed it runs {shown:.2f}x")
        else:
            reading = (f"implies sped up x{shown:.2f}: at real "
                       f"speed it runs {shown:.2f}x")
        clock_frame, clock_frame_end = _clock_frames(evidence)
        steps.append({
            "id": "clock",
            "title": f"Clock: {interpretation.strip()} rate",
            "frame": clock_frame,
            "frame_end": clock_frame_end,
            "segment_id": None,
            "short": [
                _text_block("An independent rhythm gives the "
                            "playback stretch."),
                _formula_block(
                    f"measured rate = {rate:.2f} +/- "
                    f"{rate_sig:.2f} Hz against natural "
                    f"{nat_lo:g}-{nat_hi:g} Hz ({domain})",
                    f"f = {rate:.2f} \\pm {rate_sig:.2f} \\, "
                    f"\\mathrm{{Hz}}",
                    _make_chip(f"{rate:.2f} Hz", "intermediate")),
                _formula_block(
                    f"implied stretch = {shown:.2f} +/- "
                    f"{shown_sig:.2f}; {reading}",
                    f"k = {shown:.2f} \\pm {shown_sig:.2f}",
                    _make_chip(f"x{shown:.2f}", "final")),
            ],
            "full": [],
            "caveats": [],
        })
    elif has_segments:
        # Brief §41: a missing clock reads as a fixed sentence written
        # by the validator. clock_absent_reason stays in the result,
        # but the step never prints the agent's text.
        text = ("No independent clock in this clip: the speed is "
                "taken as filmed.")
        steps.append({
            "id": "clock",
            "title": "Independent clock",
            "frame": None,
            "frame_end": None,
            "segment_id": None,
            "short": [_text_block(text)],
            "full": [],
            "caveats": [],
        })
    # Range checks add one scale step each before uncertainty.
    # A raised σ travels in the step's caveats (brief §33).
    try:
        step_raises = (computed or {}).get("range_sigma_raises", {})
    except AttributeError:
        step_raises = {}
    steps.extend(range_calc_steps(
        [s for s in (scored or []) if isinstance(s, dict)], mean_m,
        step_raises))
    # 7. Uncertainty: σ total plus the bars block.
    if isinstance(sigma_total, (int, float)) and sigma_total and \
            sigma_total > 0:
        steps.append({
            "id": "uncertainty",
            "title": "Uncertainty",
            "frame": None,
            "frame_end": None,
            "segment_id": None,
            "short": [
                _text_block("Itemised error budget, recombined in "
                            "quadrature."),
                _formula_block(
                    f"sigma total = {sigma_total:.3f} m/s2",
                    f"\\sigma = {sigma_total:.3f} \\, "
                    f"\\mathrm{{m/s^2}}",
                    _make_chip("error budget", "final")),
                {"type": "bars", "source": "error_budget"},
            ],
            "full": [_formula_block(
                f"{c.get('name')}: "
                f"{float(c.get('sigma_contribution', 0.0)):.3f} m/s2",
                f"\\sigma_{{{c.get('name')}}} = "
                f"{float(c.get('sigma_contribution', 0.0)):.3f}",
                _make_chip(str(c.get("name")), "intermediate"))
                for c in (components or [])
                if isinstance(c, dict) and c.get("name")],
            "caveats": [],
        })
    else:
        steps.append({
            "id": "uncertainty",
            "title": "Uncertainty",
            "frame": None,
            "frame_end": None,
            "segment_id": None,
            "short": [
                _text_block("Each range check carries its own "
                            "uncertainty; there is no gravity total."),
                {"type": "bars", "source": "error_budget"},
            ],
            "full": [],
            "caveats": [],
        })
    # 8. The verdict: the sentence's numbers as a formula, with the
    # world or answer as a chip.
    steps.append(_verdict_step(evidence, result_segments, verdict))
    return steps


def _verdict_step(evidence, result_segments, verdict):
    kind = verdict.get("kind")
    g_measured = verdict.get("g_measured")
    sig_g = verdict.get("sigma_g")
    if isinstance(g_measured, (int, float)) and isinstance(
            sig_g, (int, float)) and sig_g > 0:
        numbers = format_g(g_measured, sig_g).replace("±", "+/-")
        numbers_lx = format_g(g_measured, sig_g).replace(
            "±", "\\pm")
        g_text = f"g = {numbers} m/s2"
        g_latex = f"g = {numbers_lx} \\, \\mathrm{{m/s^2}}"
    else:
        g_text = ""
        g_latex = ""
    frame = None
    if isinstance(result_segments, list) and result_segments:
        try:
            last = result_segments[-1].get("frames", {})
            frame = int(last.get("end")) + 1 \
                if isinstance(last, dict) else None
        except (TypeError, ValueError):
            frame = None
    if isinstance(frame, bool):
        frame = None
    if kind == "world":
        world = verdict.get("world") or "?"
        fallback = f"{g_text}" if g_text else str(world)
        latex = f"{g_latex}" if g_latex else str(world)
        chip = _make_chip(str(world), "final")
    elif kind == "retimed":
        world = verdict.get("world") or "?"
        try:
            factor = float(verdict.get("factor") or 0.0)
        except (TypeError, ValueError):
            factor = 0.0
        word = ("slowed down"
                if verdict.get("direction") == "slowed" else "sped up")
        fallback = (f"{word} x{factor:.2f} to {world}"
                    + (f"; {g_text}" if g_text else ""))
        latex = fallback
        chip = _make_chip(str(world), "final")
    elif kind == "impossible":
        world = verdict.get("world") or "?"
        reason = verdict.get("reason") or "the motion cannot fit"
        fallback = (f"{reason}" + (f"; {g_text}" if g_text else ""))
        latex = fallback
        chip = _make_chip(str(world), "final")
    else:
        reason = verdict.get("reason") or "no result"
        fallback = (f"Undetermined: {reason}"
                    + (f" {g_text}" if g_text else ""))
        latex = fallback
        chip = None
    return {
        "id": "verdict",
        "title": "Verdict",
        "frame": frame,
        "frame_end": None,
        "segment_id": None,
        "short": [_formula_block(fallback, latex, chip)],
        "full": [_text_block("Computed deterministically from the "
                             "evidence by this validator.")],
        "caveats": [],
    }


def _assemble_provenance(evidence, ctx):
    provenance = evidence.get("provenance", {})
    artifacts = provenance.get("artifacts", []) if isinstance(
        provenance, dict) else []
    run_id = str(ctx.get("run_id", "run") or "run")
    try:
        model = str(_config.SPARK_MODEL)
    except AttributeError:
        model = "muse-spark-1.3-contributor"
    produced = set(ctx.get("produced_files", []) or [])
    out = []
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            path = artifact.get("path", "")
            if not isinstance(path, str) or not path:
                continue
            out.append({
                "name": artifact.get("name", path),
                "produced_by": ("run_python" if path in produced
                                else "tool"),
                "path": path,
            })
    return {"model": model, "run_id": run_id, "artifacts": out}


def _selfbuilt_result(ctx):
    try:
        from src.selfbuilt.registry import load_registry
    except ImportError:
        return []
    try:
        registry = load_registry(str(ctx.get("run_dir", ".") or "."))
    except (ValueError, OSError):
        return []
    out = []
    for entry in registry.get("tools", []) or []:
        if not isinstance(entry, dict):
            continue
        out.append({"name": entry.get("name", ""),
                    "purpose": entry.get("purpose", ""),
                    "attempts": entry.get("attempts", 1),
                    "status": entry.get("status", "")})
    return out

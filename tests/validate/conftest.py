# generated from brief/11 · part 11 owns this file
"""Shared factories for part 11's tests (never imported by name)."""

import copy
import json
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
RUN8 = REPO / "fixtures" / "source" / "run-8"

FPS = 30.0
N_FRAMES = 300
G_MOON = 1.62
M_PER_PX = 0.01


def _write(path: Path, content: str, produced: list, run_dir: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    produced.append(str(path.relative_to(run_dir)))


def make_run(tmp_path: Path, fps=FPS, n_frames=N_FRAMES):
    """A minimal run directory with timing, ready for validation."""
    run_dir = tmp_path / "run"
    (run_dir / "input").mkdir(parents=True)
    (run_dir / "workspace").mkdir(parents=True)
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "logs").mkdir(parents=True)
    timing = {
        "claimed_fps": fps,
        "measured_fps": fps,
        "frame_count": n_frames,
        "duration_s": n_frames / fps,
        "timestamps": [i / fps for i in range(n_frames)],
        "confirmed_duplicates": [],
        "cuts": [],
    }
    (run_dir / "input" / "timing.json").write_text(
        json.dumps(timing), encoding="utf-8")
    return run_dir


def make_context(run_dir: Path, produced):
    artifacts = sorted(
        str(p.relative_to(run_dir)) for p in
        (run_dir / "artifacts").rglob("*") if p.is_file())
    timing = json.loads(
        (run_dir / "input" / "timing.json").read_text(encoding="utf-8"))
    return {"run_dir": str(run_dir), "run_id": run_dir.name,
            "timing": timing, "artifacts": artifacts,
            "produced_files": list(produced), "mask_checks": []}


def write_track(run_dir, rel, rows, produced):
    _write(run_dir / rel, json.dumps(rows), produced, run_dir)


def parabola_track(start, end, level_y=200.0, x_px=100.0,
                   g=G_MOON, scale=M_PER_PX, fps=FPS):
    """Exact free-flight rows: takeoff ``start``, landing ``end``."""
    airtime = (end - start) / fps
    vy = g * airtime / 2.0
    rows = []
    for frame in range(start, end + 1):
        moment = (frame - start) / fps
        y_m = vy * moment - 0.5 * g * moment * moment
        rows.append({"frame": frame, "x_px": x_px,
                     "y_px": level_y - y_m / scale})
    return rows


def fit_curve_for(rows, fps=FPS, level_y=200.0):
    t0 = rows[0]["frame"] / fps
    return [{"t_s": r["frame"] / fps, "x_px": r["x_px"],
             "y_px": r["y_px"]} for r in rows]


def write_mask(run_dir, rel, entries, produced, shape=(240, 352)):
    """``entries``: ``{object_id: {frame: [(r0,c0,r1,c1), ...]}}``.

    Written with the part-09 ``save_masks`` writer — the ``segment``
    tool's own writer — so the validator reads it back through the
    helpers' reader (brief §25).
    """
    import numpy as np

    from src.helpers.masks_io import save_masks

    masks = {}
    for object_id, frames in entries.items():
        per_frame = {}
        for frame, boxes in frames.items():
            canvas = np.zeros(shape, dtype=bool)
            for r0, c0, r1, c1 in boxes:
                canvas[r0:r1, c0:c1] = True
            per_frame[int(frame)] = canvas
        masks[object_id] = per_frame
    path = run_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    save_masks(str(path), masks)
    produced.append(str(path.relative_to(run_dir)))
    return str(rel)


def write_cover_mask(run_dir, rel, produced, shape, boxes,
                     frame=0):
    """A mask covering extent endpoints, via the helpers' writer.

    ``shape`` is ``(height, width)``; ``boxes`` are
    ``(r0, c0, r1, c1)`` full-frame boxes. Range-check extents must
    lie on a mask from this run's ``segment`` artifacts (brief §25),
    so fixtures with typed extents add one of these.
    """
    import numpy as np

    from src.helpers.masks_io import save_masks

    canvas = np.zeros(shape, dtype=bool)
    for r0, c0, r1, c1 in boxes:
        canvas[r0:r1, c0:c1] = True
    save_masks(str(run_dir / rel), {"cover": {int(frame): canvas}})
    produced.append(str((run_dir / rel).relative_to(run_dir)))
    return str(rel)


def write_check(run_dir, rel, produced, alternatives=(),
                coverage="covers the whole reference block"):
    content = {"overlay_artifact": "artifacts/view_0.jpg",
               "coverage_answer": coverage,
               "alternatives": list(alternatives),
               "confidence": None, "turn": 1}
    _write(run_dir / rel, json.dumps(content), produced, run_dir)
    return str(rel)


def write_reference_line_checks(run_dir, produced, evidence,
                                dimension="height", view="front",
                                turn=1):
    """Agreeing blind line checks for an evidence's references (§50).

    Each reference's ``extent_px`` gains a ``check_line`` journal
    record on its own frame with both endpoints exact, ``agrees:
    true`` and a named ``dimension`` (part 07 §22), so the
    ``REFERENCE_LINE_NOT_CONFIRMED`` check passes. Appends to
    ``artifacts/line_checks.jsonl``; safe to call again after a test
    moves an extent (the new line gains its own record).
    """
    journal = run_dir / "artifacts" / "line_checks.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as handle:
        for ref in evidence.get("references", []) or []:
            if not isinstance(ref, dict):
                continue
            extent = ref.get("extent_px") or {}
            try:
                frame = int(extent.get("frame", 0))
                if isinstance(frame, bool):
                    continue
                x1 = float(extent["x1"])
                y1 = float(extent["y1"])
                x2 = float(extent["x2"])
                y2 = float(extent["y2"])
            except (KeyError, TypeError, ValueError):
                continue
            name = ref.get("name")
            if not isinstance(name, str) or not name.strip():
                name = "reference"
            name = name.strip()
            handle.write(json.dumps({
                "frame": frame,
                "lines": [{
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "claim": f"height of the {name}",
                    "description": f"the line runs along the {name}",
                    "view": view, "dimension": dimension,
                    "agrees": True,
                    "why": "the description matches the claim"}],
                "overlay_artifact": "artifacts/t1_check_line_0.png",
                "turn": turn}) + "\n")
    rel = "artifacts/line_checks.jsonl"
    if rel not in produced:
        produced.append(rel)


@pytest.fixture
def cover_mask():
    """Factory fixture: a mask covering extent endpoints (brief §25)."""
    return write_cover_mask


@pytest.fixture
def baseline():
    """A factory for schema-valid evidence that passes every check.

    Returns ``(evidence, run_dir, context, produced)`` in a fresh
    temporary run. Callers deep-copy and mutate the evidence.
    """
    def _make(tmp_path, **overrides):
        import numpy as np  # noqa: F401

        run_dir = make_run(tmp_path)
        produced: list = []
        # Reference masks: two disjoint blocks on frame 10.
        mask_a = write_mask(
            run_dir, "artifacts/ref_a.npz",
            {"0": {10: [(20, 20, 86, 40)]}, }, produced)
        mask_b = write_mask(
            run_dir, "artifacts/ref_b.npz",
            {"0": {10: [(20, 100, 86, 271)]}, }, produced)
        check_a = write_check(run_dir, "artifacts/check_a.json",
                              produced)
        check_b = write_check(run_dir, "artifacts/check_b.json",
                              produced)
        rows = parabola_track(30, 60)
        write_track(run_dir, "workspace/track_hop_a.json", rows,
                    produced)
        # Segment masks for the shape-term check (brief §57): a
        # constant-shape rectangle over the fit frames, so the
        # centroid and median rows follow the same parabola and the
        # shape term is ~0.
        seg_mask = write_mask(
            run_dir, "artifacts/seg_hop_a.npz",
            {"0": {frame: [(100, 150, 160, 210)]
                   for frame in range(30, 61)}}, produced)
        ref_rows = [{"frame": f, "x_px": 150.0, "y_px": 150.0}
                    for f in range(30, 61)]
        write_track(run_dir, "workspace/ref_static.json", ref_rows,
                    produced)
        # Whole-clip masks for the motion survey (brief §43): the
        # body rests at rows 100-160 and rides one smooth hump over
        # frames 30-60, one trajectory the overview recomputes. The
        # hump is a parabola, so its centroid track fits one
        # parabola too (brief §45); a teleporting box would read as
        # a non-parabolic flight.
        ground = {frame: [(100, 150, 160, 210)]
                  for frame in range(N_FRAMES)}
        for frame in range(30, 61):
            unit = (frame - 45) / 15.0
            bottom = int(round(160 - 60 * (1 - unit * unit)))
            ground[frame] = [(bottom - 60, 150, bottom, 210)]
        write_mask(run_dir, "artifacts/masks_all.npz", {"0": ground},
                   produced, shape=(240, 352))
        _write(run_dir / "artifacts" / "overview.json",
               json.dumps({"masks_artifact": "artifacts/masks_all.npz",
                           "object_id": "0",
                           "candidates": [{"id": "F1", "frame_start": 30,
                                           "frame_end": 60}]}),
               produced, run_dir)
        _write(run_dir / "artifacts" / "view_0.jpg", "fake-image",
               produced, run_dir)
        _write(run_dir / "artifacts" / "excl_mars.jpg", "fake-image",
               produced, run_dir)
        _write(run_dir / "artifacts" / "t0_web_search_0.json",
               json.dumps({
                   "query": "reference block height figure height",
                   "facts": [
                       {"url": "https://example.com/block",
                        "quote": "the block is 66 cm tall",
                        "text": "the block is 66 cm tall"},
                       {"url": "https://example.com/height",
                        "quote": "average height 171 cm",
                        "text": "average height 171 cm"}]}),
               produced, run_dir)
        evidence = {
            "first_look": {
                "question": "Does the physics add up to the Moon?",
                "summary": "A suited figure hops across grey ground.",
                "scene_card": {
                    "scene": "Grey ground with a suited figure.",
                    "place_date": None,
                    "confidence": "medium",
                    "objects": ["suited figure", "backpack"]},
                "by_eye": None,
                "views": [{"frame_start": 0, "frame_end": 299,
                           "artifact": "artifacts/view_0.jpg"}],
                "motions": [
                    {"frame_start": 30, "frame_end": 60,
                     "description": "foreground hop",
                     "segment_id": "hop_a", "skip_reason": None}],
                "overview": {
                    "artifact": "artifacts/masks_all.npz",
                    "object_id": "0",
                    "tool_result": "artifacts/overview.json",
                    "candidates": [
                        {"id": "cand_1", "frame_start": 30,
                         "frame_end": 60, "airtime_s": 1.0,
                         "peak_rise_px": 60.0, "decision": "measured",
                         "segment_id": "hop_a", "reason": None}],
                    "first_check": {"segment_id": "hop_a",
                                    "why": "longest clear flight"}},
            },
            "references": [
                {
                    "name": "reference block",
                    "extent_description": "height of the block",
                    "extent_type": "face_on",
                    "extent_px": {"x1": 20.0, "y1": 20.0, "x2": 20.0,
                                  "y2": 86.0, "length_px": 66.0,
                                  "frame": 10},
                    "size_m": 0.66,
                    "size_tolerance_m": 0.03,
                    "size_derivation": {
                        "mode": "single",
                        "note": "quoted block height",
                        "state_match": {
                            "shown_and_covered": "block body shown and covered",
                            "shown_not_covered": "lid shown but not covered"}},
                    "sources": [
                        {"url": "https://example.com/block",
                         "domain": "example.com",
                         "quote": "the block is 66 cm tall",
                         "quote_highlight": "66 cm",
                         "value_m": 0.66,
                         "source_type": "catalogue"}],
                    "mask": {"artifact": mask_a, "object_id": "0",
                             "frame": 10,
                             "outline": [[20.0, 20.0], [40.0, 20.0],
                                         [40.0, 86.0], [20.0, 86.0]]},
                    "mask_check": {
                        "artifact": check_a,
                        "coverage_answer": "covers the whole reference block",
                        "confidence": None, "alternative_readings": []},
                },
                {
                    "name": "standing figure",
                    "extent_description": "standing height",
                    "extent_type": "rotation_invariant",
                    "extent_px": {"x1": 100.0, "y1": 20.0, "x2": 100.0,
                                  "y2": 191.0, "length_px": 171.0,
                                  "frame": 10},
                    "size_m": 1.71,
                    "size_tolerance_m": 0.20,
                    "size_derivation": {
                        "mode": "single",
                        "note": "quoted standing height",
                        "state_match": {
                            "shown_and_covered": "figure shown and covered",
                            "shown_not_covered": "boots shown but not covered"}},
                    "sources": [
                        {"url": "https://example.com/height",
                         "domain": "example.com",
                         "quote": "average height 171 cm",
                         "quote_highlight": "171 cm",
                         "value_m": 1.71,
                         "source_type": "reference"}],
                    "mask": {"artifact": mask_b, "object_id": "0",
                             "frame": 10,
                             "outline": [[100.0, 20.0], [271.0, 20.0],
                                         [271.0, 191.0], [100.0, 191.0]]},
                    "mask_check": {
                        "artifact": check_b,
                        "coverage_answer": "covers the whole figure",
                        "confidence": None, "alternative_readings": []},
                },
            ],
            "scale": {
                "frame": 10,
                "m_per_px": 0.01,
                "sigma_m_per_px": 0.0006,
                "reference_index": 0,
                "extent_px": {"x1": 20.0, "y1": 20.0, "x2": 20.0,
                              "y2": 86.0, "length_px": 66.0,
                              "frame": 10},
                "second_reference_index": 1,
                "second_reference_absent_reason": None,
                "check_scale": {"m_per_px": 0.01, "sigma": 0.0012},
            },
            "segments": [
                {
                    "id": "hop_a",
                    "label": "Jump one",
                    "kind": "free_flight",
                    "mask": {"artifact": seg_mask, "object_id": "0"},
                    "frames": {"start": 30, "apex": 45, "end": 60},
                    "key_moments": [
                        {"type": "takeoff", "frame": 30,
                         "caption": "leaving the ground"},
                        {"type": "apex", "frame": 45,
                         "caption": "hanging at the top"},
                        {"type": "landing", "frame": 60,
                         "caption": "touching down softly"}],
                    "track_artifact": "workspace/track_hop_a.json",
                    "tracked_point": "top of the helmet",
                    "fit_curve_px": fit_curve_for(rows),
                    "repetitions": [],
                },
            ],
            "clock": None,
            "clock_absent_reason": "no visible independent rhythm",
            "worlds": {
                "candidates": [{"world": "Moon"}, {"world": "Earth"}],
                "excluded": [
                    {"world": "Mars",
                     "evidence_text": "grey ground, no red soil",
                     "evidence_frames": [0],
                     "evidence_artifact": "artifacts/excl_mars.jpg"}],
            },
            "error_budget": {
                "components": [
                    {"name": "reference_size",
                     "sigma_contribution": 0.05,
                     "basis": "quoted size spread"},
                    {"name": "pixel_scale",
                     "sigma_contribution": 0.03,
                     "basis": "endpoint placement"},
                    {"name": "fit", "sigma_contribution": 0.04,
                     "basis": "parabola residuals"},
                    {"name": "point_vs_com",
                     "sigma_contribution": 0.05,
                     "basis": "point versus centre"}],
                "sigma_relative": 0.2,
            },
            "camera": {
                "still": {
                    "reference_phrase": "distant rock",
                    "reference_track_artifact":
                        "workspace/ref_static.json"},
            },
            "provenance": {
                "artifacts": [
                    {"name": "view",
                     "path": "artifacts/view_0.jpg"},
                    {"name": "segment masks",
                     "path": seg_mask},
                    {"name": "mask check",
                     "path": "artifacts/check_b.json"},
                    {"name": "track",
                     "path": "workspace/track_hop_a.json"},
                    {"name": "reference track",
                     "path": "workspace/ref_static.json"}],
            },
            "page_texts": {},
        }
        for key, value in overrides.items():
            evidence[key] = value
        # Every reference line carries an agreeing blind check_line
        # record with a named dimension (brief §50).
        write_reference_line_checks(run_dir, produced, evidence)
        ctx = make_context(run_dir, produced)
        return evidence, run_dir, ctx, produced

    return _make


@pytest.fixture
def run8_copy():
    """Copy the eighth-run source tree into a temp dir as a run."""
    def _make(tmp_path):
        run_dir = tmp_path / "run-8"
        shutil.copytree(str(RUN8), str(run_dir),
                        ignore=shutil.ignore_patterns("logs"))
        produced = []
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                produced.append(str(path.relative_to(run_dir)))
        (run_dir / "workspace" / "produced_files.json").write_text(
            json.dumps(produced), encoding="utf-8")
        timing = json.loads(
            (run_dir / "input" / "timing.json").read_text(
                encoding="utf-8"))
        artifacts = sorted(
            str(p.relative_to(run_dir)) for p in
            (run_dir / "artifacts").rglob("*") if p.is_file())
        ctx = {"run_dir": str(run_dir), "run_id": run_dir.name,
               "timing": timing, "artifacts": artifacts,
               "produced_files": produced, "mask_checks": []}
        evidence = json.loads(
            (run_dir / "artifacts" / "t44_evidence.json").read_text(
                encoding="utf-8"))
        return evidence, run_dir, ctx

    return _make


@pytest.fixture
def patch_run8():
    """Patch function for run-8 evidence (factory fixture)."""
    return patched_run8


def patched_run8(evidence):
    """Patches the run-8 evidence predates: motions + state_match."""
    evidence = copy.deepcopy(evidence)
    evidence["first_look"]["motions"] = [
        {"frame_start": 220, "frame_end": 290,
         "description": "foreground hop", "segment_id": "hop_a",
         "skip_reason": None}]
    for ref in evidence["references"]:
        ref.setdefault("size_derivation", {}).setdefault(
            "state_match", {})
        match = ref["size_derivation"]["state_match"]
        match.setdefault("shown_and_covered",
                         "body shown and covered by the quoted size")
        match.setdefault("shown_not_covered",
                         "helmet shown but outside the extent")
    return evidence

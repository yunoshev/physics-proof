"""One-off: build the two M9 fixture analyses (synthetic scenes, not Moon/wall clips).

Writes tests/fixtures/analysis_ball.json (ball tossed on Earth, image frame,
fits Earth) and tests/fixtures/analysis_ramp.json (skater up a vertical ramp,
moving camera, kind wall, measured 4.0 +/- 0.5 vs 9.81, timescale normal).
Decide dicts and overall verdicts come from blocks.decide and schema.combine
so the fixtures are internally consistent by construction.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from physics_proof import blocks
from physics_proof.schema import combine

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def ball_points() -> list[dict[str, float]]:
    """Exact parabola in image px (y down): takeoff, apex, landing frames 10/25/40."""
    fps, a_px, v0, y0, start = 30.0, 981.0, -490.5, 400.0, 10
    points = []
    for frame in range(10, 41):
        t = (frame - start) / fps
        y = y0 + v0 * t + 0.5 * a_px * t * t
        points.append({"frame": frame, "x": 320.0, "y": y})
    return points


def ramp_points() -> list[dict[str, float]]:
    """Steady climb in reference sizes (y down): frames 100..160."""
    fps, v0, a_ref, y0, start = 24.0, -3.3, 2.0, 5.0, 100
    points = []
    for frame in range(100, 161):
        t = (frame - start) / fps
        y = y0 + v0 * t + 0.5 * a_ref * t * t
        points.append({"frame": frame, "x": 1.5, "y": y})
    return points


def make_ball() -> dict:
    fps = 30.0
    flight_decide = blocks.decide(9.81, 0.3, {"Earth": 9.81})
    top_decide = blocks.decide(9.81, 0.3, {"Earth": 9.81, "Moon": 1.62})
    verdict = dict(top_decide, worlds={"Earth": 9.81, "Moon": 1.62})
    overall = combine(verdict, None)
    assert overall["label"] == "Earth", overall
    ghost = []
    for frame in (10, 20, 30, 40):
        t = (frame - 10) / fps
        ghost.append({"frame": frame, "y": 400.0 - 490.5 * t + 490.5 * t * t})
    return {
        "type": "world-g",
        "schema_version": 1,
        "clip": {
            "file": "ball.mp4", "fps": fps, "frames": 120,
            "width": 640, "height": 480, "duplicates_found": 0,
            "notes": "Frame rate measured from the file; no duplicates found.",
        },
        "context": {
            "scene": "A ball tossed straight up outdoors.",
            "claim": "The tossed ball is in free flight under Earth gravity.",
            "expected": [
                {"quantity": "g", "value": 9.81, "unit": "m/s^2", "source": "CODATA"}
            ],
            "sources": ["https://physics.nist.gov/cgi-bin/cuu/Value?gn"],
        },
        "first_look": {
            "what": "ball", "where": "centre frame", "when": "frames 10-40",
            "source": "agent", "confidence": 0.6,
            "by_eye": {"quantity": "rise", "value": 1.2, "unit": "m"},
        },
        "reference": [
            {
                "name": "ball", "extent": "diameter", "value_m": 0.22,
                "tolerance_m": 0.005,
                "source_url": "https://example.org/ball-specs",
                "quote": "Official size: 22 cm diameter.",
                "source_type": "primary",
                "mask": {"file": "sam/ball.0-120.npz", "object": "ball"},
                "mask_check": {"verdict": "agrees", "covers": "the whole ball"},
            }
        ],
        "scale": {
            "frame": 12, "extent_px": 22.0, "extent_px_err": 0.5,
            "m_per_px": 0.01, "m_per_px_err": 0.0005,
            "second": None, "frame_of_reference": "image",
        },
        "track": {"what": "ball centre", "method": "centroid", "unit": "px", "points": ball_points()},
        "masks": {
            "ball": {
                "12": [[270, 300, 340], [271, 298, 342]],
                "25": [[200, 310, 350], [201, 308, 352]],
            }
        },
        "flights": [
            {
                "kind": "flight", "start": 10, "apex": 25, "end": 40,
                "rise_m": 1.22625, "duration_s": 1.0,
                "fit": {"a": 981.0, "a_err": 30.0, "rms": 0.4, "v0": -490.5,
                        "n": 31, "window": {"first": 10, "last": 40}},
                "accel": 9.81, "accel_err": 0.3,
                "hypothesis": {"name": "Earth", "value": 9.81},
                "decide": flight_decide,
                "ghost": ghost,
                "notes": "Clean free flight between release and catch.",
            }
        ],
        "timescale": None,
        "error_budget": {"reference": 0.023, "scale": 0.05, "fit": 0.031, "tracking": 0.02},
        "verdict": verdict,
        "overall": overall,
    }


def make_ramp() -> dict:
    fps = 24.0
    flight_decide = blocks.decide(4.0, 0.5, {"unsupported on Earth": 9.81})
    top_decide = blocks.decide(4.0, 0.5, {"unsupported on Earth": 9.81})
    verdict = dict(
        top_decide,
        worlds={"unsupported on Earth": 9.81},
        worlds_tested=["unsupported on Earth"],
        worlds_ruled_out=[
            {
                "world": "Moon",
                "by": "outdoor daylight scene with buildings and people "
                "walking normally in the background",
            }
        ],
    )
    timescale = {
        "method": "step rate on the run-up", "value": 5.1, "err": 0.17,
        "unit": "steps/s", "expected_range": [2.5, 4.5], "verdict": "normal",
    }
    overall = combine(verdict, timescale)
    assert overall["label"] == "impossible", overall
    ghost = []
    for frame in (100, 120, 140, 160):
        t = (frame - 100) / fps
        ghost.append({"frame": frame, "y": 5.0 - 3.3 * t + 0.5 * 4.905 * t * t})
    return {
        "type": "world-g",
        "schema_version": 1,
        "clip": {
            "file": "ramp.mp4", "fps": fps, "frames": 240,
            "width": 1280, "height": 720, "duplicates_found": 0,
            "notes": "Frame rate measured from the file; no duplicates found.",
        },
        "context": {
            "scene": "A skater rolling up a vertical ramp.",
            "claim": "The vertical climb is unsupported motion under Earth gravity.",
            "expected": [
                {"quantity": "a", "value": 9.81, "unit": "m/s^2", "source": "CODATA"}
            ],
            "sources": ["https://physics.nist.gov/cgi-bin/cuu/Value?gn"],
        },
        "first_look": {
            "what": "skater", "where": "centre ramp", "when": "frames 100-160",
            "source": "agent", "confidence": 0.5,
            "by_eye": {"quantity": "rise", "value": 4.0, "unit": "m"},
        },
        "reference": [
            {
                "name": "gate", "extent": "width", "value_m": 2.0,
                "tolerance_m": 0.05,
                "source_url": "https://example.org/venue",
                "quote": "The start gate is 2 m wide.",
                "source_type": "secondary",
                "mask": {"file": "sam/gate.0-240.npz", "object": "gate"},
                "mask_check": {"verdict": "agrees", "covers": "the whole gate"},
            }
        ],
        "scale": {
            "frame": 110, "extent_px": 150.0, "extent_px_err": 3.0,
            "m_per_ref": 2.0, "m_per_ref_err": 0.05,
            "second": {"name": "lane marker", "m_per_px": 0.02,
                       "m_per_px_err": 0.001, "agree_sigma": 0.8},
            "frame_of_reference": {
                "object": "wall", "anchor": "bottom", "size_px_per_frame": 300.0,
            },
        },
        "track": {"what": "skater hips", "method": "centroid", "unit": "ref", "points": ramp_points()},
        "masks": {
            "skater": {
                "110": [[300, 500, 560], [301, 498, 562]],
                "160": [[180, 505, 565], [181, 503, 567]],
            }
        },
        "flights": [
            {
                "kind": "wall", "start": 100, "apex": None, "end": 160,
                "rise_m": 4.0, "duration_s": 2.5,
                "fit": {"a": 2.0, "a_err": 0.25, "rms": 0.03, "v0": -3.3,
                        "n": 61, "window": {"first": 100, "last": 160}},
                "accel": 4.0, "accel_err": 0.5,
                "hypothesis": {"name": "unsupported on Earth", "value": 9.81},
                "decide": flight_decide,
                "ghost": ghost,
                "notes": "Vertical climb with the camera panning; positions in wall sizes.",
            }
        ],
        "timescale": timescale,
        "error_budget": {"reference": 0.025, "scale": 0.03, "fit": 0.125, "tracking": 0.02},
        "verdict": verdict,
        "overall": overall,
    }


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, make in (("analysis_ball.json", make_ball), ("analysis_ramp.json", make_ramp)):
        path = FIXTURES / name
        path.write_text(json.dumps(make(), indent=2) + "\n", encoding="utf-8")
        print("wrote " + str(path), flush=True)


if __name__ == "__main__":
    main()

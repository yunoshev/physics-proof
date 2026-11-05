# generated from brief/15 · part 15 owns this file
"""Offline tests for the acceptance harness (brief part 15 §4, part 03).

Every check is a pure function of stubbed inputs: no model calls, no
network, nothing costs money. The live path (`run_full_acceptance`,
behind PHYSICS_PROOF_LIVE=1 via `dev_loop --acceptance`) is stubbed at
its seams, never executed.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent


def _load_harness():
    name = "acceptance_harness_under_test"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    loader = importlib.machinery.SourceFileLoader(
        name, str(REPO / "tests" / "acceptance" / "harness.py")
    )
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def harness():
    return _load_harness()


def _moon_result(g=1.62, sigma=0.2):
    return {
        "verdict": {"world": "Moon", "g_measured": g, "sigma_g": sigma},
        "calculation_steps": [{"id": "mask_check"}],
    }


def _moon_summary(cost=0.5, wall=600.0, masks=1):
    return {
        "cost_usd": {"total": cost},
        "wall_time_s": wall,
        "mask_checks": masks,
    }


def test_3runs_2of3_per_clip_with_harness_only_constants(harness):
    assert harness.RUNS_PER_CLIP == 3
    assert harness.PASSES_NEEDED == 2
    assert set(harness.CLIP_CHECKERS) == {"A", "B", "C"}
    # A passing Moon verdict clears its own checker twice over.
    assert harness.check_clip_a(_moon_result()) == []
    assert harness.check_clip_a(_moon_result()) == []


def test_clip_a_rejects_wrong_world_and_loose_sigma(harness):
    assert harness.check_clip_a(_moon_result(g=9.81, sigma=0.2))
    assert harness.check_clip_a(_moon_result(g=1.62, sigma=0.5))
    assert harness.check_clip_a({"verdict": {"world": "Moon"}})


def test_clip_b_needs_retiming_without_native_fit(harness):
    good = {
        "verdict": {"world": "Moon", "factor": 1.5},
        "worlds": {"candidates": [{"world": "Moon", "fits_native": False}]},
    }
    assert harness.check_clip_b(good) == []
    native = {
        "verdict": {"world": "Earth", "factor": 1.0},
        "worlds": {"candidates": [{"world": "Earth", "fits_native": True}]},
    }
    assert harness.check_clip_b(native)
    far = {
        "verdict": {"world": "Moon", "factor": 2.5},
        "worlds": {"candidates": [{"world": "Moon", "fits_native": False}]},
    }
    assert harness.check_clip_b(far)


def test_clip_c_needs_impossible_wall_and_normal_clock(harness):
    good = {
        "verdict": {"kind": "impossible", "reason": "wall run is impossible"},
        "segments": [
            {"id": "wall-segment", "g": 9.81 - 6 * 0.2, "sigma": 0.2},
        ],
        "clock": {"verdict": "normal"},
    }
    assert harness.check_clip_c(good) == []
    assert harness.check_clip_c(
        {**good, "verdict": {"kind": "world", "reason": ""}}
    )
    assert harness.check_clip_c({**good, "segments": []})
    assert harness.check_clip_c({**good, "clock": {"verdict": "odd"}})


def test_universal_cost_time_maskcheck_valid_provenance(harness):
    assert harness.check_universal(_moon_result(), _moon_summary()) == []
    assert harness.check_universal(_moon_result(), _moon_summary(cost=2.0))
    assert harness.check_universal(_moon_result(), _moon_summary(wall=1800.0))
    bare = {"verdict": _moon_result()["verdict"], "calculation_steps": []}
    assert harness.check_universal(bare, _moon_summary(masks=0))
    assert harness.check_universal(_moon_result(), "not-a-summary")


def test_prompt_leak_scan_identities_verdicts_tolerances(harness):
    # System/operator text: identities AND expectations both fail.
    assert harness.check_no_leak(["the apollo clip"], [], [])
    assert harness.check_no_leak(["must be moon"], [], [])
    # The agent may name what it identifies in the frames (part 01):
    # identities in agent turns are not a leak.
    assert harness.check_no_leak([], ["this looks like apollo hardware"], []) == []
    # But acceptance constants and expected verdicts in agent turns are.
    assert harness.check_no_leak([], ["expected moon"], [])
    assert harness.check_no_leak([], [], ["should be moon"])
    # Ordinary physics numbers are not expectations.
    assert harness.check_no_leak(["g is 9.81 m/s^2"], [], []) == []
    assert harness.check_no_leak([], ["measured 1.7 m/s^2"], []) == []
    # Matching is case-insensitive.
    assert harness.check_no_leak(["APOLLO"], [], [])


def test_structural_no_runtime_import_of_tests(harness, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "clean.py").write_text("X = 1\n", encoding="utf-8")
    assert harness.check_runtime_separation(tmp_path) == []
    (tmp_path / "src" / "dirty.py").write_text(
        "from tests.acceptance import harness\n", encoding="utf-8"
    )
    findings = harness.check_runtime_separation(tmp_path)
    assert findings and "dirty.py" in findings[0]
    # The regeneration driver legitimately references the harness and is
    # out of scope: only src/, prompts/ and player/ are scanned.
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "dev_loop").write_text(
        "load tests/acceptance/harness.py\n", encoding="utf-8"
    )
    assert harness.check_runtime_separation(tmp_path) == findings


def test_cross_clip_ratio_report_only_never_on_page(harness):
    assert harness.ab_ratio(1.62, 2.43) == pytest.approx(1.5)
    assert harness.ab_ratio(0.0, 2.43) is None
    assert harness.ab_ratio(None, 2.43) is None
    # The ratio is a free function for the acceptance report: it takes
    # both clips' numbers as arguments and writes nothing anywhere — no
    # page build, no page file, no feedback into any run.
    import inspect

    source = inspect.getsource(harness.ab_ratio).casefold()
    for writer in ("write", "index.html", "build_page", "pagebuild",
                   "open(", "save", "publish"):
        assert writer not in source


def test_leak_failure_beats_right_verdicts(harness):
    """A leak finding fails the run even when every verdict is right."""
    run_problems = list(harness.check_clip_a(_moon_result()))
    run_problems += harness.check_no_leak(["a16salute"], [], [])
    assert run_problems

"""E1 probes: eval/check.py verdicts, --dry-run, and the blindness guard.

Offline. check.py is driven through subprocess on hand-made run dirs;
each case gets one PASS, one SOFT FAIL and one HARD FAIL run.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from physics_proof import video

REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "eval" / "check.py"
SCRIPT = REPO / "scripts" / "make_moon_clips.py"
#: Decoded frame count of the source `a16salute.mpg` (E1 run 2026-10-27,
#: confirmed by the maintainer with `physics_proof.video`).
SOURCE_FRAMES = 466


def write_run(tmp_path: Path, analysis: dict, summary: dict) -> Path:
    """Write a minimal run dir with analysis.json and summary.json."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "analysis.json").write_text(json.dumps(analysis), encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return run_dir


def base_summary(**over: float) -> dict:
    """A summary.json that passes the common checks."""
    summary = {"cost_usd": 1.0, "wall_time_s": 600.0, "turns": 10,
               "mask_checks": 1}
    summary.update(over)
    return summary


def base_analysis() -> dict:
    """Minimal analysis.json with one logged mask check."""
    return {"reference": [{"mask_check": {"verdict": "agrees",
                                           "covers": "the whole object"}}]}


def run_check(run_dir: Path, case: str) -> subprocess.CompletedProcess[str]:
    """Run eval/check.py on a run dir for one case."""
    return subprocess.run(
        [sys.executable, str(CHECK), str(run_dir), "--case", case],
        capture_output=True, text=True, cwd=REPO,
    )


def test_expected_json_has_all_cases() -> None:
    """expected.json holds the pass criteria from SPEC 5 as data."""
    expected = json.loads((REPO / "eval" / "expected.json").read_text())
    assert expected["moon-A"]["verdict_state"] == "fits:Moon"
    assert expected["moon-A"]["g_err_max"] == pytest.approx(0.35)
    assert expected["moon-B"]["verdict_state"] == "none_fits"
    assert expected["moon-B"]["k_target"] == pytest.approx(1.5)
    assert expected["moon-B"]["k_tol"] == pytest.approx(0.25)
    assert expected["wallrun"]["overall_label"] == "impossible"
    assert expected["wallrun"]["timescale_verdict"] == "normal"


def test_moon_a_pass(tmp_path: Path) -> None:
    """Clip A verdict fits:Moon inside 2 sigma with a tight error."""
    analysis = base_analysis()
    analysis["verdict"] = {"state": "fits:Moon", "g": 1.62, "g_err": 0.2}
    proc = run_check(write_run(tmp_path, analysis, base_summary()), "moon-A")
    assert proc.returncode == 0
    assert proc.stdout.startswith("PASS")


def test_moon_a_soft(tmp_path: Path) -> None:
    """Clip A undetermined is a soft fail."""
    analysis = base_analysis()
    analysis["verdict"] = {"state": "undetermined", "g": 5.0, "g_err": 4.0}
    proc = run_check(write_run(tmp_path, analysis, base_summary()), "moon-A")
    assert proc.returncode == 1
    assert proc.stdout.startswith("SOFT FAIL")


def test_moon_a_hard(tmp_path: Path) -> None:
    """Clip A fitting Earth is a hard fail."""
    analysis = base_analysis()
    analysis["verdict"] = {"state": "fits:Earth", "g": 9.81, "g_err": 0.2}
    proc = run_check(write_run(tmp_path, analysis, base_summary()), "moon-A")
    assert proc.returncode == 2
    assert proc.stdout.startswith("HARD FAIL")


def test_moon_b_pass(tmp_path: Path) -> None:
    """Clip B verdict none_fits with k near 1.5 passes."""
    analysis = base_analysis()
    analysis["verdict"] = {"state": "none_fits", "g": 0.72,
                           "g_err": 0.2, "k": 1.5}
    proc = run_check(write_run(tmp_path, analysis, base_summary()), "moon-B")
    assert proc.returncode == 0
    assert proc.stdout.startswith("PASS")


def test_moon_b_soft(tmp_path: Path) -> None:
    """Clip B undetermined is a soft fail."""
    analysis = base_analysis()
    analysis["verdict"] = {"state": "undetermined", "g": 3.0, "g_err": 3.0,
                           "k": None}
    proc = run_check(write_run(tmp_path, analysis, base_summary()), "moon-B")
    assert proc.returncode == 1
    assert proc.stdout.startswith("SOFT FAIL")


def test_moon_b_hard(tmp_path: Path) -> None:
    """Clip B fitting the Moon is a hard fail."""
    analysis = base_analysis()
    analysis["verdict"] = {"state": "fits:Moon", "g": 1.62, "g_err": 0.2,
                           "k": 1.0}
    proc = run_check(write_run(tmp_path, analysis, base_summary()), "moon-B")
    assert proc.returncode == 2
    assert proc.stdout.startswith("HARD FAIL")


def wall_analysis(label: str = "impossible", sigma: float = -8.0,
                  timescale: str = "normal",
                  state: str = "none_fits") -> dict:
    """Minimal wall-run analysis.json with one wall segment."""
    analysis = base_analysis()
    analysis["flights"] = [{
        "kind": "wall",
        "accel": 0.5, "accel_err": 0.2,
        "hypothesis": {"name": "unsupported on Earth", "value": 9.81},
        "decide": {"state": state, "sigmas": {"unsupported on Earth": sigma}},
    }]
    analysis["timescale"] = {"verdict": timescale}
    analysis["overall"] = {"label": label}
    return analysis


def test_wallrun_pass(tmp_path: Path) -> None:
    """Wall run impossible at normal speed with |sigma| > 5 passes."""
    proc = run_check(write_run(tmp_path, wall_analysis(), base_summary()),
                     "wallrun")
    assert proc.returncode == 0
    assert proc.stdout.startswith("PASS")


def test_wallrun_soft(tmp_path: Path) -> None:
    """Wall run with an unchecked time scale is a soft fail."""
    proc = run_check(write_run(tmp_path, wall_analysis(timescale="slow"),
                               base_summary()), "wallrun")
    assert proc.returncode == 1
    assert proc.stdout.startswith("SOFT FAIL")


def test_wallrun_hard(tmp_path: Path) -> None:
    """Wall run with no wall segment is a hard fail."""
    analysis = base_analysis()
    analysis["flights"] = [{"kind": "flight"}]
    analysis["timescale"] = {"verdict": "normal"}
    analysis["overall"] = {"label": "impossible"}
    proc = run_check(write_run(tmp_path, analysis, base_summary()), "wallrun")
    assert proc.returncode == 2
    assert proc.stdout.startswith("HARD FAIL")


def test_budget_overrun_is_hard(tmp_path: Path) -> None:
    """Cost above the cap hard-fails an otherwise passing run."""
    analysis = base_analysis()
    analysis["verdict"] = {"state": "fits:Moon", "g": 1.62, "g_err": 0.2}
    proc = run_check(write_run(tmp_path, analysis, base_summary(cost_usd=5.0)),
                     "moon-A")
    assert proc.returncode == 2
    assert "cost" in proc.stdout


def test_missing_mask_check_is_hard(tmp_path: Path) -> None:
    """A run with no logged mask check hard-fails."""
    analysis: dict = {"verdict": {"state": "fits:Moon", "g": 1.62,
                                  "g_err": 0.2}}
    summary = base_summary(mask_checks=0)
    proc = run_check(write_run(tmp_path, analysis, summary), "moon-A")
    assert proc.returncode == 2
    assert "mask check" in proc.stdout


@pytest.mark.slow
def test_clip_a_matches_source_frames() -> None:
    """E1-fix1: committed A.mp4 holds exactly the decoded source frames.

    Frame count equals the source's decoded count and no duplicate runs
    were inserted by the re-encode. Runs on the committed file, so it
    decodes the whole clip (slow).
    """
    clip = REPO / "examples" / "moon" / "A.mp4"
    assert video.probe(clip).frame_count == SOURCE_FRAMES
    assert video.duplicate_runs(video.frame_diffs(clip)) == []


def test_dry_run_prints_commands(tmp_path: Path) -> None:
    """--dry-run prints both ffmpeg commands without downloading."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"], capture_output=True,
        text=True, cwd=REPO,
    )
    assert proc.returncode == 0
    assert "a16salute.mpg" in proc.stdout
    assert "30000/1001" in proc.stdout
    assert "setpts=1.5*PTS" in proc.stdout
    assert "minterpolate" in proc.stdout


def test_package_reads_no_eval_data() -> None:
    """physics_proof/ never loads eval/ data or clip SOURCE.md files."""
    package = REPO / "physics_proof"
    offenders = []
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "eval/" in text or "expected.json" in text or "SOURCE.md" in text:
            offenders.append(path.name)
    assert offenders == []


def test_agent_prompt_has_no_answers() -> None:
    """Ground-truth strings stay out of the agent prompt (if it exists)."""
    prompt = REPO / "config" / "prompts" / "agent_system.md"
    if not prompt.exists():
        return
    text = prompt.read_text(encoding="utf-8")
    for needle in ("1.62", "Moon", "slowed", "1.5"):
        assert needle not in text

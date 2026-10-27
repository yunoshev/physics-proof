"""E1. Check one analysis run against the acceptance criteria.

Reads only ``run_dir/analysis.json`` and ``run_dir/summary.json``, then
prints one verdict line: PASS, SOFT FAIL or HARD FAIL, with reasons.

Usage: eval/check.py <run_dir> --case moon-A|moon-B|wallrun
       [--expected eval/expected.json] [--cap-usd 2.0]

Exit codes: 0 PASS, 1 SOFT FAIL, 2 HARD FAIL, 3 usage or unreadable files.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

CASES = ("moon-A", "moon-B", "wallrun")

_PASS = 0
_SOFT = 1
_HARD = 2

_COST_KEYS = ("cost_usd", "cost", "total_cost_usd", "spend_usd")
_WALL_KEYS = ("wall_time_s", "wall_s", "elapsed_s", "wall_time", "duration_s")
_TURN_KEYS = ("turns", "n_turns")
_MASK_KEYS = ("mask_checks", "mask_check", "n_mask_checks")


def _first(d: dict, keys: tuple[str, ...]):
    """First present key's value, or None."""
    for key in keys:
        if isinstance(d, dict) and key in d and isinstance(d[key], (int, float)):
            value = d[key]
            if isinstance(value, bool):
                continue
            return value
    return None


def _num(value) -> float | None:
    """Finite float from a JSON number, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def load_json(path: Path) -> dict:
    """Load a JSON object file; exit 3 with a message on failure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("HARD FAIL: missing file " + str(path), flush=True)
        raise SystemExit(3)
    except (OSError, json.JSONDecodeError) as exc:
        print("HARD FAIL: cannot read " + str(path) + ": " + str(exc), flush=True)
        raise SystemExit(3)
    if not isinstance(data, dict):
        print("HARD FAIL: " + str(path) + " is not a JSON object", flush=True)
        raise SystemExit(3)
    return data


def mask_check_count(analysis: dict, summary: dict) -> int:
    """Mask checks logged in analysis.json plus summary.json."""
    count = 0
    refs = analysis.get("reference")
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            check = ref.get("mask_check")
            if isinstance(check, dict) and check.get("verdict") in (
                "agrees", "covers_more", "covers_less",
                "different_object", "cannot_tell",
            ):
                count += 1
    logged = _first(summary, _MASK_KEYS)
    if logged is not None and logged > count:
        count = int(logged)
    return count


def common_checks(analysis: dict, summary: dict, cap: float,
                  wall_max: float) -> tuple[list[str], list[str]]:
    """Budget, wall-time, turns and mask-check gate. Returns (hard, soft)."""
    hard: list[str] = []
    soft: list[str] = []
    cost = _num(_first(summary, _COST_KEYS))
    if cost is None:
        hard.append("cost not reported in summary.json")
    elif cost > cap:
        hard.append("cost $" + f"{cost:.2f}" + " exceeds cap $" + f"{cap:.2f}")
    wall = _num(_first(summary, _WALL_KEYS))
    if wall is None:
        hard.append("wall time not reported in summary.json")
    elif wall > wall_max:
        hard.append("wall time " + f"{wall:.0f}" + "s exceeds "
                    + f"{wall_max:.0f}" + "s")
    turns = _num(_first(summary, _TURN_KEYS))
    if turns is None or turns < 1:
        hard.append("no turns logged in summary.json")
    if mask_check_count(analysis, summary) < 1:
        hard.append("no mask check logged")
    return hard, soft


def check_moon_a(analysis: dict, want: dict) -> tuple[list[str], list[str]]:
    """Clip A must fit the Moon with a tight error bar."""
    hard: list[str] = []
    soft: list[str] = []
    verdict = analysis.get("verdict")
    if not isinstance(verdict, dict):
        return ["verdict section missing"], []
    state = verdict.get("state")
    g = _num(verdict.get("g"))
    g_err = _num(verdict.get("g_err"))
    if g is None or g_err is None or g_err <= 0:
        return ["verdict g/g_err missing or not positive"], []
    moon = float(want["g_moon"])
    tol = float(want["sigma_tol"])
    within = abs(g - moon) <= tol * g_err
    tight = g_err <= float(want["g_err_max"])
    if state == want["verdict_state"] and within and tight:
        return [], []
    if state == "undetermined":
        soft.append("verdict undetermined (g " + f"{g:.2f}" + " +- "
                    + f"{g_err:.2f}" + ")")
        return hard, soft
    if state == want["verdict_state"]:
        if not within:
            soft.append("|g - 1.62| = " + f"{abs(g - moon):.2f}"
                        + " exceeds 2*g_err")
        if not tight:
            soft.append("g_err " + f"{g_err:.2f}" + " exceeds 0.35")
        return hard, soft
    hard.append("verdict " + str(state) + " is not fits:Moon")
    return hard, soft


def check_moon_b(analysis: dict, want: dict) -> tuple[list[str], list[str]]:
    """Clip B must fit no world, with slowdown k near 1.5."""
    hard: list[str] = []
    soft: list[str] = []
    verdict = analysis.get("verdict")
    if not isinstance(verdict, dict):
        return ["verdict section missing"], []
    state = verdict.get("state")
    if state == "undetermined":
        return [], ["verdict undetermined"]
    if state == want["verdict_state"]:
        k = _num(verdict.get("k"))
        if k is None:
            return [], ["verdict none_fits but k missing"]
        if abs(k - float(want["k_target"])) <= float(want["k_tol"]):
            return [], []
        return [], ["k " + f"{k:.2f}" + " outside 1.5 +- 0.25"]
    if isinstance(state, str) and state.startswith("fits:"):
        hard.append("verdict " + state + " claims the slowed clip fits a world")
        return hard, soft
    hard.append("verdict " + str(state) + " is not none_fits")
    return hard, soft


def check_wallrun(analysis: dict, want: dict) -> tuple[list[str], list[str]]:
    """Wall run: unsupported wall segment, impossible overall, normal time."""
    hard: list[str] = []
    soft: list[str] = []
    walls = []
    flights = analysis.get("flights")
    if isinstance(flights, list):
        walls = [f for f in flights
                 if isinstance(f, dict) and f.get("kind") == want["segment_kind"]]
    if not walls:
        return ["no wall segment found"], []
    bad_state = True
    weak_sigma = False
    for flight in walls:
        decide = flight.get("decide") if isinstance(flight, dict) else None
        if not isinstance(decide, dict):
            continue
        if decide.get("state") != "none_fits":
            continue
        bad_state = False
        sigmas = decide.get("sigmas")
        if isinstance(sigmas, dict):
            values = [_num(v) for v in sigmas.values()]
            peak = max([abs(v) for v in values if v is not None], default=None)
        else:
            peak = None
        if peak is None:
            accel = _num(flight.get("accel"))
            err = _num(flight.get("accel_err"))
            hyp = flight.get("hypothesis") if isinstance(flight, dict) else None
            value = _num(hyp.get("value")) if isinstance(hyp, dict) else None
            if accel is not None and err is not None and err > 0 and value is not None:
                peak = abs((accel - value) / err)
        if peak is None or peak <= float(want["sigma_min"]):
            weak_sigma = True
        else:
            weak_sigma = False
            break
    if bad_state:
        states = [f.get("decide", {}).get("state") if isinstance(f.get("decide"), dict)
                  else None for f in walls]
        if any(isinstance(s, str) and s.startswith("fits:") for s in states):
            hard.append("wall segment verdict " + str(states[0]) + " claims support")
        else:
            soft.append("wall segment verdict is not none_fits")
        return hard, soft
    if weak_sigma:
        soft.append("wall segment |sigma| does not exceed "
                    + str(want["sigma_min"]))
    timescale = analysis.get("timescale")
    mark = timescale.get("verdict") if isinstance(timescale, dict) else None
    if mark != want["timescale_verdict"]:
        soft.append("timescale verdict " + str(mark) + " is not normal")
    overall = analysis.get("overall")
    label = overall.get("label") if isinstance(overall, dict) else None
    if label != want["overall_label"]:
        states = [f.get("decide", {}).get("state")
                  if isinstance(f.get("decide"), dict) else None for f in walls]
        if any(isinstance(s, str) and s.startswith("fits:") for s in states):
            hard.append("overall label " + str(label) + " claims support")
        else:
            soft.append("overall label " + str(label) + " is not impossible")
    return hard, soft


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Check an E1 run.")
    parser.add_argument("run_dir", help="run directory with analysis.json")
    parser.add_argument("--case", required=True, choices=CASES)
    parser.add_argument("--expected", default=None,
                        help="path to expected.json (default: eval/expected.json)")
    parser.add_argument("--cap-usd", type=float, default=None,
                        help="override the cost cap from expected.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: load run files, check, print PASS/SOFT FAIL/HARD FAIL."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    run_dir = Path(args.run_dir)
    default_expected = Path(__file__).resolve().parent / "expected.json"
    expected = load_json(Path(args.expected) if args.expected else default_expected)
    case_want = expected.get(args.case)
    if not isinstance(case_want, dict):
        print("HARD FAIL: case " + args.case + " missing from expected.json",
              flush=True)
        return 3
    analysis = load_json(run_dir / "analysis.json")
    summary = load_json(run_dir / "summary.json")
    try:
        cap = float(args.cap_usd) if args.cap_usd is not None \
            else float(expected["cost_cap_usd"])
        wall_max = float(expected["wall_time_max_s"])
    except (KeyError, TypeError, ValueError):
        print("HARD FAIL: bad cost_cap_usd/wall_time_max_s in expected.json",
              flush=True)
        return 3
    if args.case == "moon-A":
        hard, soft = check_moon_a(analysis, case_want)
    elif args.case == "moon-B":
        hard, soft = check_moon_b(analysis, case_want)
    else:
        hard, soft = check_wallrun(analysis, case_want)
    common_hard, _ = common_checks(analysis, summary, cap, wall_max)
    hard.extend(common_hard)
    cost = _first(summary, _COST_KEYS)
    wall = _first(summary, _WALL_KEYS)
    context = "cost $" + (f"{cost:.2f}" if _num(cost) is not None else "?") \
        + ", wall " + (f"{wall:.0f}" + "s" if _num(wall) is not None else "?") \
        + ", mask checks " + str(mask_check_count(analysis, summary))
    if hard:
        print("HARD FAIL (" + args.case + "): " + "; ".join(hard)
              + " [" + context + "]", flush=True)
        return _HARD
    if soft:
        print("SOFT FAIL (" + args.case + "): " + "; ".join(soft)
              + " [" + context + "]", flush=True)
        return _SOFT
    print("PASS (" + args.case + "): criteria met [" + context + "]", flush=True)
    return _PASS


if __name__ == "__main__":
    raise SystemExit(main())

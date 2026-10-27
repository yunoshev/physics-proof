"""M8 probes: agent loop with a scripted fake Spark (offline).

SAM and the mask check are served from fixtures/fakes; the python tool
runs for real in the sandbox. Plus one opt-in live call (``-m api``,
<= $0.05): a real run on the synthetic clip with 4 turns reaches at
least two tool calls and the turn costs match the ledger.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from physics_proof import sandbox as sandbox_mod

from physics_proof import blocks, video
from physics_proof.agent import (
    FORBIDDEN_WORDS,
    _prune,
    assemble_system_prompt,
    clip_probe_text,
    run_analysis,
)
from physics_proof.mask_check import MASK_CHECK_SCHEMA
from physics_proof.meta_client import FunctionCall, SamObject, SamResult, SparkResponse, UsageStats
from physics_proof.schema import combine, validate
from physics_proof.search_tool import CLASSIFY_SCHEMA

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIP = FIXTURES / "sam_clip.mp4"


def _resp(
    calls: list[FunctionCall] | None = None, text: str = "", cost: float = 0.001
) -> SparkResponse:
    """One fake Spark turn with parsed function calls."""
    return SparkResponse(
        id="resp-fake",
        model="fake-spark",
        status="completed",
        text=text,
        output=[],
        function_calls=list(calls or []),
        usage=UsageStats(),
        cost_usd=cost,
        raw=b"",
    )


def _call(name: str, args: dict[str, Any]) -> FunctionCall:
    """One fake native tool call with a dict of arguments."""
    return FunctionCall(
        id="fc-1", call_id="call-1", name=name, arguments=args, status="completed"
    )


def _square(n: int, w: int, h: int, size: int = 40) -> dict[int, list[SamObject]]:
    """One gliding square, one frame entry per cut frame."""
    out: dict[int, list[SamObject]] = {}
    for i in range(n):
        mask = np.zeros((h, w), dtype=bool)
        x = 10 + i * 5
        mask[100 : 100 + size, x : x + size] = True
        ys, xs = np.nonzero(mask)
        out[i] = [
            SamObject(
                id="0",
                box=(int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1),
                confidence=0.9,
                mask=mask,
            )
        ]
    return out


class ScriptSpark:
    """Scripted fake Spark: replays fixed tool calls for agent turns.

    Turns with ``note="mask-check"`` get a canned checker answer; anything
    else pops the next scripted item: ("call", name, args), ("text", text).
    """

    def __init__(
        self,
        script: list[tuple],
        *,
        cost: float = 0.001,
        mask_cost: float = 0.0007,
    ) -> None:
        self.script = list(script)
        self.pos = 0
        self.cost = cost
        self.mask_cost = mask_cost
        self.model = "fake-spark"
        self.turns = 0
        self.mask_calls = 0

    def video_part(self, path: str | Path) -> dict[str, Any]:
        return {"type": "input_video", "video_url": "data:video/mp4;base64,FAKE"}

    def image_part(self, path: str | Path) -> dict[str, Any]:
        return {"type": "input_image", "image_url": "data:image/png;base64,FAKE"}

    def sam_video(self, video_path: str, phrase: str, **kwargs: Any) -> SamResult:
        info = video.probe(video_path)
        n = info.frame_count
        return SamResult(
            frames=_square(n, info.width, info.height),
            frames_processed=n,
            cost_usd=n * 0.20 / 1000.0,
        )

    def respond(self, messages: Any, **kwargs: Any) -> Any:
        if kwargs.get("note") == "mask-check":
            assert kwargs.get("json_schema") == MASK_CHECK_SCHEMA
            self.mask_calls += 1
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "inside": "red square",
                        "outside": "grey background",
                        "covers": "the whole red square",
                        "verdict": "agrees",
                        "reason": "the tint covers the square only",
                    }
                ),
                cost_usd=self.mask_cost,
            )
        if kwargs.get("json_schema") == CLASSIFY_SCHEMA or kwargs.get("web_search"):
            raise AssertionError("search should not be called in this script")
        self.turns += 1
        kind = self.script[self.pos]
        self.pos += 1
        if kind[0] == "text":
            return _resp(text=kind[1], cost=self.cost)
        if kind[0] == "call":
            _, name, args = kind
            return _resp(calls=[_call(name, args)], text="calling " + name, cost=self.cost)
        raise AssertionError("bad script item " + repr(kind[0]))


def _analysis(clip_path: Path, npz_name: str) -> dict[str, Any]:
    """A valid analysis for the 10-frame synthetic clip."""
    info = video.probe(clip_path)
    dupes = video.duplicate_runs(video.frame_diffs(clip_path))
    flight_decide = blocks.decide(9.81, 0.5, {"Earth": 9.81})
    verdict_decide = blocks.decide(9.81, 0.5, {"Earth": 9.81, "Moon": 1.62})
    verdict = dict(verdict_decide, worlds={"Earth": 9.81, "Moon": 1.62})
    points = [
        {"frame": f, "x": 128.0, "y": y}
        for f, y in enumerate([200.0, 185.0, 172.0, 161.0, 152.0, 145.0, 150.0, 160.0, 175.0, 195.0])
    ]
    return {
        "type": "world-g",
        "schema_version": 1,
        "clip": {
            "file": "clip.mp4",
            "fps": float(info.fps),
            "frames": info.frame_count,
            "width": info.width,
            "height": info.height,
            "duplicates_found": len(dupes),
            "notes": "Synthetic test clip.",
        },
        "context": {
            "scene": "A red square glides across a grey frame.",
            "claim": "The square is in free flight under Earth gravity.",
            "expected": [{"quantity": "g", "value": 9.81, "unit": "m/s^2", "source": "CODATA"}],
            "sources": ["https://physics.nist.gov/cgi-bin/cuu/Value?gn"],
        },
        "first_look": {
            "what": "square",
            "where": "centre frame",
            "when": "frames 0-9",
            "source": "agent",
            "confidence": 0.6,
            "by_eye": {"quantity": "rise", "value": 0.1, "unit": "m"},
        },
        "reference": [
            {
                "name": "red square",
                "extent": "side",
                "value_m": 0.08,
                "tolerance_m": 0.002,
                "source_url": "https://example.org/red-square",
                "quote": "The square is 8 cm on a side.",
                "source_type": "primary",
                "mask": {"file": npz_name, "object": "0"},
                "mask_check": {"verdict": "agrees", "covers": "the whole red square"},
            }
        ],
        "scale": {
            "frame": 0,
            "extent_px": 40.0,
            "extent_px_err": 1.0,
            "m_per_px": 0.002,
            "m_per_px_err": 0.0001,
            "second": {
                "name": "red square width",
                "m_per_px": 0.002,
                "m_per_px_err": 0.0001,
                "agree_sigma": 0.2,
            },
            "frame_of_reference": "image",
        },
        "track": {"what": "square centre", "method": "centroid", "unit": "px", "points": points},
        "masks": {"square": {"0": [[100, 100, 140]], "4": [[80, 110, 150]]}},
        "flights": [
            {
                "kind": "flight",
                "start": 0,
                "apex": 4,
                "end": 9,
                "rise_m": 0.096,
                "duration_s": 0.9,
                "fit": {
                    "a": 490.5,
                    "a_err": 15.0,
                    "rms": 0.4,
                    "v0": -98.1,
                    "n": 10,
                    "window": {"first": 0, "last": 9},
                },
                "accel": 9.81,
                "accel_err": 0.5,
                "hypothesis": {"name": "Earth", "value": 9.81},
                "decide": flight_decide,
                "ghost": [{"frame": 0, "y": 200.0}, {"frame": 9, "y": 195.0}],
                "notes": "Clean synthetic flight.",
            }
        ],
        "timescale": None,
        "error_budget": {"reference": 0.025, "scale": 0.05, "fit": 0.05, "tracking": 0.02},
        "verdict": verdict,
        "overall": combine(verdict, None),
    }


def _code(analysis: dict[str, Any], name: str = "draft.json") -> str:
    """Sandbox code that writes one analysis file to the workspace."""
    return (
        "import json\nanalysis = json.loads("
        + json.dumps(json.dumps(analysis))
        + ")\nwith open("
        + json.dumps(name)
        + ", 'w') as handle:\n    json.dump(analysis, handle)\nprint('wrote "
        + name
        + "')\n"
    )


def _full_script(analysis: dict[str, Any], npz_name: str) -> list[tuple]:
    """The standard six-turn script for a complete run."""
    return [
        ("call", "video_info", {}),
        ("call", "frames", {"frames": [0, 5, 9], "crop": [], "label": "flight"}),
        ("call", "sam", {"phrase": "red square", "start": 0, "stop": 10}),
        (
            "call",
            "mask_check",
            {
                "file": npz_name,
                "object": 0,
                "frames": [0, 5, 9],
                "claim": "the mask covers only the red square",
            },
        ),
        ("call", "python", {"code": _code(analysis)}),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
    ]


def _local_python(code: str, workspace: str | Path) -> sandbox_mod.SandboxResult:
    """Test runner: M5 review plus plain execution, no Seatbelt profile.

    This shell cannot apply Seatbelt profiles (nested sandbox-exec is
    denied), so offline loop tests run code without the profile. The
    profile itself is M5's covered territory.
    """
    ws = Path(workspace).resolve()
    scripts = ws / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    problems = sandbox_mod.review(code)
    script = sandbox_mod._next_script_path(scripts)
    script.write_text(code, encoding="utf-8")
    if problems:
        return sandbox_mod.SandboxResult(ok=False, refused=True, problems=problems, script=script)
    before = sandbox_mod._image_snapshot(ws)
    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ws),
        capture_output=True,
        text=True,
        timeout=120,
    )
    seconds = time.monotonic() - start
    images = sandbox_mod._newest_images(ws, before)
    return sandbox_mod.SandboxResult(
        ok=proc.returncode == 0,
        refused=False,
        exit_code=proc.returncode,
        stdout=sandbox_mod._truncate(proc.stdout),
        stderr=sandbox_mod._truncate(proc.stderr),
        seconds=seconds,
        images=images,
        script=script,
    )


def _turns(run_dir: Path) -> list[dict[str, Any]]:
    """Load all turn files in order."""
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_dir / "turns").glob("turn*.json"))
    ]


NPZ = "sam/red_square.0-10.npz"


def test_full_run_writes_valid_analysis(tmp_path: Path) -> None:
    """Probe 1: a scripted run ends with a valid analysis and summary."""
    analysis = _analysis(CLIP, NPZ)
    assert validate(analysis) == []
    spark = ScriptSpark(_full_script(analysis, NPZ))
    run_dir = tmp_path / "run"
    summary = run_analysis(CLIP, run_dir, spark=spark, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    assert summary.analysis_path is not None
    saved = json.loads(Path(summary.analysis_path).read_text(encoding="utf-8"))
    assert validate(saved) == []
    stored = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    for key in (
        "status", "turns", "sam_calls", "sam_frames", "searches",
        "mask_checks", "cost_usd", "wall_s", "analysis_path", "tier", "model",
    ):
        assert key in stored, key
    assert stored["turns"] == 6
    assert stored["sam_calls"] == 1 and stored["sam_frames"] == 10
    assert stored["mask_checks"] == 1 and stored["searches"] == 0
    turns = _turns(run_dir)
    assert len(turns) == 6
    assert "The clip:" in turns[0]["result_text"]
    assert "turn02.png" in turns[1]["result_text"]
    assert "red square" in turns[2]["result_text"]
    assert "agrees" in turns[3]["result_text"]
    assert "exit 0" in turns[4]["result_text"]
    assert "valid" in turns[5]["result_text"]
    lines = (run_dir / "conversation.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 7
    assert sum(item["cost"] for item in turns) == pytest.approx(stored["cost_usd"])


def test_malformed_and_text_only_continue(tmp_path: Path) -> None:
    """Probe 2: a bad call and a text-only answer get a reply; the run goes on."""
    analysis = _analysis(CLIP, NPZ)
    script = [
        ("call", "frobnicate", {"x": 1}),
        ("text", "let me think about this clip"),
        *_full_script(analysis, NPZ),
    ]
    spark = ScriptSpark(script)
    summary = run_analysis(CLIP, tmp_path / "run", spark=spark, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    turns = _turns(tmp_path / "run")
    assert turns[0]["tool_call"] == "frobnicate"
    assert "unknown tool" in turns[0]["result_text"]
    assert turns[1]["tool_call"] is None
    assert "exactly one tool" in turns[1]["result_text"]
    assert len(turns) == 8


def test_finish_errors_return_paths_and_gate(tmp_path: Path) -> None:
    """Probe 3: schema errors name paths; finish without a check is refused."""
    good = _analysis(CLIP, NPZ)
    script = [
        ("call", "python", {"code": _code({}, "bad.json")}),
        ("call", "finish", {"analysis_file": "bad.json", "page_texts": ""}),
        ("call", "sam", {"phrase": "red square", "start": 0, "stop": 10}),
        ("call", "python", {"code": _code(good)}),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
        (
            "call",
            "mask_check",
            {
                "file": NPZ,
                "object": 0,
                "frames": [0, 5, 9],
                "claim": "the mask covers only the red square",
            },
        ),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
    ]
    spark = ScriptSpark(script)
    summary = run_analysis(CLIP, tmp_path / "run", spark=spark, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    turns = _turns(tmp_path / "run")
    assert "/reference" in turns[1]["result_text"]
    assert "no mask check" in turns[4]["result_text"]
    assert "valid" in turns[6]["result_text"]


def test_dollar_cap_stops_mid_run(tmp_path: Path) -> None:
    """Probe 4: the cap stops the run with an undetermined-budget summary."""
    script = [("call", "video_info", {})] * 10
    spark = ScriptSpark(script, cost=0.001)
    summary = run_analysis(CLIP, tmp_path / "run", spark=spark, cap_usd=0.0001)
    assert summary.status == "undetermined: budget"
    assert summary.analysis_path is None
    stored = json.loads((tmp_path / "run" / "summary.json").read_text(encoding="utf-8"))
    assert stored["status"] == "undetermined: budget"
    assert stored["turns"] == 1
    assert stored["cost_usd"] == pytest.approx(0.001)


def test_kill_and_resume_reproduces_turns(tmp_path: Path) -> None:
    """Probe 5: resume replays saved turns without calling and continues."""
    analysis = _analysis(CLIP, NPZ)
    full = _full_script(analysis, NPZ)
    first = ScriptSpark(full[:2])
    run_dir = tmp_path / "run"
    summary = run_analysis(CLIP, run_dir, spark=first, max_turns=2, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "undetermined: budget"
    before = {path.name: path.read_bytes() for path in (run_dir / "turns").glob("*.json")}
    assert set(before) == {"turn01.json", "turn02.json"}
    second = ScriptSpark(full[2:])
    summary = run_analysis(CLIP, run_dir, spark=second, max_turns=10, resume=True, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    after = {path.name: path.read_bytes() for path in (run_dir / "turns").glob("*.json")}
    assert after["turn01.json"] == before["turn01.json"]
    assert after["turn02.json"] == before["turn02.json"]
    assert second.turns == 4
    assert len(after) == 6


def test_blind_prompt_and_clip_name(tmp_path: Path) -> None:
    """Probe 6: the prompt never sees the file name; the clip is clip.mp4."""
    named = tmp_path / "apollo16_moon_jump.mp4"
    named.write_bytes(CLIP.read_bytes())
    run_dir = tmp_path / "run"
    spark = ScriptSpark([("call", "video_info", {})])
    run_analysis(named, run_dir, spark=spark, max_turns=1, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert (run_dir / "workspace" / "clip.mp4").exists()
    assert not (run_dir / "workspace" / named.name).exists()
    info = video.probe(run_dir / "workspace" / "clip.mp4")
    prompt = assemble_system_prompt(
        max_turns=40,
        sam_frames=1500,
        searches=6,
        mask_checks=4,
        cap_usd=2.0,
        probe_text=clip_probe_text(info, []),
    )
    lowered = prompt.lower()
    for word in FORBIDDEN_WORDS:
        assert word not in lowered, word
    assert "apollo16" not in lowered
    assert named.name not in prompt
    logged = (run_dir / "conversation.jsonl").read_text(encoding="utf-8").lower()
    assert "apollo" not in logged


def test_image_pruning_keeps_last_two() -> None:
    """Context: images older than the last two tool results are replaced."""
    def shot(n: int) -> dict[str, Any]:
        return {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "shots"},
                {"type": "input_image", "image_url": "img" + str(n)},
            ],
        }

    messages = [shot(0), {"role": "user", "content": "x"}, shot(1), shot(2), shot(3)]
    pruned = _prune(messages)
    kept = [
        item for item in pruned
        if any(isinstance(p, dict) and p.get("type") == "input_image" for p in item.get("content", []))
        if isinstance(item.get("content"), list)
    ]
    assert len(kept) == 2
    assert kept[0]["content"][1]["image_url"] == "img2"
    assert "omitted" in pruned[0]["content"][0]["text"]


def _no_computed(analysis: dict[str, Any]) -> dict[str, Any]:
    """Copy with measurements only: no decide, no computed verdict/overall keys."""
    import copy

    broken = copy.deepcopy(analysis)
    for flight in broken["flights"]:
        flight.pop("decide", None)
    verdict = broken.get("verdict", {})
    for key in ("state", "world", "consistent", "sigmas", "nearest", "k", "text", "k_sigma"):
        verdict.pop(key, None)
    broken["overall"] = {"label": "Earth", "text": "A hand-written guess, not combine."}
    return broken


def test_finish_fills_decide_verdict_overall(tmp_path: Path) -> None:
    """Probe 1 (fix1): finish computes decide/verdict/overall; no text guess needed."""
    from physics_proof.agent import run_analysis as local_run

    analysis = _no_computed(_analysis(CLIP, NPZ))
    assert analysis["overall"]["label"] == "Earth"
    script = [
        ("call", "sam", {"phrase": "red square", "start": 0, "stop": 10}),
        (
            "call",
            "mask_check",
            {
                "file": NPZ,
                "object": 0,
                "frames": [0, 5, 9],
                "claim": "the mask covers only the red square",
            },
        ),
        ("call", "python", {"code": _code(analysis)}),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
    ]
    spark = ScriptSpark(script)
    run_dir = tmp_path / "run"
    summary = local_run(CLIP, run_dir, spark=spark, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    saved = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    assert validate(saved) == []
    flight_decide = blocks.decide(9.81, 0.5, {"Earth": 9.81})
    verdict_decide = blocks.decide(9.81, 0.5, {"Earth": 9.81, "Moon": 1.62})
    for key in ("state", "consistent", "k", "text"):
        assert saved["flights"][0]["decide"][key] == flight_decide[key]
    for key in ("state", "consistent", "k", "text"):
        assert saved["verdict"][key] == verdict_decide[key]
    assert saved["overall"] == combine(
        dict(verdict_decide, worlds={"Earth": 9.81, "Moon": 1.62}), None
    )
    turns = _turns(run_dir)
    assert "does not match combine" not in turns[-1]["result_text"]
    assert "valid" in turns[-1]["result_text"]


def test_finish_coerces_type_slips(tmp_path: Path) -> None:
    """Probe 6 (fix1): int/list slips are coerced and reported, not rejected."""
    import copy

    from physics_proof.agent import run_analysis as local_run

    analysis = copy.deepcopy(_analysis(CLIP, NPZ))
    analysis["clip"]["duplicates_found"] = [(1, 2), (4, 5)]
    analysis["reference"][0]["mask"]["object"] = 0
    flight = analysis["flights"][0]
    flight["accel"] = [flight["accel"], flight["accel_err"]]
    del flight["accel_err"]
    flight.pop("decide", None)
    analysis["scale"]["second"] = [analysis["scale"]["second"]]
    script = [
        ("call", "sam", {"phrase": "red square", "start": 0, "stop": 10}),
        (
            "call",
            "mask_check",
            {
                "file": NPZ,
                "object": 0,
                "frames": [0, 5, 9],
                "claim": "the mask covers only the red square",
            },
        ),
        ("call", "python", {"code": _code(analysis)}),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
    ]
    spark = ScriptSpark(script)
    run_dir = tmp_path / "run"
    summary = local_run(CLIP, run_dir, spark=spark, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    saved = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    assert validate(saved) == []
    assert saved["clip"]["duplicates_found"] == 2
    assert saved["reference"][0]["mask"]["object"] == "0"
    assert saved["flights"][0]["accel"] == pytest.approx(9.81)
    assert saved["flights"][0]["accel_err"] == pytest.approx(0.5)
    assert isinstance(saved["scale"]["second"], dict)
    assert saved["scale"]["second"]["name"] == "red square width"
    turns = _turns(run_dir)
    assert "Coercions" in turns[-1]["result_text"]
    assert "/clip/duplicates_found" in turns[-1]["result_text"]
    assert "/reference/0/mask/object" in turns[-1]["result_text"]


def test_finish_second_null_needs_second_missing(tmp_path: Path) -> None:
    """Probe (fix3): second:null needs second_missing; neither is a schema issue."""
    import copy

    from physics_proof.agent import run_analysis as local_run

    neither = copy.deepcopy(_analysis(CLIP, NPZ))
    neither["scale"]["second"] = None
    fixed = copy.deepcopy(neither)
    fixed["scale"]["second_missing"] = (
        "No second object of known size is visible at the same depth."
    )
    assert any(
        issue.path == "/scale/second_missing" for issue in validate(neither)
    )
    assert validate(fixed) == []
    script = [
        ("call", "sam", {"phrase": "red square", "start": 0, "stop": 10}),
        (
            "call",
            "mask_check",
            {
                "file": NPZ,
                "object": 0,
                "frames": [0, 5, 9],
                "claim": "the mask covers only the red square",
            },
        ),
        ("call", "python", {"code": _code(neither, "neither.json")}),
        ("call", "finish", {"analysis_file": "neither.json", "page_texts": ""}),
        ("call", "python", {"code": _code(fixed)}),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
    ]
    spark = ScriptSpark(script)
    run_dir = tmp_path / "run"
    summary = local_run(CLIP, run_dir, spark=spark, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    turns = _turns(run_dir)
    assert len(turns) == 6
    assert "/scale/second_missing" in turns[3]["result_text"]
    assert "valid" in turns[5]["result_text"]
    saved = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    assert validate(saved) == []
    assert saved["scale"]["second"] is None


def _rect_mask(height: int, width: int, box: tuple[int, int, int, int]) -> np.ndarray:
    """One 2D bool mask with a filled rectangle (y0, y1, x0, x1)."""
    mask = np.zeros((height, width), dtype=bool)
    y0, y1, x0, x1 = box
    mask[y0:y1, x0:x1] = True
    return mask


def _write_ref_npz(path: Path, frames: list[int], ids: list[int], tracks: list[list[np.ndarray]]) -> None:
    """Save one synthetic reference-mask archive for the finish gate."""
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.stack([np.stack(track, axis=0) for track in tracks], axis=1)
    blocks.save_masks(path, frames, ids, arr, [0.9] * len(ids))


def _ref_entry(name: str, npz: str, obj: str, extent: str = "height") -> dict[str, Any]:
    """One reference entry pointing at a synthetic mask."""
    return {
        "name": name,
        "extent": extent,
        "value_m": 0.5,
        "tolerance_m": 0.02,
        "source_url": "https://example.org/object",
        "quote": "The object is 50 cm.",
        "source_type": "primary",
        "mask": {"file": npz, "object": obj},
        "mask_check": {"verdict": "agrees", "covers": "the whole object"},
    }


def test_finish_second_same_mask_refused_then_fixed(tmp_path: Path) -> None:
    """Probe (fix3): height and width of one mask are refused with the IoU."""
    import copy

    from physics_proof.agent import run_analysis as local_run

    pack_npz = "sam/pack.0-10.npz"
    frames = list(range(10))
    _write_ref_npz(
        tmp_path / "run" / "workspace" / pack_npz,
        frames,
        [0],
        [[_rect_mask(256, 256, (100, 180, 50, 90)) for _ in frames]],
    )
    bad = copy.deepcopy(_analysis(CLIP, pack_npz))
    bad["reference"] = [
        _ref_entry("backpack", pack_npz, "0", "height"),
        _ref_entry("backpack width", pack_npz, "0", "width"),
    ]
    bad["scale"]["second"] = {
        "name": "backpack width",
        "m_per_px": 0.002,
        "m_per_px_err": 0.0001,
        "agree_sigma": 0.08,
        "reference_index": 1,
    }
    assert validate(bad) == []
    good = copy.deepcopy(bad)
    good["scale"]["second"] = None
    good["scale"]["second_missing"] = (
        "Only the backpack has a known size; no independent reference exists."
    )
    script = [
        (
            "call",
            "mask_check",
            {
                "file": pack_npz,
                "object": 0,
                "frames": [0, 5, 9],
                "claim": "the mask covers only the backpack",
            },
        ),
        ("call", "python", {"code": _code(bad, "bad.json")}),
        ("call", "finish", {"analysis_file": "bad.json", "page_texts": ""}),
        ("call", "python", {"code": _code(good)}),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
    ]
    spark = ScriptSpark(script)
    run_dir = tmp_path / "run"
    summary = local_run(CLIP, run_dir, spark=spark, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    turns = _turns(run_dir)
    assert len(turns) == 5
    assert "the second reference is the same object as the first" in turns[2]["result_text"]
    assert "IoU 1.00" in turns[2]["result_text"]
    assert "second_missing" in turns[2]["result_text"]
    assert "valid" in turns[4]["result_text"]
    saved = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    assert validate(saved) == []


def test_finish_second_independent_mask_accepted(tmp_path: Path) -> None:
    """Probe (fix3): a small mask inside a large one (IoU ~0.2) is accepted."""
    import copy

    from physics_proof.agent import _second_independence_error, run_analysis as local_run

    suit_npz = "sam/suit.0-10.npz"
    frames = list(range(10))
    suit = [_rect_mask(256, 256, (20, 120, 30, 130)) for _ in frames]
    pack = [_rect_mask(256, 256, (40, 80, 60, 110)) for _ in frames]
    _write_ref_npz(tmp_path / "run" / "workspace" / suit_npz, frames, [0, 1], [suit, pack])
    refs = [
        _ref_entry("suit", suit_npz, "0"),
        _ref_entry("backpack", suit_npz, "1"),
    ]
    scale = {
        "second": {
            "name": "backpack",
            "m_per_px": 0.002,
            "m_per_px_err": 0.0001,
            "agree_sigma": 0.2,
            "reference_index": 1,
        }
    }
    workspace = tmp_path / "run" / "workspace"
    assert _second_independence_error(workspace, scale, refs) is None
    analysis = copy.deepcopy(_analysis(CLIP, suit_npz))
    analysis["reference"] = refs
    analysis["scale"]["second"] = dict(scale["second"])
    script = [
        (
            "call",
            "mask_check",
            {
                "file": suit_npz,
                "object": 0,
                "frames": [0, 5, 9],
                "claim": "the mask covers the whole suit",
            },
        ),
        ("call", "python", {"code": _code(analysis)}),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
    ]
    spark = ScriptSpark(script)
    run_dir = tmp_path / "run"
    summary = local_run(CLIP, run_dir, spark=spark, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    saved = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    assert validate(saved) == []


def test_second_independence_no_shared_frame_and_same_file(tmp_path: Path) -> None:
    """Probe (fix3): masks sharing no frame are independent; identical masks are not."""
    from physics_proof.agent import _second_independence_error

    workspace = tmp_path / "workspace"
    early = "sam/early.0-5.npz"
    late = "sam/late.5-10.npz"
    rect = _rect_mask(256, 256, (100, 180, 50, 90))
    _write_ref_npz(workspace / early, [0, 1, 2, 3, 4], [0], [[rect] * 5])
    _write_ref_npz(workspace / late, [5, 6, 7, 8, 9], [0], [[rect] * 5])
    refs = [_ref_entry("early", early, "0"), _ref_entry("late", late, "0")]
    scale = {
        "second": {
            "name": "late",
            "m_per_px": 0.002,
            "m_per_px_err": 0.0001,
            "agree_sigma": 0.1,
            "reference_index": 1,
        }
    }
    assert _second_independence_error(workspace, scale, refs) is None
    twin = "sam/twin.0-10.npz"
    _write_ref_npz(workspace / twin, list(range(10)), [0], [[rect] * 10])
    twin_refs = [_ref_entry("early", early, "0"), _ref_entry("twin", twin, "0")]
    twin_scale = {
        "second": {
            "name": "twin",
            "m_per_px": 0.002,
            "m_per_px_err": 0.0001,
            "agree_sigma": 0.0,
            "reference_index": 1,
        }
    }
    refused = _second_independence_error(workspace, twin_scale, twin_refs)
    assert refused is not None
    assert "the second reference is the same object as the first" in refused
    assert "IoU 1.00" in refused


def test_tool_results_name_workspace_files(tmp_path: Path) -> None:
    """Probe 2 (fix1): every tool result names the files it produced."""
    analysis = _analysis(CLIP, NPZ)
    spark = ScriptSpark(_full_script(analysis, NPZ))
    run_dir = tmp_path / "run"
    summary = run_analysis(CLIP, run_dir, spark=spark, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    turns = _turns(run_dir)
    assert "sheets/turn02.png" in turns[1]["result_text"]
    assert "sam/red_square.0-10.npz" in turns[2]["result_text"]
    assert "sam/red_square.0-10.png" in turns[2]["result_text"]
    assert "mask_checks/" in turns[3]["result_text"]
    assert NPZ in turns[3]["result_text"]
    assert "scripts/" in turns[4]["result_text"]


def test_blocks_doc_has_full_signatures() -> None:
    """Probe 3 (fix1): the prompt carries full signatures and docstrings."""
    from physics_proof.agent import assemble_system_prompt, blocks_doc

    doc = blocks_doc()
    for name in blocks.__all__:
        func = getattr(blocks, name)
        assert "blocks." + name + "(" in doc, name
        first_line = (func.__doc__ or "").strip().splitlines()[0]
        assert first_line[:40] in doc, name
    assert "fit_parabola(frames" in doc
    assert "decide(g" in doc
    prompt = assemble_system_prompt(
        max_turns=60,
        sam_frames=1500,
        searches=6,
        mask_checks=4,
        cap_usd=2.0,
        probe_text=clip_probe_text(video.probe(CLIP), []),
    )
    assert "rglob" in prompt
    assert "finish computes" in prompt
    assert "sam/<phrase>.<start>-<stop>.npz" in prompt


def test_finish_worlds_tested_earth_only(tmp_path: Path) -> None:
    """Probe (fix2): worlds_tested ["Earth"] on the r3 numbers.

    g 3.75 ± 0.72 with the clock at 5.10 ± 0.17 steps/s against a natural
    range of 2.5-4.5: finish runs decide against Earth alone, so none_fits
    with k = sqrt(9.81 / 3.75) ≈ 1.62, and the true rate ≈ 8.3 steps/s is
    outside the natural range, so overall is impossible. The Moon stays in
    verdict.worlds but out of the decide table.
    """
    from physics_proof.agent import run_analysis as local_run

    analysis = _no_computed(_analysis(CLIP, NPZ))
    flight = analysis["flights"][0]
    flight["accel"] = 3.75
    flight["accel_err"] = 0.72
    flight["hypothesis"] = {"name": "Earth", "value": 9.81}
    verdict = analysis["verdict"]
    verdict["g"] = 3.75
    verdict["g_err"] = 0.72
    verdict["worlds"] = {"Earth": 9.81, "Moon": 1.62}
    verdict["worlds_tested"] = ["Earth"]
    verdict["worlds_ruled_out"] = [
        {
            "world": "Moon",
            "by": "street scene with buildings and people walking normally",
        }
    ]
    analysis["timescale"] = {
        "method": "step rate on the run-up",
        "value": 5.10,
        "err": 0.17,
        "unit": "steps/s",
        "expected_range": [2.5, 4.5],
        "verdict": "normal",
    }
    spark = ScriptSpark(_full_script(analysis, NPZ))
    run_dir = tmp_path / "run"
    summary = local_run(CLIP, run_dir, spark=spark, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    assert summary.status == "ok"
    saved = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    assert validate(saved) == []
    assert saved["verdict"]["state"] == "none_fits"
    assert saved["verdict"]["worlds_tested"] == ["Earth"]
    assert saved["verdict"]["k"] == pytest.approx(1.62, abs=0.01)
    assert saved["verdict"]["nearest"] == "Earth"
    assert saved["overall"]["label"] == "impossible"


def test_effort_high_default_and_logged(tmp_path: Path) -> None:
    """Defaults: 60 turns, high reasoning effort, logged in the summary."""
    import inspect

    from physics_proof.agent import run_analysis as local_run

    assert inspect.signature(local_run).parameters["max_turns"].default == 60
    assert inspect.signature(local_run).parameters["effort"].default == "high"
    spark = ScriptSpark([("call", "video_info", {})])
    run_dir = tmp_path / "run"
    summary = local_run(CLIP, run_dir, spark=spark, max_turns=1, python_runner=_local_python, cache_dir=tmp_path / "samcache")
    stored = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert stored["effort"] == "high"
    assert summary.effort == "high"


@pytest.mark.api
def test_real_run_reaches_two_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """API: a 4-turn real run reaches two tool calls; costs match the ledger."""
    from physics_proof.agent import run_analysis as real_run

    monkeypatch.setenv("META_GLOBAL_LEDGER", str(tmp_path / "global.jsonl"))
    run_dir = tmp_path / "run"
    summary = real_run(CLIP, run_dir, tier="contributor", cap_usd=0.05, max_turns=4)
    print("api cost: $%.6f status %s" % (summary.cost_usd, summary.status), flush=True)
    assert summary.cost_usd <= 0.05
    turns = _turns(run_dir)
    used = [item for item in turns if item["tool_call"] is not None]
    assert len(used) >= 2, [item["tool_call"] for item in turns]
    ledger_total = 0.0
    for line in (run_dir / "ledger.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            ledger_total += float(json.loads(line)["usd"])
    assert ledger_total > 0
    assert sum(item["cost"] for item in turns) == pytest.approx(ledger_total)

"""M14 probes: the agent builds and verifies its own tools (offline).

make_tool registers a module only when its probe exits 0 and prints
PASS; only registered tools are importable from later python calls.
Limits, finish and promote are covered too. The python runner here
mirrors the production sandbox bootstrap (workspace tools/registered
on the child sys.path); the Seatbelt profile itself is M5 territory.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from physics_proof import sandbox as sandbox_mod
from physics_proof.agent import run_analysis
from physics_proof.schema import validate
from physics_proof.toolbox import (
    is_valid_name,
    module_functions,
    module_purpose,
    promote_tool,
)

from test_agent_m8 import CLIP, NPZ, ScriptSpark, _analysis

TOOL_CODE = (
    '"""Double each sample: demo measurement tool.\n'
    "\n"
    "Argument shapes: values holds numbers in px; returns numbers in px doubled.\n"
    '"""\n'
    "\n"
    "\n"
    "def double_each(values):\n"
    '    """Double each sample.\n'
    "\n"
    "    Argument shapes: values is a list of numbers in px.\n"
    "    Returns: a list of numbers in px.\n"
    '    """\n'
    "    return [2.0 * float(v) for v in values]\n"
)


def _probe(name: str) -> str:
    """A probe on synthetic data with a known answer and a tolerance."""
    return (
        "import " + name + "\n"
        "got = " + name + ".double_each([1.0, 2.5, -3.0])\n"
        "want = [2.0, 5.0, -6.0]\n"
        "assert len(got) == len(want), repr(got)\n"
        "for g, w in zip(got, want):\n"
        "    assert abs(g - w) <= 1e-9, repr((g, w))\n"
        'print("PASS")\n'
    )


def _local_tools_python(
    code: str, workspace: str | Path, extra_imports: tuple[str, ...] = ()
) -> sandbox_mod.SandboxResult:
    """Test runner: M5 review plus plain execution, tools preloaded.

    Mirrors the production bootstrap: registered tools are preloaded
    from explicit file paths into sys.modules (no directory is ever
    put on the path), so only registered tools are importable. Review
    sees the agent code only.
    """
    ws = Path(workspace).resolve()
    scripts = ws / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    problems = sandbox_mod.review(code, extra_imports=extra_imports)
    script = sandbox_mod._next_script_path(scripts)
    if problems:
        script.write_text(code, encoding="utf-8")
        return sandbox_mod.SandboxResult(ok=False, refused=True, problems=problems, script=script)
    reg = ws / "tools" / "registered"
    preamble = ""
    if reg.is_dir():
        mods = sorted(reg.glob("*.py"))
        if mods:
            lines = ["import importlib.util as _ilu", "import sys as _sys"]
            for mod in mods:
                lines.append(
                    "_spec = _ilu.spec_from_file_location("
                    + json.dumps(mod.stem) + ", " + json.dumps(str(mod)) + ")"
                )
                lines.append("_m = _ilu.module_from_spec(_spec)")
                lines.append("_sys.modules[" + json.dumps(mod.stem) + "] = _m")
                lines.append("_spec.loader.exec_module(_m)")
            preamble = "\n".join(lines) + "\n"
    script.write_text(preamble + code, encoding="utf-8")
    import time

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


def _tool_writer(analysis: dict, name: str = "draft.json") -> str:
    """Sandbox code that uses the tool, then writes one analysis file."""
    return (
        "import json\n"
        "import mytool\n"
        "assert mytool.double_each([1.0]) == [2.0]\n"
        "analysis = json.loads(" + json.dumps(json.dumps(analysis)) + ")\n"
        "with open(" + json.dumps(name) + ", 'w') as handle:\n"
        "    json.dump(analysis, handle)\n"
        "print('wrote " + name + "')\n"
    )


def _mask_args() -> dict:
    """Mask-check arguments matching the fixture reference mask."""
    return {
        "file": NPZ,
        "object": 0,
        "frames": [0, 5, 9],
        "claim": "the mask covers only the red square",
    }


def test_names_purpose_and_signatures() -> None:
    """Unit checks: names, purpose line, public function signatures."""
    assert is_valid_name("gait_signal")
    assert is_valid_name("tool2_v3")
    assert not is_valid_name("Bad-Name")
    assert not is_valid_name("123abc")
    assert not is_valid_name("")
    assert not is_valid_name("blocks")
    assert not is_valid_name(None)
    assert module_purpose(TOOL_CODE) == "Double each sample: demo measurement tool."
    assert module_purpose("x = 1\n") == ""
    assert module_functions(TOOL_CODE) == ["double_each(values)"]
    assert module_functions("def _hidden(a):\n    return a\n") == []


def test_runner_source_preloads_registered_without_path() -> None:
    """The production bootstrap preloads registered tools, no path edit."""
    source = sandbox_mod._runner_source(
        sandbox_mod._repo_root(), Path("/tmp/ws/scripts/001.py"), []
    )
    assert "tools" in source and "registered" in source
    assert "_sys.path.insert" not in source
    assert "spec_from_file_location" in source


def test_passing_probe_registers_and_imports(tmp_path: Path) -> None:
    """Probe 1: a passing probe registers the tool; python can import it."""
    analysis = _analysis(CLIP, NPZ)
    script = [
        ("call", "make_tool", {"name": "mytool", "code": TOOL_CODE, "probe": _probe("mytool")}),
        ("call", "sam", {"phrase": "red square", "start": 0, "stop": 10}),
        ("call", "mask_check", _mask_args()),
        ("call", "python", {"code": _tool_writer(analysis)}),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
    ]
    spark = ScriptSpark(script)
    run_dir = tmp_path / "run"
    summary = run_analysis(
        CLIP, run_dir, spark=spark, python_runner=_local_tools_python,
        cache_dir=tmp_path / "samcache",
    )
    assert summary.status == "ok"
    assert summary.tools_made == 1
    registry = json.loads((run_dir / "workspace" / "tools" / "registry.json").read_text(encoding="utf-8"))
    assert len(registry) == 1
    entry = registry[0]
    assert entry["name"] == "mytool"
    assert entry["purpose"] == "Double each sample: demo measurement tool."
    assert entry["functions"] == ["double_each(values)"]
    assert "import mytool" in entry["probe_source"]
    assert "PASS" in entry["probe_output"]
    assert entry["turn"] == 1
    assert entry["attempt"] == 1
    saved = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    assert validate(saved) == []
    assert saved["tools"][0]["name"] == "mytool"
    assert saved["tools"][0]["purpose"] == "Double each sample: demo measurement tool."
    assert saved["tools"][0]["functions"] == ["double_each(values)"]
    assert saved["tools"][0]["verified"] is True
    assert saved["tools"][0]["probe_summary"]
    turns = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in (run_dir / "turns").glob("*.json")}
    assert "registered" in turns["turn01.json"]["result_text"]
    assert "exit 0" in turns["turn04.json"]["result_text"]
    assert turns["turn04.json"]["counters"]["tools"] == 1
    versions = sorted((run_dir / "workspace" / "tools" / "versions").glob("mytool*"))
    assert len(versions) == 2


def test_failing_probe_rejected_and_not_importable(tmp_path: Path) -> None:
    """Probe 2: a wrong answer is rejected with its output; no import."""
    bad_probe = (
        "import mytool\n"
        "got = mytool.double_each([1.0])\n"
        "assert got == [3.0], repr(got)\n"
        'print("PASS")\n'
    )
    script = [
        ("call", "make_tool", {"name": "mytool", "code": TOOL_CODE, "probe": bad_probe}),
        ("call", "python", {"code": "import mytool\nprint(mytool.double_each([1.0]))\n"}),
    ]
    spark = ScriptSpark(script)
    run_dir = tmp_path / "run"
    run_analysis(
        CLIP, run_dir, spark=spark, python_runner=_local_tools_python,
        max_turns=2, cache_dir=tmp_path / "samcache",
    )
    turns = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in (run_dir / "turns").glob("*.json")}
    assert "failed" in turns["turn01.json"]["result_text"]
    assert "stays unregistered" in turns["turn01.json"]["result_text"]
    assert "AssertionError" in turns["turn01.json"]["result_text"]
    assert "refused" in turns["turn02.json"]["result_text"]
    assert "import-allowlist" in turns["turn02.json"]["result_text"]
    assert not (run_dir / "workspace" / "tools" / "registry.json").exists()
    assert not (run_dir / "workspace" / "tools" / "registered" / "mytool.py").exists()


def test_banned_import_refused_without_running(tmp_path: Path) -> None:
    """Probe 3: a tool importing a banned module is refused; probe never runs."""
    probe = (
        "from pathlib import Path\n"
        "Path('tools/ran_marker.txt').write_text('ran')\n"
        "import mytool\n"
        'print("PASS")\n'
    )
    script = [
        ("call", "make_tool", {"name": "mytool", "code": "import socket\n", "probe": probe}),
    ]
    spark = ScriptSpark(script)
    run_dir = tmp_path / "run"
    run_analysis(
        CLIP, run_dir, spark=spark, python_runner=_local_tools_python,
        max_turns=1, cache_dir=tmp_path / "samcache",
    )
    turns = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((run_dir / "turns").glob("*.json"))]
    assert "refused" in turns[0]["result_text"]
    assert "import-allowlist" in turns[0]["result_text"]
    assert "nothing was run" in turns[0]["result_text"]
    assert not (run_dir / "workspace" / "tools" / "ran_marker.txt").exists()
    assert not (run_dir / "workspace" / "tools" / "registered" / "mytool.py").exists()
    attempts = json.loads((run_dir / "workspace" / "tools" / "attempts.json").read_text(encoding="utf-8"))
    assert attempts == {"mytool": 1}


def test_tool_limit_and_attempt_limit_hold(tmp_path: Path) -> None:
    """Probe 4: the per-run tool limit and the per-name attempt limit hold."""
    maker = lambda name: ("call", "make_tool", {"name": name, "code": TOOL_CODE, "probe": _probe(name)})
    run_dir = tmp_path / "run"
    spark = ScriptSpark([maker("tool_a"), maker("tool_b"), maker("tool_c")])
    run_analysis(
        CLIP, run_dir, spark=spark, python_runner=_local_tools_python,
        max_turns=3, max_tools=2, cache_dir=tmp_path / "samcache",
    )
    turns = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((run_dir / "turns").glob("*.json"))]
    assert "registered" in turns[0]["result_text"]
    assert "registered" in turns[1]["result_text"]
    assert "already registered 2 of 2" in turns[2]["result_text"]

    bad = (
        "import mytool\n"
        "assert mytool.double_each([1.0]) == [9.0]\n"
        'print("PASS")\n'
    )
    run_dir2 = tmp_path / "run2"
    spark2 = ScriptSpark(
        [
            ("call", "make_tool", {"name": "mytool", "code": TOOL_CODE, "probe": bad}),
            ("call", "make_tool", {"name": "mytool", "code": TOOL_CODE, "probe": bad}),
            (
                "call", "make_tool",
                {"name": "mytool", "code": TOOL_CODE, "probe": _probe("mytool")},
            ),
        ]
    )
    run_analysis(
        CLIP, run_dir2, spark=spark2, python_runner=_local_tools_python,
        max_turns=3, tool_attempts=2, cache_dir=tmp_path / "samcache",
    )
    turns2 = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((run_dir2 / "turns").glob("*.json"))]
    assert "failed" in turns2[0]["result_text"]
    assert "attempt 1 of 2" in turns2[0]["result_text"]
    assert "attempt 2 of 2" in turns2[1]["result_text"]
    assert "already used 2 of 2" in turns2[2]["result_text"]


def test_reregister_replaces_and_keeps_versions(tmp_path: Path) -> None:
    """Re-registering the same name replaces it but keeps every version."""
    v2 = TOOL_CODE.replace("[2.0 * float(v) for v in values]", "[2.0 * float(v) + 1.0 for v in values]")
    probe_v2 = (
        "import mytool\n"
        "got = mytool.double_each([1.0])\n"
        "assert got == [3.0], repr(got)\n"
        'print("PASS")\n'
    )
    script = [
        ("call", "make_tool", {"name": "mytool", "code": TOOL_CODE, "probe": _probe("mytool")}),
        ("call", "make_tool", {"name": "mytool", "code": v2, "probe": probe_v2}),
        ("call", "python", {"code": "import mytool\nprint(mytool.double_each([1.0]))\n"}),
    ]
    spark = ScriptSpark(script)
    run_dir = tmp_path / "run"
    run_analysis(
        CLIP, run_dir, spark=spark, python_runner=_local_tools_python,
        max_turns=3, cache_dir=tmp_path / "samcache",
    )
    turns = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in (run_dir / "turns").glob("*.json")}
    assert "[3.0]" in turns["turn03.json"]["result_text"]
    versions = sorted((run_dir / "workspace" / "tools" / "versions").glob("mytool*"))
    assert len(versions) == 4
    registry = json.loads((run_dir / "workspace" / "tools" / "registry.json").read_text(encoding="utf-8"))
    assert len(registry) == 1 and registry[0]["attempt"] == 2


def test_tool_can_import_another_registered_tool(tmp_path: Path) -> None:
    """A tool may build on a registered tool; both become importable."""
    second_code = (
        '"""Add one then double: demo composition.\n'
        "\n"
        "Argument shapes: values holds numbers in px; returns numbers in px.\n"
        '"""\n'
        "import aaa_add\n"
        "\n"
        "\n"
        "def add_and_double(values):\n"
        '    """Add one then double each sample.\n'
        "\n"
        "    Argument shapes: values is a list of numbers in px.\n"
        "    Returns: a list of numbers in px.\n"
        '    """\n'
        "    return aaa_add.double_each([v + 1.0 for v in values])\n"
    )
    second_probe = (
        "import zzz_use\n"
        "got = zzz_use.add_and_double([1.0])\n"
        "assert got == [4.0], repr(got)\n"
        'print("PASS")\n'
    )
    script = [
        ("call", "make_tool", {"name": "aaa_add", "code": TOOL_CODE, "probe": _probe("aaa_add")}),
        ("call", "make_tool", {"name": "zzz_use", "code": second_code, "probe": second_probe}),
        ("call", "python", {"code": "import zzz_use\nprint(zzz_use.add_and_double([1.0]))\n"}),
    ]
    spark = ScriptSpark(script)
    run_dir = tmp_path / "run"
    summary = run_analysis(
        CLIP, run_dir, spark=spark, python_runner=_local_tools_python,
        max_turns=3, cache_dir=tmp_path / "samcache",
    )
    assert summary.tools_made == 2
    turns = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in (run_dir / "turns").glob("*.json")}
    assert "registered" in turns["turn02.json"]["result_text"]
    assert "[4.0]" in turns["turn03.json"]["result_text"]


def test_tools_section_rejects_malformed_entries() -> None:
    """The validator names bad tools entries by path."""
    good = _analysis(CLIP, NPZ)
    broken = dict(good)
    broken["tools"] = [{"name": "mytool"}]
    paths = [issue.path for issue in validate(broken)]
    assert "/tools/0/purpose" in paths
    assert "/tools/0/functions" in paths
    assert "/tools/0/verified" in paths
    broken["tools"] = "mytool"
    assert any(issue.path == "/tools" for issue in validate(broken))


def test_finish_tools_section_and_empty_run(tmp_path: Path) -> None:
    """Probe 5: finish fills analysis.tools; a run without tools has none."""
    analysis = _analysis(CLIP, NPZ)
    analysis["tools"] = [{"name": "fake", "purpose": "x", "functions": [], "probe_summary": "y", "verified": True}]
    script = [
        ("call", "make_tool", {"name": "mytool", "code": TOOL_CODE, "probe": _probe("mytool")}),
        ("call", "sam", {"phrase": "red square", "start": 0, "stop": 10}),
        ("call", "mask_check", _mask_args()),
        ("call", "python", {"code": _tool_writer(analysis)}),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
    ]
    run_dir = tmp_path / "run"
    summary = run_analysis(
        CLIP, run_dir, spark=ScriptSpark(script), python_runner=_local_tools_python,
        cache_dir=tmp_path / "samcache",
    )
    assert summary.status == "ok"
    saved = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    assert validate(saved) == []
    assert [entry["name"] for entry in saved["tools"]] == ["mytool"]
    assert all(entry["verified"] is True for entry in saved["tools"])

    plain = _analysis(CLIP, NPZ)
    script2 = [
        ("call", "sam", {"phrase": "red square", "start": 0, "stop": 10}),
        ("call", "mask_check", _mask_args()),
        (
            "call", "python",
            {"code": "import json\nanalysis = json.loads(" + json.dumps(json.dumps(plain)) + ")\nwith open('draft.json', 'w') as handle:\n    json.dump(analysis, handle)\nprint('wrote draft.json')\n"},
        ),
        ("call", "finish", {"analysis_file": "draft.json", "page_texts": ""}),
    ]
    run_dir2 = tmp_path / "run2"
    summary2 = run_analysis(
        CLIP, run_dir2, spark=ScriptSpark(script2), python_runner=_local_tools_python,
        cache_dir=tmp_path / "samcache",
    )
    assert summary2.status == "ok"
    saved2 = json.loads((run_dir2 / "analysis.json").read_text(encoding="utf-8"))
    assert validate(saved2) == []
    assert "tools" not in saved2


def test_promote_creates_files_and_test_passes(tmp_path: Path) -> None:
    """Probe 6: promote copies the module and the probe test passes."""
    run_dir = tmp_path / "tag-run"
    tools = run_dir / "workspace" / "tools"
    tools.mkdir(parents=True)
    (tools / "mytool.py").write_text(TOOL_CODE, encoding="utf-8")
    (tools / "registry.json").write_text(
        json.dumps(
            [
                {
                    "name": "mytool",
                    "purpose": "Double each sample: demo measurement tool.",
                    "functions": ["double_each(values)"],
                    "probe_source": _probe("mytool"),
                    "probe_output": "PASS",
                    "turn": 1,
                    "attempt": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    repo = tmp_path / "repo"
    (repo / "physics_proof" / "contrib").mkdir(parents=True)
    (repo / "tests" / "contrib").mkdir(parents=True)
    contrib_path, test_path = promote_tool(run_dir, "mytool", repo_root=repo)
    assert contrib_path == repo / "physics_proof" / "contrib" / "mytool.py"
    assert test_path == repo / "tests" / "contrib" / "test_mytool.py"
    assert ("run " + run_dir.name) in contrib_path.read_text(encoding="utf-8")
    assert "Double each sample" in test_path.read_text(encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_path), "-q"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    with pytest.raises(ValueError, match="not registered"):
        promote_tool(run_dir, "nosuchtool", repo_root=repo)

# generated from brief/07 · part 07 owns this file
"""``run_python`` live sandbox probes (run for real, never weakened).

Positive controls first (``ALIVE``, library versions, helpers
import), then the denials. Each test needs the ``sandbox_live``
canary; without a working ``sandbox-exec`` it skips, never passes.
"""

from __future__ import annotations

import json
import os
import time

from src.tools import run_python

POSITIVE = (
    "print('ALIVE')\n"
    "import numpy, scipy, cv2\n"
    "print('numpy', numpy.__version__)\n"
    "print('scipy', scipy.__version__)\n"
    "print('cv2', cv2.__version__)\n"
    "from helpers import masks_io, tracks, physics, clock\n"
    "print('helpers', masks_io.__name__)\n"
)


def _run(make_run, code, **kwargs):
    run = make_run(frames=20)
    started = time.monotonic()
    result = run_python.run_python(str(run), 0, code=code, **kwargs)
    wall = time.monotonic() - started
    return run, result, wall


def test_positive_control_alive_and_versions(make_run, sandbox_live,
                                             ledger):
    run, result, _ = _run(make_run, POSITIVE, ledger=ledger)
    assert result["ok"], result["metrics"].get("stderr")
    assert "ALIVE" in result["metrics"]["stdout"]
    assert "numpy" in result["metrics"]["stdout"]
    assert "helpers" in result["metrics"]["stdout"]
    assert result["metrics"]["stderr"] == "", "clean runs stay quiet"
    assert result["metrics"]["sandboxed"] is True
    assert ledger.execs == 1


def test_workspace_write_and_timing_read(make_run, sandbox_live):
    code = ("import json, pathlib\n"
            "timing = json.loads(pathlib.Path("
            "'input/timing.json').read_text())\n"
            "print('frames', timing['frame_count'])\n"
            "pathlib.Path('workspace/probe.txt').write_text('ok')\n"
            "pathlib.Path('artifacts/note.txt').write_text('ok')\n")
    run, result, _ = _run(make_run, code)
    assert result["ok"], result["metrics"].get("stderr")
    assert "frames 20" in result["metrics"]["stdout"]
    assert (run / "workspace" / "probe.txt").is_file()
    created = {row["path"]
               for row in result["metrics"]["created_files"]}
    assert "workspace/probe.txt" in created
    assert "artifacts/note.txt" in created
    assert result["files"][0] == result["metrics"]["stdout_artifact"]


def test_repo_brief_tests_original_unreadable(make_run, sandbox_live):
    repo = run_python.__file__
    code = (
        "import pathlib\n"
        "here = pathlib.Path('src/tools/run_python.py')\n"
        f"repo = pathlib.Path({str(repo)!r})\n"
        "for candidate in [here, repo,\n"
        "                  pathlib.Path('brief/07-agent-tools.md'),\n"
        "                  pathlib.Path('tests/tools/conftest.py')]:\n"
        "    try:\n"
        "        data = candidate.read_bytes()\n"
        "    except OSError:\n"
        "        print('DENIED', candidate)\n"
        "    else:\n"
        "        print('READABLE', candidate, len(data))\n")
    _, result, _ = _run(make_run, code)
    assert result["ok"], result["metrics"].get("stderr")
    assert "READABLE" not in result["metrics"]["stdout"]


def test_decoys_parent_sibling_tmpdir_unreadable(make_run,
                                                 sandbox_live,
                                                 tmp_path):
    parent = tmp_path / "parent_decoy.txt"
    parent.write_text("parent-secret")
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    (sibling / "decoy.txt").write_text("sibling-secret")
    exposed = tmp_path / "tmp_decoy"
    exposed.mkdir()
    (exposed / "decoy.txt").write_text("tmp-secret")
    run = make_run(frames=10)
    code = (
        "import os, pathlib\n"
        f"targets = [{str(parent)!r}, {str(sibling / 'decoy.txt')!r},\n"
        f"           {str(exposed / 'decoy.txt')!r}]\n"
        "for target in targets:\n"
        "    try:\n"
        "        pathlib.Path(target).read_bytes()\n"
        "    except OSError:\n"
        "        print('DENIED', target)\n"
        "    else:\n"
        "        print('READABLE', target)\n"
        # No in-sandbox resolve(): the run root is unreadable, so
        # resolving the cwd itself is denied (as is listing it).
        f"for directory in [{str(run.parent)!r},\n"
        f"                    {str(sibling)!r}, {str(exposed)!r}]:\n"
        "    try:\n"
        "        os.listdir(directory)\n"
        "    except OSError:\n"
        "        print('DENIED-LIST', directory)\n"
        "    else:\n"
        "        print('READABLE-LIST', directory)\n")
    result = run_python.run_python(str(run), 0, code=code)
    assert result["ok"], result["metrics"].get("stderr")
    assert "READABLE" not in result["metrics"]["stdout"]


def test_run_root_and_logs_unreadable(make_run, sandbox_live):
    run = make_run(frames=10)
    (run / "probe.json").write_text('{"source": "operator-only"}',
                                    encoding="utf-8")
    (run / "logs" / "decoy.txt").write_text("operator-log",
                                            encoding="utf-8")
    (run / "workspace" / "ok.txt").write_text("agent-data",
                                              encoding="utf-8")
    (run / "artifacts" / "ok.txt").write_text("agent-data",
                                              encoding="utf-8")
    # The run root is addressed by its literal path: resolving the
    # cwd itself is denied (the root is unreadable, as is listing
    # it), while relative opens under the three subtrees work.
    code = (
        "import os, pathlib\n"
        f"here = pathlib.Path({str(run)!r})\n"
        "for target in [here / 'probe.json',\n"
        "               here / 'logs' / 'decoy.txt']:\n"
        "    try:\n"
        "        target.read_bytes()\n"
        "    except OSError:\n"
        "        print('DENIED', target.name)\n"
        "    else:\n"
        "        print('READABLE', target)\n"
        "try:\n"
        "    os.listdir(here)\n"
        "except OSError:\n"
        "    print('DENIED-LIST run-root')\n"
        "else:\n"
        "    print('READABLE-LIST run-root')\n"
        "for target in ['input/timing.json',\n"
        "               'workspace/ok.txt', 'artifacts/ok.txt']:\n"
        "    try:\n"
        "        pathlib.Path(target).read_bytes()\n"
        "    except OSError:\n"
        "        print('DENIED-KEPT', target)\n"
        "    else:\n"
        "        print('READABLE-KEPT', target)\n")
    result = run_python.run_python(str(run), 0, code=code)
    assert result["ok"], result["metrics"].get("stderr")
    stdout = result["metrics"]["stdout"]
    assert "READABLE " not in stdout
    assert "READABLE-LIST" not in stdout
    assert "DENIED-KEPT" not in stdout
    assert stdout.count("READABLE-KEPT") == 3


def test_home_and_config_unlistable(make_run, sandbox_live):
    code = ("import os\n"
            "import pathlib\n"
            "for directory in [str(pathlib.Path.home()),\n"
            "                  str(pathlib.Path.home() / '.config')]:\n"
            "    try:\n"
            "        os.listdir(directory)\n"
            "    except OSError:\n"
            "        print('DENIED-LIST', directory)\n"
            "    else:\n"
            "        print('READABLE-LIST', directory)\n")
    _, result, _ = _run(make_run, code)
    assert result["ok"], result["metrics"].get("stderr")
    assert "READABLE-LIST" not in result["metrics"]["stdout"]


def test_no_network_and_no_escape_writes(make_run, sandbox_live):
    code = ("import socket, pathlib\n"
            "try:\n"
            "    socket.create_connection(('127.0.0.1', 9), timeout=2)\n"
            "except OSError as exc:\n"
            "    print('NET-DENIED', type(exc).__name__)\n"
            "else:\n"
            "    print('NET-OPEN')\n"
            "for target in ['/tmp/escape.txt',\n"
            "               str(pathlib.Path.home() / 'escape.txt')]:\n"
            "    try:\n"
            "        pathlib.Path(target).write_text('x')\n"
            "    except OSError:\n"
            "        print('DENIED-WRITE', target)\n"
            "    else:\n"
            "        print('ESCAPE-WROTE', target)\n")
    _, result, _ = _run(make_run, code)
    assert result["ok"], result["metrics"].get("stderr")
    assert "NET-OPEN" not in result["metrics"]["stdout"]
    assert "ESCAPE-WROTE" not in result["metrics"]["stdout"]


def test_secrets_scrubbed_from_env(make_run, sandbox_live,
                                   monkeypatch):
    monkeypatch.setenv("META_API_KEY", "sk-test-secret")
    monkeypatch.setenv("MY_TOKEN", "tok-test-secret")
    code = ("import os\n"
            "print('META' if 'sk-test-secret' in repr(os.environ)\n"
            "      else 'NO-META')\n"
            "print('TOK' if 'tok-test-secret' in repr(os.environ)\n"
            "      else 'NO-TOK')\n"
            "print('HOME=' + os.environ.get('HOME', ''))\n")
    run, result, _ = _run(make_run, code)
    assert result["ok"], result["metrics"].get("stderr")
    assert "NO-META" in result["metrics"]["stdout"]
    assert "NO-TOK" in result["metrics"]["stdout"]
    assert os.path.expanduser("~") not in result["metrics"]["stdout"]


def test_elapsed_is_measured_not_timeout(make_run, sandbox_live):
    _, result, wall = _run(make_run, "import time\ntime.sleep(1)\n")
    assert result["ok"], result["metrics"].get("stderr")
    elapsed = result["metrics"]["elapsed_s"]
    assert 0.8 <= elapsed <= 10, elapsed
    assert abs(wall - elapsed) < 5


def test_truncation_names_stdout_file(make_run, sandbox_live):
    code = "print('x' * 20000)\n"
    _, result, _ = _run(make_run, code)
    assert result["ok"], result
    assert result["metrics"]["stdout_truncated"] is True
    assert result["files"][0] == result["metrics"]["stdout_artifact"]
    assert result["files"][0].endswith(".stdout.txt")


def test_timeout_and_memory_clamped(make_run, sandbox_live):
    from src import config

    _, result, _ = _run(make_run, "print('fast')\n", timeout_s=10**9,
                        memory_mb=10**9)
    assert result["ok"], result["metrics"].get("stderr")
    assert result["metrics"]["timeout_s"] == float(
        config.SANDBOX_EXEC_TIMEOUT_S)
    assert result["metrics"]["memory_mb"] == float(
        config.SANDBOX_MEMORY_MB)
    for bad in (0, -5, "soon"):
        run = make_run(frames=10)
        denied = run_python.run_python(str(run), 0, code="print(1)\n",
                                       timeout_s=bad)
        assert not denied["ok"]
        assert denied["error"]["code"] == "bad_arguments"


def test_tracebacks_are_run_relative(make_run, sandbox_live):
    code = "raise ValueError('boom')\n"
    _, result, _ = _run(make_run, code)
    assert not result["ok"]
    assert result["error"]["code"] == "exec_failed"
    assert "boom" in result["summary"]
    assert "Users/" not in result["summary"]

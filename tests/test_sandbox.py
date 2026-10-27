"""M5 probes: static review and Seatbelt sandbox (all offline)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from physics_proof.sandbox import Problem, SandboxResult, review, run_python


def _can_sandbox() -> bool:
    """True when this shell can apply a Seatbelt profile (macOS, unblocked)."""
    if sys.platform != "darwin" or shutil.which("sandbox-exec") is None:
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".sb", delete=False) as handle:
        handle.write("(version 1)\n(allow default)\n")
        profile = handle.name
    try:
        proc = subprocess.run(
            ["sandbox-exec", "-f", profile, "/usr/bin/true"],
            capture_output=True,
            timeout=30,
        )
    except OSError:
        return False
    finally:
        os.unlink(profile)
    return proc.returncode == 0


CAN_SANDBOX = _can_sandbox()

needs_sandbox = pytest.mark.skipif(
    not CAN_SANDBOX,
    reason="sandbox-exec cannot apply profiles in this shell; run on macOS",
)

RUN_SLOW = os.environ.get("PHYSICS_PROOF_RUN_SLOW") == "1"

needs_slow = pytest.mark.skipif(
    not RUN_SLOW, reason="minute-long; set PHYSICS_PROOF_RUN_SLOW=1 to run it"
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


# Probe 1: the review layer refuses dangerous code on its own.
@pytest.mark.parametrize(
    "code",
    [
        "import socket",
        "import urllib.request\nurllib.request.urlopen('http://x')",
        "open('/etc/passwd')",
        "open('../x')",
        "x = '~/x'",
        'import subprocess\nsubprocess.run(["sh", "-c", "ls"])',
        'import subprocess\nsubprocess.run("ffmpeg ...", shell=True)',
        'eval("1")',
        'exec("x = 1")',
        'compile("1", "s", "eval")',
        '__import__("os")',
        "import os\nos.system('ls')",
        "import os\nos.popen('ls')",
        "import os\nos.execv('/bin/sh', ['sh'])",
        "import os\nos.spawnl(1, 'x')",
        "import ctypes",
        "import requests",
        "import http.client",
        "import importlib",
        "x = getattr(mod, name)",
        "import subprocess as sp\nsp.run(['sh', '-c', 'ls'])",
        "from subprocess import run\nrun(['sh', '-c', 'ls'])",
        b"open(b'/etc/passwd')",
    ],
)
def test_review_refuses(code) -> None:
    if isinstance(code, bytes):
        code = code.decode("ascii")
    problems = review(code)
    assert problems, code
    for problem in problems:
        assert isinstance(problem, Problem)
        assert problem.line >= 1
        assert problem.rule
        assert problem.message


def test_review_reports_lines() -> None:
    problems = review("import numpy\nimport socket\n")
    assert len(problems) == 1
    assert problems[0].line == 2
    assert problems[0].rule == "import-allowlist"


# Probe 1: the review layer allows the documented good cases.
@pytest.mark.parametrize(
    "code",
    [
        'x = "https://example.com/a.png"',
        'import subprocess\nsubprocess.run(["ffprobe", "-v", "error", "clip.mp4"])',
        'import subprocess\nsubprocess.run(["ffmpeg", "-y", "in.mp4", "out.mp4"])',
        "import numpy as np\nimport scipy\nimport matplotlib.pyplot as plt\na = np.arange(3)",
        "import blocks\nimport math\nimport json\nimport pathlib",
        'import subprocess\nsubprocess.run(["ffprobe", "clip.mp4"], shell=False)',
        "import matplotlib\nmatplotlib.use('Agg')",
    ],
)
def test_review_allows(code: str) -> None:
    assert review(code) == []


def test_review_getattr_literal_ok() -> None:
    assert review('getattr(blocks, "fit_parabola")') == []


# Probe 2 is split per behavior below; each runs with the review off so
# only the sandbox layer is exercised.
@needs_sandbox
def test_sandbox_blocks_socket(workspace: Path) -> None:
    code = (
        "import socket\n"
        "try:\n"
        '    socket.create_connection(("1.1.1.1", 443), timeout=5)\n'
        '    print("SOCKET-OPEN")\n'
        "except Exception as exc:\n"
        '    print("SOCKET-DENIED " + type(exc).__name__)\n'
    )
    result = run_python(code, workspace, _skip_review=True)
    assert isinstance(result, SandboxResult)
    assert "SOCKET-DENIED" in result.stdout
    assert "SOCKET-OPEN" not in result.stdout


@needs_sandbox
def test_sandbox_home_write_denied(workspace: Path) -> None:
    import pwd

    home = pwd.getpwuid(os.getuid()).pw_dir
    target = Path(home) / "sandbox_probe_physics_proof.txt"
    if target.exists():
        target.unlink()
    code = (
        "import os\n"
        "import pwd\n"
        "home = pwd.getpwuid(os.getuid()).pw_dir\n"
        'target = os.path.join(home, "sandbox_probe_physics_proof.txt")\n'
        "try:\n"
        '    open(target, "w").write("x")\n'
        '    print("WRITE-OK")\n'
        "except Exception as exc:\n"
        '    print("WRITE-DENIED " + type(exc).__name__)\n'
    )
    try:
        result = run_python(code, workspace, _skip_review=True)
        assert "WRITE-DENIED" in result.stdout
        assert "WRITE-OK" not in result.stdout
        assert not target.exists()
    finally:
        if target.exists():
            target.unlink()


@needs_sandbox
def test_sandbox_home_read_denied(workspace: Path, tmp_path: Path) -> None:
    home = Path.home()
    secret = home / ("sandbox_secret_" + str(os.getpid()) + ".txt")
    secret.write_text("SECRET-outside-workspace", encoding="utf-8")
    code = (
        "try:\n"
        "    data = open(" + repr(str(secret)) + ").read()\n"
        '    print("READ-OK " + data)\n'
        "except Exception as exc:\n"
        '    print("READ-DENIED " + type(exc).__name__)\n'
    )
    try:
        result = run_python(code, workspace, _skip_review=True)
        assert "READ-DENIED" in result.stdout
        assert "SECRET-outside-workspace" not in result.stdout
    finally:
        secret.unlink(missing_ok=True)


@needs_sandbox
def test_sandbox_blocks_shell(workspace: Path) -> None:
    code = (
        "import subprocess\n"
        "try:\n"
        '    subprocess.run(["/bin/sh", "-c", "echo hi"], capture_output=True, timeout=10)\n'
        '    print("SHELL-OK")\n'
        "except Exception as exc:\n"
        '    print("SHELL-DENIED " + type(exc).__name__)\n'
    )
    result = run_python(code, workspace, _skip_review=True)
    assert "SHELL-DENIED" in result.stdout
    assert "SHELL-OK" not in result.stdout


@needs_sandbox
def test_sandbox_env_scrubbed(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("META_API_KEY", "fake-parent-key")
    monkeypatch.setenv("PARENT_ONLY", "yes")
    code = (
        "import os\n"
        'print("KEY-ABSENT" if "META_API_KEY" not in os.environ else "KEY-PRESENT")\n'
        'print("HOME=" + os.environ.get("HOME", ""))\n'
        'print("PARENT=" + os.environ.get("PARENT_ONLY", "missing"))\n'
    )
    result = run_python(code, workspace, _skip_review=True)
    assert "KEY-ABSENT" in result.stdout
    assert "KEY-PRESENT" not in result.stdout
    assert "HOME=" + str(workspace.resolve()) in result.stdout
    assert "PARENT=missing" in result.stdout


# Probe 3: the timeout kills the whole process group (fast variant).
@needs_sandbox
def test_sandbox_timeout_fast(workspace: Path) -> None:
    result = run_python("import time\ntime.sleep(5)\n", workspace, timeout_s=2, _skip_review=True)
    assert not result.ok
    assert result.exit_code != 0
    assert result.seconds < 10
    assert result.seconds >= 1.5


# Probe 3: the real 60/61 s values, opt-in via PHYSICS_PROOF_RUN_SLOW=1.
@needs_sandbox
@pytest.mark.slow
@needs_slow
def test_sandbox_timeout_slow(workspace: Path) -> None:
    result = run_python("import time\ntime.sleep(61)\n", workspace, timeout_s=60, _skip_review=True)
    assert not result.ok
    assert result.seconds < 65


# Probe 4: one plot comes back; three images return the two newest.
@needs_sandbox
def test_sandbox_returns_plot(workspace: Path) -> None:
    code = (
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
        "plt.plot([0, 1], [0, 1])\n"
        'plt.savefig("plot.png")\n'
        'print("PLOT-OK")\n'
    )
    result = run_python(code, workspace, _skip_review=True)
    assert result.ok, result.stderr
    assert "PLOT-OK" in result.stdout
    assert [p.name for p in result.images] == ["plot.png"]
    assert result.script is not None and result.script.exists()


@needs_sandbox
def test_sandbox_returns_two_newest_images(workspace: Path) -> None:
    code = (
        "from PIL import Image\n"
        "import time\n"
        'for name in ["a.png", "b.png", "c.png"]:\n'
        '    Image.new("RGB", (8, 8)).save(name)\n'
        "    time.sleep(0.05)\n"
        'print("IMAGES-OK")\n'
    )
    result = run_python(code, workspace, _skip_review=True)
    assert result.ok, result.stderr
    assert [p.name for p in result.images] == ["c.png", "b.png"]


# Probe 5: import blocks works and fit_parabola runs on a small array.
@needs_sandbox
def test_sandbox_import_blocks(workspace: Path) -> None:
    code = (
        "import blocks\n"
        "out = blocks.fit_parabola([0, 1, 2, 3, 4], [0.0, 1.0, 4.0, 9.0, 16.0], 1.0)\n"
        'print("G-OK " + str(out["g_px"]))\n'
    )
    result = run_python(code, workspace, _skip_review=True)
    assert result.ok, result.stderr
    assert "G-OK 2.0" in result.stdout


# Probe 6: ffprobe on a clip inside the workspace works.
@needs_sandbox
def test_sandbox_ffprobe(workspace: Path) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "sam_clip.mp4"
    shutil.copy(fixture, workspace / "clip.mp4")
    code = (
        "import subprocess\n"
        "out = subprocess.run("
        '["ffprobe", "-v", "error", "-show_entries", "format=duration", '
        '"-of", "csv=p=0", "clip.mp4"], capture_output=True, text=True, timeout=30)\n'
        "assert out.returncode == 0, out.stderr\n"
        'print("FFPROBE-OK " + out.stdout.strip())\n'
    )
    result = run_python(code, workspace, _skip_review=True)
    assert result.ok, result.stderr
    assert "FFPROBE-OK 1" in result.stdout


# Refused code is not run; the script file still records what was refused.
def test_run_python_refused(workspace: Path) -> None:
    result = run_python("import socket\n", workspace)
    assert not result.ok
    assert result.refused
    assert result.problems
    assert result.exit_code is None
    assert result.script is not None and result.script.exists()


# Long output is truncated to 8 000 characters with a note.
@needs_sandbox
def test_sandbox_truncates_output(workspace: Path) -> None:
    result = run_python('print("y" * 9000)\n', workspace, _skip_review=True)
    assert result.ok, result.stderr
    assert len(result.stdout) <= 8100
    assert "truncated" in result.stdout


# Offline: every deny rule with more than one filter wraps them in
# require-all (Seatbelt ORs filters inside one rule; see M5-fix2).
def _split_forms(text: str) -> list[str]:
    """Split top-level balanced s-expressions, ignoring parens in strings."""
    forms: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "(":
            if depth == 0:
                start = index
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and start >= 0:
                forms.append(text[start : index + 1])
                start = -1
    return forms


def test_profile_multi_filter_denies_use_require_all() -> None:
    from physics_proof.sandbox import _sandbox_profile

    home = Path.home()
    if str(home) in ("", "/"):
        pytest.skip("no home-directory deny rule without a home path")
    # A workspace under home forces file-read carve-outs, so every deny
    # rule carries more than one filter here.
    workspace = home / ("ws_profile_probe_" + str(os.getpid()))
    profile = _sandbox_profile(
        workspace,
        Path(__file__).resolve().parent.parent,
        sys.executable,
        ["ffmpeg", "/usr/bin/ffmpeg"],
    )
    assert "(require-all" in profile
    wrapped = 0
    for block in _split_forms(profile):
        if not block.startswith("(deny "):
            continue
        rest = block[len("(deny "):-1].strip()
        _, _, filters_text = rest.partition(" ")
        filters = _split_forms(filters_text.strip())
        assert len(filters) <= 1, "deny rule with OR-ed filters: " + block
        if filters and filters[0].startswith("(require-all"):
            inner = _split_forms(filters[0][len("(require-all"):-1])
            assert len(inner) > 1, block
            wrapped += 1
    # file-write and process-exec always carry several filters.
    assert wrapped >= 2


# Offline: the last matching rule wins (shown on the Mac), so every deny
# must come after `(allow default)` in the generated profile.
def test_profile_denies_come_last() -> None:
    from physics_proof.sandbox import _sandbox_profile

    profile = _sandbox_profile(
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        sys.executable,
        ["ffmpeg"],
    )
    forms = _split_forms(profile)
    assert "(allow default)" in forms
    allow_at = forms.index("(allow default)")
    denies = [form for form in forms if form.startswith("(deny ")]
    assert denies, "profile has no deny rules"
    for block in denies:
        assert forms.index(block) > allow_at, "deny before (allow default): " + block


# Offline: on a framework-Python layout the launcher shim's app binary is
# carved out of the process-exec deny (otherwise the shim dies with
# "posix_spawn: ... Undefined error: 0"; seen on the Mac).
def test_profile_carves_out_shim_target(tmp_path: Path) -> None:
    from physics_proof.sandbox import _sandbox_profile, _shim_targets

    tmp_path = tmp_path.resolve()
    app_bin = (
        tmp_path
        / "Frameworks/Python.framework/Versions/3.13/bin/python3.13"
    )
    app_bin.parent.mkdir(parents=True)
    app_bin.touch()
    target = (
        tmp_path
        / "Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python"
    )
    target.parent.mkdir(parents=True)
    target.touch()
    found = _shim_targets(
        app_bin, tmp_path / "Frameworks/Python.framework/Versions/3.13"
    )
    assert str(target) in found
    profile = _sandbox_profile(tmp_path / "ws", tmp_path, str(app_bin), [])
    assert str(target) in profile
    # A plain layout with no app bundle needs no extra carve-out.
    lone = tmp_path / "bin/python3"
    lone.parent.mkdir(parents=True, exist_ok=True)
    lone.touch()
    assert _shim_targets(lone, tmp_path / "other") == []


# Seatbelt finding (shown on the Mac): when several rules match, the last
# matching rule wins — deny-then-allow permits the read, allow-then-deny
# refuses it. The generated profile therefore puts every deny after
# `(allow default)` (see test_profile_denies_come_last below).
@needs_sandbox
def test_seatbelt_last_matching_rule_wins(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("x", encoding="utf-8")
    deny_last = '(version 1)\n(allow default)\n(allow file-read* (subpath "' + str(tmp_path) + '"))\n(deny file-read* (subpath "' + str(tmp_path) + '"))\n'
    allow_last = '(version 1)\n(allow default)\n(deny file-read* (subpath "' + str(tmp_path) + '"))\n(allow file-read* (subpath "' + str(tmp_path) + '"))\n'
    profile = tmp_path / "deny_last.sb"
    profile.write_text(deny_last, encoding="utf-8")
    proc = subprocess.run(
        ["sandbox-exec", "-f", str(profile), "/bin/cat", str(secret)],
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode != 0, deny_last
    assert proc.stdout == b""
    profile = tmp_path / "allow_last.sb"
    profile.write_text(allow_last, encoding="utf-8")
    proc = subprocess.run(
        ["sandbox-exec", "-f", str(profile), "/bin/cat", str(secret)],
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, allow_last
    assert proc.stdout == b"x"

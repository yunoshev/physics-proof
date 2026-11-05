# generated from brief/15 · part 15 owns this file
"""A generation writes only its own paths (brief part 15 §16).

Offline: the coding-agent call and every suite run are stubbed. No
model calls, no network, nothing costs money. `collect_test_functions`
still shells to real `pytest --collect-only` on tiny fixture repos.
"""

from __future__ import annotations

PASS_TEST = "def test_f():\n    pass\n"

BASELINE_OK = (
    "tests/fake99/test_f.py::test_f PASSED\n"
    "tests/other/test_o.py::test_o PASSED\n"
)

FOREIGN_KEEP = "keep me\n"


def _usage():
    return {
        "models": [
            {
                "model": "fake-model",
                "input_tokens": 10,
                "cached_tokens": 0,
                "output_tokens": 5,
                "calls": 1,
            }
        ],
        "calls": 1,
        "completed_calls": 1,
        "failed_calls": 0,
    }


def _stub_muse(monkeypatch, devloop, behaviour):
    def fake_run_muse(
        *, model, effort, max_steps, workspace, prompt, browser=False
    ):
        from pathlib import Path

        return behaviour(Path(workspace))

    monkeypatch.setattr(devloop, "run_muse", fake_run_muse)


def _completed(root, writes=None):
    for rel, content in dict(writes or {}).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return {
        "usage": _usage(),
        "terminal": {"terminal": "completed", "text": "stub generation"},
        "returncode": 0,
        "stderr": "",
        "stdout_text": '{"payload": {"kind": "other"}}',
    }


def _stub_suites(monkeypatch, devloop, part_results=(0, "1 passed")):
    def fake_part_tests(test_command, cwd, browser=False):
        return part_results

    def fake_collection(test_runner, cwd, browser=False):
        return 0, ""

    state = {"count": 0}

    def fake_full_suite(test_runner, cwd, browser=False):
        state["count"] += 1
        return 0, BASELINE_OK

    def fake_one_test(test_runner, cwd, test_id, browser=False):
        return 0, ""

    monkeypatch.setattr(devloop, "run_part_tests", fake_part_tests)
    monkeypatch.setattr(devloop, "run_suite_collection", fake_collection)
    monkeypatch.setattr(devloop, "run_full_suite", fake_full_suite)
    monkeypatch.setattr(devloop, "run_one_test", fake_one_test)


def _foreign_repo(make_repo):
    """Fixture repo with foreign files the part does not own."""
    return make_repo(
        test_files={
            "tests/fake99/test_f.py": PASS_TEST,
            "src/other/keep.py": FOREIGN_KEEP,
        }
    )


def test_foreign_write_fails_and_is_restored(
    devloop, make_repo, run_args, monkeypatch, capsys
):
    """§16: a fake attempt that writes under another part's paths fails
    with that message and leaves the file as it was."""
    root = _foreign_repo(make_repo)

    def behaviour(r):
        return _completed(
            r,
            {
                "tests/fake99/test_f.py": PASS_TEST,
                "src/other/keep.py": "tampered\n",
                "src/other/new.py": "planted\n",
            },
        )

    _stub_muse(monkeypatch, devloop, behaviour)
    _stub_suites(monkeypatch, devloop)
    code = devloop.cmd_part(run_args(root))
    assert code == 1
    err = capsys.readouterr().err
    assert (
        "wrote outside its paths: src/other/keep.py, src/other/new.py"
        in err
    )
    # The modified file is restored, the planted one is gone.
    assert (root / "src/other/keep.py").read_text(encoding="utf-8") == (
        FOREIGN_KEEP
    )
    assert not (root / "src/other/new.py").exists()
    # The owned write survives: retries continue from the attempt's files.
    assert (root / "tests/fake99/test_f.py").read_text(
        encoding="utf-8"
    ) == PASS_TEST
    line = (root / "ITERATIONS.md").read_text(encoding="utf-8").strip()
    assert "wrote outside its paths" in line
    assert "src/other/keep.py" in line
    records = list((root / ".dev_loop" / "99").glob("*/test_output.txt"))
    assert records
    assert "wrote outside its paths" in records[0].read_text(
        encoding="utf-8"
    )


def test_deleted_foreign_file_is_restored(
    devloop, make_repo, run_args, monkeypatch
):
    """§16: a fake attempt that deletes another part's file fails, and
    the file comes back with its old content."""
    root = _foreign_repo(make_repo)

    def behaviour(r):
        (r / "src/other/keep.py").unlink()
        return _completed(r, {"tests/fake99/test_f.py": PASS_TEST})

    _stub_muse(monkeypatch, devloop, behaviour)
    _stub_suites(monkeypatch, devloop)
    assert devloop.cmd_part(run_args(root)) == 1
    assert (root / "src/other/keep.py").read_text(encoding="utf-8") == (
        FOREIGN_KEEP
    )


def test_owned_only_write_passes_this_check(
    devloop, make_repo, run_args, monkeypatch, capsys
):
    """§16: a fake attempt that writes only its own paths passes."""
    root = _foreign_repo(make_repo)
    _stub_muse(
        monkeypatch,
        devloop,
        lambda r: _completed(r, {"tests/fake99/test_f.py": PASS_TEST}),
    )
    _stub_suites(monkeypatch, devloop)
    assert devloop.cmd_part(run_args(root)) == 0
    assert "wrote outside its paths" not in capsys.readouterr().err
    assert "wrote outside its paths" not in (
        root / "ITERATIONS.md"
    ).read_text(encoding="utf-8")
    assert (root / "src/other/keep.py").read_text(encoding="utf-8") == (
        FOREIGN_KEEP
    )


def test_tool_own_writes_are_exempt(
    devloop, make_repo, run_args, monkeypatch
):
    """§16: README.md is on the exempt list, so an attempt that touches
    it (as dev_loop itself does after every run) is not flagged."""
    root = _foreign_repo(make_repo)
    _stub_muse(
        monkeypatch,
        devloop,
        lambda r: _completed(
            r,
            {
                "tests/fake99/test_f.py": PASS_TEST,
                "README.md": "attempt notes\n",
            },
        ),
    )
    _stub_suites(monkeypatch, devloop)
    assert devloop.cmd_part(run_args(root)) == 0


def test_snapshot_helpers_round_trip(devloop, tmp_path):
    """Unit level: the snapshot sees new/modified/deleted files, and
    the restore puts each kind back."""
    root = tmp_path / "tree"
    (root / "owned").mkdir(parents=True)
    (root / "foreign").mkdir(parents=True)
    (root / "owned" / "a.py").write_text("a", encoding="utf-8")
    (root / "foreign" / "b.py").write_text("b", encoding="utf-8")
    (root / "foreign" / "c.py").write_text("c", encoding="utf-8")
    owned = ["owned/"]
    before = devloop.snapshot_tree(root)
    before_dirs = devloop.snapshot_dirs(root)
    (root / "owned" / "a.py").write_text("a2", encoding="utf-8")
    (root / "foreign" / "b.py").write_text("b2", encoding="utf-8")
    (root / "foreign" / "c.py").unlink()
    (root / "foreign" / "fresh").mkdir()
    (root / "foreign" / "fresh" / "d.py").write_text(
        "d", encoding="utf-8"
    )
    changed, outside = devloop.check_attempt_writes(
        root, owned, before, before_dirs
    )
    assert "owned/a.py" in changed
    assert "foreign/fresh/d.py" in changed
    assert outside == [
        "foreign/b.py",
        "foreign/c.py",
        "foreign/fresh/d.py",
    ]
    assert (root / "foreign" / "b.py").read_text(encoding="utf-8") == "b"
    assert (root / "foreign" / "c.py").read_text(encoding="utf-8") == "c"
    assert not (root / "foreign" / "fresh" / "d.py").exists()
    assert not (root / "foreign" / "fresh").exists()
    # The owned write is reported but left alone.
    assert (root / "owned" / "a.py").read_text(encoding="utf-8") == "a2"

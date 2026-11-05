# generated from brief/15 · part 15 owns this file
"""Dev-loop loop tests: deletion, retries, records, and the suite guards.

Offline: the coding-agent call and every suite run are stubbed. No
model calls, no network, nothing costs money. `collect_test_functions`
still shells to real `pytest --collect-only` on tiny fixture repos.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PASS_TEST = "def test_f():\n    pass\n"

BASELINE_OK = (
    "tests/fake99/test_f.py::test_f PASSED\n"
    "tests/other/test_o.py::test_o PASSED\n"
)


def _usage(calls=1):
    return {
        "models": [
            {
                "model": "fake-model",
                "input_tokens": 10,
                "cached_tokens": 0,
                "output_tokens": 5,
                "calls": calls,
            }
        ],
        "calls": calls,
        "completed_calls": calls,
        "failed_calls": 0,
    }


def _stub_muse(monkeypatch, devloop, behaviour):
    """Replace run_muse with a scripted stub; record prompts and attempts."""
    calls = {"prompts": [], "count": 0}

    def fake_run_muse(
        *, model, effort, max_steps, workspace, prompt, browser=False
    ):
        calls["count"] += 1
        calls["prompts"].append(prompt)
        root = Path(workspace)
        return behaviour(root, calls["count"])

    monkeypatch.setattr(devloop, "run_muse", fake_run_muse)
    return calls


def _completed(root, writes=None, stdout_text=""):
    for rel, content in dict(writes or {}).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return {
        "usage": _usage(),
        "terminal": {"terminal": "completed", "text": "stub generation"},
        "returncode": 0,
        "stderr": "",
        "stdout_text": stdout_text
        or '{"payload_type": "x", "payload": {"kind": "other"}}',
    }


def _stub_suites(monkeypatch, devloop, part_results, collect=(0, ""),
                 baselines=None, guards=None, one_test=(0, "")):
    part_calls = {"part": [], "browser_flags": []}
    full_calls = {"count": 0, "browser_flags": []}
    baseline_outputs = list(baselines or [BASELINE_OK])
    guard_outputs = list(guards or [BASELINE_OK])

    def fake_part_tests(test_command, cwd, browser=False):
        part_calls["part"].append((list(test_command), str(cwd)))
        part_calls["browser_flags"].append(browser)
        code, output = part_results[min(
            len(part_calls["part"]) - 1, len(part_results) - 1
        )]
        return code, output

    def fake_collection(test_runner, cwd, browser=False):
        return collect

    def fake_full_suite(test_runner, cwd, browser=False):
        full_calls["count"] += 1
        full_calls["browser_flags"].append(browser)
        if full_calls["count"] == 1:
            return 0, baseline_outputs[0]
        return 0, guard_outputs[min(full_calls["count"] - 2,
                                    len(guard_outputs) - 1)]

    def fake_one_test(test_runner, cwd, test_id, browser=False):
        full_calls["browser_flags"].append(browser)
        return one_test

    monkeypatch.setattr(devloop, "run_part_tests", fake_part_tests)
    monkeypatch.setattr(
        devloop, "run_suite_collection", fake_collection
    )
    monkeypatch.setattr(devloop, "run_full_suite", fake_full_suite)
    monkeypatch.setattr(devloop, "run_one_test", fake_one_test)
    return part_calls, full_calls


def _iterations(root):
    return (root / "ITERATIONS.md").read_text(encoding="utf-8")


def test_deletion_once_retries_continue_from_files(
    devloop, make_repo, run_args, monkeypatch, capsys
):
    root = make_repo(
        test_files={"tests/fake99/test_f.py": PASS_TEST}
    )
    seen = {}

    def behaviour(r, attempt):
        if attempt == 1:
            writes = {
                "tests/fake99/test_f.py": PASS_TEST,
                "tests/fake99/marker.txt": "attempt1-marker",
            }
        else:
            marker = r / "tests/fake99/marker.txt"
            seen["marker_survived"] = (
                marker.is_file()
                and marker.read_text(encoding="utf-8") == "attempt1-marker"
            )
            writes = {
                "tests/fake99/test_f.py": PASS_TEST,
                "tests/fake99/attempt2.txt": "second attempt files",
            }
        return _completed(r, writes)

    _stub_muse(monkeypatch, devloop, behaviour)
    _stub_suites(
        monkeypatch, devloop,
        part_results=[
            (1, "FAILED tests/fake99/test_f.py::test_f - boom"),
            (0, "1 passed"),
        ],
    )
    deletes = {"count": 0}
    real_delete = devloop.delete_owned

    def counting_delete(r, owned, keep):
        deletes["count"] += 1
        return real_delete(r, owned, keep)

    monkeypatch.setattr(devloop, "delete_owned", counting_delete)
    code = devloop.cmd_part(run_args(root))
    assert code == 0
    assert deletes["count"] == 1
    assert seen["marker_survived"] is True
    assert (root / "tests/fake99/attempt2.txt").is_file()
    line = _iterations(root).strip()
    assert "after 2 attempt(s)" in line
    assert "tests pass" in line


def test_red_end_records_attempts_and_names_failures(
    devloop, make_repo, run_args, monkeypatch, capsys
):
    root = make_repo(
        test_files={"tests/fake99/test_f.py": PASS_TEST}
    )

    def behaviour(r, attempt):
        return _completed(
            r,
            {"tests/fake99/test_f.py": PASS_TEST},
            stdout_text=('{"payload_type": "run.usage", "payload": '
                         '{"kind": "run_usage", "models": []}}'),
        )

    _stub_muse(monkeypatch, devloop, behaviour)
    _stub_suites(
        monkeypatch, devloop,
        part_results=[(1, "FAILED tests/fake99/test_f.py::test_f - boom\n"
                          "E       boom\n")] * 2,
    )
    code = devloop.cmd_part(run_args(root))
    assert code == 1
    line = _iterations(root).strip()
    assert "FAILED after 2 attempt(s)" in line
    err = capsys.readouterr().err
    assert "tests/fake99/test_f.py::test_f" in err
    assert "last attempt record:" in err
    records = sorted((root / ".dev_loop" / "99").glob("*/test_output.txt"))
    assert len(records) == 2
    first = records[0].parent
    for name in ("events.jsonl", "final_message.txt", "test_output.txt",
                 "cost.txt"):
        assert (first / name).is_file()


def test_own_shrink_fails_and_names_missing(
    devloop, make_repo, run_args, monkeypatch
):
    root = make_repo(
        test_files={
            "tests/fake99/test_keep.py": "def test_keep():\n    pass\n",
            "tests/fake99/test_drop.py": "def test_drop():\n    pass\n",
        }
    )

    def behaviour(r, attempt):
        # Regeneration stub drops one test function and passes the rest.
        return _completed(
            r, {"tests/fake99/test_keep.py": "def test_keep():\n    pass\n"}
        )

    _stub_muse(monkeypatch, devloop, behaviour)
    baseline = ("tests/fake99/test_keep.py::test_keep PASSED\n"
                "tests/fake99/test_drop.py::test_drop PASSED\n")
    _stub_suites(monkeypatch, devloop, part_results=[(0, "1 passed")] * 2,
                 baselines=[baseline], guards=[baseline])
    code = devloop.cmd_part(run_args(root))
    assert code == 1
    line = _iterations(root).strip()
    assert "own tests went missing" in line
    assert "tests/fake99/test_drop.py::test_drop" in line
    record_outputs = list(
        (root / ".dev_loop" / "99").glob("*/test_output.txt")
    )
    assert record_outputs
    assert "MISSING tests/fake99/test_drop.py::test_drop" in (
        record_outputs[0].read_text(encoding="utf-8")
    )


def test_removes_test_excuses_shrink(
    devloop, make_repo, run_args, monkeypatch
):
    root = make_repo(
        test_files={
            "tests/fake99/test_keep.py": "def test_keep():\n    pass\n",
            "tests/fake99/test_drop.py": "def test_drop():\n    pass\n",
        },
        extra_spec_lines=(
            "Removes test: tests/fake99/test_drop.py::test_drop\n"
        ),
    )

    def behaviour(r, attempt):
        return _completed(
            r, {"tests/fake99/test_keep.py": "def test_keep():\n    pass\n"}
        )

    _stub_muse(monkeypatch, devloop, behaviour)
    baseline = ("tests/fake99/test_keep.py::test_keep PASSED\n"
                "tests/other/test_o.py::test_o PASSED\n")
    _stub_suites(monkeypatch, devloop, part_results=[(0, "1 passed")],
                 baselines=[baseline], guards=[baseline])
    assert devloop.cmd_part(run_args(root)) == 0
    assert "tests pass" in _iterations(root)


def test_parametrize_change_keeps_function(
    devloop, make_repo, run_args, monkeypatch
):
    first = ("import pytest\n\n@pytest.mark.parametrize('n', [1, 2])\n"
             "def test_p(n):\n    pass\n")
    root = make_repo(
        test_files={"tests/fake99/test_p.py": first}
    )
    second = ("import pytest\n\n@pytest.mark.parametrize('n', [1, 2, 3])\n"
              "def test_p(n):\n    pass\n")

    def behaviour(r, attempt):
        return _completed(r, {"tests/fake99/test_p.py": second})

    _stub_muse(monkeypatch, devloop, behaviour)
    _stub_suites(monkeypatch, devloop, part_results=[(0, "3 passed")])
    assert devloop.cmd_part(run_args(root)) == 0


def test_attempt_prompt_contains_every_recorded_name(
    devloop, make_repo, run_args, monkeypatch
):
    root = make_repo(
        test_files={
            "tests/fake99/test_keep.py": "def test_keep():\n    pass\n",
            "tests/fake99/test_drop.py": "def test_drop():\n    pass\n",
        }
    )
    calls = _stub_muse(
        monkeypatch, devloop,
        lambda r, attempt: _completed(
            r,
            {"tests/fake99/test_keep.py": "def test_keep():\n    pass\n",
             "tests/fake99/test_drop.py": "def test_drop():\n    pass\n"},
        ),
    )
    baseline = ("tests/fake99/test_keep.py::test_keep PASSED\n"
                "tests/fake99/test_drop.py::test_drop PASSED\n")
    _stub_suites(monkeypatch, devloop, part_results=[(0, "2 passed")],
                 baselines=[baseline], guards=[baseline])
    assert devloop.cmd_part(run_args(root)) == 0
    prompt = calls["prompts"][0]
    assert "tests/fake99/test_keep.py::test_keep" in prompt
    assert "tests/fake99/test_drop.py::test_drop" in prompt


def test_baseline_and_guard_force_browser_on(
    devloop, make_repo, run_args, monkeypatch, capsys
):
    root = make_repo(
        browser=False,
        test_files={"tests/fake99/test_f.py": PASS_TEST},
    )
    _stub_muse(
        monkeypatch, devloop,
        lambda r, attempt: _completed(
            r, {"tests/fake99/test_f.py": PASS_TEST}
        ),
    )
    baseline = ("tests/fake99/test_f.py::test_f PASSED\n"
                "tests/other/test_o.py::test_o PASSED\n"
                "tests/other/test_skip.py::test_s SKIPPED\n")
    part_calls, full_calls = _stub_suites(
        monkeypatch, devloop, part_results=[(0, "1 passed")],
        baselines=[baseline], guards=[baseline],
    )
    assert devloop.cmd_part(run_args(root)) == 0
    # The part's own tests keep the part flag; baseline, guard and the
    # alone-rerun path always set PHYSICS_PROOF_BROWSER=1.
    assert part_calls["browser_flags"] == [False]
    assert full_calls["browser_flags"] and all(
        flag is True for flag in full_calls["browser_flags"]
    )
    err = capsys.readouterr().err
    assert "baseline: 2 passed, 1 skipped of 3 collected tests" in err


def test_guard_skip_of_baseline_passed_test_fails(
    devloop, make_repo, run_args, monkeypatch
):
    root = make_repo(
        browser=False,
        test_files={"tests/fake99/test_f.py": PASS_TEST},
    )
    _stub_muse(
        monkeypatch, devloop,
        lambda r, attempt: _completed(
            r, {"tests/fake99/test_f.py": PASS_TEST}
        ),
    )
    baseline = ("tests/fake99/test_f.py::test_f PASSED\n"
                "tests/other/test_o.py::test_o PASSED\n")
    guard = ("tests/fake99/test_f.py::test_f PASSED\n"
             "tests/other/test_o.py::test_o SKIPPED\n")
    _stub_suites(monkeypatch, devloop, part_results=[(0, "1 passed")],
                 baselines=[baseline], guards=[guard])
    code = devloop.cmd_part(run_args(root))
    assert code == 1
    line = _iterations(root).strip()
    assert "other parts' tests broke" in line
    assert "tests/other/test_o.py::test_o" in line


def test_foreign_fail_passing_alone_is_flaky(
    devloop, make_repo, run_args, monkeypatch
):
    root = make_repo(
        test_files={"tests/fake99/test_f.py": PASS_TEST}
    )
    _stub_muse(
        monkeypatch, devloop,
        lambda r, attempt: _completed(
            r, {"tests/fake99/test_f.py": PASS_TEST}
        ),
    )
    baseline = ("tests/fake99/test_f.py::test_f PASSED\n"
                "tests/other/test_o.py::test_o PASSED\n")
    guard = ("tests/fake99/test_f.py::test_f PASSED\n"
             "tests/other/test_o.py::test_o FAILED\n"
             "FAILED tests/other/test_o.py::test_o - flaky\n")
    _stub_suites(
        monkeypatch, devloop, part_results=[(0, "1 passed")],
        baselines=[baseline], guards=[guard],
        one_test=(0, "tests/other/test_o.py::test_o PASSED\n"),
    )
    assert devloop.cmd_part(run_args(root)) == 0
    assert "flaky" in _iterations(root)


def test_baseline_failed_test_never_blocks(
    devloop, make_repo, run_args, monkeypatch
):
    root = make_repo(
        test_files={"tests/fake99/test_f.py": PASS_TEST}
    )
    _stub_muse(
        monkeypatch, devloop,
        lambda r, attempt: _completed(
            r, {"tests/fake99/test_f.py": PASS_TEST}
        ),
    )
    baseline = ("tests/fake99/test_f.py::test_f PASSED\n"
                "tests/other/test_o.py::test_o FAILED\n")
    guard = ("tests/fake99/test_f.py::test_f PASSED\n"
             "tests/other/test_o.py::test_o FAILED\n")
    _stub_suites(monkeypatch, devloop, part_results=[(0, "1 passed")],
                 baselines=[baseline], guards=[guard])
    assert devloop.cmd_part(run_args(root)) == 0


def test_breaks_on_purpose_excuses_foreign_fail(
    devloop, make_repo, run_args, monkeypatch
):
    root = make_repo(
        test_files={"tests/fake99/test_f.py": PASS_TEST},
        extra_spec_lines=(
            "Breaks on purpose: tests/other/test_o.py\n"
        ),
    )
    _stub_muse(
        monkeypatch, devloop,
        lambda r, attempt: _completed(
            r, {"tests/fake99/test_f.py": PASS_TEST}
        ),
    )
    baseline = ("tests/fake99/test_f.py::test_f PASSED\n"
                "tests/other/test_o.py::test_o PASSED\n")
    guard = ("tests/fake99/test_f.py::test_f PASSED\n"
             "tests/other/test_o.py::test_o FAILED\n"
             "FAILED tests/other/test_o.py::test_o - expected\n")
    _stub_suites(monkeypatch, devloop, part_results=[(0, "1 passed")],
                 baselines=[baseline], guards=[guard])
    assert devloop.cmd_part(run_args(root)) == 0
    line = _iterations(root).strip()
    assert "expected breaks" in line
    assert "tests/other/test_o.py::test_o" in line


def test_collection_error_fails_attempt(
    devloop, make_repo, run_args, monkeypatch
):
    root = make_repo(
        test_files={"tests/fake99/test_f.py": PASS_TEST}
    )
    _stub_muse(
        monkeypatch, devloop,
        lambda r, attempt: _completed(
            r, {"tests/fake99/test_f.py": PASS_TEST}
        ),
    )
    _stub_suites(
        monkeypatch, devloop, part_results=[(0, "1 passed")],
        collect=(2, "ERROR tests/a/test_dup.py\nERROR tests/b/test_dup.py\n"
                    "collection error: duplicate basename test_dup"),
    )
    code = devloop.cmd_part(run_args(root))
    assert code == 1
    assert "FAILED" in _iterations(root)


def test_changes_section_starts_at_last_generation_not_last_touch(
    devloop, tmp_path
):
    """Brief part 15 §17: the base is the last generation commit.

    A part is generated (an ITERATIONS.md line is added), its spec gains
    paragraph A, one of its owned files is then changed by another
    commit, and its spec gains paragraph B. The prompt's changes section
    must contain both A and B: a revert/touch of an owned file must not
    move the base to the newest owned-paths commit (which would hold
    only B).
    """
    import shutil
    import subprocess

    if shutil.which("git") is None:
        pytest.skip("git is not available")
    root = tmp_path / "changes-repo"
    (root / "brief").mkdir(parents=True)
    (root / "skills").mkdir(parents=True)
    (root / "tests" / "fake99").mkdir(parents=True)
    spec_rel = "brief/99-fake-part.md"
    skill_rel = "skills/fake-skill.md"
    owned_file = root / "tests" / "fake99" / "test_f.py"
    para_a = "PARAGRAPH-ALPHA-17-SPEC-CHANGE-A"
    para_b = "PARAGRAPH-BETA-17-SPEC-CHANGE-B"

    def git(*argv):
        proc = subprocess.run(
            ["git", *argv], cwd=root, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        return proc

    (root / spec_rel).write_text("Fake part 99.\n", encoding="utf-8")
    (root / "brief" / "04-architecture-and-constraints.md").write_text(
        "Fake shared constraints.\n", encoding="utf-8"
    )
    (root / "PLAN.md").write_text("Fake plan.\n", encoding="utf-8")
    (root / skill_rel).write_text("Fake skill.\n", encoding="utf-8")
    owned_file.write_text(PASS_TEST, encoding="utf-8")
    (root / "ITERATIONS.md").write_text("", encoding="utf-8")
    git("init")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    git("add", "-A")
    git("commit", "-m", "initial")
    # The generation commit: adds a line for this part to ITERATIONS.md.
    with (root / "ITERATIONS.md").open("a", encoding="utf-8") as handle:
        handle.write("2026-10-30 | part 99 | generated | tests pass\n")
    git("add", "-A")
    git("commit", "-m", "Part 99 generated")
    # Paragraph A lands after the generation.
    with (root / spec_rel).open("a", encoding="utf-8") as handle:
        handle.write(f"\n{para_a}\n")
    git("add", "-A")
    git("commit", "-m", "spec gains paragraph A")
    # Another commit touches an owned file (revert/fixture fix style).
    with owned_file.open("a", encoding="utf-8") as handle:
        handle.write("# touched by another commit\n")
    git("add", "-A")
    git("commit", "-m", "touch an owned file")
    # Paragraph B lands last.
    with (root / spec_rel).open("a", encoding="utf-8") as handle:
        handle.write(f"\n{para_b}\n")
    git("add", "-A")
    git("commit", "-m", "spec gains paragraph B")

    section = devloop.build_spec_changes_section(
        root, spec_rel, [skill_rel], ["tests/fake99/"], part="99",
    )
    assert para_a in section
    assert para_b in section
    prompt = devloop.build_prompt(
        root, spec_rel, [skill_rel], browser=False,
        owned=["tests/fake99/"], part="99",
    )
    assert para_a in prompt
    assert para_b in prompt

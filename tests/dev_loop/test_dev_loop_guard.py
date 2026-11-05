# generated from brief/15 · part 15 owns this file
"""Dev-loop guard unit tests: the hash check, pricing, and spec parsing.

Offline: stubbed data only, no Muse calls, no network, no money.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


def _sealed(make_repo, **kwargs):
    kwargs.setdefault(
        "test_files",
        {"tests/fake99/test_fake99_keep.py": "def test_keep():\n    pass\n"},
    )
    return make_repo(**kwargs)


def test_hand_edit_refusal_names_file(devloop, make_repo):
    root = _sealed(make_repo)
    owned = ["tests/fake99/"]
    manifest = devloop.load_manifest(root / "tools" / "manifest.json")
    assert devloop.check_clean(root, "99", owned, manifest) == []
    target = root / "tests/fake99/test_fake99_keep.py"
    target.write_text(
        "def test_keep():\n    assert False  # hand edit\n", encoding="utf-8"
    )
    violations = devloop.check_clean(root, "99", owned, manifest)
    assert violations == ["tests/fake99/test_fake99_keep.py"]


def test_unlisted_file_under_owned_paths_is_violation(devloop, make_repo):
    root = _sealed(make_repo)
    owned = ["tests/fake99/"]
    manifest = devloop.load_manifest(root / "tools" / "manifest.json")
    (root / "tests/fake99/test_added_by_hand.py").write_text(
        "def test_hand():\n    pass\n", encoding="utf-8"
    )
    violations = devloop.check_clean(root, "99", owned, manifest)
    assert violations == ["tests/fake99/test_added_by_hand.py"]


def test_missing_header_is_never_a_violation(devloop, make_repo):
    root = make_repo(
        test_files={
            "tests/fake99/test_bare.py": "def test_bare():\n    pass\n",
        }
    )
    owned = ["tests/fake99/"]
    manifest = devloop.load_manifest(root / "tools" / "manifest.json")
    # Sealed without any generated-from header: still clean.
    assert devloop.check_clean(root, "99", owned, manifest) == []
    assert (
        devloop.header_part(root / "tests/fake99/test_bare.py") is None
    )


def test_delete_owned_removes_only_owned_paths(devloop, make_repo):
    root = _sealed(
        make_repo,
        test_files={
            "tests/fake99/test_a.py": "X = 1\n",
            "tests/other/test_o.py": "Y = 2\n",
            "src/keep.py": "Z = 3\n",
        },
    )
    deleted = devloop.delete_owned(
        root, ["tests/fake99/"], keep=set()
    )
    assert deleted == ["tests/fake99/"]
    assert not (root / "tests/fake99").exists()
    assert (root / "tests/other/test_o.py").is_file()
    assert (root / "src/keep.py").is_file()


def test_price_usage_cached_subset_not_addend(devloop):
    usage = {
        "models": [
            {
                "model": "muse-spark-1.3-contributor",
                "input_tokens": 1_000_000,
                "cached_tokens": 900_000,
                "output_tokens": 1_000_000,
                "reasoning_tokens": 400_000,
                "calls": 3,
            }
        ]
    }
    dollars, _ = devloop.price_usage(usage)
    # (100k x $0.10 + 900k x $0.002 + 1M x $0.20) / 1M; reasoning tokens
    # sit inside output_tokens and are never priced twice.
    assert dollars == pytest.approx(
        (100_000 * 0.10 + 900_000 * 0.002 + 1_000_000 * 0.20) / 1_000_000
    )


def test_price_usage_unknown_model_is_unknown(devloop):
    dollars, summary = devloop.price_usage(
        {
            "models": [
                {
                    "model": "muse-spark-9.9",
                    "input_tokens": 10,
                    "cached_tokens": 0,
                    "output_tokens": 5,
                    "calls": 1,
                }
            ]
        }
    )
    assert dollars is None
    assert "muse-spark-9.9" in summary


def test_run_cost_sums_every_attempt(devloop):
    line = devloop.format_run_cost([1.61, 1.66], ["a", "b"])
    assert "cost $3.2700" in line
    assert "over 2 attempts" in line
    assert "$1.6100 + $1.6600" in line


def test_run_cost_unknown_when_any_attempt_unknown(devloop):
    line = devloop.format_run_cost([1.61, None], ["a", "no usage reported"])
    assert line.startswith("cost unknown over 2 attempts")


def test_breaks_on_purpose_strips_punctuation(devloop, make_repo):
    root = make_repo(
        spec_text=(
            "Fake part.\n"
            "Breaks on purpose: `tests/a/test_x.py`.\n"
            "Breaks on purpose: (`tests/a/`),\n"
            "Breaks on purpose: tests/a/test_y.py;\n"
        )
    )
    paths = devloop.load_breaks_on_purpose(root, "brief/99-fake-part.md")
    assert "tests/a/test_x.py" in paths
    assert "tests/a" in paths
    assert "tests/a/test_y.py" in paths
    assert all(
        not path.endswith((".", "`", ";", ",")) for path in paths
    )


def test_breaks_on_purpose_two_paths_one_line(devloop, make_repo):
    root = make_repo(
        spec_text=(
            "Fake part.\n"
            "Breaks on purpose: tests/a/test_x.py tests/b/test_y.py\n"
        )
    )
    paths = devloop.load_breaks_on_purpose(root, "brief/99-fake-part.md")
    assert paths == ["tests/a/test_x.py", "tests/b/test_y.py"]


def test_removes_test_parsed_like_breaks(devloop, make_repo):
    root = make_repo(
        spec_text=(
            "Fake part.\n"
            "Removes test: `tests/fake99/test_old.py::test_gone`.\n"
        )
    )
    removed = devloop.load_removed_tests(root, "brief/99-fake-part.md")
    assert removed == ["tests/fake99/test_old.py::test_gone"]
    assert devloop.is_removed(
        "tests/fake99/test_old.py::test_gone", removed
    )
    assert not devloop.is_removed(
        "tests/fake99/test_old.py::test_stays", removed
    )


def test_removes_test_bare_name_excuses_function(devloop):
    assert devloop.is_removed(
        "tests/fake99/test_old.py::test_gone", ["test_gone"]
    )


def test_strip_param_suffix(devloop):
    assert (
        devloop.strip_param_suffix("tests/a/test_x.py::test_f[a-1]")
        == "tests/a/test_x.py::test_f"
    )
    assert (
        devloop.strip_param_suffix("tests/a/test_x.py::test_f")
        == "tests/a/test_x.py::test_f"
    )


def test_owned_test_targets_only_tests(devloop):
    assert devloop.owned_test_targets(
        ["tools/dev_loop", "tests/dev_loop/", "tests/acceptance/"]
    ) == ["tests/dev_loop/", "tests/acceptance/"]


def test_baseline_line_names_skipped(devloop):
    verdicts = {
        "tests/a/test_x.py::test_1": "PASSED",
        "tests/a/test_x.py::test_2": "SKIPPED",
        "tests/b/test_y.py::test_3": "PASSED",
    }
    line = devloop.format_baseline_line(
        verdicts, {"tests/a/test_x.py::test_1", "tests/b/test_y.py::test_3"}
    )
    assert line == "baseline: 2 passed, 1 skipped of 3 collected tests"
    assert "skipped" in line


def test_recorded_block_lists_every_function(devloop):
    recorded = [
        "tests/fake99/test_a.py::test_one",
        "tests/fake99/test_a.py::test_two",
    ]
    block = devloop.format_recorded_tests_block(recorded)
    for node_id in recorded:
        assert node_id in block


def test_missing_block_names_functions(devloop):
    missing = ["tests/fake99/test_a.py::test_vanished"]
    block = devloop.format_missing_own_block(missing)
    assert "OWN TESTS THAT WENT MISSING" in block
    assert missing[0] in block


def test_prompt_contains_changes_section_and_browser(devloop, make_repo):
    root = make_repo(browser=True)
    prompt = devloop.build_prompt(
        root,
        "brief/99-fake-part.md",
        ["skills/fake-skill.md"],
        browser=True,
        owned=["tests/fake99/"],
    )
    assert "=== SPEC PART: brief/99-fake-part.md ===" in prompt
    assert "=== SHARED CONSTRAINTS:" in prompt
    assert "=== PLAN.md ===" in prompt
    assert "=== SKILL: skills/fake-skill.md ===" in prompt
    assert "SPEC CHANGES SINCE THE LAST GENERATION OF THIS PART" in prompt
    assert "This part builds a screen (browser: true)" in prompt
    prompt_plain = devloop.build_prompt(
        root,
        "brief/99-fake-part.md",
        ["skills/fake-skill.md"],
        browser=False,
        owned=["tests/fake99/"],
    )
    assert "This part builds a screen" not in prompt_plain


def test_run_usage_last_event_wins(devloop):
    stdout = (
        '{"payload_type": "run.usage", "payload": {"kind": "run_usage", '
        '"models": [{"model": "m1", "input_tokens": 1}], "calls": 1}}\n'
        '{"payload_type": "run.terminal.completed", "payload": '
        '{"kind": "run_terminal", "terminal": "completed", "text": "done"}}\n'
    )
    usage, terminal = devloop.parse_events(stdout)
    assert usage["models"][0]["model"] == "m1"
    assert terminal["terminal"] == "completed"
    assert terminal["text"] == "done"


def test_summarize_failures_names_tests(devloop):
    output = (
        "FAILED tests/a/test_x.py::test_bad - assert 1 == 2\n"
        "E       assert 1 == 2\n"
        "1 failed in 0.1s\n"
    )
    failures = devloop.summarize_failures(output)
    assert failures[0][0] == "tests/a/test_x.py::test_bad"
    assert "assert 1 == 2" in failures[0][1]


def test_gated_commands_need_live_flag(devloop, make_repo, run_args):
    root = make_repo()
    args = run_args(root)
    assert devloop.cmd_acceptance(args) == devloop.EXIT_UNAVAILABLE
    assert devloop.cmd_pages(args) == devloop.EXIT_UNAVAILABLE
    iterations = Path(root / "ITERATIONS.md")
    assert not iterations.exists()

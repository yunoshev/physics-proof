# generated from brief/07 · part 07 owns this file
"""Sandbox profile: deny-by-default with an explicit allow-list."""

from __future__ import annotations

from pathlib import Path

from src.tools import sandbox


def test_profile_is_deny_by_default(tmp_path):
    profile = sandbox.build_profile(str(tmp_path))
    assert "(deny default)" in profile
    assert "(deny network*)" in profile
    assert profile.rindex("(deny network*)") > profile.index(
        "(allow file-read*")
    assert '(subpath "/")' not in profile


def test_run_layout_allows_exactly_three_subtrees(tmp_path):
    root = tmp_path / "runs" / "abc"
    (root / "input").mkdir(parents=True)
    profile = sandbox.build_profile(str(root), run_layout=True)
    resolved = str(root.resolve())
    assert f'(subpath "{resolved}/input")' in profile
    assert f'(subpath "{resolved}/workspace")' in profile
    assert f'(subpath "{resolved}/artifacts")' in profile
    # The run root itself is never an allowed subtree: logs/ and
    # run-root files stay unreadable and the directory cannot be
    # listed (part 07 §13).
    assert f'(subpath "{resolved}")' not in profile.replace(
        f'{resolved}/', "")


def test_profile_allows_only_the_run_tree(tmp_path):
    root = tmp_path / "runs" / "abc"
    root.mkdir(parents=True)
    profile = sandbox.build_profile(str(root))
    assert f'(subpath "{root.resolve()}")' in profile
    assert "workspace" not in profile.replace(str(root.resolve()),
                                              "")
    assert str(tmp_path) not in profile.replace(
        str(root.resolve()), "")


def test_profile_allows_helpers_sandbox_env_and_system(tmp_path):
    env = tmp_path / "env"
    env.mkdir()
    profile = sandbox.build_profile(str(tmp_path), sandbox_env=env)
    helpers = str(sandbox.repo_helpers_dir().resolve())
    assert f"(allow file-read* (subpath \"{helpers}\"))" in profile
    assert f"(allow file-read* (subpath \"{env.resolve()}\"))" in profile
    for system in ("/System/Library", "/usr/lib", "/usr/share",
                   "/private/var/db/timezone", "/dev/null",
                   "/dev/urandom"):
        assert system in profile
    assert "(allow file-read-metadata)" in profile


def test_sandbox_env_hash_covers_deps_and_python():
    first = sandbox.sandbox_env_hash("3.13.3", {"numpy": "1",
                                                "scipy": "2",
                                                "cv2": "3"})
    assert first == sandbox.sandbox_env_hash(
        "3.13.3", {"numpy": "1", "scipy": "2", "cv2": "3"})
    assert first != sandbox.sandbox_env_hash(
        "3.13.3", {"numpy": "9", "scipy": "2", "cv2": "3"})
    assert first != sandbox.sandbox_env_hash(
        "3.12.0", {"numpy": "1", "scipy": "2", "cv2": "3"})


def test_sandbox_env_reused_across_calls(tmp_path):
    first = sandbox.ensure_sandbox_env(tmp_path / "base")
    assert (first / "helpers").is_dir()
    for dep in sandbox.SANDBOX_ENV_DEPS:
        assert (first / dep).exists(), dep
    assert (first / "ENV_MARKER.txt").is_file()
    second = sandbox.ensure_sandbox_env(tmp_path / "base")
    assert second == first

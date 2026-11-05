"""Registry tests: schema, names, hashes, result listing (part 10 §3)."""
from __future__ import annotations

import json

import pytest

from src.selfbuilt import registry as reg
from tests.selfbuilt.conftest import GOOD_MODULE, make_test, pass_executor


def test_registry_schema(run_dir, tmp_path):
    from src.selfbuilt.gate import try_register
    test_source = make_test("sb_wall_line")
    result = try_register(run_dir, "sb_wall_line", GOOD_MODULE, test_source,
                          "fit wall line", 17, executor=pass_executor)
    assert result["ok"]
    raw = json.loads((run_dir / "workspace" / "selfbuilt"
                      / "registry.json").read_text(encoding="utf-8"))
    assert set(raw) == {"tools"}
    assert len(raw["tools"]) == 1
    entry = raw["tools"][0]
    assert set(entry) == {"name", "module_sha256", "test_sha256", "attempts",
                          "status", "purpose", "registered_at_turn"}
    assert entry == {"name": "sb_wall_line",
                     "module_sha256": reg.sha256_text(GOOD_MODULE),
                     "test_sha256": reg.sha256_text(test_source),
                     "attempts": 1, "status": "passed",
                     "purpose": "fit wall line", "registered_at_turn": 17}


def test_empty_registry_when_nothing_registered(run_dir):
    assert reg.load_registry(run_dir) == {"tools": []}
    assert reg.is_importable(run_dir, "sb_anything") is False
    assert reg.list_tools_for_result(run_dir) == []


def test_corrupt_registry_raises_and_fails_closed(run_dir, tmp_path):
    path = run_dir / "workspace" / "selfbuilt" / "registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{nope", encoding="utf-8")
    with pytest.raises(ValueError, match="registry_corrupt"):
        reg.load_registry(run_dir)
    assert reg.is_importable(run_dir, "sb_x") is False


def test_tool_name_rejects_missing_prefix():
    ok, code, detail = reg.validate_tool_name("wall_line")
    assert not ok and code == "bad_tool_name"
    assert "sb_" in detail


@pytest.mark.parametrize("bad", ["sb_", "sb-Wall", "sb.wall", "sb wall",
                                 "SB_WALL", "", None, 42])
def test_tool_name_rejects_bad_shapes(bad):
    ok, code, _ = reg.validate_tool_name(bad)
    assert not ok and code == "bad_tool_name"


@pytest.mark.parametrize("shadow", ["sb_json", "sb_os", "sb_sys",
                                    "sb_tracks", "sb_physics", "sb_clock",
                                    "sb_masks_io", "sb_promoted"])
def test_tool_name_rejects_stdlib_and_helper_shadows(shadow):
    ok, code, _ = reg.validate_tool_name(shadow)
    assert not ok and code == "name_collision"


def test_tool_name_allows_fresh_and_retry_names(run_dir):
    assert reg.validate_tool_name("sb_wall_line")[0] is True
    from src.selfbuilt.gate import try_register
    try_register(run_dir, "sb_wall_line", GOOD_MODULE,
                 make_test("sb_wall_line"), "fit wall line", 3,
                 executor=pass_executor)
    # Same name is a retry (consumes an attempt at test time), not a reject.
    assert reg.validate_tool_name(
        "sb_wall_line", reg.load_registry(run_dir))[0] is True

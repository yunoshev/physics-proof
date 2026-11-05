"""Evidence tests: submissions must name registered, passing tools (part 10 §4)."""
from __future__ import annotations

from src.selfbuilt import registry as reg
from src.selfbuilt.gate import try_register
from tests.selfbuilt.conftest import (
    GOOD_MODULE,
    fail_executor,
    make_test,
    pass_executor,
)


def _register(run_dir, name="sb_wall_line", executor=pass_executor):
    return try_register(run_dir, name, GOOD_MODULE, make_test(name),
                        "fit wall line", 17, executor=executor)


def test_result_must_name_used_tool(run_dir):
    _register(run_dir)
    assert reg.validate_evidence_tools(["sb_wall_line"], run_dir) == []
    assert reg.validate_evidence_tools([], run_dir) == []
    assert reg.validate_evidence_tools(None, run_dir) == []


def test_unregistered_tool_name_rejected(run_dir):
    _register(run_dir)
    errors = reg.validate_evidence_tools(["sb_ghost_tool"], run_dir)
    assert len(errors) == 1
    assert errors[0]["code"] == "unregistered_selfbuilt_tool"
    assert errors[0]["field"] == "evidence.selfbuilt_tools"
    assert "sb_ghost_tool" in errors[0]["detail"]


def test_failed_tool_name_rejected(run_dir):
    _register(run_dir, name="sb_failed", executor=fail_executor)
    errors = reg.validate_evidence_tools(["sb_failed"], run_dir)
    assert len(errors) == 1
    assert errors[0]["code"] == "unregistered_selfbuilt_tool"
    assert "never passed" in errors[0]["detail"]


def test_edited_tool_name_rejected(run_dir):
    _register(run_dir)
    module = run_dir / "workspace" / "selfbuilt" / "sb_wall_line.py"
    module.write_text(GOOD_MODULE + "\n# edited\n", encoding="utf-8")
    errors = reg.validate_evidence_tools(["sb_wall_line"], run_dir)
    assert len(errors) == 1
    assert errors[0]["code"] == "unregistered_selfbuilt_tool"
    assert "modified" in errors[0]["detail"]


def test_list_tools_for_result_names_purpose_attempts(run_dir):
    _register(run_dir)
    _register(run_dir, name="sb_second")
    listed = reg.list_tools_for_result(run_dir)
    assert listed == [{"name": "sb_wall_line", "purpose": "fit wall line",
                       "attempts": 1},
                      {"name": "sb_second", "purpose": "fit wall line",
                       "attempts": 1}]

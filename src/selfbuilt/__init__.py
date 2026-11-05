"""Self-built tools: the agent's extendable toolkit (part 10).

The whole mechanism is a directory, a JSON registry, and one test-runner
invocation. No plugin framework.

A self-built tool is exactly two files, written by Spark via ``run_python``
into the run workspace::

    workspace/selfbuilt/sb_<name>.py        the module (``sb_`` prefix mandatory)
    workspace/selfbuilt/test_sb_<name>.py   its synthetic test

The gate (:mod:`src.selfbuilt.gate`) runs the test in a fresh temporary
directory containing only the two files, under the same sandbox as
``run_python`` (part 07) with a short timeout. On a pass the loop registers
the tool (:mod:`src.selfbuilt.registry`) and adds ``workspace/selfbuilt/``
to the import path for later ``run_python`` calls in the run; on a fail the
module is not importable and the failure output goes back to Spark.

Caps (enforced here, accounted by the loop's ledger): at most 4 self-built
tools per run, at most 3 attempts each — every test execution counts, pass
or fail. At the cap, further builds are refused with a structured error and
the run proceeds with helpers only.

Promotion is human-only (``python -m src.selfbuilt.promote <run-id>
<sb_name>``); there is no agent-facing promote action.
"""

from __future__ import annotations

from src.selfbuilt.gate import (
    SELFBUILT_TEST_TIMEOUT_S,
    check_module_imports,
    import_path_for_run,
    importable_names,
    is_importable,
    try_register,
)
from src.selfbuilt.registry import (
    MAX_ATTEMPTS_PER_TOOL,
    MAX_TOOLS_PER_RUN,
    REGISTRY_FILENAME,
    SELFBUILT_DIR_NAME,
    find_tool,
    list_tools_for_result,
    load_registry,
    registry_path,
    selfbuilt_dir,
    sha256_file,
    sha256_text,
    validate_evidence_tools,
    validate_tool_name,
)

__all__ = [
    "MAX_ATTEMPTS_PER_TOOL",
    "MAX_TOOLS_PER_RUN",
    "REGISTRY_FILENAME",
    "SELFBUILT_DIR_NAME",
    "SELFBUILT_TEST_TIMEOUT_S",
    "check_module_imports",
    "find_tool",
    "import_path_for_run",
    "importable_names",
    "is_importable",
    "list_tools_for_result",
    "load_registry",
    "registry_path",
    "selfbuilt_dir",
    "sha256_file",
    "sha256_text",
    "try_register",
    "validate_evidence_tools",
    "validate_tool_name",
]

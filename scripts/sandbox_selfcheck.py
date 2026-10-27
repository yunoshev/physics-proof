"""Maintainer probe for M5-fix1: run on the Mac (sandbox-exec works there).

Prints the generated Seatbelt profile, then runs a trivial print(1)
through run_python and shows exit code, stdout and stderr.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from physics_proof.sandbox import run_python


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sandbox_selfcheck_") as tmp:
        workspace = Path(tmp) / "ws"
        workspace.mkdir()
        result = run_python("print(1)\n", workspace)
    profile = result.script.with_suffix(".sb").read_text(encoding="utf-8") if result.script else ""
    print("=== profile ===", flush=True)
    print(profile, flush=True)
    print("=== run ===", flush=True)
    print("ok=" + str(result.ok), flush=True)
    print("exit_code=" + str(result.exit_code), flush=True)
    print("stdout=" + result.stdout.strip(), flush=True)
    print("stderr=" + (result.stderr.strip() or "(empty)"), flush=True)
    if not result.ok or result.stdout.strip() != "1":
        sys.exit(1)


if __name__ == "__main__":
    main()

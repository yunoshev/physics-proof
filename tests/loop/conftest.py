# generated from brief/06 · part 06 owns this file
"""Shared fixtures for the loop tests (part 04: helpers shared by a
part's tests are pytest fixtures in its own ``conftest.py``, factory
fixtures where a test needs to call them with arguments).

``run_loop`` is driven with stub Spark clients and a fake clock. Caps
always come from :mod:`src.config`; no test here names a literal cap.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.accounting import Ledger
from src.loop import run_loop


@pytest.fixture()
def make_run(tmp_path):
    """Factory: fresh run directory with the part-04 §4 layout."""

    def _make(name="run"):
        run_dir = tmp_path / name
        for sub in ("input", "workspace", "artifacts", "logs"):
            (run_dir / sub).mkdir(parents=True, exist_ok=True)
        (run_dir / "input" / "timing.json").write_text(
            json.dumps({"frame_count": 8,
                        "timestamps": [i / 10 for i in range(8)],
                        "measured_fps": 10.0,
                        "confirmed_duplicates": [], "cuts": []})
            + "\n", encoding="utf-8")
        return run_dir

    return _make


@pytest.fixture()
def make_ledger():
    """Factory: fresh ledger per run (loops never share state, §6)."""

    def _make(run_id="run", run_dir=None):
        return Ledger(run_id=run_id,
                      run_dir=str(run_dir) if run_dir else None)

    return _make


class FakeClock:
    """Manual wall clock (seconds); ``advance`` moves it forward."""

    def __init__(self, start=0.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += float(seconds)


@pytest.fixture()
def fake_clock():
    return FakeClock()


@pytest.fixture()
def stub_responses():
    """Canned spark responses and tool calls."""

    def _completed(text="", calls=(), usage=None):
        return {"terminal": "response.completed", "text": text,
                "tool_calls": list(calls),
                "usage": (dict(usage) if usage is not None
                          else {"input_tokens": 10, "cached_tokens": 0,
                                "output_tokens": 5,
                                "reasoning_tokens": 0})}

    def _call(name, arguments=None, call_id="call-1"):
        return {"call_id": call_id, "name": name,
                "arguments": dict(arguments or {})}

    return {"completed": _completed, "call": _call}


@pytest.fixture()
def script_spark(stub_responses):
    """Factory: spark stub replaying a script, recording requests."""

    def _make(script):
        requests: list = []
        pending = list(script)

        def _spark(request):
            requests.append(request)
            if not pending:
                return stub_responses["completed"]("out of script")
            item = pending.pop(0)
            if callable(item):
                return item(request)
            return item

        _spark.requests = requests
        return _spark

    return _make


@pytest.fixture()
def accepting_validator():
    """Factory: validator stub accepting everything, writing a file."""

    def _make(run_dir, result=None):
        seen: list = []

        def _validate(evidence, run_context=None, dry_run=False):
            seen.append({"evidence": evidence, "dry_run": bool(dry_run)})
            path = Path(str(run_dir)) / "result.json"
            path.write_text(json.dumps(result or {"accepted": True})
                            + "\n", encoding="utf-8")
            return {"accepted": True, "errors": [],
                    "result": result or {"accepted": True},
                    "result_path": str(path)}

        _validate.seen = seen
        return _validate

    return _make


@pytest.fixture()
def rejecting_validator():
    """Factory: validator stub rejecting with queued error lists."""

    def _error(code, field="evidence", detail="bad"):
        return {"code": code, "field": field, "detail": detail}

    def _make(run_dir, error_lists):
        calls: list = []
        queue = [list(errors) for errors in error_lists]

        def _validate(evidence, run_context=None, dry_run=False):
            calls.append({"evidence": evidence, "dry_run": bool(dry_run)})
            errors = queue.pop(0) if queue else []
            if errors:
                return {"accepted": False, "errors": list(errors)}
            path = Path(str(run_dir)) / "result.json"
            path.write_text(json.dumps({"accepted": True}) + "\n",
                            encoding="utf-8")
            return {"accepted": True, "errors": [],
                    "result": {"accepted": True},
                    "result_path": str(path)}

        _validate.calls = calls
        return _validate

    _make.error = _error
    return _make


@pytest.fixture()
def measured_evidence():
    """Factory: minimal evidence carrying a real measurement.

    A dry run needs a reference with an ``extent_px``, a range
    check with an extent, or a segment with frames — otherwise the
    loop refuses it as a placeholder (part 06 addendum 2026-10-31,
    hand run 7 / wall run 12). This segment with frames is the
    smallest such evidence.
    """

    def _make():
        return {"segments": [{"frames": {"start": 1, "apex": 5,
                                         "end": 9}}]}

    return _make


@pytest.fixture()
def drive_loop():
    """Factory: one call to the pinned ``run_loop`` with test defaults."""

    def _drive(run_dir, spark, clock=None, validator=None, ledger=None,
               **kwargs):
        if ledger is None:
            ledger = Ledger(run_id=run_dir.name, run_dir=str(run_dir))
        kwargs.setdefault("sleep", lambda s: None)
        return run_loop(str(run_dir), run_dir.name, spark_client=spark,
                        ledger=ledger, clock=clock, validator=validator,
                        **kwargs)

    return _drive

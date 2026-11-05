"""Shared fixtures for part-10 selfbuilt tests (no models, no network)."""
from __future__ import annotations

import pytest

GOOD_MODULE = """\
import numpy as np


def predict(xs):
    arr = np.asarray(xs, dtype=float)
    return 2.0 * arr + 1.0
"""

def make_test(name):
    """Self-contained synthetic test importing its sibling module."""
    return f"""\
import numpy as np

from {name} import predict


def test_recovers_line():
    xs = np.array([0.0, 1.0, 2.0])
    assert np.allclose(predict(xs), [1.0, 3.0, 5.0], atol=1e-9)
"""


def pass_executor(test_path, isolated_dir, timeout_s):
    return {"returncode": 0, "stdout": "1 passed", "stderr": "",
            "timed_out": False}


def fail_executor(test_path, isolated_dir, timeout_s):
    return {"returncode": 1, "stdout": "",
            "stderr": "FAILED test_sb_x.py::test_recovers_line - assert 0 == 1",
            "timed_out": False}


@pytest.fixture()
def run_dir(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    return run

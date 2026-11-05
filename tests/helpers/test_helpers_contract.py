# owned by part 09 · cross-module contracts for src/helpers/
"""The library's licence to exist: API surface, error codes, docs drift.

- The five modules expose exactly the functions part 09 §§2/7
  names — no classes, no model calls, no network, no state.
- Every documented ``ValueError`` code has at least one raiser.
- ``HELPERS_DOCS.md`` is byte-identical to what ``gen_docs`` renders:
  regenerating docs and getting a diff fails the build (part 15).
- The sandbox import shape (``from helpers import <module>``) works:
  each module file loads standalone under the ``helpers`` package
  name.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

EXPECTED = {
    "masks_io": {"save_masks", "load_masks", "clip_facts", "read_frames"},
    "tracks": {"mask_stats", "largest_component", "track_point",
               "track_quality", "relative_track", "find_still_patches",
               "still_track"},
    "physics": {"fit_parabola", "scale_from_reference",
                "track_to_metres", "worlds_fit", "ghost"},
    "clock": {"gait_signal", "step_rate", "clock_evidence"},
    "ranges": {"mask_extent", "range_value", "print_check"},
}

REPO = Path(__file__).resolve().parent.parent.parent
HELPERS = REPO / "src" / "helpers"


@pytest.mark.parametrize("module", sorted(EXPECTED))
def test_module_exposes_exactly_the_spec_functions(module):
    """Five modules, the §§2/7 function names, nothing more or less."""
    package = pytest.importorskip("src.helpers")
    mod = getattr(package, module, None)
    if mod is None:
        mod = __import__(f"src.helpers.{module}",
                         fromlist=[module])
    public = {name for name, obj in vars(mod).items()
              if inspect.isfunction(obj) and not name.startswith("_")}
    assert public == EXPECTED[module]


@pytest.mark.parametrize("module", sorted(EXPECTED))
def test_modules_define_no_classes(module):
    """Small-code principle: functions over arrays, no classes."""
    package = pytest.importorskip("src.helpers")
    mod = getattr(package, module, None)
    if mod is None:
        mod = __import__(f"src.helpers.{module}",
                         fromlist=[module])
    defined = [name for name, obj in vars(mod).items()
               if inspect.isclass(obj)
               and getattr(obj, "__module__", "") == mod.__name__]
    assert defined == []


@pytest.mark.parametrize("module", sorted(EXPECTED))
def test_modules_do_not_import_network_or_models(module):
    """No sockets, no subprocess, no model clients in the library."""
    source = (HELPERS / f"{module}.py").read_text(encoding="utf-8")
    for banned in ("socket", "urllib", "requests", "httpx", "subprocess",
                   "http.client"):
        assert f"import {banned}" not in source, (module, banned)


def test_helpers_raise_coded_valueerrors():
    """Each documented error code has at least one raiser."""
    import numpy as np

    from src.helpers import clock as clock_mod
    from src.helpers import physics as physics_mod
    from src.helpers import tracks as tracks_mod

    empty = np.zeros((6, 6), dtype=bool)
    with pytest.raises(ValueError, match="empty_mask"):
        tracks_mod.mask_stats(empty)
    with pytest.raises(ValueError, match="empty_mask"):
        tracks_mod.largest_component(empty)
    with pytest.raises(ValueError, match="empty_mask"):
        tracks_mod.track_point({0: empty}, "centroid")
    with pytest.raises(ValueError, match="empty_mask"):
        clock_mod.gait_signal({0: empty})
    with pytest.raises(ValueError, match="bad_mode"):
        tracks_mod.track_point({0: np.ones((4, 4), dtype=bool)},
                               "head_bob")
    with pytest.raises(ValueError, match="no_common_frames"):
        tracks_mod.relative_track([], [])
    with pytest.raises(ValueError, match="short_track"):
        physics_mod.fit_parabola([0.0], [1.0])
    with pytest.raises(ValueError, match="bad_scale"):
        physics_mod.scale_from_reference(0.0, 1.0, 1.0, 0.1)
    with pytest.raises(ValueError, match="bad_sigma"):
        physics_mod.worlds_fit(1.0, 0.0, [{"name": "Moon", "g": 1.62}])
    with pytest.raises(ValueError, match="no_takeoff"):
        physics_mod.ghost({"x0": 0.0, "y0": 0.0, "vx": 1.0, "vy": 0.0},
                          9.81, 0.01, [0.0, 0.1])
    with pytest.raises(ValueError, match="peak_at_band_edge"):
        clock_mod.step_rate(list(np.sin(np.arange(8, dtype=float))),
                            [float(i) for i in range(8)], (1.0, 4.0))
    result, flag = clock_mod.step_rate(
        list(np.sin(2.0 * np.pi * 1.25 * np.arange(120) / 30.0)),
        list(np.arange(120) / 30.0), (1.0, 4.0))
    assert result is None and flag == "no_reliable_clock"


def test_sandbox_import_shape_loads_each_module():
    """``from helpers import <module>`` works file-standalone."""
    import sys

    for module in sorted(EXPECTED):
        name = f"helpers_{module}_contract"
        spec = importlib.util.spec_from_file_location(
            name, HELPERS / f"{module}.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.modules.pop(name, None)
        assert callable(getattr(mod, sorted(EXPECTED[module])[0]))


def test_gen_docs_diff_fails_build():
    """The checked-in docs equal the docstring render, byte for byte."""
    from src.helpers import gen_docs

    target = gen_docs.docs_path()
    assert target.is_file()
    current = target.read_text(encoding="utf-8")
    assert gen_docs.GENERATED_MARKER in current
    assert current == gen_docs.generate_docs()
    assert gen_docs.main(["--check"]) == 0

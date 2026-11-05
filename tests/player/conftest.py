# generated from brief/13 · part 13 owns this file
"""Shared browser fixtures for part 13's player tests (brief §§15–34).

Synchronisation rule (part 13 §34.2): tests wait on page state exposed
through ``window.__pp`` with generous timeouts, never on fixed delays.
``time.sleep`` is used only to check that something does *not* happen.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PW_TIMEOUT = 30000


def _result(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / name / "result.json").read_text())


def _result_src(name: str) -> dict:
    return json.loads(
        (ROOT / "fixtures/source" / name / "result.json").read_text())


def _write_variant(name: str, mutate) -> Path:
    from src.pagebuild import build_page

    dest = Path("/tmp/ppvar") / name
    if dest.exists():
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    result = _result("clip-a")
    mutate(result)
    (dest / "result.json").write_text(json.dumps(result))
    shutil.copy(ROOT / "fixtures/clip-a/summary.json", dest / "summary.json")
    (dest / "input").mkdir(exist_ok=True)
    shutil.copy(ROOT / "fixtures/clip-a/input/clip.mp4", dest / "input/clip.mp4")
    out = dest / "page"
    build_page(str(dest / "result.json"), str(dest / "input/clip.mp4"),
               str(out), str(dest / "summary.json"), slug=name)
    return out


def _two_segment_result():
    result = _result("clip-a")
    import copy
    seg = copy.deepcopy(result["segments"][0])
    seg["id"] = "hop_b"
    seg["label"] = "Jump 2"
    fps = result["video"]["measured_fps"]
    dt = 99 / fps
    seg["frames"] = {k: v + 99 for k, v in seg["frames"].items()}
    seg["times_s"] = {k: v + dt for k, v in seg["times_s"].items()}
    for ov in seg["overlay"]:
        ov["frame"] += 99
    for p in seg["track"]:
        p["frame"] += 99
        p["t_s"] += dt
    for p in seg["fit_curve_px"]:
        p["t_s"] += dt
    for km in seg.get("key_moments", []):
        km["frame"] += 99
        km["t_s"] += dt
    for g in seg["ghosts"]:
        for p in g["points"]:
            p["frame"] += 99
            p["t_s"] += dt
        g["landing"]["t_s"] += dt
    for o in seg.get("world_outcomes", []):
        o["landing_time_s"] += dt
    result["segments"].append(seg)
    result["first_look"]["motions"][1]["segment_id"] = "hop_b"
    result["first_look"]["motions"][1]["skip_reason"] = None
    result["first_look"]["motions"][1]["frame_start"] = 340
    result["first_look"]["motions"][1]["frame_end"] = 376
    result["calculation_steps"].append(
        {"id": "segment_b", "title": "Segment Jump 2", "frame": 340,
         "frame_end": None, "segment_id": "hop_b",
         "short": [{"type": "text", "text": "second jump"}], "full": [],
         "caveats": []})
    return result


@pytest.fixture(scope="session")
def pages():
    from src.pagebuild import build_page, template_hash

    out = {}
    jobs = {
        "clip-a": ("fixtures/clip-a/result.json",
                   "fixtures/clip-a/input/clip.mp4",
                   "fixtures/clip-a/summary.json"),
        "still": ("fixtures/still-range/result.json", None, None),
        "run-7": ("fixtures/run-7/result.json", None, None),
    }
    base = Path("/tmp/ppages")
    # Always rebuild: pages embed the frozen template, so a cached page
    # from an older template would test stale code (§34: tests wait on
    # the page, and the page must be the current template).
    for name, (res, vid, summ) in jobs.items():
        dest = base / name
        shutil.rmtree(dest, ignore_errors=True)
        build_page(str(ROOT / res),
                   str(ROOT / vid) if vid else None,
                   str(dest),
                   str(ROOT / summ) if summ else None,
                   slug=name)
        (dest / ".template_hash").write_text(template_hash())
        out[name] = dest
    return out


@pytest.fixture(scope="session")
def two_seg_page():
    import copy

    dest = Path("/tmp/ppvar/two-seg")
    from src.pagebuild import build_page

    work = Path("/tmp/ppvar/two-seg-work")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    shutil.copytree(ROOT / "fixtures/clip-a/artifacts", work / "artifacts")
    result = _two_segment_result()
    (work / "result.json").write_text(json.dumps(result))
    shutil.copy(ROOT / "fixtures/clip-a/summary.json",
                work / "summary.json")
    shutil.rmtree(dest, ignore_errors=True)
    build_page(str(work / "result.json"),
               str(ROOT / "fixtures/clip-a/input/clip.mp4"),
               str(dest), str(work / "summary.json"), slug="two-seg")
    return dest


@pytest.fixture(scope="session")
def moon_range_page():
    import copy

    dest = Path("/tmp/ppvar/moon-range")
    from src.pagebuild import build_page

    work = Path("/tmp/ppvar/moon-range-work")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    shutil.copytree(ROOT / "fixtures/clip-a/artifacts", work / "artifacts")
    if (dest).exists():
        shutil.rmtree(dest, ignore_errors=True)
    result = _result("clip-a")
    result["range_checks"] = [{
        "id": "hand_ratio", "label": "hand ratio",
        "answers": "checks proportions", "unit": "ratio", "frame": 100,
        "extents": [{"name": "hand", "x1": 50, "y1": 40, "x2": 50,
                      "y2": 240, "length_px": 200, "frame": 100}],
        "value": 0.45, "sigma": 0.02, "formula": "palm_px / hand_px",
        "uses_scale": False,
        "measurement_artifact": "artifacts/x.txt",
        "range": {"min": 0.4, "max": 0.52, "typical": 0.46,
                  "what": "adult survey", "bounds_kind": "percentile",
                  "percentiles": [5, 95], "sources": [{
                      "url": "https://example.com/a",
                      "domain": "example.com",
                      "quote": "range 0.40 to 0.52",
                      "quote_highlight": "0.40", "value": 0.4,
                      "bound": "min", "source_type": "survey"}]},
        "outcome": "inside", "delta_sigma": 0, "side": None}]
    (work / "result.json").write_text(json.dumps(result))
    shutil.copy(ROOT / "fixtures/clip-a/summary.json",
                work / "summary.json")
    build_page(str(work / "result.json"),
               str(ROOT / "fixtures/clip-a/input/clip.mp4"),
               str(dest), str(work / "summary.json"),
               slug="moon-range")
    return dest


@pytest.fixture(scope="session")
def moon22_page():
    # Moon run 22's shape (brief 13 §37): the fit has a negative y0 and
    # a positive v0 in px/s, and the stored Moon landing_time_s minus the
    # takeoff start is negative ("Moon -7.36 s" under the old convention).
    # The drawn curves are clip-a's, so the end labels must stay positive.
    import copy

    dest = Path("/tmp/ppvar/moon22")
    from src.pagebuild import build_page

    work = Path("/tmp/ppvar/moon22-work")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    shutil.copytree(ROOT / "fixtures/clip-a/artifacts", work / "artifacts")
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    result = copy.deepcopy(_result("clip-a"))
    seg = result["segments"][0]
    start = seg["times_s"]["start"]
    for o in seg.get("world_outcomes", []):
        if o["world"] == "Moon":
            o["landing_time_s"] = start - 7.36
    fit = seg.get("fit", {})
    fit.update({"a_px_s2": 122.6, "v0": 13.5, "y0": -57.2})
    (work / "result.json").write_text(json.dumps(result))
    shutil.copy(ROOT / "fixtures/clip-a/summary.json",
                work / "summary.json")
    build_page(str(work / "result.json"),
               str(ROOT / "fixtures/clip-a/input/clip.mp4"),
               str(dest), str(work / "summary.json"), slug="moon22")
    return dest


@pytest.fixture(scope="session")
def hand8_page():
    # Hand run 8's shape (brief 13 §40): a verdict of kind "world"
    # decided by a range check with no measured g, and two long
    # overlapping unmeasured motions whose names used to overlap on
    # the timeline.
    dest = Path("/tmp/ppvar/hand8")
    from src.pagebuild import build_page

    work = Path("/tmp/ppvar/hand8-work")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    shutil.copytree(ROOT / "fixtures/still-range/artifacts",
                    work / "artifacts")
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    result = _result("still-range")
    result["verdict"] = {
        "kind": "world", "world": "Earth", "direction": None,
        "factor": None, "g_measured": None, "sigma_g": None,
        "reason": None, "clock_note": None,
        "decided_by": "palm_hand_ratio"}
    result["first_look"]["motions"] = [
        {"frame_start": 0, "frame_end": 0,
         "description": "Foreground leap, the main jump over the carpet grid",
         "segment_id": None,
         "skip_reason": "approach run left unmeasured in the source run"},
        {"frame_start": 0, "frame_end": 0,
         "description": "foreground astronaut standing after landing",
         "segment_id": None,
         "skip_reason": "standing still: no motion to measure"}]
    (work / "result.json").write_text(json.dumps(result))
    build_page(str(work / "result.json"), None, str(dest), None,
               slug="hand8")
    return dest


@pytest.fixture(scope="session")
def run22_page():
    """Run 22's page with its real clip (brief part 13 §42)."""
    import shutil

    from src.pagebuild import build_page

    dest = Path("/tmp/ppvar/run22")
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    build_page(str(ROOT / "fixtures/source/run-22/result.json"),
               str(ROOT / "fixtures/source/run-22/input/clip.mp4"),
               str(dest),
               str(ROOT / "fixtures/source/run-22/summary.json"),
               slug="run-22")
    return dest


def _portrait_video(path: Path) -> Path:
    import subprocess

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
             "-i", "testsrc=size=720x1280:rate=30:duration=6",
             "-pix_fmt", "yuv420p", str(path)],
            check=True, timeout=300)
    return path


@pytest.fixture(scope="session")
def portrait_page():
    """A synthetic 720x1280 portrait page with a range-check result
    holding one event at 2.0 s (brief part 13 §42.3)."""
    import shutil

    from src.pagebuild import build_page

    work = Path("/tmp/ppvar/portrait-work")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    shutil.copytree(ROOT / "fixtures/still-range/artifacts",
                    work / "artifacts")
    video = _portrait_video(work / "clip-src.mp4")
    result = _result("still-range")
    result["video"] = {"coded_width": 720, "coded_height": 1280,
                       "sample_aspect": {"num": 1, "den": 1},
                       "measured_fps": 30.0, "frame_count": 180,
                       "duration_s": 6.0}
    for rc in result.get("range_checks", []):
        rc["frame"] = 60
    result["first_look"]["motions"] = [
        {"frame_start": 0, "frame_end": 179,
         "description": "portrait test motion",
         "segment_id": None,
         "skip_reason": "synthetic portrait page"}]
    (work / "result.json").write_text(json.dumps(result))
    dest = Path("/tmp/ppvar/portrait")
    shutil.rmtree(dest, ignore_errors=True)
    build_page(str(work / "result.json"), str(video), str(dest),
               None, slug="portrait")
    return dest


@pytest.fixture(scope="session")
def fake1_page():
    """Sped-up Moon page (brief part 13 §45/§47.4), rebuilt every session."""
    import shutil

    from src.pagebuild import build_page

    dest = Path("/tmp/ppvar/fake1")
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    build_page(str(ROOT / "fixtures/source/fake-1/result.json"),
               str(ROOT / "fixtures/source/fake-1/input/clip.mp4"),
               str(dest),
               str(ROOT / "fixtures/source/fake-1/summary.json"),
               slug="fake-1")
    return dest


@pytest.fixture(scope="session")
def http_base():
    """A local HTTP server on /tmp (brief part 13 §46.2): pages under
    /tmp/ppages and /tmp/ppvar are reachable as http://127.0.0.1:PORT/...
    The server is torn down at session end."""
    import socket
    import subprocess
    import time as _time
    import urllib.request

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd="/tmp", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    deadline = _time.time() + 30
    while _time.time() < deadline:
        try:
            urllib.request.urlopen(base + "/", timeout=2).close()
            break
        except Exception:  # noqa: BLE001 — retry until the server is up
            _time.sleep(0.2)
    else:
        proc.terminate()
        pytest.fail("local HTTP server did not start")
    yield base
    proc.terminate()
    proc.wait(timeout=30)


@pytest.fixture(scope="session")
def run22_earth_page():
    """Run 22's result plus the always-weighed Earth candidate
    (part 11 §41): Moon fits, Earth needs a ×2.48 slow-down."""
    import copy
    import shutil

    from src.pagebuild import build_page

    work = Path("/tmp/ppvar/run22-earth-work")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    result = copy.deepcopy(_result_src("run-22"))
    result["worlds"]["candidates"].append(
        {"world": "Earth", "g_m_s2": 9.81, "fits_native": False,
         "delta_sigma": 33.27, "retime_factor": 2.48})
    shutil.copytree(ROOT / "fixtures/source/run-22/artifacts",
                    work / "artifacts")
    (work / "result.json").write_text(json.dumps(result))
    shutil.copy(ROOT / "fixtures/source/run-22/summary.json",
                work / "summary.json")
    dest = Path("/tmp/ppvar/run22-earth")
    shutil.rmtree(dest, ignore_errors=True)
    build_page(str(work / "result.json"),
               str(ROOT / "fixtures/source/run-22/input/clip.mp4"),
               str(dest), str(work / "summary.json"),
               slug="run22-earth")
    return dest


@pytest.fixture(scope="session")
def pw():
    # One Playwright driver for the whole session. Playwright's sync
    # API marks this thread's event loop as running after the first
    # call, so a second sync_playwright() context started later in the
    # same thread raises "use the Async API instead". Every browser
    # (Chrome, Firefox, WebKit) is launched from this one instance.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(pw):
    yield pw.chromium.launch(channel="chrome")


@pytest.fixture()
def page(browser):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    yield pg
    pg.close()


def goto(page, page_dir: Path, query: str = ""):
    page.goto(f"file://{page_dir}/index.html{query}", timeout=30000)
    page.wait_for_function("window.__pp && window.__pp.cutsReady() === true",
                           timeout=PW_TIMEOUT)


def wait_frame(page, n: int):
    page.wait_for_function(f"window.__pp.frame() === {n}", timeout=PW_TIMEOUT)


def wait_hold(page, kind: str | None):
    if kind is None:
        page.wait_for_function("window.__pp.hold() === null",
                               timeout=PW_TIMEOUT)
    else:
        page.wait_for_function(
            f"window.__pp.hold() && window.__pp.hold().kind === '{kind}'",
            timeout=PW_TIMEOUT)


def wait_hold_seq(page, kinds: list[str]):
    for kind in kinds:
        page.wait_for_function(
            "window.__pp.hold() === null || "
            f"window.__pp.hold().kind !== '{kind}'",
            timeout=120000)
        wait_hold(page, kind)


def stage_texts(page):
    return page.evaluate("""() => [...document.querySelectorAll(
      '#stageOverlay text')].map(t => { const r = t.getBoundingClientRect();
        return {id: t.id, text: t.textContent, x: r.left, y: r.top,
                w: r.width, h: r.height}; })""")

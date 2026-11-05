# generated from brief/13 · part 13 owns this file
"""Three-engine ride tests (brief part 13 §44.3).

The real-time ride tests run in Chrome (installed Google Chrome),
Playwright's Firefox and Playwright's WebKit. If an engine cannot
decode the page video the test fails with that message — it never
skips. Each ride runs twice: once from "Watch the analysis", once
from the round play button. Synchronisation is state-based (§34.2):
every wait targets ``window.__pp`` with a generous timeout; a fixed
delay is allowed only to check that something does *not* happen.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PW_TIMEOUT = 60000

ENGINES = ["chrome", "firefox", "webkit"]

# Hold durations by kind (brief part 13 §18.1); ``range`` holds reuse
# the scale shape at 2.0 s. Used only to bound the ride wall time.
_HOLD_DURS = {"scale": 3.8, "takeoff": 1.5, "apex": 2.8,
              "landing": 5.6, "range": 2.0, "verdict": 0.0}


@pytest.fixture(params=ENGINES, ids=ENGINES)
def engine_page(request, pw):
    # Launch from the session Playwright instance (see conftest.pw):
    # a fresh sync_playwright() context here would raise "use the Async
    # API instead" once the session browser has marked this thread's
    # loop as running.
    try:
        if request.param == "chrome":
            browser = pw.chromium.launch(channel="chrome")
        elif request.param == "firefox":
            browser = pw.firefox.launch()
        else:
            browser = pw.webkit.launch()
    except Exception as e:  # noqa: BLE001 — launch failure is fatal
        pytest.fail(f"{request.param}: cannot launch: {e}")
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    yield request.param, pg
    pg.close()
    browser.close()


def _goto(engine_page, page_dir: Path, query: str = ""):
    engine, pg = engine_page
    pg.goto(f"file://{page_dir}/index.html{query}", timeout=30000)
    pg.wait_for_function(
        "window.__pp && window.__pp.cutsReady() === true",
        timeout=PW_TIMEOUT)
    # §44.3: an engine that cannot decode the page video fails here
    # with that message. It does not skip.
    try:
        pg.wait_for_function(
            "() => { const v = document.querySelector('video');"
            " return v && v.videoWidth > 0 && v.readyState >= 2; }",
            timeout=30000)
    except Exception:  # noqa: BLE001 — any wait failure is fatal
        pytest.fail(f"{engine} cannot decode the page video")


def _hold_dur(kind: str) -> float:
    return _HOLD_DURS.get(kind, 6.0)


@pytest.mark.parametrize("start", ["watch", "play"])
def test_engines_ride(engine_page, run22_page, start):
    # §44.3: the full ride in every engine, from either start button.
    # Extra assertions over the Chrome ride: every event caption is
    # seen exactly once, currentTime never drops by more than one
    # frame, and the verdict arrives within clip + holds + 5 s.
    engine, pg = engine_page
    _goto(engine_page, run22_page)
    n_events = pg.evaluate("window.__pp.events().length")
    duration = pg.evaluate("document.querySelector('video').duration")
    assert duration > 1, duration
    t0 = time.time()
    if start == "watch":
        pg.click("#watchBtn")
    else:
        pg.click("#playBtn")
    worst_drop = 0.0
    prev = pg.evaluate("""() => ({
      t: document.querySelector('video').currentTime,
      hold: window.__pp.hold() ? window.__pp.hold().kind : null
    })""")
    deadline = time.time() + 180
    while time.time() < deadline:
        row = pg.evaluate("""() => ({
          t: document.querySelector('video').currentTime,
          hold: window.__pp.hold() ? window.__pp.hold().kind : null,
          seen: window.__pp.seen()
        })""")
        # A hold snaps the playhead back onto its exact event frame
        # by design (§§18.1, 44.2); the no-rewind rule governs free
        # playback, so only hold-free pairs count here.
        if prev["hold"] is None and row["hold"] is None:
            worst_drop = max(worst_drop, prev["t"] - row["t"])
        prev = row
        if any(s.startswith("verdict:") for s in row["seen"]):
            break
        time.sleep(0.2)
    else:  # noqa: PLW0120 — the ride never reached the verdict
        pytest.fail(f"{engine}/{start}: no verdict within 180 s")
    elapsed = time.time() - t0
    seen = pg.evaluate("window.__pp.seen()")
    kinds = [s.split(":")[0] for s in seen]
    # Every event caption is seen exactly once per ride.
    assert len(seen) == n_events, (engine, start, seen)
    assert len(set(seen)) == len(seen), (engine, start, seen)
    # Outside holds, currentTime never drops by more than one
    # frame (§44.3).
    assert worst_drop <= 1 / 29.0 + 1e-6, (engine, start, worst_drop)
    # The verdict appears within clip length + holds + 5 s of wall time.
    bound = duration + sum(_hold_dur(k) for k in kinds) + 5.0
    assert elapsed <= bound, (engine, start, elapsed, bound)


def test_engines_pause_while_playing(engine_page, portrait_page):
    # §42.3 in every engine: pause freezes currentTime and the stage.
    engine, pg = engine_page
    _goto(engine_page, portrait_page)
    pg.evaluate("document.querySelector('#watchBtn').click()")
    pg.wait_for_function(
        "document.querySelector('video').paused === false",
        timeout=PW_TIMEOUT)
    time.sleep(1.0)
    pg.keyboard.press(" ")
    pg.wait_for_function(
        "document.querySelector('video').paused === true",
        timeout=PW_TIMEOUT)
    t0 = pg.evaluate("document.querySelector('video').currentTime")
    time.sleep(1.5)
    t1 = pg.evaluate("document.querySelector('video').currentTime")
    assert abs(t1 - t0) <= 1 / 29.0 + 1e-6, (engine, t0, t1)
    pg.keyboard.press(" ")
    pg.wait_for_function(
        "document.querySelector('video').paused === false",
        timeout=PW_TIMEOUT)


def test_engines_pause_in_hold(engine_page, portrait_page):
    # §42.3 in every engine: pausing in a hold freezes its bar and
    # title; the next press finishes the hold, then the video moves.
    engine, pg = engine_page
    _goto(engine_page, portrait_page)
    pg.evaluate("document.querySelector('#watchBtn').click()")
    pg.wait_for_function(
        "window.__pp.hold() !== null", timeout=120000)
    pg.keyboard.press(" ")
    pg.wait_for_function(
        "document.querySelector('video').paused === true",
        timeout=PW_TIMEOUT)
    bar0 = pg.evaluate("document.getElementById('holdbar').style.width")
    time.sleep(1.5)
    bar1 = pg.evaluate("document.getElementById('holdbar').style.width")
    assert bar0 == bar1, (engine, bar0, bar1)
    pg.keyboard.press(" ")
    pg.wait_for_function("window.__pp.hold() === null",
                         timeout=PW_TIMEOUT)
    t0 = pg.evaluate("document.querySelector('video').currentTime")
    pg.wait_for_function(
        f"document.querySelector('video').currentTime > {t0}",
        timeout=PW_TIMEOUT)


def test_engines_timeline_seek_and_drag(engine_page, portrait_page):
    # §42.3 in every engine: the timeline seeks and pauses; clicks at
    # three fractions land within a frame; drag takes several values.
    engine, pg = engine_page
    _goto(engine_page, portrait_page)
    seen_times = []
    for frac in (0.25, 0.50, 0.75):
        box = pg.evaluate("""() => {
          const r = document.getElementById('timeline')
            .getBoundingClientRect();
          return {x: r.left, y: r.top, w: r.width, h: r.height};
        }""")
        assert box["h"] >= 24, (engine, box)
        pg.mouse.click(box["x"] + frac * box["w"],
                       box["y"] + box["h"] / 2)
        pg.wait_for_function(f"""() => {{
          const v = document.querySelector('video');
          return Math.abs(v.currentTime - {frac} * v.duration)
            < 1.5 / 30;
        }}""", timeout=PW_TIMEOUT)
        assert pg.evaluate(
            "document.querySelector('video').paused === true"), engine
        seen_times.append(
            pg.evaluate("document.querySelector('video').currentTime"))
    assert len({round(v, 2) for v in seen_times}) == 3, \
        (engine, seen_times)
    box = pg.evaluate("""() => {
      const r = document.getElementById('timeline').getBoundingClientRect();
      return {x: r.left, y: r.top, w: r.width, h: r.height};
    }""")
    seen = []
    pg.mouse.move(box["x"] + 0.2 * box["w"], box["y"] + box["h"] / 2)
    pg.mouse.down()
    for i in range(1, 9):
        pg.mouse.move(box["x"] + (0.2 + 0.05 * i) * box["w"],
                      box["y"] + box["h"] / 2, steps=2)
        seen.append(pg.evaluate(
            "document.querySelector('video').currentTime"))
    pg.mouse.up()
    assert len({round(v, 3) for v in seen}) >= 3, (engine, seen)


@pytest.mark.parametrize("start", ["watch", "play"])
@pytest.mark.parametrize("proto", ["file", "http"])
def test_engines_stage_moves(engine_page, pages, http_base, start, proto):
    # §46.2 in every engine, from file:// and over HTTP: while the video
    # plays (not paused, not in a hold) and currentTime advances, the
    # stage screenshots differ; at most 20 % of such pairs may be equal.
    # §47.3 over HTTP the clip loads as a blob URL before the ride.
    import os
    import time as _time

    engine, pg = engine_page
    page_dir = pages["clip-a"]
    if proto == "file":
        pg.goto(f"file://{page_dir}/index.html", timeout=30000)
    else:
        rel = os.path.relpath(str(page_dir), "/tmp")
        pg.goto(f"{http_base}/{rel}/index.html", timeout=30000)
    pg.wait_for_function(
        "window.__pp && window.__pp.cutsReady() === true",
        timeout=PW_TIMEOUT)
    if proto == "http":
        src = pg.evaluate("document.querySelector('video').src")
        assert src.startswith("blob:"), (engine, src)
    if start == "watch":
        pg.click("#watchBtn")
    else:
        pg.click("#playBtn")
    pg.wait_for_function(
        "document.querySelector('video').paused === false",
        timeout=120000)
    box = pg.evaluate("""() => {
      const r = document.getElementById('stage').getBoundingClientRect();
      return {x: r.x, y: r.y, width: r.width, height: r.height};
    }""")
    playing = []
    t0 = _time.time()
    while _time.time() - t0 < 90:
        row = pg.evaluate("""() => ({
          t: document.querySelector('video').currentTime,
          paused: document.querySelector('video').paused,
          hold: window.__pp.hold() ? window.__pp.hold().kind : null,
          seen: window.__pp.seen()
        })""")
        if any(s.startswith("verdict:") for s in row["seen"]):
            break
        if not row["paused"] and row["hold"] is None:
            playing.append((row["t"], pg.screenshot(clip=box)))
            if len(playing) >= 9:
                break
        _time.sleep(0.25)
    pairs = [(a, b) for a, b in zip(playing, playing[1:])
             if b[0] - a[0] > 0.05]
    assert len(pairs) >= 5, (engine, proto, start, len(pairs))
    equal = sum(1 for a, b in pairs if a[1] == b[1])
    assert equal / len(pairs) <= 0.2, (engine, proto, start, equal,
                                       len(pairs))

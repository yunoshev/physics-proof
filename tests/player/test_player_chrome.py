# generated from brief/13 · part 13 owns this file
"""Browser tests for the frozen player (brief part 13 §§5, 14–34).

Run with ``PHYSICS_PROOF_BROWSER=1`` against the installed Google
Chrome (Playwright ``channel="chrome"``). Without Chrome the browser
tests skip with a reason. Synchronisation is state-based (§34.2): every
wait targets ``window.__pp`` with a 30 s+ timeout; no fixed-delay sync.
"""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

import pytest

PW_TIMEOUT = 60000


def goto(page, page_dir, query=""):
    page.goto(f"file://{page_dir}/index.html{query}", timeout=30000)
    page.wait_for_function("window.__pp && window.__pp.cutsReady() === true",
                           timeout=PW_TIMEOUT)


def wait_frame(page, n):
    page.wait_for_function(f"window.__pp.frame() === {n}",
                           timeout=PW_TIMEOUT)


def wait_hold(page, kind):
    if kind is None:
        page.wait_for_function("window.__pp.hold() === null",
                               timeout=PW_TIMEOUT)
    else:
        page.wait_for_function(
            f"window.__pp.hold() && window.__pp.hold().kind === '{kind}'",
            timeout=PW_TIMEOUT)


def wait_hold_seq(page, kinds):
    # State-based (34.2): the page logs every entered hold in
    # window.__pp.seen(), so quick holds are never missed by polling.
    for i, kind in enumerate(kinds):
        page.wait_for_function(
            f"""() => window.__pp.seen().filter(
              s => s.startsWith('{kind}:')).length >= """
            + str(sum(1 for k in kinds[:i + 1] if k == kind)),
            timeout=300000)


def seen_kinds(page):
    return [s.split(":")[0] for s in
            page.evaluate("window.__pp.seen()")]


def assertShown(page, sel):
    """SVG lines have an empty CSS box; check the drawn length instead."""
    info = page.evaluate("""(sel) => {
      const e = document.querySelector(sel);
      if (!e) return {found: false};
      const r = e.getBoundingClientRect();
      return {found: true, w: r.width, h: r.height};
    }""", sel)
    assert info["found"], sel
    assert info["w"] + info["h"] > 0, sel


def stage_texts(page):
    return page.evaluate("""() => [...document.querySelectorAll(
      '#stageOverlay text')].map(t => { const r = t.getBoundingClientRect();
        return {id: t.id, text: t.textContent, x: r.left, y: r.top,
                w: r.width, h: r.height}; })""")

ROOT = Path(__file__).resolve().parents[2]


def _chrome_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome")
            b.close()
        return True
    except Exception:
        return False


needs_chrome = pytest.mark.skipif(
    not _chrome_available(), reason="no installed Google Chrome")


def _result_data(page) -> dict:
    return json.loads(page.evaluate(
        "document.getElementById('result-data').textContent"))


def _visible_stage_texts(page):
    # One entry per rendered line box: a wrapping text node's union rect
    # would self-collide with its neighbours, so use getClientRects().
    return page.evaluate("""() => {
      const sr = document.getElementById('stage').getBoundingClientRect();
      const out = [];
      const walker = document.createTreeWalker(
        document.getElementById('stage'), NodeFilter.SHOW_TEXT);
      const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const [idx, n] of nodes.entries()) {
        if (!n.nodeValue || !n.nodeValue.trim()) continue;
        const el = n.parentElement;
        if (!el || el.closest('script,style')) continue;
        if (el.closest('.katex-mathml')) continue;
        const r = document.createRange();
        r.selectNodeContents(n);
        if (el.closest('#intro') && getComputedStyle(
            document.getElementById('intro')).display === 'none') continue;
        // the rotated stamp is one rigid unit; its internal AABBs overlap
        const stamp = !!el.closest('#stamp');
        for (const b of r.getClientRects()) {
          if (b.width < 1 && b.height < 1) continue;
          out.push({text: n.nodeValue.trim().slice(0, 60), x: b.left - sr.left,
                    y: b.top - sr.top, w: b.width, h: b.height, n: idx,
                    stamp: stamp});
        }
      }
      return out;
    }""")


@needs_chrome
def test_chrome_first_screen(page, pages):
    # 43.7: the first screen asks one question; the Claim line and
    # the What-we-see card live under Full calculation.
    goto(page, pages["clip-a"])
    headline = page.text_content("#intro h2")
    result = _result_data(page)
    assert headline == result["first_look"]["question"]
    intro = page.text_content("#intro")
    assert "What we check:" in intro
    assert "Claim:" not in intro
    assert "What we see" not in intro
    assert "By eye, before measuring" in intro
    assert page.is_visible("#watchBtn")
    assert page.text_content("#chartEmpty") == "waiting for takeoff"
    page.click("#ckFull")
    intro_full = page.text_content("#intro")
    assert "Claim:" in intro_full
    assert "What we see" in intro_full


@needs_chrome
def test_chrome_event_states_clip_a(page, pages):
    for query, els in [
            ("?event=scale", ["#ruler", "#scaleChipA", "#refcard"]),
            ("?event=takeoff", ["#takeoffLine", "#takeoffLabel"]),
            ("?event=apex", ["#apexRuler", "#apexChip"]),
            ("?event=landing", ["#chronoAxis", "#arcMeasured"]),
            ("?event=verdict", ["#verdict", "#stamp"])]:
        goto(page, pages["clip-a"], query)
        for el in els:
            if el.startswith("#ruler") or el.startswith("#takeoffLine") \
                    or el.startswith("#apexRuler") or el == "#chronoAxis" \
                    or el == "#arcMeasured":
                assertShown(page, el)
            else:
                assert page.is_visible(el), (query, el)


@needs_chrome
def test_chrome_no_page_scroll(page, pages):
    goto(page, pages["clip-a"], "?event=verdict")
    assert page.evaluate(
        "document.scrollingElement.scrollHeight === window.innerHeight")


@needs_chrome
def test_chrome_registration_both_sar(page, pages):
    cases = [(pages["clip-a"], "?frame=250", "hop_a", 250, 321.5 / 352.0),
             (pages["run-7"], "?frame=260", None, 260, 1.0)]
    for pdir, query, seg, frame, sar in cases:
        goto(page, pdir, query)
        if seg is None:
            page.wait_for_function(f"window.__pp.frame() === {frame}",
                                   timeout=PW_TIMEOUT)
        got = page.evaluate("""(frame) => {
          const vbox = document.getElementById('vbox').getBoundingClientRect();
          const k = vbox.width / window.__ppK_DW;
          const m = document.querySelector('[data-testid="track-marker"]');
          if (!m) return null;
          const r = m.getBoundingClientRect();
          return {x: (r.left + r.width / 2 - vbox.left) / k,
                  y: (r.top + r.height / 2 - vbox.top) / (vbox.height / window.__ppK_DH)};
        }""", frame) if False else None
        result = json.loads((pdir / "index.html").read_text().split(
            '<script id="result-data" type="application/json">')[1].split(
            "</script>")[0])
        seg0 = result["segments"][0]
        tp = next(p for p in seg0["track"] if p["frame"] == frame)
        expect = page.evaluate("""(tp) => {
          const vbox = document.getElementById('vbox').getBoundingClientRect();
          const sr = document.getElementById('stage').getBoundingClientRect();
          const m = document.querySelector('[data-testid="track-marker"]');
          const r = m.getBoundingClientRect();
          return {mx: r.left + r.width / 2 - vbox.left,
                  my: r.top + r.height / 2 - vbox.top,
                  vw: vbox.width, vh: vbox.height};
        }""", tp)
        disp_w = (result["video"]["coded_width"]
                  * result["video"]["sample_aspect"]["num"]
                  / result["video"]["sample_aspect"]["den"])
        k = expect["vw"] / disp_w
        kv = expect["vh"] / result["video"]["coded_height"]
        assert abs(expect["mx"] / k - tp["x_px"]) <= 1.0, (pdir, frame)
        assert abs(expect["my"] / kv - tp["y_px"]) <= 1.0, (pdir, frame)


@needs_chrome
def test_chrome_overlay_sizes_and_outline(page, pages):
    goto(page, pages["clip-a"], "?event=apex")
    sizes = page.evaluate("""() => [...document.querySelectorAll(
      '#stageOverlay text')].map(t => ({
        fs: parseFloat(getComputedStyle(t).fontSize),
        title: t.id === 'capT' || t.closest('#caption .t') !== null}))""")
    for s in sizes:
        assert s["fs"] <= 16 or s["title"], s
    d = page.get_attribute("#stageOverlay path", "d")
    assert d is not None and len(d.split("L")) >= 20


@needs_chrome
def test_chrome_no_text_overlap_and_hud_clear(page, pages):
    # 42.5 removed the HUD line and the SAM badge from the visible
    # page; the overlap rule stays, the HUD-clear check goes.
    for query in ["", "?event=scale", "?event=takeoff", "?event=apex",
                  "?event=landing", "?event=verdict"]:
        goto(page, pages["clip-a"], query)
        texts = _visible_stage_texts(page)
        for i, a in enumerate(texts):
            for b in texts[i + 1:]:
                if a["n"] == b["n"]:
                    continue
                if a["stamp"] and b["stamp"]:
                    continue
                overlap = not (a["x"] + a["w"] <= b["x"] + 1
                                 or b["x"] + b["w"] <= a["x"] + 1
                                 or a["y"] + a["h"] <= b["y"] + 1
                                 or b["y"] + b["h"] <= a["y"] + 1)
                assert not overlap, (query, a, b)


@needs_chrome
def test_chrome_labels_inside_stage(page, pages):
    for fixture, queries in [
            ("clip-a", ["?event=scale", "?event=takeoff", "?event=apex",
                        "?event=landing", "?event=verdict"]),
            ("run-7", ["?event=takeoff", "?event=apex", "?event=landing",
                       "?event=verdict"])]:
        for query in queries:
            goto(page, pages[fixture], query)
            info = page.evaluate("""() => {
              const sr = document.getElementById('stage').getBoundingClientRect();
              const bad = [];
              const walker = document.createTreeWalker(
                document.getElementById('stage'), NodeFilter.SHOW_TEXT);
              const nodes = [];
              while (walker.nextNode()) nodes.push(walker.currentNode);
              for (const n of nodes) {
                if (!n.nodeValue || !n.nodeValue.trim()) continue;
                const el = n.parentElement;
                if (el.closest('.katex-mathml')) continue;
                const r = document.createRange();
                r.selectNodeContents(n);
                const b = r.getBoundingClientRect();
                if (b.width < 1 && b.height < 1) continue;
                if (b.left < sr.left - 1 || b.top < sr.top - 1
                    || b.right > sr.right + 1 || b.bottom > sr.bottom + 1)
                  bad.push(n.nodeValue.trim().slice(0, 40));
              }
              const apex = [...document.querySelectorAll(
                '#apexChip,#apexRuler')].filter(
                e => e.getBoundingClientRect().width > 0).length;
              return {bad: bad, apex: apex};
            }""")
            assert info["bad"] == [], (fixture, query, info["bad"])
            if query == "?event=scale":
                assert info["apex"] == 0, (fixture, query)


@needs_chrome
def test_chrome_caption_bright(page, pages):
    goto(page, pages["clip-a"], "?event=apex")
    # Sticky holds show final states at once, but the reveal/count
    # transitions need a beat to settle; wait for that page state.
    page.wait_for_function(
        "document.getAnimations().filter("
        "a => a.playState === 'running').length === 0",
        timeout=PW_TIMEOUT)
    info = page.evaluate("""() => {
      const t = document.querySelector('#caption .t');
      const r = t.getBoundingClientRect();
      const el = document.elementFromPoint(
        r.left + r.width / 2, r.top + r.height / 2);
      let op = 1, e = t;
      while (e) { op *= parseFloat(getComputedStyle(e).opacity || '1'); e = e.parentElement; }
      const anims = document.getAnimations().filter(
        a => a.playState === 'running');
      return {hit: el === t || (el && t.contains(el)), op: op,
              col: getComputedStyle(t).color, anims: anims.length};
    }""")
    assert info["hit"] and info["op"] == 1 and info["anims"] == 0


@needs_chrome
def test_chrome_track_marker_single(page, pages):
    goto(page, pages["clip-a"], "?frame=253")
    n = page.evaluate(
        "document.querySelectorAll('[data-testid=\"track-marker\"]').length")
    assert n == 1


@needs_chrome
def test_chrome_trail_and_strobes(page, pages):
    goto(page, pages["clip-a"], "?frame=260")
    info = page.evaluate("() => ({polys: document.querySelectorAll("
                        "'#stageOverlay polyline').length, "
                        "rings: [...document.querySelectorAll("
                        "'#stageOverlay circle')].length})")
    assert info["polys"] >= 1 and info["rings"] >= 1


@needs_chrome
def test_chrome_rounding_everywhere(page, pages):
    for query in ["", "?event=scale", "?event=apex", "?event=landing",
                  "?event=verdict"]:
        goto(page, pages["clip-a"], query)
        text = page.evaluate("document.body.innerText")
        assert not re.search(r"\d\.\d{4,}", text), query
        assert not re.search(r"\d\.\d{2,}σ", text), query
        assert not re.search(r"\d\.\d{3,} s", text), query
        assert "^" not in text, query


@needs_chrome
def test_chrome_cards_inside_stage(page, pages):
    goto(page, pages["clip-a"], "?event=scale")
    info = page.evaluate("""() => {
      const sr = document.getElementById('stage').getBoundingClientRect();
      const c = document.getElementById('refcard').getBoundingClientRect();
      return {w: c.width / sr.width, h: c.height / sr.height};
    }""")
    assert info["w"] <= 0.40 and info["h"] <= 0.60


@needs_chrome
def test_chrome_chart_and_timeline(page, pages):
    goto(page, pages["clip-a"], "?event=apex")
    info = page.evaluate("""() => ({
      dots: document.querySelectorAll('#chart circle').length,
      arcs: document.querySelectorAll('#arcMeasured,#arc-Moon,#arc-Earth').length,
      tl: document.getElementById('timeline').getBoundingClientRect().height,
      tickfs: parseFloat(getComputedStyle(
        document.querySelector('.tltick span')).fontSize)})""")
    assert info["dots"] >= 5
    assert info["arcs"] >= 2
    assert info["tl"] <= 64
    assert info["tickfs"] >= 11


@needs_chrome
def test_chrome_chart_legend_off_data(page, pages):
    goto(page, pages["clip-a"], "?event=apex")
    info = page.evaluate("""() => {
      const lg = document.getElementById('legendRow').getBoundingClientRect();
      const ch = document.getElementById('chart').getBoundingClientRect();
      const hit = !(lg.bottom <= ch.top || lg.top >= ch.bottom);
      const bad = [...document.querySelectorAll('#chart text')].filter(t => {
        const r = t.getBoundingClientRect();
        return r.left < ch.left - 1 || r.right > ch.right + 1
          || r.top < ch.top - 1 || r.bottom > ch.bottom + 1;
      }).length;
      return {hit: hit, bad: bad};
    }""")
    assert not info["hit"] and info["bad"] == 0


@needs_chrome
def test_chrome_chrono(page, pages):
    goto(page, pages["clip-a"], "?event=landing")
    page.wait_for_function(
        "document.querySelectorAll('[data-testid=\"chrono-copy\"]').length >= 5",
        timeout=PW_TIMEOUT)
    info = page.evaluate("""() => {
      const sr = document.getElementById('stage').getBoundingClientRect();
      const copies = [...document.querySelectorAll(
        '[data-testid="chrono-copy"]')].map(e => ({
        x: +e.getAttribute('x'), y: +e.getAttribute('y'),
        w: +e.getAttribute('width'), h: +e.getAttribute('height')}));
      const ax = document.getElementById('chronoAxis');
      return {copies: copies,
              axisY: ax ? +ax.getAttribute('y1') : null};
    }""")
    assert len(info["copies"]) >= 5
    xs = [c["x"] + c["w"] / 2 for c in info["copies"]]
    assert all(b > a for a, b in zip(xs, xs[1:]))
    for c in info["copies"]:
        assert abs(c["h"] - 135) / 135 <= 0.10
        assert 0 <= c["x"] and c["x"] + c["w"] <= 321.5
    assert info["axisY"] is not None


@needs_chrome
def test_chrome_chrono_heading_clear(page, pages):
    goto(page, pages["clip-a"], "?event=landing")
    clear = page.evaluate("""() => {
      const hd = document.getElementById('chronoHead');
      if (!hd) return false;
      const hr = hd.getBoundingClientRect();
      const dots = [...document.querySelectorAll(
        '#stageOverlay .cdot')].map(
        e => e.getBoundingClientRect());
      for (const r of dots) {
        if (r.width < 1 && r.height < 1) continue;
        if (!(hr.right < r.left - 2 || r.right < hr.left - 2
              || hr.bottom < r.top - 2 || r.bottom < hr.top - 2))
          return false;
      }
      for (const t of document.querySelectorAll('#stageOverlay text')) {
        const r = t.getBoundingClientRect();
        if (r.width < 1) continue;
        if (!(hr.right < r.left || r.right < hr.left
              || hr.bottom < r.top || r.bottom < hr.top)) return false;
      }
      return true;
    }""")
    assert clear


@needs_chrome
def test_chrome_landing_only_chrono(page, pages):
    goto(page, pages["clip-a"], "?event=landing")
    page.wait_for_function(
        "document.querySelectorAll('[data-testid=\"chrono-copy\"]').length >= 5",
        timeout=PW_TIMEOUT)
    # 43.2: each chronophotograph figure keeps its own thin rim
    # (data-testid chrono-rim); the live body outline stays hidden.
    info = page.evaluate("""() => ({
      scale: document.querySelectorAll('#ruler,#scaleChipA').length,
      apex: document.querySelectorAll('#apexRuler,#apexChip').length,
      body: [...document.querySelectorAll(
        '#stageOverlay path[stroke="#4FE3F0"]')].filter(
        e => e.dataset.testid !== 'chrono-rim').length,
      rims: document.querySelectorAll(
        '[data-testid="chrono-rim"]').length,
      rects: [...document.querySelectorAll(
        '#stageOverlay rect')].filter(
        e => e.getAttribute('data-testid') === 'chipbg').length
    })""")
    assert info == {"scale": 0, "apex": 0, "body": 0,
                    "rims": info["rims"], "rects": 0}, info
    assert info["rims"] >= 4, info


@needs_chrome
def test_chrome_verdict(page, pages):
    goto(page, pages["clip-a"], "?event=verdict")
    assert "REALISTIC ON THE MOON" in page.text_content("#stamp")
    assert "g =" in page.text_content("#verdict")
    assert page.text_content("#gauge .gunit").strip() == "g, m/s²"


@needs_chrome
def test_chrome_verdict_fold_summary(page, pages):
    # 47.1: no fold at the verdict. Every listed step is open with all
    # its lines, no step has zero lines, and the column's scroll position
    # is at its end (within 20 px). A heading still expands on click.
    # There is no Summary block repeating the verdict card and no
    # "How this was made" block (43.5).
    goto(page, pages["clip-a"], "?event=verdict")
    page.wait_for_function(
        """() => { const r = document.getElementById('sideInner');
          return Math.abs(r.scrollHeight - r.scrollTop
            - r.clientHeight) <= 20; }""",
        timeout=PW_TIMEOUT)
    info = page.evaluate("""() => {
      const steps = [...document.querySelectorAll('#steps .step')];
      const lines = [...document.querySelectorAll('#steps .ln')];
      const r = document.getElementById('sideInner');
      return {
        steps: steps.length,
        open: steps.filter(d => d.classList.contains('open')).length,
        empty: steps.filter(
          d => d.querySelectorAll('.ln').length === 0).length,
        hidden: lines.filter(l => !l.classList.contains('shown')).length,
        end: Math.abs(r.scrollHeight - r.scrollTop - r.clientHeight),
        nosum: document.getElementById('summaryBlock') === null
          && document.getElementById('sumBody') === null,
        nohow: (document.getElementById('howmade') || {textContent: 'x'})
          .textContent.trim() === ''
      };
    }""")
    assert info["steps"] > 0, info
    assert info["open"] == info["steps"], info
    assert info["empty"] == 0 and info["hidden"] == 0, info
    assert info["end"] <= 20, info
    assert info["nosum"] and info["nohow"], info
    page.click("#step-segment >> nth=0 >> .shead")
    assert page.evaluate(
        "![...document.querySelector('#step-segment')"
        ".classList].includes('open')")
    page.click("#step-segment >> nth=0 >> .shead")
    assert page.evaluate("""() => {
      const d = document.querySelector('#step-segment');
      return d.classList.contains('open')
        && [...d.querySelectorAll('.ln')].every(
          l => l.classList.contains('shown'));
    }""")


@needs_chrome
def test_chrome_gauge_unit_whole(page, pages):
    goto(page, pages["clip-a"], "?event=verdict")
    ok = page.evaluate("""() => {
      const g = document.getElementById('gauge').getBoundingClientRect();
      return [...document.querySelectorAll('#gauge *')].every(e => {
        const r = e.getBoundingClientRect();
        if (r.width < 1 && r.height < 1) return true;
        return r.left >= g.left - 1 && r.right <= g.right + 1
          && r.top >= g.top - 1 && r.bottom <= g.bottom + 1;
      });
    }""")
    assert ok


@needs_chrome
def test_chrome_stamp_kinds(page, pages):
    goto(page, pages["still"], "?event=verdict")
    assert "NOT REALISTIC ON EARTH" in page.text_content("#stamp")
    goto(page, pages["clip-a"], "?event=verdict")
    assert "REALISTIC ON THE MOON" in page.text_content("#stamp")


@needs_chrome
def test_chrome_one_candidate_gauge(page, pages, tmp_path):
    # 31: one tested world renders one gauge marker, one chip, no list.
    import shutil
    work = tmp_path / "one-cand"
    shutil.copytree(ROOT / "fixtures/clip-a", work)
    result = json.loads((work / "result.json").read_text())
    result["worlds"]["candidates"] = [result["worlds"]["candidates"][0]]
    (work / "result.json").write_text(json.dumps(result))
    from src.pagebuild import build_page
    out = tmp_path / "one-cand-page"
    build_page(str(work / "result.json"), str(work / "input/clip.mp4"),
               str(out), str(work / "summary.json"), slug="one-cand")
    goto(page, out, "?event=verdict")
    info = page.evaluate("""() => ({
      marks: document.querySelectorAll('[data-testid="gauge-mark"]').length,
      chips: document.querySelectorAll('[data-testid="sig-chip"]').length,
      excl: document.getElementById('verdict').textContent.includes('why not')
    })""")
    assert info == {"marks": 1, "chips": 1, "excl": False}, info
    goto(page, pages["clip-a"], "?event=verdict")
    info = page.evaluate("""() => ({
      marks: document.querySelectorAll('[data-testid="gauge-mark"]').length,
      chips: document.querySelectorAll('[data-testid="sig-chip"]').length
    })""")
    assert info["marks"] == 2 and info["chips"] == 2, info


@needs_chrome
def test_chrome_maskcheck_chip_whole(page, pages):
    # 43.5: the mask chip (agent prose) shows only with Full
    # calculation on; there it still wraps to at most 3 lines.
    goto(page, pages["clip-a"], "?event=scale")
    assert page.evaluate(
        "document.getElementById('mchkChip') === null")
    page.click("#ckFull")
    info = page.evaluate("""() => {
      const c = document.getElementById('mchkChip');
      if (!c) return null;
      const lines = c.getBoundingClientRect().height
        / parseFloat(getComputedStyle(c).lineHeight);
      return {lines: lines, clipped: c.scrollWidth > c.clientWidth + 1
        || c.scrollHeight > c.clientHeight + 1, title: !!c.title,
              ellipsis: c.textContent.includes('…')};
    }""")
    assert info is not None and info["lines"] <= 3
    assert info["title"] and (not info["clipped"] or info["ellipsis"])


@needs_chrome
def test_chrome_rail_and_mask_thumb(page, pages):
    # 20.2: steps the playhead passed stay open; later steps are title
    # rows; the mask-check picture renders at panel width, <= 150 px tall.
    goto(page, pages["clip-a"], "?event=apex")
    info = page.evaluate("""() => {
      const steps = [...document.querySelectorAll('#steps .step')];
      const open = steps.filter(d => d.classList.contains('open'));
      const cur = document.querySelector('#steps .step.cur .st');
      const rr = cur ? cur.getBoundingClientRect() : null;
      const pr = document.getElementById('sideInner').getBoundingClientRect();
      return {open: open.length, late: steps.filter(
        d => !d.classList.contains('open')).length,
        curInView: rr ? rr.top >= pr.top - 1 && rr.bottom <= pr.bottom + 1 : false};
    }""")
    assert info["open"] > 0 and info["late"] > 0
    assert info["curInView"]
    goto(page, pages["clip-a"], "?event=scale")
    img = page.evaluate("""() => {
      const img = document.getElementById('mchkImg');
      if (!img) return null;
      const r = img.getBoundingClientRect();
      return {nat: img.naturalWidth, rw: r.width, rh: r.height};
    }""")
    assert img is not None
    assert img["nat"] > 0 and img["rw"] >= 200 and img["rh"] <= 150, img


@needs_chrome
def test_chrome_ghost_placement(page, pages):
    # 17.2/42.1: a ghost is the figure's cut-out translated by
    # (ghost - track); its top equals the figure mask top + dy, its
    # height matches the mask. The figure's bbox comes from the build
    # (maskboxes), never from the result's overlay polygons.
    goto(page, pages["clip-a"], "?event=apex")
    ok = page.evaluate("""() => {
      const res = JSON.parse(document.getElementById('result-data').textContent);
      const flags = JSON.parse(
        document.getElementById('page-flags').textContent);
      const sg = res.segments[0], F = sg.frames;
      const tp = sg.track.find(p => p.frame === F.apex);
      const bb = flags.maskboxes[sg.id][String(F.apex)];
      for (const g of sg.ghosts) {
        // landed ghosts hold their last model point at or before apex
        const past = g.points.filter(p => p.frame <= F.apex);
        const gp = past.reduce((a, b) => b.frame >= a.frame ? b : a);
        const el = document.querySelector(
          `[data-testid="ghost"][data-world="${g.world}"]`);
        if (!el || !gp) return false;
        const top = +el.getAttribute('y'), h = +el.getAttribute('height');
        const x = +el.getAttribute('x'), w = +el.getAttribute('width');
        const dy = gp.y_px - tp.y_px;
        if (Math.abs(top - (bb[1] + dy)) > 3) return [top, bb[1] + dy];
        if (Math.abs(h - bb[3]) / bb[3] > 0.10) return [h, bb[3]];
        const overlap = Math.max(0, Math.min(bb[0] + bb[2], x + w)
          - Math.max(bb[0], x));
        if (overlap / bb[2] >= 0.15) return ['overlap', overlap / bb[2]];
      }
      return true;
    }""")
    assert ok is True, ok


@needs_chrome
def test_chrome_ghost_colour_and_ring(page, pages):
    # 20.1: ghosts are tinted silhouettes, no CSS masks. The median
    # blue-minus-red rises in the Earth ghost, red-minus-blue in Moon's.
    import cv2
    import numpy as np

    goto(page, pages["clip-a"], "?event=apex")
    _wait_seek_settled(page, 253)
    page.wait_for_function(
        "document.querySelectorAll('[data-testid=\"ghost\"]').length >= 2",
        timeout=PW_TIMEOUT)
    boxes = page.evaluate("""() => {
      const sr = document.getElementById('stage').getBoundingClientRect();
      const out = {};
      for (const g of document.querySelectorAll('[data-testid="ghost"]')) {
        const r = g.getBoundingClientRect();
        out[g.dataset.world] = {x: r.left - sr.left, y: r.top - sr.top,
                                w: r.width, h: r.height};
      }
      return out;
    }""")
    assert set(boxes) >= {"Earth", "Moon"}, boxes
    on = "/tmp/ppvar/ghost-on.png"
    _stage_shot(page, on)
    page.evaluate("""() => {
      for (const g of document.querySelectorAll(
          '[data-testid="ghost"],[data-testid="impact-ring"]')) {
        g.style.display = 'none';
      }
    }""")
    off = "/tmp/ppvar/ghost-off.png"
    _stage_shot(page, off)
    a = cv2.imread(on).astype(float)
    b = cv2.imread(off).astype(float)
    assert a.shape == b.shape
    ih, iw, _ = a.shape
    sr = page.evaluate("""() => {
      const r = document.getElementById('stage').getBoundingClientRect();
      return {w: r.width, h: r.height};
    }""")
    kx, ky = iw / sr["w"], ih / sr["h"]
    for world, sign in (("Earth", 1), ("Moon", -1)):
        r = boxes[world]
        x0, x1 = int((r["x"] + r["w"] * 0.25) * kx), \
            int((r["x"] + r["w"] * 0.75) * kx)
        y0, y1 = int((r["y"] + r["h"] * 0.25) * ky), \
            int((r["y"] + r["h"] * 0.75) * ky)
        da = np.median(a[y0:y1, x0:x1, 0].astype(float)
                       - a[y0:y1, x0:x1, 2].astype(float))
        db = np.median(b[y0:y1, x0:x1, 0].astype(float)
                       - b[y0:y1, x0:x1, 2].astype(float))
        assert sign * (da - db) >= 10, (world, da, db)
    css = (ROOT / "player/template.html").read_text()
    assert "mask-image" not in css


def _stage_shot(page, path):
    page.locator("#stage").screenshot(path=path)


def _wait_seek_settled(page, frame, fps=29.97):
    # 16.1: HUD, overlays and picture show the same frame — wait until
    # the video has actually sought and the freeze canvas redrew for it.
    page.wait_for_function(
        f"Math.abs(document.querySelector('video').currentTime "
        f"- {frame}/{fps}) < 0.5/{fps} && "
        f"document.getElementById('freeze').dataset.drawn === '{frame}'",
        timeout=PW_TIMEOUT)


@needs_chrome
def test_chrome_no_body_fill(page, pages, tmp_path):
    # 17.1: the outline is fill-free; pixels inside the mask bbox change
    # by < 10/255 with the overlay on vs off.
    import cv2
    import numpy as np

    goto(page, pages["clip-a"], "?event=apex")
    _wait_seek_settled(page, 253)
    page.wait_for_function(
        "document.querySelector('[data-testid=\"track-marker\"]')",
        timeout=PW_TIMEOUT)
    # State wait (34.2): the glowing body outline has a laid-out box,
    # and every entry animation has settled (flash, count-ups) so the
    # on/off screenshots differ only by the overlay itself.
    page.wait_for_function(
        """() => [...document.querySelectorAll(
          '#stageOverlay path[stroke="#4FE3F0"]')].some(
          p => p.getBoundingClientRect().width > 4)""",
        timeout=PW_TIMEOUT)
    page.wait_for_function(
        "document.getAnimations().filter("
        "a => a.playState === 'running').length === 0",
        timeout=PW_TIMEOUT)
    page.wait_for_function(
        "parseFloat(getComputedStyle("
        "document.getElementById('flash')).opacity || '0') === 0",
        timeout=PW_TIMEOUT)
    box = page.evaluate("""() => {
      const sr = document.getElementById('stage').getBoundingClientRect();
      let best = null;
      for (const p of document.querySelectorAll(
          '#stageOverlay path[stroke="#4FE3F0"]')) {
        const r = p.getBoundingClientRect();
        if (r.width < 4 || r.height < 4) continue;
        if (!best || r.width * r.height > best.w * best.h)
          best = {x: r.left - sr.left, y: r.top - sr.top,
                  w: r.width, h: r.height};
      }
      if (!best) return null;
      best.sw = sr.width; best.sh = sr.height;
      return best;
    }""")
    assert box is not None and box["w"] > 4 and box["h"] > 4
    on = str(tmp_path / "on.png")
    _stage_shot(page, on)
    page.evaluate("""() => {
      for (const e of document.querySelectorAll('#stageOverlay')) {
        e.style.display = 'none';
      }
      for (const e of ['#caption', '#refcard', '#verdict', '#chronoHead']) {
        const h = document.querySelector(e);
        if (h) h.style.display = 'none';
      }
    }""")
    off = str(tmp_path / "off.png")
    _stage_shot(page, off)
    a = cv2.imread(on).astype(float)
    b = cv2.imread(off).astype(float)
    assert a.shape == b.shape
    h, w, _ = a.shape
    kx, ky = w / box["sw"], h / box["sh"]
    x0 = int((box["x"] + box["w"] * 0.2) * kx)
    x1 = int((box["x"] + box["w"] * 0.8) * kx)
    y0 = int((box["y"] + box["h"] * 0.2) * ky)
    y1 = int((box["y"] + box["h"] * 0.8) * ky)
    if x1 <= x0 or y1 <= y0:
        pytest.skip("mask box too small for a pixel probe")
    # A concave silhouette's own glowing edge can cross the shrunk box
    # (limbs), so the fill-free check uses the bulk of the interior:
    # a fill or tint would move most pixels, an edge only a minority.
    diff = np.abs(a[y0:y1, x0:x1] - b[y0:y1, x0:x1]).mean(axis=2)
    p70 = float(np.percentile(diff, 70))
    assert p70 < 10.0, p70


@needs_chrome
def test_chrome_chronological_no_rewind(page, pages, tmp_path):
    # 26.1: the ride is chronological even when the scale frame sits
    # between takeoff and apex. State waits only (34.2).
    import shutil
    work = tmp_path / "chrono-work"
    shutil.copytree(ROOT / "fixtures/clip-a", work)
    result = json.loads((work / "result.json").read_text())
    result["scale"]["frame"] = 247
    result["scale"]["extent_px"]["frame"] = 247
    (work / "result.json").write_text(json.dumps(result))
    from src.pagebuild import build_page
    out = tmp_path / "chrono-page"
    build_page(str(work / "result.json"), str(work / "input/clip.mp4"),
               str(out), str(work / "summary.json"), slug="chrono")
    goto(page, out)
    page.evaluate("""() => {
      window.__ppTimes = [document.querySelector('video').currentTime];
      const v = document.querySelector('video');
      const rec = () => window.__ppTimes.push(v.currentTime);
      v.addEventListener('timeupdate', rec);
      window.__ppStop = () => v.removeEventListener('timeupdate', rec);
    }""")
    page.click("#watchBtn")
    wait_hold_seq(page, ["takeoff", "scale", "apex", "landing", "verdict"])
    times = page.evaluate(
        "window.__ppStop(), window.__ppTimes")
    assert times[0] < 0.5, times[:3]
    for a, b in zip(times, times[1:]):
        assert b + 1e-6 >= a, (a, b)


@needs_chrome
def test_chrome_ride_order(page, pages):
    goto(page, pages["clip-a"])
    page.click("#watchBtn")
    wait_hold_seq(page, ["takeoff", "apex", "scale", "landing", "verdict"])
    assert seen_kinds(page)[:5] == [
        "takeoff", "apex", "scale", "landing", "verdict"]


@needs_chrome
def test_chrome_two_segments_timeline_and_ride(page, two_seg_page):
    goto(page, two_seg_page)
    ranges = page.evaluate(
        "document.querySelectorAll('#tlSegs .tlseg').length")
    assert ranges == 2
    page.click("#watchBtn")
    wait_hold_seq(page, ["takeoff", "apex", "scale", "landing", "takeoff",
                         "apex", "landing", "verdict"])


@needs_chrome
def test_chrome_timeline_motions(page, pages):
    # 39 + 43.6: a measured bar is labelled "Jump 1"; an unmeasured
    # bar has no visible label (its description and skip reason live
    # in the tooltip, never a bare "not measured").
    goto(page, pages["clip-a"])
    info = page.evaluate("""() => [...document.querySelectorAll(
      '#tlSegs .tlseg')].map(d => ({t: d.textContent, tip: d.title}))""")
    assert len(info) == 2
    assert info[0]["t"].strip() == "Jump 1", info
    assert info[1]["t"].strip() == "", info
    assert "second hop near the flag" in info[1]["tip"]
    assert "left unmeasured" in info[1]["tip"]


@needs_chrome
def _clocked_page(tmp_path, clock_frame, clock_end, tag="clocked"):
    # A clip-a copy whose clock was measured; the clock calculation
    # step spans clock_frame..clock_end (None for no step frames).
    import shutil
    work = tmp_path / tag
    shutil.copytree(ROOT / "fixtures/clip-a", work)
    result = json.loads((work / "result.json").read_text())
    result["clock"] = {
        "signal_description": "arm swing", "measured_rate_hz": 4.0,
        "measured_rate_sigma_hz": 0.1, "interpretation": "step",
        "band_hz": [3.0, 5.0], "natural_range_hz": [1.0, 3.0],
        "natural_range_source": {"url": "https://example.com/x",
                                "quote": "q"},
        "implied_stretch": 1.0, "implied_stretch_sigma": 0.0,
        "reads_normal": False}
    for st in result["calculation_steps"]:
        if st["id"] == "clock":
            st["frame"] = clock_frame
            st["frame_end"] = clock_end
    (work / "result.json").write_text(json.dumps(result))
    from src.pagebuild import build_page
    out = tmp_path / (tag + "-page")
    build_page(str(work / "result.json"), str(work / "input/clip.mp4"),
               str(out), str(work / "summary.json"), slug=tag)
    return out


@needs_chrome
def test_chrome_timeline_bar_clock_rate(page, pages, tmp_path):
    # 39, 40 + 43.6: the clock's rate goes on one bar only — the
    # motion bar whose frames overlap the clock calculation step's
    # frames. Bar text never carries the rate (16 chars > 12), so it
    # rides in that bar's tooltip. With no such step, no bar shows it.
    out = _clocked_page(tmp_path, 340, 376)
    goto(page, out)
    info = page.evaluate("""() => [...document.querySelectorAll(
      '#tlSegs .tlseg')].map(d => ({t: d.textContent, tip: d.title}))""")
    assert len(info) == 2
    assert all("step rate" not in d["t"] for d in info), info
    rated = [d for d in info if "step rate 4.0 Hz" in d["tip"]]
    assert len(rated) == 1 and rated[0] is info[1], info
    out2 = _clocked_page(tmp_path, None, None, tag="unclocked")
    goto(page, out2)
    info2 = page.evaluate("""() => [...document.querySelectorAll(
      '#tlSegs .tlseg')].map(d => ({t: d.textContent, tip: d.title}))""")
    assert all("step rate" not in d["t"] and "step rate" not in d["tip"]
               for d in info2), info2


@needs_chrome
def test_chrome_hold_fires_after_frame_jump(page, pages):
    goto(page, pages["clip-a"], "?frame=200")
    page.evaluate("window.scrollTo(0,0)")
    page.keyboard.press(" ")
    wait_hold(page, "takeoff")


@needs_chrome
def test_chrome_space_and_camera(page, pages):
    # 18.8/42.3: space toggles playback; the timed apex hold pushes
    # the camera in. Space during a hold pauses it (42.3 replaces the
    # hold-skip rule); the next press continues the hold.
    goto(page, pages["clip-a"], "?frame=232&autoplay=0")
    page.keyboard.press(" ")
    page.wait_for_function(
        "window.__pp.hold() && window.__pp.hold().kind === 'apex'"
        " && window.__pp.hold().t >= 1",
        timeout=120000)
    # 43.3: no hold zoom makes one source pixel larger than 2.5
    # screen pixels — on clip-a every hold stays at 1.03, and the
    # outline's on-screen height scales exactly with the camera.
    z = page.evaluate("window.__pp.camera().z")
    assert abs(z - 1.03) <= 0.02, z
    ratio = page.evaluate("""() => {
      const p = document.querySelector(
        '#stageOverlay path[stroke="#4FE3F0"]');
      const r = p.getBoundingClientRect();
      const bb = p.getBBox();
      const vb = document.getElementById('vbox');
      const k0 = vb.clientWidth / 321.5;
      return r.height / (bb.height * k0);
    }""")
    assert abs(ratio - z) / z <= 0.05, (ratio, z)
    assert page.evaluate(
        "window.__pp.hold() && window.__pp.hold().kind === 'apex'")
    page.keyboard.press(" ")
    page.wait_for_function(
        "document.querySelector('video').paused === true",
        timeout=PW_TIMEOUT)
    bar0 = page.evaluate(
        "document.getElementById('holdbar').style.width")
    time.sleep(1.0)
    bar1 = page.evaluate(
        "document.getElementById('holdbar').style.width")
    assert bar0 == bar1, (bar0, bar1)
    page.keyboard.press(" ")
    page.wait_for_function("window.__pp.hold() === null",
                           timeout=PW_TIMEOUT)
    page.wait_for_function(
        "document.querySelector('video').paused === false",
        timeout=PW_TIMEOUT)
    goto(page, pages["clip-a"], "?frame=253")
    wait_frame(page, 253)


@needs_chrome
def test_chrome_katex_mathml(page, pages):
    goto(page, pages["clip-a"], "?event=apex")
    try:
        page.wait_for_function("window.katex !== undefined",
                               timeout=PW_TIMEOUT)
    except Exception:
        pytest.skip("KaTeX CDN unreachable")
    # State wait (34.2): KaTeX typesets every formula once at build; the
    # MathML copy must stay at most 1x1 px after it runs.
    page.wait_for_function(
        "document.querySelectorAll('.fx[data-tex] .katex').length > 0",
        timeout=PW_TIMEOUT)
    info = page.evaluate("""() => ({
      js: [...document.querySelectorAll('script')].filter(
        s => (s.src || '').includes('katex.min.js')).length,
      css: [...document.querySelectorAll('link')].filter(
        l => (l.href || '').includes('katex.min.css')).length,
      big: [...document.querySelectorAll(
        '.katex-mathml')].filter(e => { const r = e.getBoundingClientRect();
          return r.width > 1 || r.height > 1; }).length})""")
    assert info["js"] == 1 and info["css"] == 1 and info["big"] == 0


@needs_chrome
def test_chrome_run7_verdict_kind(page, pages):
    goto(page, pages["run-7"], "?event=verdict")
    assert "UNDETERMINED" in page.text_content("#stamp")


@needs_chrome
def test_chrome_smooth_outline_no_right_angles(page, pages):
    goto(page, pages["clip-a"], "?event=apex")
    bad = page.evaluate("""() => {
      const d = document.querySelector(
        '#stageOverlay path[stroke="#4FE3F0"]').getAttribute('d');
      const pts = d.replace(/[MZ]/g, '').split('L').map(
        s => s.split(',').map(Number));
      for (let i = 0; i + 2 < pts.length; i++) {
        const v1 = [pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]];
        const v2 = [pts[i + 2][0] - pts[i + 1][0], pts[i + 2][1] - pts[i + 1][1]];
        const l1 = Math.hypot(...v1), l2 = Math.hypot(...v2);
        if (l1 > 0.5 && l2 > 0.5) {
          const c = Math.abs(v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2);
          const deg = Math.acos(Math.min(1, Math.max(-1, c))) * 180 / Math.PI;
          if (Math.abs(deg - 90) <= 5) return true;
        }
      }
      return false;
    }""")
    assert not bad


@needs_chrome
def test_chrome_cutouts_4x(page, pages):
    # 25.2: cut-out images are at least 3.5x their mask bbox, in pixels.
    # §45: cut-outs live in the page as data URLs only.
    import base64

    import cv2
    import numpy as np

    flags = json.loads((pages["clip-a"] / "index.html").read_text().split(
        '<script id="page-flags" type="application/json">')[1].split(
        "</script>")[0])
    cuts = flags["cutouts"]["hop_a"]
    assert len(cuts) >= 5
    for c in cuts:
        assert "file" not in c, c.get("frame")
        raw = base64.b64decode(c["data"].split(",", 1)[1])
        img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8),
                           cv2.IMREAD_UNCHANGED)
        assert img is not None, c["frame"]
        assert img.shape[1] >= 3.5 * c["bbox"][2], c
        assert img.shape[0] >= 3.5 * c["bbox"][3], c


@needs_chrome
def test_chrome_trajectory_below_hud(page, pages):
    goto(page, pages["clip-a"], "?event=landing")
    ok = page.evaluate("""() => {
      const hb = document.getElementById('hud').getBoundingClientRect().bottom;
      const sr = document.getElementById('stage').getBoundingClientRect();
      const pts = (document.getElementById('arcMeasured')
        .getAttribute('points') || '').split(' ');
      const vb = document.getElementById('vbox').getBoundingClientRect();
      const res = JSON.parse(
        document.getElementById('result-data').textContent);
      const DH = res.video.coded_height;
      return pts.every(s => { const y = +s.split(',')[1];
        return vb.top + (y / DH) * vb.height >= hb + 6 - 1; });
    }""")
    assert ok


@needs_chrome
def test_chrome_rail_follows_playhead(page, pages):
    goto(page, pages["clip-a"], "?event=apex")
    info = page.evaluate("""() => {
      const rail = document.getElementById('sideInner').getBoundingClientRect();
      const cur = document.querySelector('#steps .step.cur .shead');
      if (!cur) return {ok: false};
      const r = cur.getBoundingClientRect();
      const h = document.scrollingElement.scrollHeight
        === window.innerHeight;
      return {ok: r.bottom <= rail.bottom + 1 && r.top >= rail.top - 1, h: h};
    }""")
    assert info["ok"] and info["h"]


@needs_chrome
def test_chrome_rail_calm(page, pages):
    # 28: during plain playback with no line due, the rail (built once)
    # shows zero text/child-list mutations. The 3 s window is the
    # measurement itself, started only once playback is confirmed.
    goto(page, pages["clip-a"], "?frame=100")
    page.keyboard.press(" ")
    page.wait_for_function(
        "document.querySelector('video').paused === false",
        timeout=PW_TIMEOUT)
    page.wait_for_function("window.__pp.frame() > 110", timeout=PW_TIMEOUT)
    n = page.evaluate("""() => new Promise(res => {
      let count = 0;
      const mo = new MutationObserver(muts => { count += muts.length; });
      mo.observe(document.getElementById('steps'),
        {childList: true, subtree: true, characterData: true});
      setTimeout(() => { mo.disconnect(); res(count); }, 3000);
    })""")
    assert n == 0, n


@needs_chrome
def test_chrome_rail_whole_ride_mutations(page, pages):
    # 28: over the whole ride, child-list mutations number at most the
    # line count (classes toggle; the rail is never rebuilt).
    goto(page, pages["clip-a"])
    page.evaluate("""() => {
      window.__ppMuts = 0;
      const mo = new MutationObserver(
        muts => { window.__ppMuts += muts.filter(
          m => m.type === 'childList').length; });
      mo.observe(document.getElementById('steps'),
        {childList: true, subtree: true});
      window.__ppStopMuts = () => mo.disconnect();
    }""")
    page.click("#watchBtn")
    wait_hold_seq(page, ["takeoff", "apex", "scale", "landing", "verdict"])
    n = page.evaluate("window.__ppStopMuts(), window.__ppMuts")
    lines = page.evaluate(
        "document.querySelectorAll('#steps .ln').length")
    assert n <= lines, (n, lines)


@needs_chrome
def test_chrome_unmeasured_revealed_before_verdict(page, pages):
    # 47.2: motions that were not measured are not steps in the column;
    # they show only with Full calculation on. With Full on, the
    # unmeasured second motion's line (frames 340-376) is revealed
    # before the verdict hold (27, 47.1).
    goto(page, pages["clip-a"], "?event=verdict")
    assert page.evaluate(
        "document.getElementById('step-unmeas_340') === null")
    page.click("#ckFull")
    shown = page.evaluate(
        "document.querySelector('#step-unmeas_340 .ln.shown') !== null")
    assert shown


@needs_chrome
def test_chrome_refcard_clean_end(page, pages):
    goto(page, pages["clip-a"], "?event=scale")
    info = page.evaluate("""() => {
      const c = document.getElementById('refcard');
      const r = c.getBoundingClientRect();
      const st = getComputedStyle(c);
      return {clipped: c.scrollHeight > c.clientHeight + 1,
              ellipsis: c.textContent.includes('…')};
    }""")
    assert not info["clipped"] or info["ellipsis"]


@needs_chrome
def test_chrome_stamp_fits_long_reason(browser, pages):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    goto(pg, pages["run-7"], "?event=verdict")
    info = pg.evaluate("""() => {
      const s = document.getElementById('stamp');
      const sub = s.querySelector('.s');
      // State-based line count (34.2): rendered line boxes of the
      // sub-line, never wall-clock or font-metric guesses.
      const r = document.createRange();
      r.selectNodeContents(sub);
      return {w: s.scrollWidth <= s.clientWidth + 1,
              h: s.scrollHeight <= s.clientHeight + 1,
              lines: r.getClientRects().length};
    }""")
    assert info["w"] and info["h"] and info["lines"] <= 2, info
    pg.close()


@needs_chrome
def test_chrome_video_seeks_with_state(page, pages):
    goto(page, pages["clip-a"], "?event=apex")
    ok = page.evaluate("""() => new Promise(res => {
      const v = document.querySelector('video');
      const want = 253 / 29.97;
      const check = () => res(Math.abs(v.currentTime - want) < 0.5 / 29.97
        && window.__pp.frame() === 253);
      if (v.readyState >= 1 && Math.abs(v.currentTime - want) < 0.02)
        return check();
      v.addEventListener('seeked', check, {once: true});
      setTimeout(() => res(false), 15000);
    })""")
    assert ok


@needs_chrome
def test_chrome_freeze_canvas_matches_video_aspect(page, pages):
    goto(page, pages["clip-a"], "?event=apex")
    ok = page.evaluate("""() => {
      const v = document.querySelector('video'), c = document.getElementById('freeze');
      return Math.abs(c.width / c.height - v.videoWidth / v.videoHeight) < 0.01;
    }""")
    assert ok


@needs_chrome
def test_chrome_freeze_frame_fills_canvas(page, pages):
    goto(page, pages["clip-a"], "?event=apex")
    page.wait_for_function(
        "document.getElementById('freeze').dataset.drawn === '253'",
        timeout=PW_TIMEOUT)
    assert True


@needs_chrome
def test_chrome_picture_covers_at_events(page, pages):
    for query in ["?event=takeoff", "?event=apex", "?event=landing"]:
        goto(page, pages["clip-a"], query)
        ok = page.evaluate("""() => {
          const s = document.getElementById('stage').getBoundingClientRect();
          const v = document.getElementById('vbox').getBoundingClientRect();
          const z = window.__pp.camera().z;
          return v.left <= s.left + 1 && v.top <= s.top + 1
            && v.right >= s.right - 1 && v.bottom >= s.bottom - 1 && z >= 1;
        }""")
        assert ok, query


@needs_chrome
def test_chrome_takeoff_label_on_line(page, pages):
    # 35.1: the label sits above the line's right end on a solid
    # backing, never crossed by the line.
    goto(page, pages["clip-a"], "?event=takeoff")
    ok = page.evaluate("""() => {
      const line = document.getElementById('takeoffLine');
      const t = document.getElementById('takeoffLabel');
      const sr = document.getElementById('stage').getBoundingClientRect();
      const lr = line.getBoundingClientRect(), tr = t.getBoundingClientRect();
      return tr.bottom <= lr.top + 1
        && Math.abs(tr.right - lr.right) <= 16
        && tr.left >= sr.left - 1 && tr.right <= sr.right + 1
        && tr.top >= sr.top - 1 && tr.bottom <= sr.bottom + 1;
    }""")
    assert ok


@needs_chrome
def test_chrome_portrait_freeze_frame_box(browser, pages):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    goto(pg, pages["clip-a"], "?event=takeoff")
    ok = pg.evaluate("""() => {
      const v = document.querySelector('video').getBoundingClientRect();
      const c = document.getElementById('freeze').getBoundingClientRect();
      return Math.abs(v.left - c.left) < 1 && Math.abs(v.top - c.top) < 1
        && Math.abs(v.width - c.width) < 1;
    }""")
    assert ok
    pg.close()


# --- 32: range checks on the stage and in the rail ---------------------

@needs_chrome
def test_chrome_still_range_bars_and_stamp(page, pages):
    # The still-range fixture renders two range bars (one inside, one
    # outside in red with its sigma distance) and the NOT REALISTIC
    # stamp; no gravity axis, no chart, no console errors.
    errors = []
    # Resource-load failures (the KaTeX CDN) are environmental; JS
    # errors are template defects.
    page.on("console", lambda m: errors.append(m.text)
            if m.type == "error" and "katex" not in m.text.lower()
            and "failed to load resource" not in m.text.lower()
            and "net::" not in m.text.lower() else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    goto(page, pages["still"], "?event=verdict")
    bars = page.evaluate(
        "document.querySelectorAll('[data-testid=\"rangebar\"]').length")
    assert bars == 2, bars
    outside = page.evaluate("""() => [...document.querySelectorAll(
      '[data-testid="rangebar"] .side')].map(
      e => e.textContent)""")
    assert len(outside) == 1 and "3.0σ" in outside[0] \
        and "above max" in outside[0], outside
    assert "NOT REALISTIC ON EARTH" in page.text_content("#stamp")
    assert page.evaluate(
        "document.querySelectorAll('#gauge').length") == 0
    assert page.evaluate(
        "getComputedStyle(document.getElementById("
        "'chartBlock')).display") == "none"
    assert errors == [], errors
    goto(page, pages["still"], "?event=range_finger_hand_ratio")
    assert page.evaluate(
        "document.querySelectorAll('[data-testid=\"range-chip\"]')"
        ".length") >= 1
    assert page.evaluate(
        "document.getElementById('verdict').style.display") == "none"


@needs_chrome
def test_chrome_moon_range_bar_and_chart(page, pages, moon_range_page):
    # The Moon fixture still renders as before, plus its one range bar.
    goto(page, moon_range_page, "?event=verdict")
    assert "REALISTIC ON THE MOON" in page.text_content("#stamp")
    assert page.evaluate(
        "document.querySelectorAll('[data-testid=\"rangebar\"]')"
        ".length") == 1
    goto(page, moon_range_page, "?event=range_hand_ratio")
    assert page.evaluate(
        "document.querySelectorAll('[data-testid=\"range-chip\"]')"
        ".length") >= 1


@needs_chrome
def test_chrome_range_rail_step(page, pages):
    goto(page, pages["still"])
    titles = page.evaluate(
        "document.getElementById('steps').textContent")
    assert "palm / hand length" in titles
    assert "finger / hand length" in titles


def test_chrome_contract_version_matches_src(pages):
    from src.contract import CONTRACT_VERSION

    flags = json.loads((pages["clip-a"] / "index.html").read_text().split(
        '<script id="page-flags" type="application/json">')[1].split(
        "</script>")[0])
    assert flags["contract_version"] == CONTRACT_VERSION


# --- 33: the first screen says what we check --------------------------

@needs_chrome
def test_chrome_intro_wonder(page, pages, tmp_path):
    # 43.7: one line of what is checked (the first check row); the
    # Claim line shows only with Full calculation on.
    goto(page, pages["clip-a"])
    intro = page.text_content("#intro")
    assert "What we check:" in intro
    assert "measure the hop's apparent gravity" in intro
    assert "Claim:" not in intro
    page.click("#ckFull")
    assert "Claim:" in page.text_content("#intro")
    assert "the astronaut hops far too high for Earth" in \
        page.text_content("#intro")
    import shutil
    work = tmp_path / "no-wonder"
    shutil.copytree(ROOT / "fixtures/clip-a", work)
    result = json.loads((work / "result.json").read_text())
    result["first_look"]["wonder"] = None
    (work / "result.json").write_text(json.dumps(result))
    from src.pagebuild import build_page
    out = tmp_path / "no-wonder-page"
    build_page(str(work / "result.json"), str(work / "input/clip.mp4"),
               str(out), str(work / "summary.json"), slug="no-wonder")
    goto(page, out)
    intro2 = page.text_content("#intro")
    assert "Claim:" not in intro2
    assert "What we check:" not in intro2


# --- 34: no hold is skipped --------------------------------------------

@needs_chrome
def test_chrome_throttled_ride_keeps_all_holds(page, two_seg_page):
    # Animation frames throttled to >= 250 ms each: every crossed event
    # still fires in frame order, all eight holds.
    goto(page, two_seg_page)
    page.evaluate("""() => {
      const orig = window.requestAnimationFrame.bind(window);
      window.requestAnimationFrame = (cb) => orig((t) => {
        const end = performance.now() + 250;
        while (performance.now() < end);
        cb(t);
      });
    }""")
    page.click("#watchBtn")
    wait_hold_seq(page, ["takeoff", "apex", "scale", "landing", "takeoff",
                         "apex", "landing", "verdict"])
    assert seen_kinds(page)[:8] == ["takeoff", "apex", "scale", "landing",
                                    "takeoff", "apex", "landing", "verdict"]


def test_no_fixed_delay_sync():
    # 34.2: browser tests wait on page state, never on wall-clock time.
    for name in ("test_player_chrome.py", "test_player_engines.py"):
        text = (ROOT / "tests/player" / name).read_text()
        assert "page.wait_for" + "_timeout(" not in text, name
        assert "pg.wait_for" + "_timeout(" not in text, name


# --- 37: end labels read each drawn curve's own zero-crossing -----------

_CHART_GEOM_JS = """() => ({
  texts: [...document.querySelectorAll('#chart text')].map(t => {
    const r = t.getBoundingClientRect();
    return {text: t.textContent, x: +t.getAttribute('x'),
            y: +t.getAttribute('y'), anchor: t.getAttribute('text-anchor'),
            rx: r.left, ry: r.top, rw: r.width, rh: r.height};
  }),
  arcs: Object.fromEntries([...document.querySelectorAll(
    '#chart polyline[id]')].map(
    p => [p.id, p.getAttribute('points')])),
  dots: [...document.querySelectorAll('#chart circle')].map(c => ({
    x: +c.getAttribute('cx'), y: +c.getAttribute('cy')}))
})"""


def _parse_pts(s):
    pts = []
    for pair in s.strip().split():
        x, y = pair.split(",")
        pts.append((float(x), float(y)))
    return pts


def _chart_calibration(texts):
    # ViewBox coords: x ticks are exact X(t); y ticks sit 3 px below Y(v)
    # (the template's tick layout), so the height-0 line is tick("0") - 3.
    xt = [(float(t["x"]), float(t["text"]))
          for t in texts
          if t["anchor"] == "middle" and re.fullmatch(r"-?\d+\.\d", t["text"] or "")]
    assert len(xt) >= 2, texts
    (x1, v1), (x2, v2) = xt[0], xt[-1]
    y0 = [t for t in texts if t["anchor"] == "end" and t["text"] == "0"]
    assert y0, [t["text"] for t in texts]
    return (lambda x: v1 + (x - x1) * (v2 - v1) / (x2 - x1)), y0[0]["y"] - 3


def _drawn_last(pts, t_of_x):
    # The drawn polyline's own last point (its landing), in takeoff time.
    return t_of_x(pts[-1][0])


@needs_chrome
def test_chrome_chart_fit_passes_through_dots(page, pages):
    # 37: the white fit curve passes through the measured dots: RMS
    # vertical distance under 4 chart px on clip-a.
    goto(page, pages["clip-a"], "?event=landing")
    wait_hold(page, "landing")
    info = page.evaluate(_CHART_GEOM_JS)
    fit = _parse_pts(info["arcs"]["arcFit"])
    assert len(fit) > 1
    assert len(info["dots"]) >= 10
    se, n = 0.0, 0
    for d in info["dots"]:
        seg = next(((a, b) for a, b in zip(fit, fit[1:])
                    if (a[0] - d["x"]) * (b[0] - d["x"]) <= 0 and b[0] > a[0]),
                   None)
        if seg is None:
            continue
        (x1, y1), (x2, y2) = seg
        f = (d["x"] - x1) / (x2 - x1)
        se += (y1 + f * (y2 - y1) - d["y"]) ** 2
        n += 1
    assert n >= 10, n
    assert math.sqrt(se / n) < 4, math.sqrt(se / n)


@needs_chrome
def test_chrome_chart_end_labels_zero_crossing(page, pages, moon22_page):
    # 38 (replaces 37's zero-crossing): every world end label is
    # positive and equals, within 0.02 s, its drawn polyline's own
    # last-point time (its landing); the chart's height range covers
    # every drawn point, so none lies outside the chart area. (The
    # test keeps its recorded name; the convention it checks changed.)
    for page_dir in (pages["clip-a"], moon22_page):
        goto(page, page_dir, "?event=landing")
        wait_hold(page, "landing")
        info = page.evaluate(_CHART_GEOM_JS)
        t_of_x, _ = _chart_calibration(info["texts"])
        labs = [t for t in info["texts"]
                if re.fullmatch(r"(Moon|Earth|Mars) -?\d+\.\d\d s( →)?",
                                t["text"] or "")]
        assert len(labs) >= 2, [t["text"] for t in info["texts"]]
        seen = {}
        for lab in labs:
            m = re.fullmatch(r"(Moon|Earth|Mars) (-?\d+\.\d\d) s( →)?",
                              lab["text"])
            world, num, arrow = m.group(1), float(m.group(2)), m.group(3)
            assert num > 0, lab["text"]
            pts = _parse_pts(info["arcs"]["arc-" + world])
            expect = _drawn_last(pts, t_of_x)
            assert abs(num - expect) <= 0.02, (lab["text"], expect)
            seen[world] = num
        clip = [t for t in info["texts"]
                if re.fullmatch(r"in the clip \d+\.\d\d s", t["text"] or "")]
        assert len(clip) == 1, [t["text"] for t in info["texts"]]
        clip_t = float(clip[0]["text"].split()[3])
        assert clip_t > 0
        last_t = max(t_of_x(d["x"]) for d in info["dots"])
        assert abs(clip_t - last_t) <= 0.02, (clip_t, last_t)
        # The Moon ghost ends at the landing level: close to the clip.
        assert abs(seen["Moon"] - clip_t) <= 0.05, seen
        # Every drawn point lies inside the chart's plot area.
        geom = page.evaluate("""() => {
          const c = document.getElementById('chart');
          const vb = c.viewBox.baseVal;
          return {w: vb.width, h: vb.height};
        }""")
        pl, pr, pt, pb = 44, 14, 8, 52
        W, H = geom["w"], geom["h"]
        outside = []
        for d in info["dots"]:
            if not (pl - 1 <= d["x"] <= W - pr + 1
                    and pt - 1 <= d["y"] <= H - pb + 1):
                outside.append(("dot", d))
        for aid, pts in info["arcs"].items():
            for x, y in _parse_pts(pts):
                if not (pl - 1 <= x <= W - pr + 1
                        and pt - 1 <= y <= H - pb + 1):
                    outside.append((aid, x, y))
        assert outside == [], outside[:5]


@needs_chrome
def test_chrome_chart_labels_disjoint(page, pages, moon22_page):
    # 37: no two chart labels intersect (the close Moon/clip pair included).
    for page_dir in (pages["clip-a"], moon22_page):
        goto(page, page_dir, "?event=landing")
        wait_hold(page, "landing")
        info = page.evaluate(_CHART_GEOM_JS)
        rects = [(t["rx"], t["ry"], t["rw"], t["rh"], t["text"])
                 for t in info["texts"] if t["rw"] > 0 and t["rh"] > 0]
        clashes = []
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                if not (a[0] + a[2] <= b[0] + 1 or b[0] + b[2] <= a[0] + 1
                        or a[1] + a[3] <= b[1] + 1 or b[1] + b[3] <= a[1] + 1):
                    clashes.append((a[4], b[4]))
        assert clashes == [], clashes


# --- 35: nothing overlaps, the phone shows the verdict -----------------

# Rectangles measured in the page: every visible stage text line-box,
# every box inside the stage, and every stage line/tick against every
# stage svg label (segment-vs-rect, not bbox-vs-bbox).
_LAYOUT_JS = """() => {
  const sr = document.getElementById('stage').getBoundingClientRect();
  const rel = (r) => ({x: r.left - sr.left, y: r.top - sr.top,
                       w: r.width, h: r.height});
  const introHidden = getComputedStyle(
    document.getElementById('intro')).display === 'none';
  const texts = [];
  const walker = document.createTreeWalker(
    document.getElementById('stage'), NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach((n, idx) => {
    if (!n.nodeValue || !n.nodeValue.trim()) return;
    const el = n.parentElement;
    if (!el || el.closest('script,style')) return;
    if (el.closest('.katex-mathml')) return;
    if (introHidden && el.closest('#intro')) return;
    const stamp = !!el.closest('#stamp');
    const r = document.createRange();
    r.selectNodeContents(n);
    for (const b of r.getClientRects()) {
      if (b.width < 1 && b.height < 1) continue;
      const q = rel(b);
      texts.push({t: n.nodeValue.trim().slice(0, 40), x: q.x, y: q.y,
                  w: q.w, h: q.h, n: idx, stamp: stamp});
    }
  });
  const overlaps = [];
  texts.forEach((a, i) => {
    texts.slice(i + 1).forEach((b) => {
      if (a.n === b.n || (a.stamp && b.stamp)) return;
      if (!(a.x + a.w <= b.x + 1 || b.x + b.w <= a.x + 1 ||
            a.y + a.h <= b.y + 1 || b.y + b.h <= a.y + 1))
        overlaps.push(a.t + ' <> ' + b.t);
    });
  });
  const outside = texts.filter((t) =>
    t.x < -1 || t.y < -1 || t.x + t.w > sr.width + 1 ||
    t.y + t.h > sr.height + 1).map((t) => t.t);
  const ov = document.getElementById('ov');
  const labels = [...document.querySelectorAll(
    '#stageOverlay text')].map((t) => {
    const q = rel(t.getBoundingClientRect());
    return {t: (t.textContent || '').trim().slice(0, 40), x: q.x, y: q.y,
            w: q.w, h: q.h};
  }).filter((l) => l.w >= 1 && l.h >= 1);
  const scr = (el, x, y) => {
    const p = ov.createSVGPoint();
    p.x = x; p.y = y;
    const q = p.matrixTransform(el.getScreenCTM());
    return [q.x - sr.left, q.y - sr.top];
  };
  const hits = (x1, y1, x2, y2, r) => {
    const inR = (x, y) => x > r.x - 1 && x < r.x + r.w + 1 &&
      y > r.y - 1 && y < r.y + r.h + 1;
    if (inR(x1, y1) || inR(x2, y2)) return true;
    const o = (ax, ay, bx, by, cx, cy) =>
      (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
    const xx = (p1x, p1y, p2x, p2y, p3x, p3y, p4x, p4y) => {
      const d1 = o(p3x, p3y, p4x, p4y, p1x, p1y);
      const d2 = o(p3x, p3y, p4x, p4y, p2x, p2y);
      const d3 = o(p1x, p1y, p2x, p2y, p3x, p3y);
      const d4 = o(p1x, p1y, p2x, p2y, p4x, p4y);
      return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
        ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
    };
    const E = [[r.x - 1, r.y - 1, r.x + r.w + 1, r.y - 1],
      [r.x + r.w + 1, r.y - 1, r.x + r.w + 1, r.y + r.h + 1],
      [r.x + r.w + 1, r.y + r.h + 1, r.x - 1, r.y + r.h + 1],
      [r.x - 1, r.y + r.h + 1, r.x - 1, r.y - 1]];
    return E.some((e) => xx(x1, y1, x2, y2, e[0], e[1], e[2], e[3]));
  };
  const segs = [];
  for (const e of document.querySelectorAll('#stageOverlay line')) {
    const a = scr(e, +e.getAttribute('x1'), +e.getAttribute('y1'));
    const b = scr(e, +e.getAttribute('x2'), +e.getAttribute('y2'));
    segs.push({id: e.id || 'line', a: a, b: b});
  }
  for (const e of document.querySelectorAll('#stageOverlay polyline')) {
    const pts = (e.getAttribute('points') || '').trim().split(/\\s+/)
      .map((s) => s.split(',').map(Number)).map((p) => scr(e, p[0], p[1]));
    for (let i = 0; i + 1 < pts.length; i++)
      segs.push({id: e.id || 'polyline', a: pts[i], b: pts[i + 1]});
  }
  const dots = [...document.querySelectorAll(
    '#stageOverlay circle')].map((e) => {
    const q = rel(e.getBoundingClientRect());
    return {id: e.id || e.getAttribute('data-testid') || 'circle',
            x: q.x, y: q.y, w: q.w, h: q.h};
  }).filter((c) => c.w >= 1 && c.h >= 1);
  const crossed = [];
  for (const lb of labels) {
    for (const s of segs) {
      if (hits(s.a[0], s.a[1], s.b[0], s.b[1], lb))
        crossed.push(s.id + ' x ' + lb.t);
    }
    for (const d of dots) {
      if (!(lb.x + lb.w <= d.x + 1 || d.x + d.w <= lb.x + 1 ||
            lb.y + lb.h <= d.y + 1 || d.y + d.h <= lb.y + 1))
        crossed.push(d.id + ' x ' + lb.t);
    }
  }
  return {overlaps: overlaps, outside: outside, crossed: crossed};
}"""


@needs_chrome
def test_chrome_stage_labels_layout(browser, pages):
    # 35 rule 1+3: at 1440x900 and 390x844, at every event, no two
    # visible stage labels intersect, every label lies inside the
    # stage, and no line or tick crosses a label.
    for vp in ({"width": 1440, "height": 900},
               {"width": 390, "height": 844}):
        pg = browser.new_page(viewport=vp)
        try:
            for ev in ["scale", "takeoff", "apex", "landing", "verdict"]:
                goto(pg, pages["clip-a"], f"?event={ev}")
                wait_hold(pg, ev)
                info = pg.evaluate(_LAYOUT_JS)
                assert info["overlaps"] == [], (vp, ev, info["overlaps"])
                assert info["outside"] == [], (vp, ev, info["outside"])
                assert info["crossed"] == [], (vp, ev, info["crossed"])
        finally:
            pg.close()


@needs_chrome
def test_chrome_phone_verdict_stamp(browser, pages):
    # 35 rule 2+3: on a phone the verdict card is below the video and
    # the stamp is wholly inside the viewport, covered by nothing.
    pg = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        goto(pg, pages["clip-a"], "?event=verdict")
        wait_hold(pg, "verdict")
        info = pg.evaluate("""() => {
          const vw = window.innerWidth, vh = window.innerHeight;
          const card = document.getElementById('verdict').getBoundingClientRect();
          const stage = document.getElementById('stage').getBoundingClientRect();
          const s = document.getElementById('stamp').getBoundingClientRect();
          const el = document.elementFromPoint(
            s.left + s.width / 2, s.top + s.height / 2);
          return {below: card.top >= stage.bottom - 1,
                  stamp: {l: s.left, t: s.top, r: s.right, b: s.bottom},
                  vw: vw, vh: vh,
                  onTop: el === s || (el && el.closest('#stamp') !== null)};
        }""")
        assert info["below"], info
        st = info["stamp"]
        assert st["l"] >= -1 and st["t"] >= -1 and st["r"] <= info["vw"] + 1 \
            and st["b"] <= info["vh"] + 1, info
        assert info["onTop"], info
    finally:
        pg.close()


@needs_chrome
def test_chrome_question_once(browser, pages):
    # 35: the question shows once — header on desktop, above the
    # video on a phone — never twice.
    for vp in ({"width": 1440, "height": 900},
               {"width": 390, "height": 844}):
        pg = browser.new_page(viewport=vp)
        try:
            for query in ["?event=apex", "?event=verdict"]:
                goto(pg, pages["clip-a"], query)
                n = pg.evaluate(
                    "document.body.innerText.split("
                    "document.getElementById('ttl').textContent).length - 1")
                assert n == 1, (vp, query, n)
        finally:
            pg.close()


@needs_chrome
def test_chrome_verdict_frame_matches_stage(page, pages):
    # 35: the rail's verdict frame equals the stage's frame.
    goto(page, pages["clip-a"], "?event=verdict")
    info = page.evaluate("""() => ({
      rail: document.getElementById('step-verdict').dataset.frame,
      stage: window.__pp.frame()})""")
    assert info["rail"] == str(info["stage"]), info


@needs_chrome
def test_chrome_chart_zero_tick(page, pages):
    # 35: the chart's y-axis never reads "-0.0"; zero is "0".
    goto(page, pages["clip-a"], "?event=apex")
    texts = page.evaluate(
        "[...document.querySelectorAll('#chart text')].map("
        "t => t.textContent)")
    assert "-0.0" not in texts, texts
    assert "0" in texts, texts


@needs_chrome
def test_chrome_phone_intro_and_timeline(browser, pages):
    # 35 rule 2: on a phone the title never overlaps the HUD, the
    # intro card's text is never cut off, and timeline labels never
    # crowd together.
    pg = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        goto(pg, pages["clip-a"])
        info = pg.evaluate("""() => {
          const sr = document.getElementById('stage').getBoundingClientRect();
          const hud = document.getElementById('hud').getBoundingClientRect();
          const h2 = document.querySelector('#intro h2').getBoundingClientRect();
          const intro = document.getElementById('intro');
          const rows = [...document.querySelectorAll(
            '#intro .checkrow')].map((e) => {
            const r = e.getBoundingClientRect();
            return {x: r.left, y: r.top, w: r.width, h: r.height,
                    cut: r.width > intro.clientWidth + 1};
          });
          const tl = document.getElementById('timeline').getBoundingClientRect();
          const labs = [...document.querySelectorAll(
            '#timeline .tlseg span, #timeline .tltick .tlbl')].map((e) => {
            const r = e.getBoundingClientRect();
            return {t: e.textContent, x: r.left, y: r.top,
                    w: r.width, h: r.height};
          });
          const crowd = [];
          labs.forEach((a, i) => {
            labs.slice(i + 1).forEach((b) => {
              if (!(a.x + a.w <= b.x + 1 || b.x + b.w <= a.x + 1 ||
                    a.y + a.h <= b.y + 1 || b.y + b.h <= a.y + 1))
                crowd.push(a.t + ' <> ' + b.t);
            });
          });
          const tlOut = labs.filter((l) =>
            l.x < tl.left - 1 || l.x + l.w > tl.right + 1).map((l) => l.t);
          return {titleHud: !(h2.right < hud.left || hud.right < h2.left ||
                              h2.bottom < hud.top || hud.bottom < h2.top),
                  scrollable: intro.scrollHeight <= intro.clientHeight + 1 ||
                    getComputedStyle(intro).overflowY === 'auto',
                  cut: rows.filter((r) => r.cut).map((r) => r.w),
                  crowd: crowd, tlOut: tlOut};
        }""")
        assert not info["titleHud"], info
        assert info["scrollable"], info
        assert info["cut"] == [], info
        assert info["crowd"] == [], info
        assert info["tlOut"] == [], info
    finally:
        pg.close()



# --- 39: a verdict decided by a range check reads like one -------------

@needs_chrome
def test_chrome_range_decided_stamp_no_playback_gloss(page, pages):
    # 39: the still range fixture's verdict is decided by a range
    # check with no measured g: the stamp has no playback-speed gloss
    # (its gloss is the range check's own result) and no world chip
    # with σ appears anywhere. Clip-a (gravity-decided) is unchanged.
    goto(page, pages["still"], "?event=verdict")
    stamp = page.text_content("#stamp")
    assert "NOT REALISTIC ON EARTH" in stamp
    assert "playback speed" not in stamp
    assert "3.0σ" in stamp and "above" in stamp, stamp
    chips = page.evaluate("""() => [...document.querySelectorAll(
      '[data-testid="sig-chip"]')].map(e => e.textContent)""")
    assert chips == [], chips
    whole = page.evaluate("document.body.textContent")
    assert "0.0σ" not in whole
    goto(page, pages["clip-a"], "?event=verdict")
    stamp2 = page.text_content("#stamp")
    assert "REALISTIC ON THE MOON" in stamp2
    assert "g within 2σ" in stamp2
    chips2 = page.evaluate("""() => [...document.querySelectorAll(
      '[data-testid="sig-chip"]')].map(e => e.textContent)""")
    assert len(chips2) == 2 and all("σ" in c for c in chips2), chips2


@needs_chrome
def test_chrome_formulas_never_run_words_together(page, pages, tmp_path):
    # 39: a formula with a word run (length_px × m_per_px) is shown as
    # plain monospace text exactly as written, never as run-together
    # math italics. Clip-a's symbol formulas still use KaTeX.
    import shutil
    work = tmp_path / "wall-words"
    shutil.copytree(ROOT / "fixtures/still-range", work)
    result = json.loads((work / "result.json").read_text())
    result["range_checks"][1]["formula"] = "length_px × m_per_px"
    (work / "result.json").write_text(json.dumps(result))
    from src.pagebuild import build_page
    out = tmp_path / "wall-words-page"
    build_page(str(work / "result.json"), None, str(out), None,
               slug="wall-words")
    for page_dir in (pages["still"], pages["clip-a"], out):
        goto(page, page_dir, "?event=verdict")
        texts = page.evaluate(
            "[...document.querySelectorAll('.fx')].map("
            "e => e.textContent)")
        assert not any("lengthpx" in (t or "") for t in texts), texts
        assert not any("mperpx" in (t or "") for t in texts), texts
    goto(page, out, "?event=verdict")
    exact = page.evaluate(
        "[...document.querySelectorAll('.fx.plain')].map("
        "e => e.textContent)")
    assert any("length_px × m_per_px" in (t or "") for t in exact), exact
    goto(page, pages["clip-a"], "?event=apex")
    try:
        page.wait_for_function("window.katex !== undefined",
                               timeout=PW_TIMEOUT)
    except Exception:
        pytest.skip("KaTeX CDN unreachable")
    n = page.evaluate(
        "document.querySelectorAll('.fx[data-tex] .katex').length")
    assert n > 0, n


@needs_chrome
def test_chrome_phone_no_overflow(browser, pages):
    # 39: at 390 px the verdict card, the stamp and every overlay card
    # lie inside the viewport; nothing widens the document.
    for name in ("clip-a", "still"):
        pg = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            goto(pg, pages[name], "?event=verdict")
            wait_hold(pg, "verdict")
            info = pg.evaluate("""() => {
              const vw = window.innerWidth;
              const card = document.getElementById('verdict')
                .getBoundingClientRect();
              const s = document.getElementById('stamp').getBoundingClientRect();
              const rc = document.getElementById('refcard').getBoundingClientRect();
              const el = document.elementFromPoint(
                s.left + s.width / 2, s.top + s.height / 2);
              return {sw: document.documentElement.scrollWidth, vw: vw,
                      cardR: card.right, cardW: card.width,
                      stamp: {l: s.left, t: s.top, r: s.right, b: s.bottom},
                      refOut: rc.width >= 1 && (rc.left < -1
                        || rc.right > vw + 1),
                      onTop: el === s || (el && el.closest('#stamp') !== null)};
            }""")
            assert info["sw"] <= 390, info
            assert info["cardR"] <= 390 + 1, info
            st = info["stamp"]
            assert st["l"] >= -1 and st["t"] >= -1 \
                and st["r"] <= info["vw"] + 1 \
                and st["b"] <= window_inner_height(pg) + 1, info
            assert not info["refOut"], info
            assert info["onTop"], info
        finally:
            pg.close()


def window_inner_height(pg):
    return pg.evaluate("window.innerHeight")


# --- 40: labels that read right and never collide ----------------------

_TIMELINE_GEOM_JS = """() => {
  const segs = [...document.querySelectorAll('#tlSegs .tlseg')].map(d => {
    const r = d.getBoundingClientRect();
    // 43.6: an unmeasured bar has no label element at all.
    const s = d.firstChild ? d.firstChild.getBoundingClientRect() : null;
    return {bar: [r.left, r.top, r.width, r.height],
            lab: s ? [s.left, s.top, s.width, s.height] : null,
            text: d.firstChild ? d.firstChild.textContent : '',
            tip: d.title};
  });
  const ticks = [...document.querySelectorAll('#tlTicks .tltick .tlbl')]
    .map(e => {
      const r = e.getBoundingClientRect();
      return {lab: [r.left, r.top, r.width, r.height], text: e.textContent};
    });
  return {segs: segs, ticks: ticks};
}"""


def _timeline_clashes(info):
    rects = ([s["lab"] for s in info["segs"] if s["lab"] is not None]
             + [t["lab"] for t in info["ticks"]])
    clashes = []
    for i, a in enumerate(rects):
        for j in range(i + 1, len(rects)):
            b = rects[j]
            if not (a[0] + a[2] <= b[0] + 1 or b[0] + b[2] <= a[0] + 1
                    or a[1] + a[3] <= b[1] + 1 or b[1] + b[3] <= a[1] + 1):
                clashes.append((i, j))
    return clashes


def _expected_air(page_dir):
    seg = _result_data_from(page_dir)["segments"][0]
    ts = seg["times_s"]
    return f"in the clip {(ts['end'] - ts['start']):.2f} s"


def _result_data_from(page_dir):
    return json.loads((Path(page_dir) / "index.html").read_text().split(
        '<script id="result-data" type="application/json">')[1].split(
        "</script>")[0])


@needs_chrome
def test_chrome_chart_keeps_clip_label(page, pages, moon22_page, browser):
    # 40: the chart always shows the measured airtime next to the
    # world labels — mid-flight (apex) as well as at landing — and a
    # label is never dropped when times are close (rows split).
    dirs = {"clip-a": pages["clip-a"], "moon22": moon22_page}
    for name, page_dir in dirs.items():
        air = _expected_air(page_dir)
        for query in ("?event=apex", "?event=landing"):
            goto(page, page_dir, query)
            texts = page.evaluate(
                "[...document.querySelectorAll('#chart text')].map("
                "t => t.textContent)")
            assert air in texts, (name, query, texts)
    pg = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        for name, page_dir in dirs.items():
            air = _expected_air(page_dir)
            goto(pg, page_dir, "?event=landing")
            texts = pg.evaluate(
                "[...document.querySelectorAll('#chart text')].map("
                "t => t.textContent)")
            assert air in texts, (name, texts)
            rects = pg.evaluate(
                "[...document.querySelectorAll('#chart text')].map(t => {"
                "const r = t.getBoundingClientRect();"
                "return [r.left, r.top, r.width, r.height];})")
            clashes = []
            for i, a in enumerate(rects):
                for b in rects[i + 1:]:
                    if not (a[0] + a[2] <= b[0] + 1
                            or b[0] + b[2] <= a[0] + 1
                            or a[1] + a[3] <= b[1] + 1
                            or b[1] + b[3] <= a[1] + 1):
                        clashes.append((a, b))
            assert clashes == [], (name, clashes)
    finally:
        pg.close()


@needs_chrome
def test_chrome_range_decided_world_verdict(page, hand8_page):
    # 40, hand run 8's shape (kind "world", decided by a range check,
    # no measured g): the headline is the verdict label, the stamp
    # names the world as §31 writes it, the gloss is the deciding
    # range check's own result, and no g wording appears anywhere.
    goto(page, hand8_page, "?event=verdict")
    head = page.evaluate(
        "document.querySelector('[data-testid=verdict-headline]')"
        ".textContent")
    assert head.strip() == "Realistic on Earth", head
    stamp = page.text_content("#stamp")
    assert "REALISTIC ON EARTH" in stamp, stamp
    assert "THE EARTH" not in stamp, stamp
    assert "g within" not in stamp, stamp
    assert "playback speed" not in stamp, stamp
    assert "inside its range" in stamp, stamp
    chips = page.evaluate("[...document.querySelectorAll("
                          "'[data-testid=sig-chip]')].map("
                          "e => e.textContent)")
    assert chips == [], chips
    rendered = page.evaluate("[...document.querySelectorAll("
                               "'#verdict, #summaryBlock')].map("
                               "e => e.textContent).join(' ')")
    assert "0.0σ" not in rendered, rendered
    assert "g within 2σ" not in rendered, rendered


# --- 41: a world that needs a retime says so ------------------------


@needs_chrome
def test_chrome_retime_chip(page, run22_earth_page, browser):
    # 41: a world chip that does not fit adds the retime it would
    # need from retime_factor; a chip that fits stays as before.
    # The exact σ and factor come from the data.
    goto(page, run22_earth_page, "?event=verdict")
    chips = page.evaluate("""() => [...document.querySelectorAll(
      '[data-testid="sig-chip"]')].map(e => e.textContent)""")
    assert "Moon 0.1σ ✓" in chips, chips
    assert "Earth 33.3σ ✗ · only if slowed ×2.48" in chips, chips
    pg = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        goto(pg, run22_earth_page, "?event=verdict")
        ok = pg.evaluate("""() => {
          const card = document.getElementById('verdict')
            .getBoundingClientRect();
          return [...document.querySelectorAll(
            '[data-testid="sig-chip"]')].every(e => {
            const r = e.getBoundingClientRect();
            return r.left >= card.left - 1 && r.right <= card.right + 1
              && r.top >= card.top - 1 && r.bottom <= card.bottom + 1;
          });
        }""")
        assert ok
    finally:
        pg.close()


# --- 42: the figure, working controls, one screen --------------------


def _run22_result():
    return json.loads(
        (ROOT / "fixtures/source/run-22/result.json").read_text())


@needs_chrome
def test_chrome_run22_figure_outline(page, run22_page):
    # 42.1: the outline follows the whole astronaut (the figure), not
    # the tracked backpack: its bbox height is within 10 % of the
    # figure mask's bbox height at the apex frame.
    goto(page, run22_page, "?event=apex")
    wait_hold(page, "apex")
    info = page.evaluate("""() => {
      const res = JSON.parse(
        document.getElementById('result-data').textContent);
      const flags = JSON.parse(
        document.getElementById('page-flags').textContent);
      const sg = res.segments[0];
      const bb = flags.maskboxes[sg.id][String(sg.frames.apex)];
      const r = document.querySelector(
        '#stageOverlay path[stroke="#4FE3F0"]').getBBox();
      return {drawn: r.height, mask: bb[3]};
    }""")
    assert abs(info["drawn"] - info["mask"]) / info["mask"] <= 0.10, info
    ghosts = page.evaluate("""() => {
      const res = JSON.parse(
        document.getElementById('result-data').textContent);
      const flags = JSON.parse(
        document.getElementById('page-flags').textContent);
      const sg = res.segments[0];
      const bb = flags.maskboxes[sg.id][String(sg.frames.apex)];
      return [...document.querySelectorAll(
        '[data-testid="ghost"]')].map(e => ({
        h: +e.getAttribute('height'), mask: bb[3]}));
    }""")
    assert len(ghosts) >= 1, ghosts
    for g in ghosts:
        assert abs(g["h"] - g["mask"]) / g["mask"] <= 0.10, g


@needs_chrome
def test_chrome_run22_reference_outline(page, run22_page):
    # 42.2: the scale reference outline is traced from mask pixels
    # (≥ 80 vertices), never from the result's polygons.
    goto(page, run22_page, "?event=scale")
    wait_hold(page, "scale")
    n = page.evaluate("""() => {
      const d = document.querySelector(
        '#stageOverlay path[stroke="#FFB54D"]')
        .getAttribute('d');
      return d.split('L').length - 1;
    }""")
    assert n >= 80, n


@needs_chrome
def test_chrome_run22_chrono_chips(page, run22_page):
    # 37/38 on the stage: each world's chip reads its drawn curve's
    # last point (its landing) minus the takeoff time — the same
    # number the curve is drawn with, never a world_outcomes
    # arithmetic (which printed "Moon -7.12 s" here).
    goto(page, run22_page, "?event=landing")
    wait_hold(page, "landing")
    info = page.evaluate("""() => {
      const res = JSON.parse(
        document.getElementById('result-data').textContent);
      const sg = res.segments[0];
      const t0 = sg.times_s.start;
      const want = {};
      for (const g of sg.ghosts) {
        const pts = (g.points || []).filter(p => p.frame >= sg.frames.start);
        const last = pts[pts.length - 1];
        want[g.world] = (last.t_s - t0).toFixed(2) + ' s';
      }
      want['clip'] = (sg.times_s.end - t0).toFixed(2) + ' s';
      const got = [...document.querySelectorAll(
        '[id^="lb-chlanding-"]')].map(e => e.textContent);
      return {want: want, got: got};
    }""")
    for world, num in info["want"].items():
        name = "in the clip" if world == "clip" else world
        assert any(f"{name} {num}" in g for g in info["got"]), info
        assert not any(g.startswith(f"{name} -") for g in info["got"]), \
            info


@needs_chrome
def test_chrome_run22_chrono_copies(page, run22_page):
    # 42.1: the chronophotograph draws whole figures — ≥ 4 cut-outs,
    # each at least 90 % of the figure mask's height at the apex.
    goto(page, run22_page, "?event=landing")
    page.wait_for_function(
        "document.querySelectorAll('[data-testid=\"chrono-copy\"]')"
        ".length >= 4",
        timeout=PW_TIMEOUT)
    heights = page.evaluate("""() => {
      const res = JSON.parse(
        document.getElementById('result-data').textContent);
      const flags = JSON.parse(
        document.getElementById('page-flags').textContent);
      const sg = res.segments[0];
      const mask = flags.maskboxes[sg.id][String(sg.frames.apex)][3];
      return {mask: mask, copies: [...document.querySelectorAll(
        '[data-testid="chrono-copy"]')].map(
        e => +e.getAttribute('height'))};
    }""")
    assert len(heights["copies"]) >= 4, heights
    for h in heights["copies"]:
        assert h >= 0.9 * heights["mask"], heights


def _frames_equal(a: bytes, b: bytes) -> bool:
    # Tolerant visual equality: identical video frames can differ by a
    # few decoder/compositor levels (seen: max 3 on testsrc), while a
    # genuinely different frame differs by hundreds.
    import cv2
    import numpy as np

    ia = cv2.imdecode(np.frombuffer(a, np.uint8),
                      cv2.IMREAD_COLOR).astype(float)
    ib = cv2.imdecode(np.frombuffer(b, np.uint8),
                      cv2.IMREAD_COLOR).astype(float)
    if ia.shape != ib.shape:
        return False
    d = np.abs(ia - ib)
    return d.max() <= 8 and d.mean() <= 0.5


def _sample_ride(page, page_dir, max_s=90.0):
    # Press Play and sample the ride until the verdict (or max_s).
    page.evaluate("document.querySelector('#watchBtn').click()")
    samples = []

    deadline = time.time() + max_s
    while time.time() < deadline:
        row = page.evaluate("""() => ({
          t: document.querySelector('video').currentTime,
          dur: document.querySelector('video').duration,
          hold: window.__pp.hold() ? window.__pp.hold().kind : null
        })""")
        # Wall time is stamped with the video time, before the slow
        # screenshot, so video advance can be set against it.
        row["wall"] = time.time()
        row["png"] = page.locator("#stage").screenshot()
        samples.append(row)
        if row["hold"] == "verdict":
            break
        time.sleep(0.25)
    return samples


def _visually_distinct(pngs) -> int:
    # Count visually distinct frames with decoder-noise tolerance.
    distinct = []
    for p in pngs:
        if not any(_frames_equal(p, q) for q in distinct):
            distinct.append(p)
    return len(distinct)


@needs_chrome
def test_chrome_ride_forward(page, run22_page, portrait_page):
    # 42.3: the ride only moves forward; the verdict appears only
    # after the video reaches its last frame; outside holds the stage
    # keeps changing.
    for page_dir in (run22_page, portrait_page):
        goto(page, page_dir)
        samples = _sample_ride(page, page_dir)
        assert samples and samples[-1]["hold"] == "verdict", \
            samples[-3:] if samples else None
        assert samples[-1]["t"] >= samples[-1]["dur"] - 1 / 29.0, \
            samples[-1]
        for a, b in zip(samples, samples[1:]):
            assert b["t"] + 1e-6 >= a["t"], (a, b)
        for a, b in zip(samples, samples[1:]):
            if a["hold"] is None and b["hold"] is None:
                # The video may advance only with the wall clock: a
                # slow sampler (full-stage screenshots) legitimately
                # sees more than 0.6 s of video between samples, but a
                # skip or rewind advances far ahead of the wall.
                assert b["t"] - a["t"] <= \
                    max(0.6, b["wall"] - a["wall"] + 0.15), (a, b)
        recent = []
        for row in samples:
            if row["hold"] is None:
                recent = [(t, p) for t, p in recent
                          if row["t"] - t <= 1.0 + 1e-9]
                recent.append((row["t"], row["png"]))
                if row["t"] - recent[0][0] >= 1.0 - 1e-9:
                    assert _visually_distinct(
                        [p for _, p in recent]) > 1


@needs_chrome
def test_chrome_pause_while_playing(page, run22_page, portrait_page):
    # 42.3: pause pauses — currentTime and the stage picture freeze.
    for page_dir in (run22_page, portrait_page):
        goto(page, page_dir)
        page.evaluate("document.querySelector('#watchBtn').click()")
        page.wait_for_function(
            "document.querySelector('video').paused === false",
            timeout=PW_TIMEOUT)
        time.sleep(1.0)
        page.keyboard.press(" ")
        page.wait_for_function(
            "document.querySelector('video').paused === true",
            timeout=PW_TIMEOUT)
        t0 = page.evaluate(
            "document.querySelector('video').currentTime")
        h0 = page.locator("#stage").screenshot()
        time.sleep(1.5)
        t1 = page.evaluate(
            "document.querySelector('video').currentTime")
        h1 = page.locator("#stage").screenshot()
        assert abs(t1 - t0) <= 1 / 29.0 + 1e-6, (t0, t1)
        assert _frames_equal(h0, h1)
        page.keyboard.press(" ")
        page.wait_for_function(
            "document.querySelector('video').paused === false",
            timeout=PW_TIMEOUT)


@needs_chrome
def test_chrome_pause_in_hold(page, run22_page):
    # 42.3: pausing in a hold freezes its bar and title; the next
    # press finishes the hold, then the video moves.
    goto(page, run22_page)
    page.evaluate("document.querySelector('#watchBtn').click()")
    page.wait_for_function(
        "window.__pp.hold() && window.__pp.hold().kind === 'apex'",
        timeout=120000)
    page.keyboard.press(" ")
    page.wait_for_function(
        "document.querySelector('video').paused === true",
        timeout=PW_TIMEOUT)
    bar0 = page.evaluate(
        "document.getElementById('holdbar').style.width")
    title0 = page.text_content("#caption .t")
    time.sleep(1.5)
    bar1 = page.evaluate(
        "document.getElementById('holdbar').style.width")
    assert bar0 == bar1, (bar0, bar1)
    assert page.text_content("#caption .t") == title0
    page.keyboard.press(" ")
    page.wait_for_function("window.__pp.hold() === null",
                           timeout=PW_TIMEOUT)
    t0 = page.evaluate("document.querySelector('video').currentTime")
    page.wait_for_function(
        f"document.querySelector('video').currentTime > {t0}",
        timeout=PW_TIMEOUT)


@needs_chrome
def test_chrome_timeline_seek_and_drag(page, portrait_page):
    # 42.3: the timeline is a seek bar — click seeks and pauses with
    # the live layers of that frame; drag takes several values.
    import hashlib

    goto(page, portrait_page)
    hashes = []
    for frac in (0.25, 0.50, 0.75):
        box = page.evaluate("""() => {
          const r = document.getElementById('timeline')
            .getBoundingClientRect();
          return {x: r.left, y: r.top, w: r.width, h: r.height};
        }""")
        assert box["h"] >= 24, box
        page.mouse.click(box["x"] + frac * box["w"],
                         box["y"] + box["h"] / 2)
        page.wait_for_function(f"""() => {{
          const v = document.querySelector('video');
          return Math.abs(v.currentTime - {frac} * v.duration)
            < 1.5 / 30;
        }}""", timeout=PW_TIMEOUT)
        assert page.evaluate(
            "document.querySelector('video').paused === true")
        hashes.append(hashlib.md5(
            page.locator("#stage").screenshot()).hexdigest())
    assert len(set(hashes)) == 3, hashes
    box = page.evaluate("""() => {
      const r = document.getElementById('timeline').getBoundingClientRect();
      return {x: r.left, y: r.top, w: r.width, h: r.height};
    }""")
    seen = []
    page.mouse.move(box["x"] + 0.2 * box["w"], box["y"] + box["h"] / 2)
    page.mouse.down()
    for i in range(1, 9):
        page.mouse.move(box["x"] + (0.2 + 0.05 * i) * box["w"],
                        box["y"] + box["h"] / 2, steps=2)
        seen.append(page.evaluate(
            "document.querySelector('video').currentTime"))
    page.mouse.up()
    assert len(set(round(v, 3) for v in seen)) >= 3, seen


@needs_chrome
def test_chrome_one_screen(browser, run22_page, portrait_page):
    # 42.4: header, stage and control bar stay fully visible with no
    # page scroll; the play button and the timeline are inside the
    # window.
    for vp in ({"width": 1440, "height": 900},
               {"width": 1280, "height": 720},
               {"width": 390, "height": 844}):
        pg = browser.new_page(viewport=vp)
        try:
            goto(pg, run22_page)
            pg.evaluate("document.querySelector('#watchBtn').click()")
            time.sleep(1.0)
            for query in (None, "?event=apex"):
                if query:
                    goto(pg, run22_page, query)
                    wait_hold(pg, "apex")
                info = pg.evaluate("""() => {
                  const s = document.getElementById('stage')
                    .getBoundingClientRect();
                  const b = document.getElementById('playBtn')
                    .getBoundingClientRect();
                  const t = document.getElementById('timeline')
                    .getBoundingClientRect();
                  return {scroll: document.scrollingElement.scrollHeight,
                          win: window.innerHeight,
                          play: {t: b.top, b: b.bottom},
                          tl: {t: t.top, b: t.bottom}};
                }""")
                assert info["scroll"] <= info["win"], (vp, query, info)
                assert info["play"]["t"] >= 0
                assert info["play"]["b"] <= info["win"] + 1, (vp, info)
                assert info["tl"]["t"] >= 0
                assert info["tl"]["b"] <= info["win"] + 1, (vp, info)
        finally:
            pg.close()


@needs_chrome
def test_chrome_portrait_aspect(page, portrait_page):
    # 42.4: the stage keeps the video's display aspect — 720/1280
    # here — and the picture is never stretched.
    goto(page, portrait_page)
    info = page.evaluate("""() => {
      const v = document.querySelector('video');
      return {w: v.offsetWidth, h: v.offsetHeight};
    }""")
    assert abs(info["w"] / info["h"] - 720 / 1280) <= 0.01, info


@needs_chrome
def test_chrome_no_service_text(page, run22_page):
    # 42.5: nothing on the page that the viewer does not need — no
    # HUD, badge, hash, cost, model names, keyboard help or agent
    # prose in the visible text, in any state.
    banned = ["frame ", "fps", "Freeze frame", "SAM", "sha", "$",
              "Muse", "space = "]
    for query in ["", "?event=scale", "?event=takeoff", "?event=apex",
                  "?event=landing", "?event=verdict"]:
        goto(page, run22_page, query)
        text = page.evaluate("document.body.innerText")
        for b in banned:
            assert b not in text, (query, b)
    result = _run22_result()
    prose = []
    for ref in result.get("references", []):
        mc = ref.get("mask_check") or {}
        ans = mc.get("answer") or {}
        for v in (mc.get("coverage_answer"), mc.get("covers"),
                  mc.get("claim"), mc.get("reason"),
                  ans.get("reason"), ans.get("covers"),
                  ans.get("inside"), ans.get("outside")):
            if isinstance(v, str) and len(v) > 20:
                prose.append(v)
        for alt in mc.get("alternative_readings", []) or []:
            v = (alt or {}).get("description")
            if isinstance(v, str) and len(v) > 20:
                prose.append(v)
    assert prose, "fixture has no mask/blind prose to check against"
    for query in ("?event=apex", "?event=scale"):
        goto(page, run22_page, query)
        if "apex" in query:
            wait_hold(page, "apex")
        else:
            wait_hold(page, "scale")
        text = page.evaluate("document.body.innerText")
        for s in prose:
            assert s not in text, (query, s[:60])


@needs_chrome
def test_chrome_layers_leave_after_jump(page, run22_page):
    # 42.6: 2 s of video after the landing hold ends, the jump's
    # layers are gone — no ghost and no apex chip.
    goto(page, run22_page, "?event=landing")
    wait_hold(page, "landing")
    page.keyboard.press(" ")
    page.wait_for_function("window.__pp.hold() === null",
                           timeout=PW_TIMEOUT)
    page.wait_for_function("window.__pp.frame() >= 334",
                           timeout=PW_TIMEOUT)
    info = page.evaluate("""() => ({
      ghosts: document.querySelectorAll('[data-testid="ghost"]').length,
      apex: document.querySelectorAll('#apexChip').length
    })""")
    assert info == {"ghosts": 0, "apex": 0}, info


@needs_chrome
def test_chrome_hold_camera_frames_union(page, run22_page):
    # 42.7: at the end of each timed hold every ghost bbox and the
    # figure bbox lie inside the visible stage.
    for ev in ("takeoff", "apex", "landing"):
        goto(page, run22_page, f"?event={ev}")
        wait_hold(page, ev)
        ok = page.evaluate("""() => {
          const sr = document.getElementById('stage').getBoundingClientRect();
          const inside = (r) => r.left >= sr.left - 1
            && r.top >= sr.top - 1
            && r.right <= sr.right + 1 && r.bottom <= sr.bottom + 1;
          const fig = document.querySelector(
            '#stageOverlay path[stroke="#4FE3F0"]');
          const boxes = [...document.querySelectorAll(
            '[data-testid="ghost"]')].map(e => e.getBoundingClientRect());
          if (fig) {
            const r = fig.getBoundingClientRect();
            if (r.width > 4 && !inside(r)) return 'figure';
          }
          for (const r of boxes) {
            if (r.width > 4 && !inside(r)) return 'ghost';
          }
          return true;
        }""")
        assert ok is True, ev


@needs_chrome
def test_chrome_phone_intro_scrolls(browser, run22_page):
    # 35: on a phone the intro card's text is never cut off — the
    # card scrolls — and the Watch button stays clickable.
    pg = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        goto(pg, run22_page)
        info = pg.evaluate("""() => {
          const intro = document.getElementById('intro');
          const st = getComputedStyle(intro);
          return {scroll: intro.scrollHeight > intro.clientHeight + 1,
                  oy: st.overflowY};
        }""")
        if info["scroll"]:
            assert info["oy"] in ("auto", "scroll"), info
        pg.click("#watchBtn")
        pg.wait_for_function(
            "document.querySelector('video').paused === false",
            timeout=PW_TIMEOUT)
    finally:
        pg.close()


@needs_chrome
def test_chrome_chart_on_top(page, run22_page):
    # 42.8: the chart is on top from the start — fully inside the
    # window at takeoff and at apex.
    for query in ("?event=takeoff", "?event=apex"):
        goto(page, run22_page, query)
        wait_hold(page, query.split("=")[1])
        info = page.evaluate("""() => {
          const r = document.getElementById('chartBlock')
            .getBoundingClientRect();
          return {top: r.top, bottom: r.bottom, win: window.innerHeight};
        }""")
        assert info["top"] >= -1 and info["bottom"] <= info["win"] + 1, \
            (query, info)


@needs_chrome
def test_chrome_timeline_labels_no_collide(page, pages, hand8_page,
                                           browser):
    # 40 + 43.6: no two timeline labels' boxes intersect; a motion bar
    # label ("Jump 1", at most 12 chars) lies inside its bar; an
    # unmeasured bar has no label element. At 1440 px and at 390 px.
    jobs = [("clip-a", pages["clip-a"], ""),
            ("hand8", hand8_page, "?event=verdict")]
    for name, page_dir, query in jobs:
        goto(page, page_dir, query)
        info = page.evaluate(_TIMELINE_GEOM_JS)
        assert _timeline_clashes(info) == [], (name, info)
        for s in info["segs"]:
            if s["lab"] is None:
                assert s["text"] == "", (name, s)
                continue
            assert s["lab"][0] >= s["bar"][0] - 1, (name, s)
            assert s["lab"][0] + s["lab"][2] <= s["bar"][0] + s["bar"][2] + 1, \
                (name, s)
            assert 0 < len(s["text"].strip()) <= 12, (name, s)
    pg = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        for name, page_dir, query in jobs:
            goto(pg, page_dir, query)
            info = pg.evaluate(_TIMELINE_GEOM_JS)
            assert _timeline_clashes(info) == [], (name, info)
            for s in info["segs"]:
                if s["lab"] is None:
                    continue
                assert s["lab"][0] >= s["bar"][0] - 1, (name, s)
                assert s["lab"][0] + s["lab"][2] <= s["bar"][0] + s["bar"][2] + 1, \
                    (name, s)
    finally:
        pg.close()


# --- 43: silhouettes, not boxes ---------------------------------------


def _prose_runs(result):
    # 43.5: every run of 4 consecutive words from any description,
    # note, notes or point_description string. Motion descriptions
    # (first_look.motions) are viewer-facing motion names — the rail
    # line and timeline tooltip required by §§27/43.6 — not agent
    # prose, so they are out of the corpus.
    runs = set()

    def add(s):
        words = re.findall(r"[a-z0-9]+", s.lower())
        for i in range(len(words) - 3):
            runs.add(" ".join(words[i:i + 4]))

    def walk(n, in_motions=False):
        if isinstance(n, dict):
            for k, v in n.items():
                if k in ("description", "note", "notes",
                         "point_description") \
                        and isinstance(v, str) and not in_motions:
                    add(v)
                walk(v, in_motions or k == "motions")
        elif isinstance(n, list):
            for v in n:
                walk(v, in_motions)

    walk(result)
    return runs


@needs_chrome
def test_chrome_run22_ghost_silhouette_alpha(page, run22_page):
    # 43.1: the composed ghost cut-out carries the mask in its alpha
    # channel — a bbox corner outside the mask is transparent, the
    # silhouette is present, and at least a quarter of the bbox is cut.
    goto(page, run22_page, "?event=apex")
    px = page.evaluate("""async () => {
      const g = document.querySelector('[data-testid="ghost"]');
      if (!g) return null;
      const img = new Image();
      img.src = g.getAttribute('href');
      await new Promise((res, rej) => {img.onload = res; img.onerror = rej;});
      const c = document.createElement('canvas');
      c.width = img.naturalWidth; c.height = img.naturalHeight;
      const x = c.getContext('2d');
      x.drawImage(img, 0, 0);
      const d = x.getImageData(0, 0, c.width, c.height).data;
      const at = (px, py) => d[(py * c.width + px) * 4 + 3];
      let clear = 0, solid = 0;
      for (let i = 3; i < d.length; i += 4) {
        if (d[i] === 0) clear++;
        if (d[i] > 200) solid++;
      }
      const n = c.width * c.height;
      const w = c.width, h = c.height;
      return {corner: [at(0, 0), at(w - 1, 0), at(0, h - 1),
                       at(w - 1, h - 1)],
              clearFrac: clear / n, solidFrac: solid / n};
    }""")
    assert px is not None, "no ghost cut-out composed"
    assert all(v < 16 for v in px["corner"]), px["corner"]
    assert px["solidFrac"] > 0.05, px
    assert px["clearFrac"] >= 0.25, px


@needs_chrome
def test_chrome_run22_chrono_silhouettes(page, run22_page):
    # 43.2: every chronophotograph figure is a whole silhouette at
    # video scale, inside the stage.
    goto(page, run22_page, "?event=landing")
    info = page.evaluate("""() => {
      const stage = document.getElementById('stage').getBoundingClientRect();
      const res = JSON.parse(
        document.getElementById('result-data').textContent);
      const flags = JSON.parse(
        document.getElementById('page-flags').textContent);
      const DW = res.video.coded_width;
      const scale = stage.width / DW;
      const sg = res.segments[0], F = sg.frames;
      const mbs = (flags.maskboxes || {})[sg.id] || {};
      const out = [];
      for (const e of document.querySelectorAll(
             '[data-testid="chrono-copy"]')) {
        const r = e.getBoundingClientRect();
        const fr = e.getAttribute('data-frame');
        out.push({x: r.left - stage.left, y: r.top - stage.top,
                  w: r.width, h: r.height,
                  sw: stage.width, sh: stage.height, frame: fr,
                  maskH: (mbs[String(fr)] || [0, 0, 0, 100])[3],
                  scale: scale});
      }
      return out;
    }""")
    assert len(info) >= 4, info
    for c in info:
        assert c["x"] >= -1 and c["y"] >= -1, c
        assert c["x"] + c["w"] <= c["sw"] + 1, c
        assert c["y"] + c["h"] <= c["sh"] + 1, c
        expect = c["maskH"] * c["scale"]
        assert abs(c["h"] - expect) / expect <= 0.10, (c, expect)


@needs_chrome
def test_chrome_run22_hold_zoom_capped(page, run22_page):
    # 43.3: no hold zoom makes one source pixel larger than 2.5
    # screen pixels — on run 22 every hold's camera zoom is 1.03.
    for query in ("?event=scale", "?event=takeoff", "?event=apex",
                  "?event=landing", "?event=verdict"):
        goto(page, run22_page, query)
        z = page.evaluate("window.__pp.camera().z")
        assert abs(z - 1.03) <= 0.02, (query, z)


@needs_chrome
def test_chrome_run22_outline_thin(page, run22_page):
    # 43.4: every outline core is 1.5-2 CSS px at any zoom; its glow
    # is one wider stroke of at most 5 CSS px.
    goto(page, run22_page, "?event=apex")
    widths = page.evaluate("""() => {
      const k = document.getElementById('ov').getScreenCTM().a;
      return [...document.querySelectorAll(
        '#stageOverlay path')].map(e => ({
        w: parseFloat(e.getAttribute('stroke-width')) * k,
        op: parseFloat(e.getAttribute('opacity') || '1')}));
    }""")
    assert widths, "no outline paths drawn"
    for p in widths:
        if p["op"] >= 0.5:
            assert 1.4 <= p["w"] <= 2.2, p
        else:
            assert p["w"] <= 5.05, p


@needs_chrome
def test_chrome_run22_rail_no_prose(page, run22_page):
    # 43.5: with Full calculation off, the side column shows no agent
    # prose (no 4-word run from the result's descriptions/notes) and
    # no frame numbers ("#" + digit), at every event.
    corpus = _prose_runs(_run22_result())
    assert corpus, "no prose corpus found in run-22 result"
    for query in ("", "?event=scale", "?event=takeoff", "?event=apex",
                  "?event=landing", "?event=verdict"):
        goto(page, run22_page, query)
        text = page.evaluate(
            "document.getElementById('sideInner').innerText")
        words = re.findall(r"[a-z0-9]+", text.lower())
        runs = {" ".join(words[i:i + 4])
                for i in range(len(words) - 3)}
        hit = runs & corpus
        assert not hit, (query, sorted(hit)[:3])
        body = page.evaluate("document.body.innerText")
        assert re.search(r"#\d", body) is None, (query, "frame number")


@needs_chrome
def test_chrome_timeline_short_labels(browser, run22_page, pages):
    # 43.6: every timeline label is short, lies inside the control
    # bar, and unmeasured bars carry no label element.
    jobs = [(run22_page, "?event=apex"), (pages["clip-a"], "")]
    for page_dir, query in jobs:
        for vp in ({"width": 1440, "height": 900},
                   {"width": 390, "height": 844}):
            pg = browser.new_page(viewport=vp)
            try:
                goto(pg, page_dir, query)
                info = pg.evaluate("""() => {
                  const cb = document.getElementById('controls')
                    .getBoundingClientRect();
                  const labs = [...document.querySelectorAll(
                    '#timeline .tlseg span, #timeline .tltick .tlbl')];
                  const bars = [...document.querySelectorAll(
                    '#tlSegs .tlseg')].map(d => {
                    const r = d.getBoundingClientRect();
                    return {grey: d.className.includes('grey'),
                      labelled: !!d.firstChild,
                      bar: [r.left, r.right]};
                  });
                  return {cb: [cb.left, cb.top, cb.right, cb.bottom],
                          labs: labs.map(e => {
                            const r = e.getBoundingClientRect();
                            return {t: e.textContent, sw: e.scrollWidth,
                                    w: r.width,
                                    r: [r.left, r.top, r.right, r.bottom],
                                    bar: e.closest('.tlseg') ?
                                      e.closest('.tlseg')
                                        .getBoundingClientRect().left : null,
                                    barw: e.closest('.tlseg') ?
                                      e.closest('.tlseg')
                                        .getBoundingClientRect().width
                                      : null};}),
                          bars: bars};
                }""")
                cb = info["cb"]
                for lab in info["labs"]:
                    assert len(lab["t"]) <= 12, (vp, lab)
                    # the label reads whole: never cut with an ellipsis.
                    assert lab["sw"] <= lab["w"] + 1, (vp, lab)
                    r = lab["r"]
                    assert r[0] >= cb[0] - 1 and r[1] >= cb[1] - 1 \
                        and r[2] <= cb[2] + 1 and r[3] <= cb[3] + 1, \
                        (vp, lab, cb)
                    if lab["bar"] is not None:
                        assert r[0] >= lab["bar"] - 1, (vp, lab)
                        assert r[2] <= lab["bar"] + lab["barw"] + 1, \
                            (vp, lab)
                for b in info["bars"]:
                    if b["grey"]:
                        assert not b["labelled"], (vp, b)
            finally:
                pg.close()


@needs_chrome
def test_chrome_first_screen_minimal(page, run22_page):
    # 43.7: the first screen asks one question — the question large,
    # one check line, the by-eye card, the watch button — in at most
    # 60 words; the header shows Physics Proof, never the question.
    goto(page, run22_page)
    words = page.evaluate(
        "document.getElementById('intro').innerText")
    assert len(words.split()) <= 60, len(words.split())
    body = page.evaluate("document.body.innerText")
    result = _result_data(page)
    q = result["first_look"]["question"]
    assert body.count(q) == 1, body.count(q)
    head = page.text_content("header")
    assert "Physics Proof" in head, head
    assert q not in head, head


# --- 46/47: freeze canvas, stage pixels, rail log, loading, stamp ------


def _stage_box(page):
    return page.evaluate("""() => {
      const r = document.getElementById('stage').getBoundingClientRect();
      return {x: r.x, y: r.y, width: r.width, height: r.height};
    }""")


def _ride_samples(page, max_pairs=15, deadline_s=90):
    # Sample the stage every 0.25 s (46.2). Returns the playing samples:
    # (video time, screenshot bytes) while the video plays outside holds.
    import time as _time
    box = _stage_box(page)
    playing = []
    t0 = _time.time()
    while _time.time() - t0 < deadline_s:
        row = page.evaluate("""() => ({
          t: document.querySelector('video').currentTime,
          paused: document.querySelector('video').paused,
          hold: window.__pp.hold() ? window.__pp.hold().kind : null,
          seen: window.__pp.seen()
        })""")
        if any(s.startswith("verdict:") for s in row["seen"]):
            break
        if not row["paused"] and row["hold"] is None:
            png = page.screenshot(clip=box)
            playing.append((row["t"], png,
                            _time.time() - t0))
            if len(playing) >= max_pairs + 1:
                break
        _time.sleep(0.25)
    return playing


@needs_chrome
def test_chrome_freeze_hidden_while_playing(page, pages):
    # 46.1: while the video plays the freeze canvas is hidden and the
    # viewer sees the live video; when paused it is drawn and shown.
    # 46.2 paused-frame: the drawn frame is within 1 frame of
    # floor(currentTime x fps), not an earlier frame.
    goto(page, pages["clip-a"], "?frame=100")
    page.keyboard.press(" ")
    page.wait_for_function(
        "document.querySelector('video').paused === false",
        timeout=PW_TIMEOUT)
    page.wait_for_function(
        "document.getElementById('freeze').style.visibility === 'hidden'",
        timeout=PW_TIMEOUT)
    page.keyboard.press(" ")
    page.wait_for_function(
        "document.querySelector('video').paused === true",
        timeout=PW_TIMEOUT)
    # State-based (34.2): paused flips synchronously on pause() but the
    # pause event that redraws and shows the canvas dispatches after it.
    page.wait_for_function(
        "document.getElementById('freeze').style.visibility === 'visible'",
        timeout=PW_TIMEOUT)
    info = page.evaluate("""() => ({
      vis: document.getElementById('freeze').style.visibility,
      drawn: parseInt(
        document.getElementById('freeze').dataset.drawn || '-99', 10),
      t: document.querySelector('video').currentTime
    })""")
    result = json.loads((ROOT / "fixtures/clip-a/result.json").read_text())
    fps = result["video"]["measured_fps"]
    assert info["vis"] == "visible", info
    assert abs(info["drawn"] - math.floor(info["t"] * fps)) <= 1, info


@pytest.mark.parametrize("start", ["watch", "play"])
@needs_chrome
def test_chrome_stage_moves_while_playing(page, pages, start):
    # 46.2: for every pair of samples where the video plays (not paused,
    # not in a hold) and currentTime advanced by more than 0.05 s, the
    # two stage screenshots differ; at most 20 % of pairs may be equal.
    # 47.3: this also holds in the first 1.5 s after the click — no more
    # than 2 equal stage screenshots in a row while time advances.
    goto(page, pages["clip-a"])
    if start == "watch":
        page.click("#watchBtn")
    else:
        page.click("#playBtn")
    playing = _ride_samples(page)
    pairs = [(a, b) for a, b in zip(playing, playing[1:])
             if b[0] - a[0] > 0.05]
    assert len(pairs) >= 5, len(pairs)
    equal = sum(1 for a, b in pairs if a[1] == b[1])
    assert equal / len(pairs) <= 0.2, (equal, len(pairs))
    early = [p for p in playing if p[2] <= 1.5 and p[0] > 0.05]
    run = 0
    for a, b in zip(early, early[1:]):
        run = run + 1 if a[1] == b[1] else 0
        assert run <= 2, "stage stalled at the start"


@needs_chrome
def test_chrome_http_blob_video(page, pages, http_base):
    # 47.3: over HTTP the page fetches the clip once as a blob and plays
    # it from an object URL; on file:// it uses the file directly.
    page.goto(f"{http_base}/ppages/clip-a/index.html?event=apex",
              timeout=30000)
    page.wait_for_function("window.__pp && window.__pp.cutsReady() === true",
                           timeout=PW_TIMEOUT)
    src = page.evaluate("document.querySelector('video').src")
    assert src.startswith("blob:"), src
    goto(page, pages["clip-a"], "?event=apex")
    src = page.evaluate("document.querySelector('video').src")
    assert not src.startswith("blob:"), src
    assert src.endswith("clip.mp4"), src


@needs_chrome
def test_chrome_verdict_log_and_budget(page, run22_page):
    # 47.2: the error budget reads sigma_contribution, largest first
    # ("± 0.221"), ending with "σ = √Σσᵢ² = 0.246 m/s²"; a reference
    # step is titled by its reference; chips without a digit stay
    # hidden except the verdict step's world.
    goto(page, run22_page, "?event=verdict")
    info = page.evaluate("""() => ({
      rows: [...document.querySelectorAll('#steps .brow')].map(r => ({
        name: r.querySelector('.bl').textContent,
        val: r.querySelector('.bp').textContent,
        tip: r.title,
        w: parseFloat(r.querySelector('.bf').style.width)
      })),
      foot: [...document.querySelectorAll('#steps .bars .fb')].map(
        e => e.textContent),
      heads: [...document.querySelectorAll('#steps .step .st')].map(
        e => e.textContent),
      chips: [...document.querySelectorAll('#steps .chip')].map(
        e => e.textContent)
    })""")
    assert len(info["rows"]) == 6, info["rows"]
    assert info["rows"][0]["name"] == "reference reading", info["rows"]
    assert info["rows"][0]["val"] == "± 0.221", info["rows"]
    assert info["rows"][0]["tip"] != "", info["rows"]
    assert info["rows"][0]["w"] == pytest.approx(100.0), info["rows"]
    assert "σ = √Σσᵢ² = 0.246 m/s²" in info["foot"], info["foot"]
    assert ("Reference: life-support backpack plus top unit height"
            in info["heads"]), info["heads"]
    assert "Reference: suited astronaut height" in info["heads"], \
        info["heads"]
    assert "0.914 m over 70.6 px" in page.evaluate(
        "document.getElementById('steps').textContent")
    assert "measured gravity" not in info["chips"], info["chips"]
    assert "error budget" not in info["chips"], info["chips"]
    assert "Moon" in info["chips"], info["chips"]


@needs_chrome
def test_chrome_retimed_direction_stamp(page, fake1_page, tmp_path):
    # 47.4: the retimed stamp reads the direction from verdict.direction
    # (k > 1): "NOT REAL SPEED · SPED UP ×2.1" with the gloss "at real
    # speed it fits the Moon". The old page said "SLOWED ×2.1". With a
    # measured g the headline keeps the g number with the factor under
    # it; the headline without g reads "sped up ×2.1 from Moon".
    goto(page, fake1_page, "?event=verdict")
    stamp = page.text_content("#stamp")
    assert "NOT REAL SPEED · SPED UP ×2.1" in stamp, stamp
    assert "SLOWED" not in stamp, stamp
    assert "at real speed it fits the Moon" in stamp, stamp
    head = page.evaluate(
        "document.querySelector('[data-testid=verdict-headline]')"
        ".textContent")
    assert "g = " in head and "sped up ×2.1 from Moon" in head, head
    import shutil
    work = tmp_path / "fake1-nog"
    shutil.copytree(ROOT / "fixtures/source/fake-1", work,
                    ignore=shutil.ignore_patterns("workspace", "logs"))
    result = json.loads((work / "result.json").read_text())
    result["verdict"]["g_measured"] = None
    result["verdict"]["sigma_g"] = None
    (work / "result.json").write_text(json.dumps(result))
    from src.pagebuild import build_page
    out = tmp_path / "fake1-nog-page"
    build_page(str(work / "result.json"), str(work / "input/clip.mp4"),
               str(out), str(work / "summary.json"), slug="fake1-nog")
    goto(page, out, "?event=verdict")
    stamp = page.text_content("#stamp")
    assert "NOT REAL SPEED · SPED UP ×2.1" in stamp, stamp
    head = page.evaluate(
        "document.querySelector('[data-testid=verdict-headline]')"
        ".textContent")
    assert head.strip() == "sped up ×2.1 from Moon", head


@needs_chrome
def test_chrome_range_tick_size_check(page, moon_range_page):
    # 47.4: a range event's timeline tick reads "Size check", never the
    # reference name cut at 12 characters.
    goto(page, moon_range_page)
    ticks = page.evaluate(
        "[...document.querySelectorAll('#timeline .tltick .tlbl')]"
        ".map(e => e.textContent)")
    assert "Size check" in ticks, ticks
    assert "hand ratio" not in ticks, ticks


@needs_chrome
def test_chrome_fake1_outlines_window(page, fake1_page):
    # 48.1: the figure's outline shows only inside a flight window
    # (1 s before takeoff to 1 s after landing); an outlier mask is
    # never drawn. Fake-1 takes off at frame 135, so the walk at
    # frames 20-90 draws no outline, and neither do the planted area
    # jumps at frames 32-48.
    for fr in [20, 30, 40, 50, 60, 70, 80, 90] + list(range(32, 49)):
        goto(page, fake1_page, f"?frame={fr}")
        n = page.evaluate(
            "document.querySelectorAll('#stageOverlay path[stroke=\"#4FE3F0\"]')"
            ".length")
        assert n == 0, (fr, n)
    # inside the window the outline is drawn ...
    goto(page, fake1_page, "?frame=143")
    n = page.evaluate(
        "document.querySelectorAll('#stageOverlay path[stroke=\"#4FE3F0\"]')"
        ".length")
    assert n >= 1, n
    # ... but not at the Scale hold (frame 10): only reference outlines
    goto(page, fake1_page, "?event=scale")
    n = page.evaluate(
        "document.querySelectorAll('#stageOverlay path[stroke=\"#4FE3F0\"]')"
        ".length")
    assert n == 0, n
    amber = page.evaluate(
        "document.querySelectorAll('#stageOverlay path[stroke=\"#FFB54D\"]')"
        ".length")
    assert amber >= 1, amber


@needs_chrome
def test_chrome_fake1_chrono_inside_stage(page, fake1_page):
    # 48.3: world curves are clipped to the stage; a world whose
    # landing lies beyond the time axis draws an arrow at the axis end
    # ("Moon 2.53 s →") instead of a label off the axis.
    goto(page, fake1_page, "?event=landing")
    page.wait_for_function("!!document.getElementById('chronoAxis')",
                           timeout=PW_TIMEOUT)
    info = page.evaluate("""() => {
      const sr = document.getElementById('stage').getBoundingClientRect();
      const inStage = r => r.left >= sr.left - 1 && r.top >= sr.top - 1 &&
        r.right <= sr.right + 1 && r.bottom <= sr.bottom + 1;
      const pts = [...document.querySelectorAll(
        '#stageOverlay polyline[id^="arc-"], #stageOverlay .cdot')]
        .map(e => { const r = e.getBoundingClientRect();
          return {id: e.id || e.getAttribute('class'), ok: inStage(r)}; });
      const labels = [...document.querySelectorAll('#stageOverlay text')]
        .map(t => { const r = t.getBoundingClientRect();
          if (r.width < 1 && r.height < 1) return null;
          return {text: t.textContent, ok: inStage(r)}; })
        .filter(Boolean);
      const head = document.getElementById('chronoHead');
      const hr = head ? head.getBoundingClientRect() : null;
      return {pts: pts, labels: labels, head: hr ? inStage(hr) : null};
    }""")
    bad_pts = [p for p in info["pts"] if not p["ok"]]
    assert not bad_pts, bad_pts
    bad_labels = [t for t in info["labels"] if not t["ok"]]
    assert not bad_labels, bad_labels
    assert info["head"], "chrono heading outside stage"
    got = [t["text"] for t in info["labels"]]
    assert any("Moon 2.53 s →" in g for g in got), got
    assert any("in the clip 0.57 s" in g for g in got), got


@needs_chrome
def test_chrome_two_segments_chart_verdict_rail(page, two_seg_page):
    # 48.2: every jump shares one time-since-takeoff axis (the
    # confirmation jump in the same colours at 60 % opacity, labelled
    # at its last point); the verdict card shows each jump's g; the
    # column shows the "Jumps agree" step after the jumps' fit steps.
    goto(page, two_seg_page, "?event=verdict")
    counts = page.evaluate("""() => {
      const res = JSON.parse(
        document.getElementById('result-data').textContent);
      return res.segments.map(s => (s.track || []).length);
    }""")
    assert len(counts) == 2, counts
    dots = page.evaluate(
        "document.querySelectorAll('#chart circle').length")
    assert dots == sum(counts), (dots, counts)
    chart_texts = page.evaluate(
        "[...document.querySelectorAll('#chart text')]"
        ".map(e => e.textContent)")
    assert "Jump 2" in chart_texts, chart_texts
    assert page.evaluate(
        "document.querySelectorAll('#chart [data-jump]').length") >= 1
    perjump = page.evaluate(
        "document.querySelector('[data-testid=\"per-jump-g\"]')"
        ".textContent")
    assert perjump.startswith("Jump 1: "), perjump
    assert "· Jump 2: " in perjump, perjump
    assert perjump.count("±") == 2, perjump
    agree = page.text_content("#step-jumps_agree")
    assert "Jumps agree" in agree, agree
    assert "Jump 1:" in agree and "Jump 2:" in agree, agree
    order = page.evaluate(
        "[...document.querySelectorAll('#steps .step')].map(d => d.id)")
    assert order.index("step-jumps_agree") > order.index("step-fit"), order
    # every chart label (the "Jump 2" end label included) lies inside
    # the chart box and no two overlap
    geom = page.evaluate(_CHART_GEOM_JS)
    box = page.evaluate(
        "() => { const r = document.getElementById('chart')"
        ".getBoundingClientRect();"
        " return [r.left, r.top, r.right, r.bottom]; }")
    rects = [(t["rx"], t["ry"], t["rw"], t["rh"], t["text"])
             for t in geom["texts"] if t["rw"] > 0 and t["rh"] > 0]
    for (x, y, w, h, t) in rects:
        assert x >= box[0] - 1 and y >= box[1] - 1 and \
            x + w <= box[2] + 1 and y + h <= box[3] + 1, (t, box)
    clashes = []
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            if not (a[0] + a[2] <= b[0] + 1 or b[0] + b[2] <= a[0] + 1
                    or a[1] + a[3] <= b[1] + 1 or b[1] + b[3] <= a[1] + 1):
                clashes.append((a[4], b[4]))
    assert clashes == [], clashes

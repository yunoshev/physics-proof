"""M10 probes: build the three real runs, template hash, texts, notices."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from physics_proof.page import (
    DEFAULT_TEXTS,
    build_gallery,
    build_page,
    flight_chart,
    headline_and_color,
    overlay_for_flight,
    parse_step,
    prepare_page,
    recompute_analysis,
    step_urls,
    template_hash,
)
from physics_proof.schema import schema_doc, validate

RUNS = ["2026-10-27-moonb-r2", "2026-10-27-moona-r3", "2026-10-27-wallrun-r2"]
ROOT = Path(__file__).resolve().parent.parent
PLAYER = ROOT / "player"


def load(tag: str) -> dict:
    """One real analysis dict."""
    return json.loads((ROOT / "runs" / tag / "analysis.json").read_text())


def embedded(page: Path, ident: str) -> dict:
    """Parse one embedded JSON script block out of a built page."""
    html = (page / "index.html").read_text(encoding="utf-8")
    match = re.search(re.escape('id="' + ident + '">') + r"(.*?)</script>", html, re.S)
    assert match is not None, ident
    return json.loads(match.group(1).replace("<\\/", "</"))


def test_build_pages_validate_and_fit_budget(tmp_path: Path) -> None:
    """Three builds embed valid JSON; each page without video is under 1 MB."""
    for tag in RUNS:
        out = tmp_path / tag
        info = build_page(ROOT / "runs" / tag, out)
        assert validate(embedded(out, "analysis")) == [], tag
        assert info["page_bytes"] <= 1_000_000, tag
        assert (out / "clip.mp4").exists(), tag
        assert (out / "img" / "poster.jpg").exists(), tag


def test_template_hash_stable_and_copied(tmp_path: Path) -> None:
    """player/HASH matches the template; builds copy it byte-identical."""
    assert (PLAYER / "HASH").read_text().strip() == template_hash(PLAYER)
    copies = []
    for tag in RUNS:
        out = tmp_path / tag
        build_page(ROOT / "runs" / tag, out)
        copies.append(((out / "player.js").read_bytes(),
                       (out / "player.css").read_bytes()))
    assert all(c == copies[0] for c in copies)
    assert copies[0][0] == (PLAYER / "player.js").read_bytes()
    assert copies[0][1] == (PLAYER / "player.css").read_bytes()


def test_every_default_text_is_used_and_overridable(tmp_path: Path) -> None:
    """Every static string comes from DEFAULT_TEXTS; overrides land."""
    player = (PLAYER / "player.js").read_text(encoding="utf-8")
    maker = (ROOT / "physics_proof" / "page.py").read_text(encoding="utf-8")
    missing = [k for k in DEFAULT_TEXTS if k not in player and k not in maker]
    assert missing == []
    analysis = load("2026-10-27-moona-r3")
    assert analysis.get("page_texts") is None
    analysis["page_texts"] = {
        "controls.play": "Roll film",
        "steps.clock.title": "Tick tock",
        "notice.no_timescale": "No clock here.",
        "notice.no_ghost": "No ghost here.",
    }
    probe = dict(analysis)
    probe["timescale"] = None
    probe["flights"] = [dict(f, ghost=[]) for f in analysis["flights"]]
    page = prepare_page(probe, {"model": "m", "cost_usd": 0.01}, "tag")
    assert page["texts"]["controls.play"] == "Roll film"
    assert page["texts"]["steps.clock.title"] == "Tick tock"
    assert page["flights"][0]["ghost_missing"] is True
    import tempfile
    with tempfile.TemporaryDirectory() as scratch:
        run = Path(scratch) / "run"
        run.mkdir()
        (run / "analysis.json").write_text(json.dumps(analysis))
        (run / "clip.mp4").write_bytes(
            (ROOT / "runs/2026-10-27-moona-r3/workspace/clip.mp4").read_bytes())
        build_page(run, tmp_path / "site")
        data = embedded(tmp_path / "site", "page-data")
        assert data["texts"]["controls.play"] == "Roll film"
        assert data["texts"]["notice.no_timescale"] == "No clock here."


def test_missing_sections_give_one_line_notices() -> None:
    """No timescale / no ghost render the step's one-line notice."""
    probe = load("2026-10-27-wallrun-r2")
    probe["timescale"] = None
    page = prepare_page(probe, {}, "tag")
    assert page["has_timescale"] is False
    overlay = overlay_for_flight(probe, probe["flights"][0])
    assert overlay == {"notice": "notice.no_px"}
    chart = flight_chart(probe, probe["flights"][0])
    assert "h" in chart and len(chart["h"]) == len(chart["t"]) > 0
    text = DEFAULT_TEXTS["notice.no_timescale"]
    assert isinstance(text, str) and text


def test_recompute_prints_changes(capsys: pytest.CaptureFixture,
                                tmp_path: Path) -> None:
    """build recomputes verdicts with current blocks and prints the diff."""
    analysis, changes = recompute_analysis(load("2026-10-27-moonb-r2"))
    assert any(c.startswith("/overall/label") for c in changes)
    assert validate(analysis) == []
    analysis2, changes2 = recompute_analysis(load("2026-10-27-moona-r3"))
    assert changes2 == []
    combined, _ = recompute_analysis(load("2026-10-27-wallrun-r2"))
    assert validate(combined) == []
    build_page(ROOT / "runs" / "2026-10-27-moonb-r2", tmp_path / "moonb")
    out = capsys.readouterr().out
    assert "recompute: /overall/label" in out


def test_headline_and_color_cover_states() -> None:
    """Header words and colours for fits, retimed, impossible, undetermined."""
    moon = load("2026-10-27-moona-r3")
    assert headline_and_color(moon["overall"], moon["verdict"]) == ("Moon gravity", "green")
    slow = {"label": "retimed", "text": "x"}
    assert headline_and_color(slow, {"k": 1.46})[1] == "amber"
    assert headline_and_color({"label": "impossible", "text": "x"}, {"k": 1.0}) == (
        "Physically impossible", "red")
    assert headline_and_color({"label": "undetermined", "text": "x"}, {})[1] == "grey"


def test_gallery_lists_built_pages(tmp_path: Path) -> None:
    """Gallery has one card per built analysis with a working link."""
    for tag in RUNS:
        build_page(ROOT / "runs" / tag, tmp_path / tag)
    info = build_gallery(tmp_path)
    assert info["cards"] == 3
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    for tag in RUNS:
        assert tag + "/" in html
    assert "poster.jpg" in html


def test_charts_match_stored_fits() -> None:
    """Prepared chart curves reproduce each stored fit rms (px)."""
    scales = {"2026-10-27-moonb-r2": 0.013647761194029853,
              "2026-10-27-moona-r3": 0.014168333333333333,
              "2026-10-27-wallrun-r2": 11.95609756097561}
    for tag in RUNS:
        analysis = load(tag)
        chart = flight_chart(analysis, analysis["flights"][0])
        assert "notice" not in chart, tag
        mean_sq = sum((h - hf) ** 2 for h, hf in zip(chart["h"], chart["h_fit"]))
        rms_px = (mean_sq / len(chart["h"])) ** 0.5 / scales[tag]
        assert rms_px == pytest.approx(analysis["flights"][0]["fit"]["rms"],
                                       rel=0.01), tag


def test_px_track_points_validate_and_documented() -> None:
    """Optional px survives validation; schema_doc tells the agent to write it."""
    analysis = load("2026-10-27-moona-r3")
    for point in analysis["track"]["points"]:
        point["px"] = [float(point["x"]) * 2.0, float(point["y"]) * 2.0]
    assert validate(analysis) == []
    bad = json.loads(json.dumps(analysis))
    bad["track"]["points"][0]["px"] = [1.0]
    assert any(i.path.endswith("/px") for i in validate(bad))
    assert "px" in schema_doc()


NODE = shutil.which("node")
PLAYER_TEST = ROOT / "tests" / "player_m10.test.js"


def test_player_js_logic_with_node() -> None:
    """Pure-JS step/notice logic under node; skipped when node is absent."""
    if NODE is None:
        pytest.skip("node binary not present")
    assert PLAYER_TEST.exists()
    check = subprocess.run([NODE, "--check", str(PLAYER / "player.js")],
                           capture_output=True, text=True, timeout=60)
    assert check.returncode == 0, check.stderr
    proc = subprocess.run([NODE, str(PLAYER_TEST)], capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_step_url_round_trip(tmp_path: Path) -> None:
    """screens.py URLs parse back to the same step (no Chrome needed)."""
    urls = step_urls("file:///site/slug/index.html", 8)
    assert len(urls) == 8 and urls[3].endswith("?step=3")
    assert parse_step("?step=3", 8) == {"step": 3, "frame": None}
    assert parse_step("?step=99", 8)["step"] == 7
    assert parse_step("?step=x&frame=-2", 8) == {"step": None, "frame": None}
    assert parse_step("?frame=381", 8) == {"step": None, "frame": 381}
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "screens", ROOT / "scripts" / "screens.py")
    assert spec is not None and spec.loader is not None
    screens = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(screens)
    out = tmp_path / "slug"
    build_page(ROOT / "runs" / "2026-10-27-moona-r3", out)
    steps = screens.page_steps(out)
    assert [s["id"] for s in steps] == [s["id"] for s in
                                        embedded(out, "page-data")["steps"]]
    assert steps[0]["id"] == "first-look"

# generated from brief/13 · part 13 owns this file
"""Page-build tests (brief part 13 §§2, 12, 14, 20, 24, 25, 32, 45)."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _read_index(page_dir: Path) -> str:
    return (page_dir / "index.html").read_text(encoding="utf-8")


def _flags(page_dir: Path) -> dict:
    text = _read_index(page_dir)
    m = re.search(
        r'<script id="page-flags" type="application/json">(.*?)</script>',
        text, re.S)
    assert m, "page has no page-flags block"
    return json.loads(m.group(1))


def test_pagebuild_writes_index_html(clip_a_dir):
    assert (clip_a_dir / "index.html").is_file()


def test_pagebuild_inlines_data_and_records_hash(clip_a_dir):
    from src.pagebuild import template_hash

    text = _read_index(clip_a_dir)
    result = json.loads((ROOT / "fixtures/clip-a/result.json").read_text())
    assert result["sentence"] in text
    assert template_hash() in text
    assert _flags(clip_a_dir)["template_hash"] == template_hash()


def test_pagebuild_records_template_hash(clip_a_dir):
    from src.pagebuild import template_hash

    text = _read_index(clip_a_dir)
    assert ("frozen template " + template_hash()) in text


def test_pagebuild_katex_script_and_stylesheet_same_version(clip_a_dir):
    text = _read_index(clip_a_dir)
    versions = re.findall(r"katex@([\d.]+)/dist/katex\.min\.(js|css)", text)
    assert {v[1] for v in versions} == {"js", "css"}
    assert versions[0][0] == versions[1][0]
    assert len(versions) == 2, versions
    assert "katex.min.js" in text and "katex.min.css" in text


def test_pagebuild_weight_under_cap(built_pages):
    for name, page_dir in built_pages.items():
        total = 0
        for path in sorted(page_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() in (".mp4", ".m4v", ".webm"):
                continue
            total += path.stat().st_size
        assert total < 1_000_000, (name, total)


def test_pagebuild_no_missing_warnings(tmp_path, capsys):
    # Both closed fixtures build without a line containing "missing".
    from src.pagebuild import build_page

    for res, vid, summ in (
            ("fixtures/clip-a/result.json",
             "fixtures/clip-a/input/clip.mp4",
             "fixtures/clip-a/summary.json"),
            ("fixtures/run-7/result.json", None, None),
            ("fixtures/still-range/result.json", None, None)):
        build_page(str(ROOT / res), str(ROOT / vid) if vid else None,
                   str(tmp_path / "o"), str(ROOT / summ) if summ else None,
                   slug="w")
    cap = capsys.readouterr()
    assert "missing" not in (cap.out + cap.err).lower()


def test_pagebuild_missing_artifact_fails_with_path(tmp_path):
    from src.pagebuild import build_page

    run_dir = tmp_path / "clip-a"
    run_dir.mkdir()
    src = ROOT / "fixtures/clip-a"
    for rel in ("result.json", "summary.json", "input/timing.json"):
        dest = run_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((src / rel).read_bytes())
    (run_dir / "artifacts").mkdir()
    with pytest.raises(FileNotFoundError, match=r"astronaut\.230-280\.npz"):
        build_page(str(run_dir / "result.json"), None,
                   str(tmp_path / "out"), None, slug="x")


def test_pagebuild_cwd_independent(tmp_path, monkeypatch):
    from src.pagebuild import build_page

    out1 = tmp_path / "a"
    build_page(str(ROOT / "fixtures/clip-a/result.json"),
               str(ROOT / "fixtures/clip-a/input/clip.mp4"),
               str(out1), str(ROOT / "fixtures/clip-a/summary.json"),
               slug="clip-a")
    monkeypatch.chdir(tmp_path)
    out2 = tmp_path / "b"
    build_page(str(ROOT / "fixtures/clip-a/result.json"),
               str(ROOT / "fixtures/clip-a/input/clip.mp4"),
               str(out2), str(ROOT / "fixtures/clip-a/summary.json"),
               slug="clip-a")
    assert ((out1 / "index.html").read_text()
            == (out2 / "index.html").read_text())


def test_pagebuild_strips_absolute_paths(tmp_path):
    from src.pagebuild import build_page

    run_dir = tmp_path / "run-7"
    run_dir.mkdir()
    src = ROOT / "fixtures/run-7"
    for rel in ("result.json",):
        (run_dir / rel).write_bytes((src / rel).read_bytes())
    for f in (src / "artifacts").glob("*"):
        dest = run_dir / "artifacts" / f.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(f.read_bytes())
    summary = {"contract_version": 3, "run_id": "run-7",
               "result_path": str(run_dir / "result.json"),
               "note": str(Path.home() / "operator-notes.txt")}
    (run_dir / "summary.json").write_text(json.dumps(summary))
    out = tmp_path / "out"
    build_page(str(run_dir / "result.json"), None, str(out),
               str(run_dir / "summary.json"), slug="run-7")
    text = (out / "index.html").read_text()
    assert str(run_dir) not in text
    assert str(Path.home()) not in text


def _decoded_loops(flags, seg_id):
    # §45: loops are stored before smoothing, as compact strings.
    from src.pagebuild import decode_smooth_loop

    return {fr: decode_smooth_loop(s)
            for fr, s in flags["smooth_loops"][seg_id].items()}


def test_smooth_loops_traced_and_chamfered(clip_a_dir):
    from src.pagebuild import decode_loop, decode_smooth_loop

    flags = _flags(clip_a_dir)
    stored = flags["smooth_loops"]["hop_a"]
    assert stored, "no smoothed body loops"
    # §45: one compact string per loop, integers in half-pixel units,
    # first point absolute, then deltas.
    for frame, s in stored.items():
        assert isinstance(s, str), (frame, type(s))
        raw = decode_loop(s)
        assert len(raw) >= 3, frame
        for x, y in raw:
            assert abs(x * 2 - round(x * 2)) < 1e-9, (frame, x)
            assert abs(y * 2 - round(y * 2)) < 1e-9, (frame, y)
    loops = {fr: decode_smooth_loop(s) for fr, s in stored.items()}
    result = json.loads((ROOT / "fixtures/clip-a/result.json").read_text())
    raw = {(o["frame"]): o["outline"]
           for s in result["segments"] for o in s["overlay"]}
    checked = 0
    for frame, loop in loops.items():
        assert all(len(p) == 2 for p in loop)
        for x, y in loop:
            assert abs(x * 10 - round(x * 10)) < 1e-6
        pts = [(float(x), float(y)) for x, y in loop]
        if len(pts) > 4 and int(frame) in raw and len(raw[int(frame)]) > 4:
            checked += 1
    assert checked > 0
    # Chaikin corner cutting leaves no axis-aligned staircase: with the
    # smoothed loop, consecutive long edges never meet at a right angle.
    for frame, loop in loops.items():
        pts = [(float(x), float(y)) for x, y in loop]
        n = len(pts)
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            cx, cy = pts[(i + 2) % n]
            v1 = (bx - ax, by - ay)
            v2 = (cx - bx, cy - by)
            l1 = math.hypot(*v1)
            l2 = math.hypot(*v2)
            if l1 > 0.5 and l2 > 0.5:
                cosang = abs(v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)
                assert cosang > math.cos(math.radians(95)) or \
                    cosang < math.cos(math.radians(85)), \
                    f"right angle at frame {frame}"


def _decode_data_url(durl: str):
    import base64

    import cv2
    import numpy as np

    raw = base64.b64decode(durl.split(",", 1)[1])
    return cv2.imdecode(np.frombuffer(raw, dtype=np.uint8),
                        cv2.IMREAD_UNCHANGED)


def _cutout_shapes(page_dir: Path, flags: dict):
    import cv2

    for seg_id, copies in flags["cutouts"].items():
        for c in copies:
            # §45: cut-outs live in the page as data URLs only; the
            # build writes no cut-out file.
            assert "file" not in c and "alpha" not in c, c.get("frame")
            img = _decode_data_url(c["data"])
            alpha = _decode_data_url(c["adata"])
            assert img is not None and alpha is not None
            # (43.1) the mask lives in the alpha channel (RGBA).
            if alpha.ndim == 3 and alpha.shape[2] in (2, 4):
                alpha = alpha[..., -1]
            yield seg_id, c, img, alpha


def test_pagebuild_cutout_mask_in_alpha_channel(clip_a_dir):
    # (43.1) every cut-out mask carries the mask in its alpha
    # channel (RGBA or grey + alpha): a greyscale PNG is opaque
    # everywhere, so destination-in would cut nothing.
    import cv2
    import numpy as np

    flags = _flags(clip_a_dir)
    seen = 0
    for seg_id, copies in flags["cutouts"].items():
        for c in copies:
            dinline = _decode_data_url(c["adata"])
            assert dinline is not None and dinline.ndim == 3 \
                and dinline.shape[2] in (2, 4), (seg_id, c["frame"])
            opaque = float((dinline[..., -1] > 127).mean())
            assert 0.05 < opaque < 0.97, (seg_id, c["frame"], opaque)
            seen += 1
    assert seen >= 5, seen


def test_pagebuild_cutouts_inlined_once(clip_a_dir):
    # §45: a cut-out lives in the page as data URLs only; no cut-out
    # file is written beside the page.
    flags = _flags(clip_a_dir)
    assert flags["cutouts"], "no cutouts inlined"
    for seg_id, copies in flags["cutouts"].items():
        for c in copies:
            assert c["data"].startswith("data:image/jpeg;base64,")
            assert c["adata"].startswith("data:image/png;base64,")
            assert "file" not in c and "alpha" not in c
    leftovers = [p.name for p in clip_a_dir.iterdir()
                 if p.name.startswith("cut_")]
    assert leftovers == [], leftovers


def test_cutouts_4x_silhouettes(clip_a_dir):
    flags = _flags(clip_a_dir)
    seen = 0
    for seg_id, c, img, alpha in _cutout_shapes(clip_a_dir, flags):
        w, h = c["bbox"][2], c["bbox"][3]
        assert img.shape[1] >= 3.5 * w, (seg_id, c["frame"])
        assert img.shape[0] >= 3.5 * h, (seg_id, c["frame"])
        opaque = float((alpha > 127).mean())
        assert 0.30 <= opaque <= 0.90, (seg_id, c["frame"], opaque)
        seen += 1
    assert seen >= 5


def test_pagebuild_cutouts_are_silhouettes(clip_a_dir):
    # Same contract through the alpha channel: silhouettes, not squares.
    flags = _flags(clip_a_dir)
    for seg_id, c, img, alpha in _cutout_shapes(clip_a_dir, flags):
        opaque = float((alpha > 127).mean())
        assert opaque < 1.0, (seg_id, c["frame"])
        assert opaque >= 0.30, (seg_id, c["frame"], opaque)


def test_player_template_has_no_css_mask():
    text = (ROOT / "player/template.html").read_text(encoding="utf-8")
    assert "mask-image" not in text


def test_player_template_single_format_function():
    text = (ROOT / "player/template.html").read_text(encoding="utf-8")
    assert text.count("function fmtVal(") == 1
    assert "toPrecision" not in text


def test_contract_version_matches_src(clip_a_dir):
    from src.contract import CONTRACT_VERSION

    assert _flags(clip_a_dir)["contract_version"] == CONTRACT_VERSION


def _raster(loop, shape):
    import cv2
    import numpy as np

    img = np.zeros(shape, dtype=np.uint8)
    pts = np.asarray([[[p[0], p[1]]] for p in loop], dtype=np.float32)
    cv2.fillPoly(img, [pts.astype(np.int32)], 1)
    return img > 0


def _mask_of(run_dir, artifact, object_id, frame):
    import numpy as np

    from src.pagebuild.build import _load_npz_masks

    masks = _load_npz_masks(Path(run_dir) / artifact, object_id)
    return np.asarray(masks[int(frame)])


def test_figure_selection_run22():
    # 42.1: the figure is the whole moving body — on run 22 the whole
    # astronaut's mask (t8_segment_0.npz object 0), not the tracked
    # backpack (the segment's own t13 object 0).
    import json

    from src.pagebuild import select_figure

    run = ROOT / "fixtures/source/run-22"
    result = json.loads((run / "result.json").read_text())
    figs = select_figure(result, run)
    assert figs["leap_a"]["artifact"] == "artifacts/t8_segment_0.npz"
    assert str(figs["leap_a"]["object_id"]) == "0"
    # Clip-a's figure is the astronaut object of its segment mask.
    clip = json.loads((ROOT / "fixtures/clip-a/result.json").read_text())
    cfigs = select_figure(clip, ROOT / "fixtures/clip-a")
    assert cfigs["hop_a"]["artifact"] == "artifacts/astronaut.230-280.npz"
    assert str(cfigs["hop_a"]["object_id"]) == "1"


def test_figure_selection_falls_back_to_segment_mask():
    # 42.1: when no cited object passes (run 7's legacy masks cannot be
    # mapped to frames), the figure is the segment's own mask object.
    import json

    from src.pagebuild import select_figure

    run = ROOT / "fixtures/run-7"
    result = json.loads((run / "result.json").read_text())
    figs = select_figure(result, run)
    seg = result["segments"][0]
    assert figs["hop_a"]["artifact"] == seg["mask"]["artifact"]
    assert str(figs["hop_a"]["object_id"]) == str(
        seg["mask"]["object_id"])


def test_figure_outline_vertices_and_iou(run22_page):
    # 42.2: outlines come from mask pixels only — the apex figure loop
    # has ≥ 150 vertices, the scale reference loop ≥ 80, and the
    # reference fill matches the backpack mask (IoU ≥ 0.9).
    import json

    import numpy as np

    from src.pagebuild import decode_smooth_loop

    run = ROOT / "fixtures/source/run-22"
    result = json.loads((run / "result.json").read_text())
    flags = _flags(run22_page)
    seg = result["segments"][0]
    apex = str(seg["frames"]["apex"])
    fig_loop = decode_smooth_loop(
        flags["smooth_loops"][seg["id"]][apex])
    assert len(fig_loop) >= 150, len(fig_loop)
    ref_loop = decode_smooth_loop(flags["ref_loops"]["0"])
    assert len(ref_loop) >= 80, len(ref_loop)
    m = _mask_of(run, result["references"][0]["mask"]["artifact"],
                 result["references"][0]["mask"]["object_id"],
                 result["scale"]["frame"])
    ras = _raster(ref_loop, m.shape)
    m = m > 0
    iou = float((ras & m).sum()) / float((ras | m).sum())
    assert iou >= 0.9, iou
    # The chronophotograph draws whole figures: ≥ 4 cut-outs, each at
    # least 90 % of the figure mask's height at the apex frame.
    fig = flags["figure"][seg["id"]]
    fm = _mask_of(run, fig["artifact"], fig["object_id"],
                  seg["frames"]["apex"])
    nz = np.argwhere(fm > 0)
    mh = int(nz[:, 0].max() - nz[:, 0].min() + 1)
    cuts = flags["cutouts"][seg["id"]]
    assert len(cuts) >= 4, len(cuts)
    for c in cuts:
        assert c["bbox"][3] >= 0.9 * mh, (c["frame"], c["bbox"][3], mh)


def _keyframe_times(video: Path) -> list[float]:
    import shutil
    import subprocess

    ffprobe = shutil.which("ffprobe")
    assert ffprobe, "ffprobe is required for the keyframe test"
    out = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "packet=pts_time,flags",
         "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    times = []
    for line in out.stdout.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and "K" in parts[1] and parts[0]:
            try:
                times.append(float(parts[0]))
            except ValueError:
                continue
    return times


def test_pagebuild_keyframes_within_half_second(clip_a_dir, run22_page):
    # 44.1: the page video has a keyframe at least every 0.5 s
    # (libx264 -g = -keyint_min = round(fps / 2)), so exact
    # currentTime seeks stay fast in every browser.
    for page_dir in (clip_a_dir, run22_page):
        video = page_dir / "clip.mp4"
        assert video.is_file(), page_dir
        times = _keyframe_times(video)
        assert len(times) >= 2, (page_dir, times)
        assert times[0] <= 0.05, (page_dir, times[:3])
        for a, b in zip(times, times[1:]):
            assert b - a <= 0.5 + 1e-6, (page_dir, a, b)


def test_player_template_no_fastseek():
    # 44.1: seeks are exact — the template never calls fastSeek
    # (Firefox/Safari land on the nearest keyframe and the ride loops).
    text = (ROOT / "player/template.html").read_text(encoding="utf-8")
    assert ".fastSeek" not in text


def test_pagebuild_run22_and_fake1_under_cap(run22_page, fake1_page):
    # §45: the pages of fixtures/source/run-22/ and fake-1/ build,
    # and each is < 1 MB without the video.
    for name, page_dir in (("run-22", run22_page), ("fake-1", fake1_page)):
        total = 0
        for path in sorted(page_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() in (".mp4", ".m4v", ".webm"):
                continue
            total += path.stat().st_size
        assert total < 1_000_000, (name, total)


def test_pagebuild_figure_loops_compact(run22_page):
    # §45: on run 22's page the figure loops take ≤ 200 KB.
    flags = _flags(run22_page)
    size = len(json.dumps(flags["smooth_loops"]).encode("utf-8"))
    assert size <= 200_000, size


def test_pagebuild_decoded_loop_matches_smoothing():
    # §45: a decoded, smoothed loop matches the build-side smoothing
    # of the same mask within 0.05 px at every point.
    from src.pagebuild import (decode_loop, decode_smooth_loop,
                               trace_mask_contour)
    from src.pagebuild.build import _load_npz_masks

    run = ROOT / "fixtures/source/run-22"
    result = json.loads((run / "result.json").read_text())
    from src.pagebuild import select_figure

    figs = select_figure(result, run)
    seg = result["segments"][0]
    fig = figs[seg["id"]]
    masks = _load_npz_masks(run / fig["artifact"], fig["object_id"])
    checked = 0
    for fr in sorted(masks)[:6]:
        m = masks[fr]
        direct = trace_mask_contour(m)
        if not direct:
            continue
        from src.pagebuild import encode_loop, trace_raw_loop

        s = encode_loop(trace_raw_loop(m))
        back = decode_smooth_loop(s)
        assert len(back) == len(direct), (fr, len(back), len(direct))
        for (x1, y1), (x2, y2) in zip(back, direct):
            assert abs(x1 - x2) <= 0.05 and abs(y1 - y2) <= 0.05, \
                (fr, (x1, y1), (x2, y2))
        checked += 1
    assert checked > 0


def test_pagebuild_over_limit_trims_instead_of_failing(
        tmp_path, capsys, monkeypatch):
    # §45: a page forced over the limit still builds and logs its trims.
    import src.pagebuild.build as b

    from src.pagebuild import build_page

    monkeypatch.setattr(b, "WEIGHT_LIMIT_BYTES", 100_000)
    out = tmp_path / "forced"
    build_page(str(ROOT / "fixtures/clip-a/result.json"),
               str(ROOT / "fixtures/clip-a/input/clip.mp4"),
               str(out), str(ROOT / "fixtures/clip-a/summary.json"),
               slug="forced")
    assert (out / "index.html").is_file()
    logged = capsys.readouterr().out.lower()
    assert "trimm" in logged or "thinn" in logged, logged


def test_pagebuild_inlines_retime_factors(clip_a_dir):
    # 41: a world chip that needs a retime reads it from
    # retime_factor — the built page inlines the candidates whole.
    result = json.loads((ROOT / "fixtures/clip-a/result.json").read_text())
    text = _read_index(clip_a_dir)
    m = re.search(
        r'<script id="result-data" type="application/json">(.*?)</script>',
        text, re.S)
    inlined = json.loads(m.group(1))
    assert inlined["worlds"]["candidates"] == \
        result["worlds"]["candidates"]
    assert all("retime_factor" in c
               for c in inlined["worlds"]["candidates"])
    assert "Moon" in text and "Earth" in text

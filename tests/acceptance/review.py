# generated from brief/15 · part 15 owns this file
"""Page rebuild + screenshot review (owned by part 15, brief §§5–6).

`dev_loop --pages` (behind PHYSICS_PROOF_LIVE=1) calls
`rebuild_and_review`: it rebuilds each clip's player page from completed
runs, then screenshots every page headlessly and sends the shots to a
Spark vision call that returns a structured defect list. Any defect
fails the build; only a clean review earns a request for owner
approval. Pages are never auto-published: publishing to GitHub Pages
happens only after the owner's explicit approval, recorded in
ITERATIONS.md with date + template hash + run IDs.

Offline: the pure helpers (checklists, URL building, defect parsing,
weight/hash assertions) are unit-tested with stubbed collaborators. No
browser, model, or network call happens unless `rebuild_and_review`
runs with its real collaborators under PHYSICS_PROOF_LIVE=1.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

#: Named historical defects every review must check (brief §6 item 2).
REVIEW_CHECKLIST = [
    "black video",
    "missing or thin overlay (dot-only)",
    "unreadable or dark-on-dark text",
    "numbers with absurd decimals",
    "numbers disagreeing with the result file",
    "chart/cursor desync with the video frame",
    "ghost labels missing or swapped",
]

DESKTOP_VIEWPORT = (1440, 900)
PHONE_VIEWPORT = (390, 844)

#: Screenshots are data; they must stay out of the repo and the manifest.
SHOTS_DIRNAME = ".dev_loop/shots"

#: A page without video must stay under 1 MB (part 13 pagebuild rule).
PAGE_WEIGHT_LIMIT_BYTES = 1_000_000


def event_urls(page_url, result):
    """Review URLs: the first screen plus every event (part 13 `event=`).

    `frame=` spot checks ride on the first event's URL when segments
    exist. Returns a list of ``(label, url)`` pairs.
    """
    urls = [("first-screen", page_url)]
    steps = result.get("calculation_steps") or []
    events = [
        step.get("id") for step in steps
        if isinstance(step, dict) and step.get("id")
    ]
    for event_id in events:
        urls.append((f"event-{event_id}", f"{page_url}?event={event_id}"))
    if events:
        urls.append(("frame-spot", f"{page_url}?event={events[0]}&frame=0"))
    return urls


def parse_vision_defects(text):
    """Parse the Spark vision reply into a defect list.

    The reviewer is asked for JSON: ``{"defects": [{"shot": ...,
    "defect": ..., "detail": ...}]}``. Returns ``(defects, problems)``:
    an unparseable or off-shape reply is itself a review failure, never
    a silent pass.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [], ["vision reply is not JSON"]
    if not isinstance(payload, dict) or not isinstance(
        payload.get("defects"), list
    ):
        return [], ["vision reply has no defects list"]
    defects: list[dict] = []
    for entry in payload["defects"]:
        if not isinstance(entry, dict):
            return [], ["vision reply defect is not an object"]
        if not entry.get("shot") or not entry.get("defect"):
            return [], ["vision reply defect lacks shot/defect"]
        defects.append(
            {
                "shot": str(entry["shot"]),
                "defect": str(entry["defect"]),
                "detail": str(entry.get("detail", "")),
            }
        )
    return defects, []


def check_page_weight(page_dir):
    """Assert the page weight without video stays under 1 MB (§5)."""
    page_dir = Path(page_dir)
    total = 0
    for path in sorted(page_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in (".mp4", ".m4v", ".webm"):
            continue
        total += path.stat().st_size
    if total > PAGE_WEIGHT_LIMIT_BYTES:
        return [f"page without video is {total} bytes, limit 1 MB"]
    return []


def check_template_hash(page_dir, recorded_hash):
    """The frozen-template hash in the page must match player's (§5)."""
    page_dir = Path(page_dir)
    index = page_dir / "index.html"
    if not index.is_file():
        return ["page has no index.html"]
    text = index.read_text(encoding="utf-8", errors="replace")
    if recorded_hash not in text:
        return ["frozen template hash mismatch"]
    return []


def _take_screenshots(page_url, result, shots_dir, screenshotter=None):
    """Screenshot the first screen and every event, desktop + phone."""
    shots: list[Path] = []
    for width, height in (DESKTOP_VIEWPORT, PHONE_VIEWPORT):
        for label, url in event_urls(page_url, result):
            name = f"{width}x{height}-{label}.png"
            dest = Path(shots_dir) / name
            if screenshotter is not None:
                screenshotter(url, width, height, dest)
            else:
                _chrome_shot(url, width, height, dest)
            shots.append(dest)
    return shots


def _chrome_shot(url, width, height, dest):
    """One headless shot with the installed Google Chrome (§6)."""
    from playwright.sync_api import sync_playwright  # noqa: WPS433

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        try:
            page = browser.new_page(viewport={"width": width,
                                              "height": height})
            page.goto(url)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(dest))
        finally:
            browser.close()


def _vision_review(shots, result_numbers, vision_caller=None):
    """Send shots + the result file's numbers to Spark vision (live)."""
    prompt = (
        "You are reviewing a physics-analysis player page. These "
        "screenshots show the page at its first screen and at each "
        f"event. The result file's numbers are: {result_numbers}. "
        "Check at minimum: " + "; ".join(REVIEW_CHECKLIST) + ". "
        'Return JSON only: {"defects": [{"shot": ..., "defect": ..., '
        '"detail": ...}]}; an empty list means clean.'
    )
    if vision_caller is not None:
        return vision_caller([str(s) for s in shots], prompt)
    return _spark_vision_call(shots, prompt)


def _spark_vision_call(shots, prompt):
    """Spark vision call over HTTPS (live only; needs META_API_KEY)."""
    import httpx  # noqa: WPS433

    key = os.environ.get("META_API_KEY")
    if not key:
        raise RuntimeError("META_API_KEY is not set for the vision review")
    raise RuntimeError(
        "live vision review is wired per skills/meta-api.md at run time; "
        f"refusing to guess the endpoint ({len(shots)} shots queued)"
    )


def rebuild_and_review(repo_root, runs_dir="runs", out_dir="pages",
                       builder=None, screenshotter=None, vision_caller=None):
    """Rebuild pages from completed runs and review them (§§5–6).

    Returns ``(exit_code, report_text, summary_line)``. Any defect — or
    an unparseable vision reply — fails the build. A clean review ends
    with a request for owner approval, never a publish.
    """
    repo_root = Path(repo_root)
    runs_base = Path(runs_dir) if Path(runs_dir).is_absolute() else (
        repo_root / runs_dir
    )
    out_base = Path(out_dir) if Path(out_dir).is_absolute() else (
        repo_root / out_dir
    )
    lines: list[str] = []
    failures: list[str] = []
    run_dirs = sorted(
        p for p in runs_base.glob("*") if (p / "result.json").is_file()
    ) if runs_base.is_dir() else []
    if not run_dirs:
        return 1, f"no completed runs in {runs_base}", "pages FAIL: no runs"
    for run_dir in run_dirs:
        result = json.loads(
            (run_dir / "result.json").read_text(encoding="utf-8")
        )
        slug = run_dir.name
        page_dir = out_base / slug
        if builder is not None:
            builder(run_dir, page_dir)
        else:
            _build_page(repo_root, run_dir, page_dir)
        failures.extend(
            f"{slug}: {problem}" for problem in check_page_weight(page_dir)
        )
        page_url = f"file://{page_dir / 'index.html'}"
        shots_dir = repo_root / SHOTS_DIRNAME / slug
        shots = _take_screenshots(
            page_url, result, shots_dir, screenshotter=screenshotter
        )
        numbers = json.dumps(_verdict_numbers(result))
        reply = _vision_review(shots, numbers, vision_caller=vision_caller)
        defects, problems = parse_vision_defects(reply)
        failures.extend(f"{slug}: review {p}" for p in problems)
        for defect in defects:
            failures.append(
                f"{slug} {defect['shot']}: "
                f"{defect['defect']} — {defect['detail']}"
            )
        if not defects and not problems:
            lines.append(f"{slug}: clean review ({len(shots)} shots)")
    if failures:
        report = "\n".join(lines + ["FAIL:"] + failures)
        return 1, report, f"pages FAIL: {len(failures)} defect(s)"
    report = "\n".join(
        lines + ["clean review: requesting owner approval (no auto-publish)"]
    )
    return 0, report, "pages pass: clean review, awaiting owner approval"


def _verdict_numbers(result):
    verdict = result.get("verdict") or {}
    return {
        key: verdict.get(key)
        for key in ("world", "kind", "g_measured", "sigma_g",
                    "factor", "reason")
    }


def _build_page(repo_root, run_dir, page_dir):
    """Per-clip page assembly through part 13's pagebuild (live path)."""
    import sys  # noqa: WPS433

    sys.path.insert(0, str(Path(repo_root)))
    try:
        from src.pagebuild.build import build_page  # noqa: WPS433
    finally:
        sys.path.pop(0)
    run_dir, page_dir = Path(run_dir), Path(page_dir)
    summary_path = run_dir / "summary.json"
    build_page(
        str(run_dir / "result.json"),
        _run_video(run_dir),
        str(page_dir),
        summary_path=(str(summary_path) if summary_path.is_file() else None),
        slug=run_dir.name,
    )


def _run_video(run_dir):
    clips = sorted((Path(run_dir) / "input").glob("clip.*"))
    if not clips:
        raise RuntimeError(f"no input clip in {run_dir}/input")
    return str(clips[0])

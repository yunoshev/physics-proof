#!/usr/bin/env python3
# generated from brief/15 · part 15 owns this file
"""Build the demo gallery from completed runs (brief part 15 §7).

Takes completed runs (`runs/<run-id>/` with `result.json`, `summary.json`
and `input/clip.*`) and produces per-clip player pages plus the gallery
`index.html` in the output dir, through part 13's pagebuild. The demo
video is recorded by the owner from these approved pages — never from a
live run.

Usage: scripts/demo/build_demo_pages.py [--runs-dir runs] [--out pages]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_demo_pages(runs_dir: Path, out_dir: Path) -> list[str]:
    """Build one page per completed run plus the gallery; return slugs."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    try:
        from src.pagebuild import build_gallery, build_page
    finally:
        sys.path.pop(0)
    runs_dir, out_dir = Path(runs_dir), Path(out_dir)
    run_dirs = sorted(
        p for p in runs_dir.glob("*")
        if (p / "result.json").is_file()
    ) if runs_dir.is_dir() else []
    if not run_dirs:
        raise RuntimeError(f"no completed runs in {runs_dir}")
    pages = []
    for run_dir in run_dirs:
        clips = sorted((run_dir / "input").glob("clip.*"))
        if not clips:
            raise RuntimeError(f"no input clip in {run_dir}/input")
        summary = run_dir / "summary.json"
        page_dir = out_dir / run_dir.name
        build_page(
            str(run_dir / "result.json"),
            str(clips[0]),
            str(page_dir),
            summary_path=(str(summary) if summary.is_file() else None),
            slug=run_dir.name,
        )
        poster = page_dir / "poster.jpg"
        pages.append({
            "title": run_dir.name,
            "href": f"{run_dir.name}/index.html",
            "poster": f"{run_dir.name}/poster.jpg" if poster.is_file() else "",
        })
    build_gallery(pages, str(out_dir))
    return [p["title"] for p in pages]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build demo player pages + gallery from completed runs."
    )
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--out", default="pages")
    args = parser.parse_args(argv)
    try:
        slugs = build_demo_pages(Path(args.runs_dir), Path(args.out))
    except RuntimeError as exc:
        print(f"build_demo_pages: {exc}", file=sys.stderr)
        return 1
    print(f"build_demo_pages: built {len(slugs)} page(s): "
          + ", ".join(slugs))
    return 0


if __name__ == "__main__":
    sys.exit(main())

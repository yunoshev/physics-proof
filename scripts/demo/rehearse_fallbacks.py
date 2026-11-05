#!/usr/bin/env python3
# generated from brief/15 · part 15 owns this file
"""Rehearse the demo fallbacks (brief part 15 §7) without spending money.

Checks, against a local pages directory:
1. The `file://` fallback: every expected page exists and opens from a
   local folder (the player is `file://` by design, part 13), so the demo
   survives unreachable GitHub Pages.
2. The fresh-analysis fallback: prints the one command that runs a new
   analysis end to end (7–11 min typical) — the demo never depends on it,
   so this script never runs it, only shows it.
3. Template-hash equality: each page's frozen template hash matches
   `player/`'s recorded hash, which is the fresh-clone reproduction check
   (§7: local pages behave identically to the published ones).

Usage: scripts/demo/rehearse_fallbacks.py [--pages pages]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def check_file_fallback(pages_dir: Path) -> list[str]:
    """Every page present locally; return problems (empty passes)."""
    pages_dir = Path(pages_dir)
    problems: list[str] = []
    gallery = pages_dir / "index.html"
    if not gallery.is_file():
        return [f"missing gallery {gallery}"]
    clips = sorted(
        p for p in pages_dir.glob("*")
        if p.is_dir() and (p / "index.html").is_file()
    )
    if not clips:
        problems.append(f"no per-clip pages under {pages_dir}")
    for clip in clips:
        text = (clip / "index.html").read_text(
            encoding="utf-8", errors="replace"
        )
        if "http://127.0.0.1" in text or "http://localhost" in text:
            problems.append(
                f"{clip.name}/index.html points at a local server; "
                "pages must work over file://"
            )
        print(f"file://{clip / 'index.html'}")
    print(f"file://{gallery}")
    return problems


def check_template_hashes(pages_dir: Path) -> list[str]:
    """Each page's recorded hash must equal player's (fresh-clone check)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    try:
        from src.pagebuild import template_hash
    finally:
        sys.path.pop(0)
    expected = template_hash()
    problems: list[str] = []
    for index in sorted(Path(pages_dir).glob("*/index.html")):
        text = index.read_text(encoding="utf-8", errors="replace")
        if expected not in text:
            problems.append(
                f"{index.parent.name}: frozen template hash mismatch"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rehearse demo fallbacks against local pages."
    )
    parser.add_argument("--pages", default="pages")
    args = parser.parse_args(argv)
    problems = check_file_fallback(Path(args.pages))
    problems += check_template_hashes(Path(args.pages))
    print("fresh analysis (not run here; 7-11 min typical):")
    print("  uv run python -m src.cli <video> --runs-dir runs")
    if problems:
        for problem in problems:
            print(f"rehearse_fallbacks: {problem}", file=sys.stderr)
        return 1
    print("rehearse_fallbacks: file:// fallback and template hashes OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

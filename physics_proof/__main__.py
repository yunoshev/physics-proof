"""M8/M12 command surface: ``run``, M10: ``build`` and ``gallery``."""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from .agent import run_analysis

__all__ = ["main"]


def _slug(video: Path, tag: str | None) -> str:
    """Run directory tag: explicit tag or the clip stem, file-safe."""
    raw = tag or video.stem
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", raw).strip("-").lower()
    return cleaned or "clip"


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m physics_proof``."""
    parser = argparse.ArgumentParser(prog="physics_proof")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one analysis on a video")
    run.add_argument("video", help="input video file (mp4/mov)")
    run.add_argument("--tag", default=None, help="run tag; default is the clip name")
    run.add_argument("--tier", default="contributor", choices=("contributor", "standard"))
    run.add_argument("--cap-usd", type=float, default=2.0)
    run.add_argument("--turns", type=int, default=60)
    run.add_argument("--effort", type=str, default="high")
    run.add_argument("--resume", action="store_true")
    build = sub.add_parser("build", help="build a static page from a run directory")
    build.add_argument("run_dir", help="run directory holding analysis.json")
    build.add_argument("--out", default=None,
                       help="output directory; default site/<run tag>")
    gallery = sub.add_parser("gallery", help="regenerate the gallery index")
    gallery.add_argument("--site", default="site", help="site directory")
    args = parser.parse_args(argv)

    if args.command == "build":
        from .page import build_page
        info = build_page(args.run_dir, args.out)
        print("page: " + str(info["out"]), flush=True)
        return 0
    if args.command == "gallery":
        from .page import build_gallery
        info = build_gallery(args.site)
        print("cards: " + str(info["cards"]), flush=True)
        return 0

    if args.command == "run":
        video = Path(args.video)
        if not video.exists():
            parser.error("no such video: " + str(video))
        run_dir = Path("runs") / (date.today().isoformat() + "-" + _slug(video, args.tag))
        summary = run_analysis(
            video,
            run_dir,
            tier=args.tier,
            cap_usd=args.cap_usd,
            max_turns=args.turns,
            resume=args.resume,
            effort=args.effort,
        )
        print("status: " + summary.status, flush=True)
        print("turns: " + str(summary.turns), flush=True)
        print("cost: $%.6f" % summary.cost_usd, flush=True)
        if summary.analysis_path is not None:
            print("analysis: " + str(summary.analysis_path), flush=True)
        else:
            print("analysis: none", flush=True)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

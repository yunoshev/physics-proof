"""M10 screenshots: one headless-Chrome shot per page step.

Maintainer-run: ``python scripts/screens.py site/<slug>``. Chrome is
expected at /Applications/Google Chrome.app/Contents/MacOS/Google Chrome;
without it the script fails with a clear message. The URL/step logic is
kept next to physics_proof.page so tests can cover it without Chrome.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from physics_proof.page import parse_step, step_urls

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

__all__ = ["page_steps", "main"]


def page_steps(page_dir: str | Path) -> list[dict]:
    """Step list from a built page's embedded page-data."""
    html = Path(page_dir, "index.html").read_text(encoding="utf-8")
    marker = 'id="page-data">'
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    payload = html[start:end].replace("<\\/", "</")
    return json.loads(payload)["steps"]


def main(argv: list[str] | None = None) -> int:
    """Screenshot every step of one built page."""
    args = list(argv) if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python scripts/screens.py site/<slug>", flush=True)
        return 2
    page_dir = Path(args[0])
    if not (page_dir / "index.html").exists():
        print("no built page at " + str(page_dir), flush=True)
        return 2
    chrome = Path(CHROME)
    if not chrome.exists():
        print("Chrome not found at " + CHROME + "; install it or run on macOS",
              flush=True)
        return 3
    steps = page_steps(page_dir)
    base = "file://" + str((page_dir / "index.html").resolve())
    shots = Path(page_dir, "screens")
    shots.mkdir(parents=True, exist_ok=True)
    for i, step in enumerate(steps):
        url = step_urls(base, len(steps))[i]
        dest = shots / ("step-" + str(i) + ".png")
        cmd = [str(chrome), "--headless=new", "--disable-gpu",
               "--window-size=1280,900", "--hide-scrollbars",
               "--screenshot=" + str(dest), url]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not dest.exists():
            print("shot " + str(i) + " (" + str(step.get("id"))
                  + ") failed, exit " + str(proc.returncode) + " for " + url
                  + ": " + proc.stderr.strip()[-500:], flush=True)
            return 1
        print("shot " + str(dest), flush=True)
    void = parse_step("?step=0", len(steps))
    assert void["step"] == 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

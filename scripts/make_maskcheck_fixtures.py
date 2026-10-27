"""Make M7 fixtures: a 10-frame clip plus two mask files.

Clip: grey background, a red box with a blue handle on top drifting right.
Masks: (a) box + handle, (b) box only. All synthetic, drawn by this script.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from physics_proof.blocks import save_masks  # noqa: E402

WIDTH, HEIGHT, NFRAMES = 320, 240, 10
BOX_W, BOX_H, HANDLE_W, HANDLE_H = 90, 70, 40, 24
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def paint(frame: int) -> tuple[np.ndarray, np.ndarray]:
    """Paint one RGB frame and its box+handle mask row (H, W bool)."""
    x = 60 + 4 * frame
    y = 130
    img = np.full((HEIGHT, WIDTH, 3), 160, dtype=np.uint8)
    img[y : y + BOX_H, x : x + BOX_W] = (230, 30, 30)
    img[y - HANDLE_H : y, x + 25 : x + 25 + HANDLE_W] = (30, 80, 230)
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    mask[y : y + BOX_H, x : x + BOX_W] = True
    mask[y - HANDLE_H : y, x + 25 : x + 25 + HANDLE_W] = True
    return img, mask


def main() -> None:
    """Draw the clip frames, encode them, and save both mask files."""
    frames = list(range(NFRAMES))
    masks_a = np.zeros((NFRAMES, HEIGHT, WIDTH), dtype=bool)
    masks_b = np.zeros((NFRAMES, HEIGHT, WIDTH), dtype=bool)
    with tempfile.TemporaryDirectory() as tmp:
        for i in frames:
            img, full = paint(i)
            Image.fromarray(img).save(Path(tmp) / ("f%02d.png" % i))
            masks_a[i] = full
            x = 60 + 4 * i
            y = 130
            box = np.zeros((HEIGHT, WIDTH), dtype=bool)
            box[y : y + BOX_H, x : x + BOX_W] = True
            masks_b[i] = box
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-framerate", "10", "-i", str(Path(tmp) / "f%02d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "18", "-preset", "veryfast",
            str(OUT / "maskcheck_clip.mp4"),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError("ffmpeg failed: " + proc.stderr.strip())
    save_masks(OUT / "maskcheck_a.npz", frames, [1], {1: masks_a}, [1.0])
    save_masks(OUT / "maskcheck_b.npz", frames, [1], {1: masks_b}, [1.0])
    print("wrote maskcheck_clip.mp4, maskcheck_a.npz, maskcheck_b.npz", flush=True)


if __name__ == "__main__":
    main()

# generated from brief/13 · part 13 owns this file
"""Page build: template + inlined data + assets -> ``index.html``.

Only interface used by part 15::

    build_page(result_path, video_path, out_dir,
               summary_path=None, slug=None, sidecar_path=None)
    build_gallery(pages, out_dir)
    template_hash()
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

PLAYER_DIR = Path(__file__).resolve().parent.parent.parent / "player"
TEMPLATE_PATH = PLAYER_DIR / "template.html"

# Pinned KaTeX version: script and stylesheet share it (part 13 §23.1).
KATEX_VERSION = "0.16.11"

# Page weight without video must stay under 1 MB (part 13 §12).
WEIGHT_LIMIT_BYTES = 1_000_000

# Cut-out geometry (part 13 §25): cut-outs are drawn at 4x resolution
# from the smoothed contour, edge feathered by a 0.55-video-px blur.
CUTOUT_SCALE = 4
FEATHER_VIDEO_PX = 0.55

_TOKEN_RESULT = "/*__PP_RESULT_JSON__*/null"
_TOKEN_SUMMARY = "/*__PP_SUMMARY_JSON__*/null"
_TOKEN_FLAGS = "/*__PP_FLAGS_JSON__*/null"
_TOKEN_HASH = "__PP_TEMPLATE_HASH__"


def template_hash() -> str:
    """SHA-256 of the frozen player template (part 13 §2)."""
    return hashlib.sha256(TEMPLATE_PATH.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Path scrubbing (part 13 §24)
# ---------------------------------------------------------------------------

def _scrub_strings(node, replacements: list[tuple[str, str]]):
    if isinstance(node, dict):
        return {k: _scrub_strings(v, replacements) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub_strings(v, replacements) for v in node]
    if isinstance(node, str):
        for old, new in replacements:
            if old and old in node:
                node = node.replace(old, new)
        return node
    return node


def strip_absolute_paths(obj, run_dir: Path):
    """Replace absolute filesystem paths with run-relative forms.

    Any string holding the run directory's absolute path is rewritten
    relative to the run directory; absolute paths outside it become
    their basename (part 13 §24). The home folder never leaks.
    """
    run_abs = str(run_dir.resolve())
    home = str(Path.home())
    reps: list[tuple[str, str]] = []

    def _rel(p: str) -> str:
        try:
            return os.path.relpath(p, run_abs)
        except ValueError:
            return os.path.basename(p)

    # Collect candidate absolute paths appearing in the object.
    found: set[str] = set()

    def _collect(node):
        if isinstance(node, dict):
            for v in node.values():
                _collect(v)
        elif isinstance(node, list):
            for v in node:
                _collect(v)
        elif isinstance(node, str):
            for m in re.finditer(r"/[^\s\"']{2,}", node):
                found.add(m.group(0).rstrip(".,:)]}"))

    _collect(obj)
    for p in sorted(found, key=len, reverse=True):
        if p.startswith(run_abs):
            reps.append((p, _rel(p)))
        elif p == home or p.startswith(home + "/"):
            reps.append((p, os.path.basename(p.rstrip("/")) or "~"))
    # Always neutralise the raw prefixes even when no longer path was seen.
    reps.append((run_abs, os.path.basename(run_abs)))
    reps.append((home, "~"))
    cwd = os.getcwd()
    if cwd != "/" and cwd != home:
        reps.append((cwd, os.path.basename(cwd)))
    return _scrub_strings(obj, reps)


# ---------------------------------------------------------------------------
# Artifact resolution (part 13 §21.1: resolve against the run folder)
# ---------------------------------------------------------------------------

def _need(run_dir: Path, rel: str) -> Path:
    """Resolve an artifact path against the run folder or fail with it."""
    p = run_dir / rel
    if not p.is_file():
        raise FileNotFoundError(f"page build: artifact not found: {rel}")
    return p


def _maybe(run_dir: Path, rel: str) -> Path | None:
    p = run_dir / rel
    return p if p.is_file() else None


def _match_id(want, have) -> bool:
    """Object-id equality across str/int spellings (part 13 section 21)."""
    if want is None:
        return True
    try:
        return int(str(want)) == int(str(have))
    except (ValueError, TypeError):
        return str(want) == str(have)


def _load_npz_all(npz_path: Path) -> dict:
    """Map object key -> {video frame number -> boolean mask array}.

    Supports the helpers ``masks_io`` shape (``__helpers_index__`` of
    frame/key rows), the clip-A converter shape
    (frames/ids/masks/present) and the legacy run shape (``mask_N`` keys
    in file order, frames 0..n). Unknown shapes yield ``{}``: a mask
    that cannot be mapped is never drawn from (part 13 §42.2).
    """
    import numpy as np

    z = np.load(str(npz_path), allow_pickle=True)
    keys = list(z.keys())
    if "__helpers_index__" in keys:
        try:
            index = json.loads(str(z["__helpers_index__"]))
        except (ValueError, TypeError):
            return {}
        if not isinstance(index, list):
            return {}
        out: dict = {}
        for row in index:
            try:
                key = row["key"]
                fr = int(row["frame"])
            except (KeyError, ValueError, TypeError):
                continue
            if key not in keys:
                continue
            oid = (int(row["oid"]) if row.get("int_oid")
                   else str(row.get("oid")))
            try:
                m = np.asarray(z[key]) > 0
            except (ValueError, TypeError, KeyError):
                continue
            if m.ndim != 2:
                continue
            out.setdefault(oid, {})[fr] = m
        return out
    if "masks" in keys and "frames" in keys:
        frames = [int(f) for f in z["frames"]]
        ids = list(z["ids"])
        masks = z["masks"]
        out = {}
        for j, oid in enumerate(ids):
            key = int(oid) if str(oid).lstrip("-").isdigit() else str(oid)
            per: dict[int, object] = {}
            for i, fr in enumerate(frames):
                layer = masks[i]
                if layer.ndim == 3:
                    layer = layer[j] if j < layer.shape[0] else (
                        layer > 0).any(axis=0)
                per[fr] = (np.asarray(layer) > 0)
            out[key] = per
        return out
    # Fall back: mask_N in file order.
    per = {}
    idx = 0
    for key in sorted(keys):
        if key.startswith("mask_"):
            per[idx] = (np.asarray(z[key]) > 0)
            idx += 1
    return {0: per} if per else {}


def _load_npz_masks(npz_path: Path, object_id=None) -> dict[int, "object"]:
    """Map video frame number -> boolean mask array.

    The requested object is selected by ``object_id``; masks are never
    unioned across objects (part 13 section 21).
    """
    allm = _load_npz_all(npz_path)
    if not allm:
        return {}
    if object_id is None:
        first = sorted(allm, key=str)[0]
        return allm[first]
    for oid, frames in allm.items():
        if _match_id(object_id, oid):
            return frames
    return {}


def _select_figure_for_segment(seg: dict, artifacts: list[str],
                               run_dir: Path) -> dict:
    """Pick the segment's figure among cited mask artifacts (§42.1).

    Every SAM mask artifact the result cites (segment masks and
    reference masks alike) is checked object by object: on a frame of
    the segment, the object passes if its mask has a pixel within 3 px
    of the tracked point; it must pass on ≥ 80 % of the segment's
    frames that have a tracked point, with mask area ≤ 35 % of the
    frame on each passing frame. Among the objects that pass, the
    figure is the one with the largest median area. When none passes,
    the figure is the segment's own mask object.
    """
    import numpy as np

    track = {}
    for p in seg.get("track", []) or []:
        if (p.get("frame") is not None and p.get("x_px") is not None
                and p.get("y_px") is not None):
            track[int(p["frame"])] = (float(p["x_px"]),
                                      float(p["y_px"]))
    fallback = {
        "artifact": (seg.get("mask") or {}).get("artifact"),
        "object_id": (seg.get("mask") or {}).get("object_id"),
    }
    if not track or not artifacts:
        return fallback
    need = max(1, math.ceil(0.8 * len(track)))
    best = None
    best_area = -1.0
    for art in artifacts:
        p = run_dir / str(art)
        if not p.is_file():
            continue
        try:
            allm = _load_npz_all(p)
        except (OSError, ValueError):
            continue
        for oid, frames in allm.items():
            if not frames:
                continue
            sample = next(iter(frames.values()))
            h, w = sample.shape[:2]
            limit = 0.35 * h * w
            ok = 0
            areas: list[float] = []
            for fr, (x, y) in track.items():
                m = frames.get(fr)
                if m is None:
                    continue
                try:
                    area = float(np.asarray(m).sum())
                except (ValueError, TypeError):
                    continue
                if area > limit:
                    continue
                x0 = max(0, int(math.floor(x - 3)))
                x1 = min(w, int(math.ceil(x + 3)) + 1)
                y0 = max(0, int(math.floor(y - 3)))
                y1 = min(h, int(math.ceil(y + 3)) + 1)
                if x1 <= x0 or y1 <= y0:
                    continue
                if not bool(np.asarray(m)[y0:y1, x0:x1].any()):
                    continue
                ok += 1
                areas.append(area)
            if ok >= need and areas:
                med = float(np.median(np.asarray(areas)))
                if med > best_area:
                    best_area = med
                    best = {"artifact": str(art), "object_id": oid}
    return best or fallback


def select_figure(result: dict, run_dir: Path) -> dict:
    """Figure choice per segment id (part 13 §42.1).

    The figure feeds the outline, the spotlight, the ghosts, the
    chronophotograph, the landing ring, the hold camera and the ghost
    spacing; the tracked point, trail, fit curve, takeoff level, I-beam
    and every number stay on the tracked point.
    """
    cited: list[str] = []
    for seg in result.get("segments", []) or []:
        a = (seg.get("mask") or {}).get("artifact")
        if a and a not in cited:
            cited.append(a)
    for ref in result.get("references", []) or []:
        a = (ref.get("mask") or {}).get("artifact")
        if a and a not in cited:
            cited.append(a)
    figs = {}
    for seg in result.get("segments", []) or []:
        figs[str(seg.get("id"))] = _select_figure_for_segment(
            seg, cited, run_dir)
    return figs


# ---------------------------------------------------------------------------
# Contour smoothing (part 13 §25)
# ---------------------------------------------------------------------------

def chaikin(loop: list[list[float]]) -> list[list[float]]:
    """One pass of Chaikin corner cutting (part 13 §25.1)."""
    if len(loop) < 3:
        return loop
    out: list[list[float]] = []
    n = len(loop)
    for i in range(n):
        ax, ay = loop[i]
        bx, by = loop[(i + 1) % n]
        out.append([ax + 0.25 * (bx - ax), ay + 0.25 * (by - ay)])
        out.append([ax + 0.75 * (bx - ax), ay + 0.75 * (by - ay)])
    return out


def trace_raw_loop(mask) -> list[list[float]]:
    """Marching-squares points of a mask, before smoothing (§45).

    Pixel staircases are followed point by point (so the outline tracks
    the mask in short steps). Points lie on the half-pixel grid, stored
    as floats that are multiples of 0.5. No Chaikin pass runs here: the
    player runs the two passes itself (§45), with the same result as
    :func:`trace_mask_contour`.
    """
    import cv2
    import numpy as np

    img = (np.asarray(mask) > 0).astype("uint8") * 255
    contours, _ = cv2.findContours(
        img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    if not contours:
        return []
    biggest = max(contours, key=cv2.contourArea)
    if len(biggest) >= 3 and cv2.arcLength(biggest, True) < 14.0:
        return []
    loop = [[round(float(p[0][0]) * 2) / 2, round(float(p[0][1]) * 2) / 2]
            for p in biggest]
    return loop


def smooth_raw_loop(raw: list[list[float]]) -> list[list[float]]:
    """Two Chaikin passes over decoded marching-squares points (§45).

    This is the build-side smoothing the player reproduces: decode the
    compact loop, then run the same two passes (plus the right-angle
    cleanup) here. Every outline drawn on the stage matches this
    within 0.05 px.
    """
    loop = [[float(x), float(y)] for x, y in raw]
    for _ in range(2):
        loop = chaikin([[float(x), float(y)] for x, y in loop])
    if len(loop) > 400:
        step = math.ceil(len(loop) / 400)
        loop = loop[::step]
    loop = _drop_right_angles(loop)
    return [[round(float(x), 1), round(float(y), 1)] for x, y in loop]


def trace_mask_contour(mask) -> list[list[float]]:
    """Trace a boolean mask with pixel-edge following, then smooth.

    Pixel staircases are followed point by point (so the outline tracks
    the mask in short steps), then Chaikin corner cutting rounds them.
    Loops are stride-capped at 400 points to keep the page under its
    weight cap (part 13 §12); floors the browser tests need (≥150 for
    the figure, ≥80 for a reference) stay far below the cap.

    This is exactly :func:`smooth_raw_loop` of :func:`trace_raw_loop`
    (part 13 §45): the build stores the raw points compactly and the
    player replays the same smoothing.
    """
    return smooth_raw_loop(trace_raw_loop(mask))


def encode_loop(raw: list[list[float]]) -> str:
    """Compact loop string: integers in half-pixel units (§45).

    Points lie on the half-pixel grid, so ``round(x * 2)`` is exact.
    The first point is absolute, the rest are deltas, joined as
    ``"x,y;dx,dy;..."`` in one compact string per loop.
    """
    pts = [(int(round(float(x) * 2)), int(round(float(y) * 2)))
           for x, y in raw]
    if not pts:
        return ""
    parts = [f"{pts[0][0]},{pts[0][1]}"]
    for (px, py), (x, y) in zip(pts, pts[1:]):
        parts.append(f"{x - px},{y - py}")
    return ";".join(parts)


def decode_loop(s: str) -> list[list[float]]:
    """Decode :func:`encode_loop` back to half-pixel float points."""
    if not s:
        return []
    pts: list[list[float]] = []
    x = y = 0
    for i, tok in enumerate(s.split(";")):
        a, b = tok.split(",")
        dx, dy = int(a), int(b)
        if i == 0:
            x, y = dx, dy
        else:
            x += dx
            y += dy
        pts.append([x / 2.0, y / 2.0])
    return pts


def decode_smooth_loop(s: str) -> list[list[float]]:
    """Decode a stored loop and run the build-side smoothing (§45)."""
    return smooth_raw_loop(decode_loop(s))


def _drop_right_angles(loop: list[list[float]]) -> list[list[float]]:
    """Drop the middle point of near-right-angle joints (§25.5).

    No two consecutive segments longer than 0.5 video px may meet at
    90° ± 5°. Removing the joint's middle point merges the pair into a
    chord; repeat to fixpoint so neighbours settle too.
    """
    for _ in range(20):
        n = len(loop)
        if n <= 10:
            break
        kill: set[int] = set()
        for i in range(n):
            ax, ay = loop[i]
            bx, by = loop[(i + 1) % n]
            cx, cy = loop[(i + 2) % n]
            v1 = (bx - ax, by - ay)
            v2 = (cx - bx, cy - by)
            l1 = math.hypot(*v1)
            l2 = math.hypot(*v2)
            if l1 > 0.5 and l2 > 0.5:
                if (abs(v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)
                        < math.cos(math.radians(85))):
                    kill.add((i + 1) % n)
        if not kill:
            break
        loop = [p for i, p in enumerate(loop) if i not in kill]
    return loop


# ---------------------------------------------------------------------------
# Cut-outs (part 13 §§3.6, 25.2)
# ---------------------------------------------------------------------------

def _read_video_frame(video_path: Path | None, frame_no: int):
    """Read one BGR frame from a video, or None when unavailable."""
    if video_path is None or not Path(video_path).is_file():
        return None
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ok, frame = cap.read()
    finally:
        cap.release()
    return frame if ok else None


def _crop_rect(bbox, shape, pad: float = 2.0) -> list[int]:
    """Crop rect (the cut-out's draw box): bbox expanded by pad,
    clamped to the frame (part 13 §25.2)."""
    h, w = shape[:2]
    x, y, bw, bh = (float(v) for v in bbox)
    x0 = max(0, int(math.floor(x - pad)))
    y0 = max(0, int(math.floor(y - pad)))
    x1 = min(w, int(math.ceil(x + bw + pad)))
    y1 = min(h, int(math.ceil(y + bh + pad)))
    if x1 <= x0 or y1 <= y0:
        x0, y0, x1, y1 = 0, 0, w, h
    return [x0, y0, x1, y1]


def make_cutout(mask, frame_bgr, bbox) -> "object":
    """Cut-out PNG (RGBA) at 4x from the smoothed contour (part 13 §25.2).

    ``mask`` is a boolean array, ``frame_bgr`` an optional BGR frame of
    the same size (silhouette-only when None), ``bbox`` the [x,y,w,h]
    crop in video pixels.
    """
    import cv2
    import numpy as np

    h, w = mask.shape[:2]
    x0, y0, x1, y1 = _crop_rect(bbox, mask.shape)
    s = CUTOUT_SCALE
    crop = (np.asarray(mask[y0:y1, x0:x1]) > 0).astype("uint8") * 255
    big = cv2.resize(
        crop, ((x1 - x0) * s, (y1 - y0) * s),
        interpolation=cv2.INTER_NEAREST,
    )
    sigma = FEATHER_VIDEO_PX * s
    k = max(3, int(sigma * 3) | 1)
    alpha = cv2.GaussianBlur(big.astype("float32") / 255.0, (k, k), sigma)
    if frame_bgr is not None and tuple(frame_bgr.shape[:2]) == (h, w):
        pix = cv2.resize(
            frame_bgr[y0:y1, x0:x1], ((x1 - x0) * s, (y1 - y0) * s),
            interpolation=cv2.INTER_LINEAR,
        )
        pix = cv2.cvtColor(pix, cv2.COLOR_BGR2RGBA)
    else:
        pix = np.zeros(((y1 - y0) * s, (x1 - x0) * s, 4), dtype="uint8")
        pix[..., 0:3] = 235
        pix[..., 3] = 255
    pix[..., 3] = (alpha * 255.0).astype("uint8")
    return pix


def _opaque_fraction(png) -> float:
    import numpy as np

    a = np.asarray(png)
    if a.ndim != 3 or a.shape[2] < 4:
        return 0.0
    return float((a[..., 3] > 127).mean())


def _video_size(video_path: Path | None):
    if video_path is None or not Path(video_path).is_file():
        return None
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    try:
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    finally:
        cap.release()
    if not w or not h:
        return None
    return int(w), int(h)


# ---------------------------------------------------------------------------
# Video / poster (part 13 §12)
# ---------------------------------------------------------------------------

def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def _transcode_h264(src: Path, dest: Path, fps: float = 30.0) -> bool:
    """Transcode the presentation copy to H.264 (part 13 §12).

    The page video carries a keyframe at least every 0.5 s
    (part 13 §44.1: ``-g`` = ``-keyint_min`` = round(fps / 2)), so
    exact ``currentTime`` seeks stay fast in every browser.
    """
    ff = _ffmpeg()
    if ff is None:
        shutil.copyfile(src, dest)
        return False
    try:
        fps_f = float(fps or 30.0)
        gop = max(1, round(fps_f / 2))
        # The 0.5 s interval is normative (§44.1); at 29.97 fps the
        # rounded gop spans 0.5005 s, so step down one frame there.
        if gop / fps_f > 0.5:
            gop = max(1, gop - 1)
    except (TypeError, ValueError):
        gop = 15
    try:
        subprocess.run(
            [ff, "-y", "-v", "error", "-i", str(src), "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-crf", "20",
             "-g", str(gop), "-keyint_min", str(gop),
             "-an", str(dest)],
            check=True, timeout=600,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        shutil.copyfile(src, dest)
        return False


def _grab_poster(video: Path, dest: Path, frame: int = 0) -> bool:
    ff = _ffmpeg()
    if ff is None:
        return False
    try:
        subprocess.run(
            [ff, "-y", "-v", "error", "-i", str(video), "-vf",
             f"select='eq(n\\,{frame})'", "-frames:v", "1", str(dest)],
            check=True, timeout=120,
        )
        return dest.is_file()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Mask-check picture (part 13 §20.2)
# ---------------------------------------------------------------------------

def resolve_maskcheck_image(run_dir: Path, reference: dict) -> Path | None:
    """Find the mask-check sheet image for a reference.

    The page build finds the image from the ``mask_check.artifact``
    JSONL: the row whose ``npz`` basename equals the reference's
    ``mask.artifact`` basename gives ``sheet``; the image is the file
    with that basename next to the JSONL (part 13 §20.2).
    """
    mc = reference.get("mask_check") or {}
    artifact = mc.get("artifact")
    if not artifact:
        return None
    if str(artifact).lower().endswith((".png", ".jpg", ".jpeg")):
        return _maybe(run_dir, str(artifact))
    jsonl = _maybe(run_dir, str(artifact))
    if jsonl is None or jsonl.suffix.lower() != ".jsonl":
        return None
    want = os.path.basename(str((reference.get("mask") or {}).get(
        "artifact", "")))
    try:
        with open(jsonl, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if os.path.basename(str(row.get("npz", ""))) == want:
                    sheet = row.get("sheet")
                    if sheet:
                        if Path(str(sheet)).is_absolute():
                            return _maybe(run_dir, str(sheet))
                        # Sheet paths in the JSONL are run-relative;
                        # fall back to next-to-the-JSONL.
                        return (_maybe(run_dir, str(sheet))
                                or _maybe(run_dir, str(
                                    (jsonl.parent / os.path.basename(
                                        str(sheet))).as_posix())))
                    # Row without a sheet: the image sits next to the
                    # JSONL under the npz basename (sheet convention).
                    cand = jsonl.parent / (os.path.splitext(want)[0]
                                           + ".png")
                    if cand.is_file():
                        return cand
                    return None
    except OSError:
        return None
    return None


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def _dir_weight(path: Path) -> int:
    total = 0
    for p in sorted(path.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() in (".mp4", ".m4v", ".webm"):
            continue
        total += p.stat().st_size
    return total


def build_page(result_path, video_path, out_dir, summary_path=None,
               slug=None, sidecar_path=None):
    """Assemble one per-clip page; return the ``index.html`` path.

    ``result_path`` names the part-12 ``result.json``; artifacts resolve
    against its folder (part 13 §21.1). Always writes ``index.html``
    (part 13 §22.7). Raises ``FileNotFoundError`` naming a cited
    artifact that cannot be found (part 13 §21.1).
    """
    from src.contract import CONTRACT_VERSION  # noqa: F401 (pinned by tests)
    import cv2
    import numpy as np

    result_path = Path(result_path)
    run_dir = result_path.parent
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(result_path, encoding="utf-8") as fh:
        result = json.load(fh)
    summary = None
    if summary_path is not None and Path(summary_path).is_file():
        with open(summary_path, encoding="utf-8") as fh:
            summary = json.load(fh)
    sidecar = None
    if sidecar_path is not None and Path(sidecar_path).is_file():
        with open(sidecar_path, encoding="utf-8") as fh:
            sidecar = json.load(fh)

    result = strip_absolute_paths(result, run_dir)
    if summary is not None:
        summary = strip_absolute_paths(summary, run_dir)

    video = Path(video_path) if video_path is not None else None
    if video is not None and not video.is_file():
        # Resolve page-build video paths against the run folder too.
        cand = run_dir / str(video)
        video = cand if cand.is_file() else None

    # --- figure per segment (part 13 §42.1) ---
    figs = select_figure(result, run_dir)
    # --- outline loops (part 13 §§25.1, 42.2, 45): the build stores
    # each loop as its marching-squares points before smoothing, as
    # integers in half-pixel units (first point absolute, then deltas,
    # one compact string per loop). The player decodes the string and
    # runs the two Chaikin passes itself, with the same result as the
    # build-side smoothing. The result's polygons (overlay[].outline,
    # references[].mask.outline) are never drawn.
    smooth: dict[str, dict[str, str]] = {}
    fig_masks_cache: dict[str, dict] = {}
    for seg in result.get("segments", []) or []:
        per: dict[str, str] = {}
        fig = figs.get(str(seg.get("id"))) or {}
        fart = fig.get("artifact") or (seg.get("mask") or {}).get("artifact")
        foid = fig.get("object_id")
        if foid is None:
            foid = (seg.get("mask") or {}).get("object_id")
        fig_masks: dict = {}
        if fart:
            fig_masks = _load_npz_masks(
                _need(run_dir, str(fart)), foid)
        fig_masks_cache[str(seg.get("id"))] = fig_masks
        # The outline is drawn every frame of the ride (§§3.2, 42.1),
        # so loops are traced for every figure-mask frame across the
        # segment's live range, not just the overlay frames. The Scale
        # hold (§18.5) also draws the body's outline, so the first
        # segment's range reaches back to the scale frame.
        frames_info = seg.get("frames") or {}
        fstart = int(frames_info.get("start", 0))
        fend = int(frames_info.get("end", fstart))
        flo = fstart - 3
        sc_frame = (result.get("scale") or {}).get("frame")
        if seg is (result.get("segments", []) or [None])[0]:
            try:
                flo = min(flo, int(sc_frame))
            except (TypeError, ValueError):
                pass
        for fr in sorted(fig_masks):
            if fr < flo or fr > fend + 10:
                continue
            m = fig_masks.get(fr)
            if m is None:
                # A frame with no figure mask has no outline; never
                # interpolate and never fall back to polygons (§42.1).
                continue
            raw = trace_raw_loop(m)
            if raw:
                per[str(fr)] = encode_loop(raw)
        if per:
            smooth[str(seg.get("id"))] = per
    ref_smooth: dict[str, str] = {}
    sc_frame = (result.get("scale") or {}).get("frame")
    for i, ref in enumerate(result.get("references", []) or []):
        mask = ref.get("mask") or {}
        art = mask.get("artifact")
        if not art or sc_frame is None:
            # A reference with no mask frame shows no outline (§42.2).
            continue
        rmasks = _load_npz_masks(
            _need(run_dir, str(art)), mask.get("object_id"))
        try:
            m = rmasks.get(int(sc_frame))
        except (ValueError, TypeError):
            m = None
        if m is None:
            continue
        raw = trace_raw_loop(m)
        if raw:
            ref_smooth[str(i)] = encode_loop(raw)

    # --- cut-out frames: strobes + landing per segment (part 13 §18.6) ---
    fps = float((result.get("video") or {}).get("measured_fps") or 30.0)
    strobe_step = max(1, round(fps * 0.234))
    cutout_meta: dict[str, list[dict]] = {}
    trims: list[str] = []
    # Mask bboxes per frame, for pages whose overlay bboxes are points.
    maskboxes: dict[str, dict[str, list]] = {}
    for seg in result.get("segments", []) or []:
        frames_info = seg.get("frames") or {}
        start = int(frames_info.get("start", 0))
        end = int(frames_info.get("end", start))
        want = list(range(start, end + 1, strobe_step))
        if want[-1] != end:
            want.append(end)
        # Trim the chronophotograph interval first under weight ( §12).
        while len(want) > 9:
            want = want[::2]
            if want[-1] != end:
                want.append(end)
            trims.append(
                f"pagebuild: thinned chronophotograph copies for "
                f"{seg.get('id')} to {len(want)}"
            )
        # Cut-outs and bboxes come from the figure's masks (§42.1).
        masks = fig_masks_cache.get(str(seg.get("id")), {})
        overlays = {int(o["frame"]): o
                    for o in seg.get("overlay", []) or []
                    if "frame" in o}
        if seg.get("id") not in maskboxes:
            maskboxes[str(seg.get("id"))] = {}
            for fr2, m2 in masks.items():
                nz = np.argwhere(np.asarray(m2) > 0)
                if len(nz):
                    y0, x0 = (int(nz[:, 0].min()), int(nz[:, 1].min()))
                    y1, x1 = (int(nz[:, 0].max()), int(nz[:, 1].max()))
                    maskboxes[str(seg.get("id"))][str(fr2)] = [
                        float(x0), float(y0),
                        float(x1 - x0 + 1), float(y1 - y0 + 1)]
        per_meta: list[dict] = []
        for fr in want:
            ov = overlays.get(fr, {})
            bbox = ov.get("bbox")
            if (bbox is None or float(bbox[2]) < 16
                    or float(bbox[3]) < 16):
                bbox = maskboxes[str(seg.get("id"))].get(str(fr))
            if bbox is None:
                continue
            m = masks.get(fr)
            if m is None:
                # No figure mask on this frame: no cut-out, never a
                # polygon stand-in (§§42.1, 42.2).
                continue
            frame_bgr = _read_video_frame(video, fr)
            png = make_cutout(m, frame_bgr, bbox)
            import cv2

            # Split heavy color from tiny alpha (part 13 §12 weight
            # cap): color JPEG + RGBA alpha PNG (mask in A, §43.1),
            # composited by the player. Cut-outs live in the page as
            # data URLs only (§45): file:// canvases are
            # origin-tainted, so the player composites from data URLs
            # (same-origin clean) instead of fetching sibling files at
            # runtime. The build does not also write them as files.
            ok, cbuf = cv2.imencode(
                ".jpg", png[..., :3], [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:  # pragma: no cover - encoder failure
                raise RuntimeError(
                    f"page build: could not encode cutout {fr}")
            ok, abuf = cv2.imencode(
                ".png", png[..., 3],
                [cv2.IMWRITE_PNG_COMPRESSION, 9])
            if not ok:  # pragma: no cover - encoder failure
                raise RuntimeError(
                    f"page build: could not encode cutout alpha {fr}")
            # (43.1) the mask lives in the alpha channel: a
            # greyscale PNG is opaque everywhere, so
            # destination-in would cut nothing. Rewrite the
            # single-channel alpha as RGBA (alpha in A).
            amask = cv2.imdecode(
                np.frombuffer(bytes(abuf), dtype=np.uint8),
                cv2.IMREAD_UNCHANGED)
            if amask is None or amask.ndim != 2:  # pragma: no cover
                raise RuntimeError(
                    f"page build: bad alpha for cutout {fr}")
            argb = np.zeros(
                (amask.shape[0], amask.shape[1], 4), dtype=np.uint8)
            argb[..., 3] = amask
            ok, abuf = cv2.imencode(
                ".png", argb, [cv2.IMWRITE_PNG_COMPRESSION, 9])
            if not ok:  # pragma: no cover - encoder failure
                raise RuntimeError(
                    f"page build: could not encode cutout alpha {fr}")
            import base64

            x0, y0, x1, y1 = _crop_rect(bbox, m.shape)
            per_meta.append({
                "frame": fr,
                "bbox": [float(v) for v in bbox],
                "draw": [float(x0), float(y0),
                         float(x1 - x0), float(y1 - y0)],
                "opaque": round(_opaque_fraction(png), 4),
                "data": ("data:image/jpeg;base64," + base64.b64encode(
                    bytes(cbuf)).decode("ascii")),
                "adata": ("data:image/png;base64," + base64.b64encode(
                    bytes(abuf)).decode("ascii")),
            })
        if per_meta:
            cutout_meta[str(seg.get("id"))] = per_meta

    # --- mask-check pictures (part 13 §20.2) ---
    maskcheck_files: dict[str, str] = {}
    for i, ref in enumerate(result.get("references", []) or []):
        img = resolve_maskcheck_image(run_dir, ref)
        if img is not None:
            dest = out_dir / f"maskcheck_{i}{img.suffix.lower()}"
            shutil.copyfile(img, dest)
            maskcheck_files[str(i)] = dest.name

    # --- video + poster ---
    if video is not None and video.is_file():
        _transcode_h264(video, out_dir / "clip.mp4", fps)
        _grab_poster(out_dir / "clip.mp4", out_dir / "poster.jpg")
    else:
        # Range-only or video-free fixtures: the first view is the poster.
        views = ((result.get("first_look") or {}).get("views")) or []
        for v in views:
            cand = _maybe(run_dir, str(v.get("artifact", "")))
            if cand is not None and cand.suffix.lower() in (
                    ".jpg", ".jpeg", ".png"):
                shutil.copyfile(
                    cand, out_dir / ("poster" + cand.suffix.lower()))
                break

    has_video = (out_dir / "clip.mp4").is_file()
    poster_name = None
    for cand in ("poster.jpg", "poster.png"):
        if (out_dir / cand).is_file():
            poster_name = cand
    flags = {
        "slug": slug or run_dir.name,
        "has_video": has_video,
        "poster": poster_name,
        "template_hash": template_hash(),
        "contract_version": int(result.get("contract_version", 0)),
        "smooth_loops": smooth,
        "ref_loops": ref_smooth,
        "maskboxes": maskboxes,
        "figure": {k: {"artifact": v.get("artifact"),
                       "object_id": v.get("object_id")}
                   for k, v in figs.items()},
        "cutouts": cutout_meta,
        "maskcheck_files": maskcheck_files,
        "sidecar": sidecar,
        "katex_version": KATEX_VERSION,
    }

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    result_str = json.dumps(result, separators=(",", ":"))
    summary_str = (json.dumps(summary, separators=(",", ":"))
                   if summary is not None else "null")

    def _render(fl) -> str:
        pg = template.replace(_TOKEN_HASH, template_hash())
        pg = pg.replace(_TOKEN_RESULT, result_str)
        pg = pg.replace(_TOKEN_SUMMARY, summary_str)
        pg = pg.replace(_TOKEN_FLAGS, json.dumps(fl, separators=(",", ":")))
        pg = pg.replace("KATEX_VERSION_PIN", KATEX_VERSION)
        return pg

    def _other_weight() -> int:
        total = 0
        for p in sorted(out_dir.rglob("*")):
            if not p.is_file():
                continue
            if p.name == "index.html":
                continue
            if p.suffix.lower() in (".mp4", ".m4v", ".webm"):
                continue
            total += p.stat().st_size
        return total

    other_w = _other_weight()
    page = _render(flags)
    weight = other_w + len(page.encode("utf-8"))

    # --- over the limit, the build trims; it does not fail (§45) ---
    # Order (§12): outline loops outside the segment windows ± 1 s,
    # then the chronophotograph interval, then ghost-frame density.
    # Raises only when the result and summary data alone exceed it.
    def _rebuild_weight() -> int:
        return other_w + len(_render(flags).encode("utf-8"))

    limit = WEIGHT_LIMIT_BYTES
    if weight > limit:
        kept: dict[str, tuple[int, int]] = {}
        for seg in result.get("segments", []) or []:
            fi = seg.get("frames") or {}
            try:
                win = (max(0, int(fi.get("start", 0)) - round(fps)),
                       int(fi.get("end", int(fi.get("start", 0))))
                       + round(fps))
            except (TypeError, ValueError):
                continue
            kept[str(seg.get("id"))] = win
        dropped = 0
        for sid, per in list(flags["smooth_loops"].items()):
            win = kept.get(sid)
            if win is None:
                continue
            for fr in list(per):
                try:
                    f = int(fr)
                except (TypeError, ValueError):
                    continue
                if f < win[0] or f > win[1]:
                    del per[fr]
                    dropped += 1
        if dropped:
            trims.append(
                f"pagebuild: trimmed {dropped} outline loops outside "
                f"segment windows"
            )
            weight = _rebuild_weight()
        while weight > limit and any(
                len(v) > 2 for v in flags["cutouts"].values()):
            for sid, copies in list(flags["cutouts"].items()):
                if len(copies) > 2:
                    keep = copies[::2]
                    if copies[-1] not in keep:
                        keep.append(copies[-1])
                    if len(keep) >= len(copies):
                        keep = copies[:2] + (
                            copies[-1:] if len(copies) > 2 else [])
                    flags["cutouts"][sid] = keep
                    trims.append(
                        f"pagebuild: thinned chronophotograph copies for "
                        f"{sid} to {len(keep)}"
                    )
            weight = _rebuild_weight()
        while weight > limit and any(
                len(v) > 3 for v in flags["smooth_loops"].values()):
            for sid, per in list(flags["smooth_loops"].items()):
                if len(per) > 3:
                    frs = sorted(per, key=int)
                    keep = frs[::2]
                    flags["smooth_loops"][sid] = {
                        fr: per[fr] for fr in keep}
                    trims.append(
                        f"pagebuild: thinned outline loops for {sid} "
                        f"(ghost-frame density) to {len(keep)}"
                    )
            weight = _rebuild_weight()
        if weight > limit:
            data_only = len(result_str.encode("utf-8")) + len(
                summary_str.encode("utf-8"))
            if data_only > limit:
                raise RuntimeError(
                    f"page build: page without video is {weight} bytes, "
                    f"limit {limit}"
                )
            # Last resort within the data budget: event frames only.
            for seg in result.get("segments", []) or []:
                sid = str(seg.get("id"))
                per = flags["smooth_loops"].get(sid)
                if not per:
                    continue
                fi = seg.get("frames") or {}
                keep = {str(fi[k]) for k in ("start", "apex", "end")
                        if fi.get(k) is not None}
                for fr in list(per):
                    if fr not in keep:
                        del per[fr]
            trims.append(
                "pagebuild: trimmed outline loops to event frames only"
            )
            weight = _rebuild_weight()
            if weight > limit:
                for sid in list(flags["cutouts"]):
                    flags["cutouts"][sid] = flags["cutouts"][sid][:2]
                trims.append(
                    "pagebuild: trimmed chronophotograph copies to 2 "
                    "per segment"
                )
                weight = _rebuild_weight()
            if weight > limit:
                data_only = len(result_str.encode("utf-8")) + len(
                    summary_str.encode("utf-8"))
                if data_only > limit:
                    raise RuntimeError(
                        f"page build: page without video is {weight} "
                        f"bytes, limit {limit}"
                    )
    page = _render(flags)

    header = (f"<!-- frozen template {template_hash()} "
              f"contract {int(result.get('contract_version', 0))} -->\n")
    (out_dir / "index.html").write_text(header + page, encoding="utf-8")

    weight = _dir_weight(out_dir)
    if weight > WEIGHT_LIMIT_BYTES:
        data_only = len(result_str.encode("utf-8")) + len(
            summary_str.encode("utf-8"))
        if data_only <= WEIGHT_LIMIT_BYTES:
            pass
        else:
            raise RuntimeError(
                f"page build: page without video is {weight} bytes, "
                f"limit {WEIGHT_LIMIT_BYTES}"
            )
    for line in trims:
        print(line)
    return str(out_dir / "index.html")


def build_gallery(pages, out_dir):
    """Build a small gallery index linking per-clip pages (part 13 §2)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cards = []
    for p in pages:
        title = p.get("title", "")
        href = p.get("href", "")
        poster = p.get("poster", "")
        img = (f'<img src="{poster}" alt="">' if poster else "")
        cards.append(
            f'<a class="card" href="{href}">{img}<span>{title}</span></a>'
        )
    (out_dir / "index.html").write_text(
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Gallery</title></head><body>"
        + "".join(cards) + "</body></html>",
        encoding="utf-8",
    )
    return str(out_dir / "index.html")

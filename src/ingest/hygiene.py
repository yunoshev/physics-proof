"""Timeline hygiene report (part 05 §3).

Decoded-frame forensics over the anonymised copy, recorded in
``timing.json`` so the agent can look before measuring (part 08 makes
looking a rule; part 11 checks that fits respect confirmed
duplicates/cuts):

- **Duplicated frames:** exact duplicates (identical decoded bytes,
  via per-frame MD5) are ``"confirmed"``; near-duplicates (perceptual
  hash within :data:`NEAR_DUPLICATE_HASH_BITS`) are ``"suspect"``.
  Slow genuine motion must never false-positive silently, hence the
  two labels.
- **Cuts:** frame pairs whose visual difference exceeds
  :data:`SCENE_CHANGE_THRESHOLD` — indices where a cut takes effect.
- **Interpolation suspicion:** a heuristic flag only, always labelled
  suspicion, never evidence. A motion-interpolated slowed copy has no
  duplicates and a normal frame rate; only physics plus an independent
  clock can catch it (part 02 §5). Ingest never "detects slow motion".
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

from .probe import IngestError

__all__ = [
    "NEAR_DUPLICATE_HASH_BITS",
    "SCENE_CHANGE_THRESHOLD",
    "HYGIENE_DECODE_SIZE",
    "INTERPOLATION_CV_THRESHOLD",
    "INTERPOLATION_MIN_FRAMES",
    "decode_small_frames",
    "frame_md5s",
    "dhash_bits",
    "hamming",
    "timeline_hygiene",
]

#: Max Hamming distance (64-bit dhash) for a "suspect" near-duplicate.
#: Exact duplicates are "confirmed" by byte identity; anything within
#: this distance that is *not* byte-identical is "suspect".
NEAR_DUPLICATE_HASH_BITS = 8

#: Mean absolute grayscale difference (0-1) above which a frame pair
#: is reported as a cut.
SCENE_CHANGE_THRESHOLD = 0.30

#: Decode width/height for the perceptual pass (exact duplicates use
#: full-resolution per-frame MD5 instead, so downscaling cannot invent
#: a "confirmed" duplicate).
HYGIENE_DECODE_SIZE = 64

#: Coefficient of variation of consecutive-frame differences below
#: which motion counts as "uniformly smooth" for the interpolation
#: *suspicion* heuristic (never evidence, part 05 §3).
INTERPOLATION_CV_THRESHOLD = 0.20

#: Fewer frames than this cannot support the uniformity heuristic.
INTERPOLATION_MIN_FRAMES = 12

#: Mean frame difference below which a clip counts as motionless.
_STATIC_DIFF_FLOOR = 0.002

_SUSPICION_NOTE = ("heuristic suspicion only; never evidence of native "
                   "speed or slow motion (part 05 section 3)")


def frame_md5s(video_path: str | Path, frame_count: int) -> list[str]:
    """Per-frame MD5 of the decoded bytes (framemd5, full resolution)."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise IngestError("unreadable video: required tool 'ffmpeg' not found")
    try:
        raw = subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(video_path),
             "-map", "0:v:0", "-f", "framemd5", "-"],
            capture_output=True, text=True, timeout=600, check=True,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            OSError) as exc:
        raise IngestError(
            f"unreadable video: frame hash decode failed: {exc}") from exc
    md5s = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        md5 = line.split(",")[-1].strip()
        if len(md5) == 32 and all(c in "0123456789abcdefABCDEF"
                                  for c in md5):
            md5s.append(md5.lower())
    if len(md5s) != frame_count:
        raise IngestError(
            "unreadable video: frame hash count "
            f"({len(md5s)}) != frame count ({frame_count})")
    return md5s


def decode_small_frames(video_path: str | Path,
                        frame_count: int) -> np.ndarray:
    """Decode ``HxHx3`` uint8 frames for the perceptual pass."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise IngestError("unreadable video: required tool 'ffmpeg' not found")
    size = HYGIENE_DECODE_SIZE
    try:
        proc = subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(video_path),
             "-map", "0:v:0", "-vf", f"scale={size}:{size}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, timeout=600, check=True,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            OSError) as exc:
        raise IngestError(
            f"unreadable video: perceptual decode failed: {exc}") from exc
    expect = frame_count * size * size * 3
    if len(proc) != expect:
        raise IngestError(
            "unreadable video: perceptual decode byte count "
            f"({len(proc)}) != expected ({expect})")
    return np.frombuffer(proc, dtype=np.uint8).reshape(
        frame_count, size, size, 3)


def dhash_bits(gray: np.ndarray) -> int:
    """64-bit difference hash of a grayscale frame.

    Area-averages down to 9x8, then records whether each cell is
    brighter than its right neighbour. Point sampling would alias;
    averaging makes the hash respond to genuine structure change
    rather than single-pixel noise.
    """
    h, w = gray.shape[:2]
    edges_y = np.linspace(0, h, 10)
    edges_x = np.linspace(0, w, 9)
    small = np.zeros((9, 8))
    for i in range(9):
        y0, y1 = int(edges_y[i]), int(edges_y[i + 1])
        for j in range(8):
            x0, x1 = int(edges_x[j]), int(edges_x[j + 1])
            cell = gray[y0:max(y1, y0 + 1), x0:max(x1, x0 + 1)]
            small[i, j] = float(cell.mean())
    diff = small[:, 1:] > small[:, :-1]
    bits = 0
    for flag in diff.ravel():
        bits = (bits << 1) | int(bool(flag))
    return bits


def hamming(a: int, b: int) -> int:
    """Hamming distance between two hash ints."""
    return bin(a ^ b).count("1")


def _runs(indices: list[int]) -> list[list[int]]:
    """Maximal consecutive runs of sorted frame indices."""
    runs: list[list[int]] = []
    for idx in sorted(indices):
        if runs and idx == runs[-1][-1] + 1:
            runs[-1].append(idx)
        else:
            runs.append([idx])
    return runs


def timeline_hygiene(video_path: str | Path,
                     timing: dict | None = None) -> dict:
    """Report duplicates, cuts, and interpolation suspicion for one file.

    Args:
        video_path: The (anonymised copy) to inspect.
        timing: Optional :func:`measure` result carrying ``frame_count``
            (re-measured when omitted).

    Returns a JSON-serialisable dict with ``confirmed_duplicates`` /
    ``confirmed_runs`` (byte-identical decoded frames), suspect
    near-duplicates, ``cuts``, the named thresholds, and
    ``interpolation_suspicion`` (``suspected`` bool + fixed-template
    ``reason`` + suspicion-only note).
    """
    from .measure import measure_timing as _measure  # noqa: PLC0415

    facts = timing if timing is not None else _measure(video_path)
    count = int(facts["frame_count"])
    if count < 1:
        raise IngestError("unreadable video: no decodable video frames")
    md5s = frame_md5s(video_path, count)
    frames = decode_small_frames(video_path, count)
    gray = frames.astype(float).mean(axis=3) / 255.0

    by_hash: dict[str, list[int]] = {}
    for i, digest in enumerate(md5s):
        by_hash.setdefault(digest, []).append(i)
    confirmed = sorted(i for members in by_hash.values()
                       if len(members) > 1 for i in members)
    confirmed_set = set(confirmed)

    hashes = [dhash_bits(gray[i]) for i in range(count)]
    suspect: list[int] = []
    for i in range(1, count):
        if md5s[i] == md5s[i - 1]:
            continue  # byte-identical: already confirmed, never "suspect"
        if i in confirmed_set:
            continue  # frame i repeats an earlier frame: already
            # "confirmed"; its neighbour similarity says nothing new
        if hamming(hashes[i], hashes[i - 1]) <= NEAR_DUPLICATE_HASH_BITS:
            suspect.append(i)
    suspect = sorted(set(suspect))

    diffs = ([float(np.mean(np.abs(gray[i] - gray[i - 1])))
              for i in range(1, count)] if count > 1 else [])
    cuts = [i for i, d in enumerate(diffs, start=1)
            if d > SCENE_CHANGE_THRESHOLD]

    suspicion = _interpolation_suspicion(confirmed, diffs, count)
    return {
        "confirmed_duplicates": confirmed,
        "confirmed_runs": _runs(confirmed),
        "suspect_duplicates": suspect,
        "suspect_runs": _runs(suspect),
        "near_duplicate_threshold_bits": NEAR_DUPLICATE_HASH_BITS,
        "cuts": cuts,
        "scene_change_threshold": SCENE_CHANGE_THRESHOLD,
        "interpolation_suspicion": suspicion,
        "frame_count": count,
    }


def _interpolation_suspicion(confirmed: list[int], diffs: list[float],
                             count: int) -> dict:
    """Heuristic uniformity flag — suspicion, never evidence."""
    if confirmed:
        return {"suspected": False,
                "reason": "confirmed_duplicates_present",
                "note": _SUSPICION_NOTE}
    if count < INTERPOLATION_MIN_FRAMES:
        return {"suspected": False, "reason": "too_few_frames",
                "note": _SUSPICION_NOTE}
    if not diffs:
        return {"suspected": False, "reason": "too_few_frames",
                "note": _SUSPICION_NOTE}
    mean = float(np.mean(diffs))
    if mean < _STATIC_DIFF_FLOOR:
        return {"suspected": False, "reason": "no_motion",
                "note": _SUSPICION_NOTE}
    std = float(np.std(diffs))
    cv = std / mean if mean > 0 else float("inf")
    if cv < INTERPOLATION_CV_THRESHOLD:
        return {"suspected": True,
                "reason": "uniform_frame_differences",
                "note": _SUSPICION_NOTE}
    return {"suspected": False, "reason": "motion_variance_normal",
            "note": _SUSPICION_NOTE}

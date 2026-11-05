# generated from brief/04 · part 04 owns this file
"""SAM 3.1 segmentation client (part 04 §6, ``skills/sam-3-1.md``).

Implements the ``segment`` backend exactly as
:func:`src.tools.segment.segment` defines it: ``(phrase,
frame_indices, frames)`` returning ``{object_id: [bool HxW]}`` with
one array per requested frame (all-False where the object is
absent). The call:

1. cuts the requested range into a fresh H.264 yuv420p mp4 (CRF 18,
   no audio) so only needed frames are paid for, and checks its
   frame count;
2. uploads it through the Files API (even when small), posts
   ``{"model": "sam-3.1", …}`` with string metadata, no
   ``instructions``/``reasoning``/``max_output_tokens``/``tools``;
3. reads the answer text once, from the first terminal event's
   output message text;
4. decodes with ``meta-sam-parser`` (never a hand-written decoder),
   pairs box and mask records by (frame, id), pastes each crop into
   a full-frame array, and maps the cut index back by the cut's
   start frame;
5. deletes the uploaded file (a failed delete is ignored).

Billing follows the terminal ``usage``: the ledger is billed
``max(50, frames, video_frames_processed)``
(:func:`sam_billed_frames`).

Gap (named per part 04 §6): the tool's interface returns only the
masks, so the part-07 tool debits ``max(50, frames)`` itself and
cannot see ``video_frames_processed``. The client records the full
billing on ``sam_client.last_report`` after every call
(``video_frames_processed`` is padded to 50 for short cuts, so the
two agree in practice); a caller that owns a ledger can top up the
difference from there.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from src import config as _config
from src.accounting import FailedCallError

from ._http import auth_headers, request_with_retries
from .files import delete_file, upload_file

__all__ = [
    "decode_sam_text",
    "make_sam_client",
    "sam_billed_frames",
    "write_cut_mp4",
]


def sam_billed_frames(frames_requested: int,
                      video_frames_processed=None) -> int:
    """Frames billed for a SAM call (part 14 pricing).

    ``max(50, frames, video_frames_processed)`` — the 50-frame
    minimum, the requested count, and the terminal usage padding.
    """
    requested = int(frames_requested)
    if requested < 0:
        raise ValueError(f"frames_requested must be >= 0, got "
                         f"{frames_requested!r}")
    processed = 0
    if video_frames_processed is not None:
        try:
            processed = max(0, int(video_frames_processed))
        except (TypeError, ValueError):
            processed = 0
    return max(int(_config.SAM_MIN_BILLED_FRAMES), requested, processed)


def write_cut_mp4(frames, path) -> dict:
    """Cut ``frames`` (H×W×3 uint8) to H.264 yuv420p mp4 (no audio).

    Returns ``{"frames", "width", "height", "path"}``. Prefers an
    ffmpeg raw-frame pipe (``libx264``, CRF 18); falls back to an
    OpenCV writer when ffmpeg is missing.
    """
    import numpy as np

    grids = [np.asarray(frame) for frame in frames]
    if not grids:
        raise ValueError("SAM cut needs at least one frame")
    height, width = grids[0].shape[:2]
    for grid in grids:
        if grid.shape[:2] != (height, width):
            raise ValueError("SAM cut frames have mixed shapes")
    out = Path(str(path))
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is not None:
        command = [
            ffmpeg, "-y", "-v", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{int(width)}x{int(height)}",
            "-framerate", "30", "-i", "-",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            "-an", str(out),
        ]
        raw = b"".join(np.ascontiguousarray(g, dtype="uint8").tobytes()
                       for g in grids)
        completed = subprocess.run(command, input=raw, capture_output=True,
                                   timeout=300)
        if completed.returncode != 0 or not out.is_file():
            raise RuntimeError(
                "ffmpeg cut failed: "
                + completed.stderr.decode("utf-8", "replace")[-500:])
        return {"frames": len(grids), "width": int(width),
                "height": int(height), "path": str(out)}
    import cv2  # noqa: PLC0415 — fallback writer only

    writer = cv2.VideoWriter(str(out),
                             cv2.VideoWriter_fourcc(*"mp4v"), 30,
                             (int(width), int(height)))
    if not writer.isOpened():
        raise RuntimeError("no mp4 writer available for the SAM cut")
    try:
        for grid in grids:
            writer.write(np.ascontiguousarray(grid, dtype="uint8"))
    finally:
        writer.release()
    return {"frames": len(grids), "width": int(width),
            "height": int(height), "path": str(out)}


def decode_sam_text(text: str):
    """``(boxes, masks)`` record maps from one SAM answer text.

    Records pair by ``(cut_frame_index, object_id)``; the cut index
    is zero-based within the uploaded cut. Decodes only through
    ``meta-sam-parser`` — anything else is a hand-written decoder
    and forbidden.
    """
    try:
        import meta_sam_parser as parser_lib
    except ImportError as exc:
        raise RuntimeError(
            "meta-sam-parser is not installed; SAM output cannot be "
            "decoded") from exc
    parser = parser_lib.video_segmentation_format().create_parser()
    chunk = str(text or "")
    if chunk and not chunk.endswith("\n"):
        chunk += "\n"
    parser.push(chunk)
    result = parser.finish(parser_lib.CompletedOutcome()).result
    boxes: dict = {}
    masks: dict = {}
    for record in result.records or ():
        frame = getattr(record, "frame", None)
        index = getattr(frame, "frame_index", None)
        object_id = getattr(record, "object_id", None)
        if index is None or object_id is None:
            continue
        key = (int(index), str(object_id))
        if isinstance(record, parser_lib.SegmentationBoxRecord):
            boxes[key] = record
        elif isinstance(record, parser_lib.SegmentationMaskRecord):
            masks[key] = record
    return boxes, masks


def _raster_of(mask_record) -> tuple:
    """``(width, height, row-major 0/1 bytes)`` for one mask record."""
    try:
        import meta_sam_parser as parser_lib
    except ImportError as exc:
        raise RuntimeError(
            "meta-sam-parser is not installed; SAM output cannot be "
            "decoded") from exc
    mask = mask_record.mask
    raster = parser_lib.decode_mask_to_raster(mask)
    return int(mask.width), int(mask.height), bytes(raster)


def _placement_of(mask_record, box_record) -> tuple:
    """``(left, top)`` paste origin of one mask crop."""
    bounds = getattr(mask_record, "bounds", None)
    if bounds is not None and getattr(bounds, "left", None) is not None:
        try:
            return int(bounds.left), int(bounds.top)
        except (TypeError, ValueError):
            pass
    if box_record is not None:
        return int(box_record.left), int(box_record.top)
    return 0, 0


def make_sam_client(api_key, *, base_url=None, timeout=None,
                    sleep=None):
    """The ``segment`` SAM backend (part 04 §6)."""
    key = str(api_key)
    base = str(base_url or _config.API_BASE_URL)
    limit = float(timeout if timeout is not None
                  else _config.API_TIMEOUT_S)
    pause = sleep

    def sam_client(phrase, frame_indices, frames) -> dict:
        """Segment one noun phrase; return ``{id: [full-frame bool]}``."""
        if not isinstance(phrase, str) or not phrase.strip():
            raise ValueError("SAM needs a non-empty phrase")
        indices = [int(i) for i in (frame_indices or [])]
        grids = list(frames or [])
        if not indices or not grids or len(indices) != len(grids):
            raise ValueError("SAM needs frame_indices aligned with frames")
        import numpy as np

        full_h, full_w = np.asarray(grids[0]).shape[:2]
        start_frame = indices[0]
        requested = len(indices)
        with tempfile.TemporaryDirectory(prefix="sam-cut-") as tmp:
            cut = write_cut_mp4(grids, Path(tmp) / "cut.mp4")
            if int(cut["frames"]) != requested:
                raise RuntimeError(
                    f"SAM cut holds {cut['frames']} frames for "
                    f"{requested} requested")
            record = upload_file(key, base, cut["path"], timeout=limit,
                                 sleep=pause)
            file_id = record.get("id")
            if not file_id:
                raise FailedCallError("Files upload returned no file id")
            try:
                body = {
                    "model": _config.SAM_MODEL,
                    "input": [{
                        "role": "user",
                        "content": [
                            {"type": "input_text",
                             "text": phrase.strip()},
                            {"type": "input_video",
                             "file_id": file_id},
                        ],
                    }],
                    "metadata": {
                        "include_confidence": "true",
                        "mask_encoding": "lossless",
                    },
                    "stream": True,
                    "store": False,
                }
                terminal, _ = request_with_retries(
                    f"{base}/responses", auth_headers(key), body,
                    timeout=limit, sleep=pause)
            finally:
                delete_file(key, base, file_id, timeout=limit)
        kind = (terminal or {}).get("type")
        if kind != "response.completed":
            raise FailedCallError(
                f"SAM ended {kind or 'without a terminal event'}")
        inner = terminal.get("response") or {}
        texts = []
        for item in inner.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for part in item.get("content") or []:
                if (isinstance(part, dict)
                        and part.get("type") == "output_text"
                        and part.get("text")):
                    texts.append(str(part["text"]))
                    break
            if texts:
                break
        answer = texts[0] if texts else ""
        usage = inner.get("usage") if isinstance(inner, dict) else None
        processed = (usage.get("video_frames_processed")
                     if isinstance(usage, dict) else None)
        billed = sam_billed_frames(requested, processed)
        boxes, masks = decode_sam_text(answer)
        object_ids = sorted({oid for (_, oid) in masks})
        out: dict = {}
        for oid in object_ids:
            seq = []
            for position, clip_frame in enumerate(indices):
                cut_index = int(clip_frame) - int(start_frame)
                grid = np.zeros((full_h, full_w), dtype=bool)
                record_m = masks.get((cut_index, oid))
                if record_m is not None:
                    mask_w, mask_h, raster = _raster_of(record_m)
                    left, top = _placement_of(
                        record_m, boxes.get((cut_index, oid)))
                    crop = np.frombuffer(raster,
                                         dtype=np.uint8).reshape(mask_h,
                                                                 mask_w)
                    bottom = min(full_h, top + mask_h)
                    right = min(full_w, left + mask_w)
                    if bottom > max(0, top) and right > max(0, left):
                        grid[max(0, top):bottom, max(0, left):right] = (
                            crop[:bottom - max(0, top),
                                 :right - max(0, left)].astype(bool))
                seq.append(grid)
            out[oid] = seq
        sam_client.last_report = {
            "phrase": phrase.strip(),
            "frames_requested": requested,
            "frame_start": int(start_frame),
            "video_frames_processed": processed,
            "frames_billed": billed,
        }
        return out

    sam_client.last_report = {}
    return sam_client

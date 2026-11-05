# Skill — SAM 3.1 (remote segmentation)

Facts from the owner's first-attempt notes; owning brief part is 07 (§3), with id-stability consequences in parts 08/09.

- Remote, through the same Meta API (`https://api.meta.ai/v1`). **$0.20 per 1000 frames, billed for at least 50 frames per call** — a 12-frame request still costs 50. The tool debits `max(50, frames)` (brief part 07 §3).
- **One noun phrase per call.** Segment "the astronaut" or "the wall", not "the astronaut and the wall". Multiple phrases = multiple calls = multiple 50-frame minimums — plan phrases accordingly.
- **Up to 16 objects** returned per call, each with an object id.
- **Object ids are unstable when objects overlap** — an id can silently swap between two overlapping objects mid-range. Never trust id continuity: the helper library's `track_quality` flags identity swaps via frame-to-frame IoU (brief part 09), and a flagged span must be re-tracked or excluded.
- **Masks come back compressed per frame.** Decode/encode in exactly one place (`helpers/masks_io`, brief part 09).
- **Cut the frame range into a short clip before sending**, so you pay only for the frames you need — send the trimmed range, not the whole video with a range hint.
- **Cache by (clip hash, phrase, frame range)** — but **within the run only**: acceptance runs must be independent (brief part 03 §2), so no cache survives a run boundary. The cache saves repeated identical requests inside one analysis; it is not memory between analyses.
- The tool returns masks + previews + per-frame stats; it never interprets them. Whether a mask covers what the phrase meant is established by the blind `check_mask` call (brief part 07 §4), not by SAM's confidence.

## Protocol (owner's notes from the first attempt's live calls, 2026-10-27)

**Call.** SAM 3.1 has no endpoint of its own: it is `POST {base}/responses` with `"model": "sam-3.1"`.
- **Upload first.** The video is always uploaded through the Files API, even when small (see meta-api skill). Cut the requested frame range into a fresh H.264 yuv420p mp4 (CRF 18, no audio), check its frame count, then upload it.
- **Body.** `{"model":"sam-3.1","input":[{"role":"user","content":[{"type":"input_text","text":"<one noun phrase>"},{"type":"input_video","file_id":"<id>"}]}],"metadata":{"include_confidence":"true","mask_encoding":"lossless"},"stream":true,"store":false}`.
- **Metadata values are strings.** `mask_encoding` can also be `"one_bit"`, which is smaller.
- **Omitted fields.** No `instructions`, `reasoning`, `max_output_tokens` or `tools`.
- **Delete the file afterwards.** A failed delete is ignored.

**Answer.** The answer is text in the usual SSE stream, one line per frame that has objects; frames without objects get no line. The full text repeats in several terminal events (~9 MB for 466 frames), so read it once, from the terminal `output` message text.

**Line grammar.** `<Nf>` is the **zero-based frame index within the uploaded cut**; add the cut's start frame to get the clip frame. Then come records separated by `,`:
`<id><|box;x1=29;y1=107;x2=70;y2=147;w=256;h=256;c=0.93|><|mask;x=0;y=0;c=0.93;data=41,42,~<payload>|>`.
- `id` is a decimal string.
- Box coordinates are **inclusive** source pixels; `w,h` are the **frame** size, not the box size.
- `c` is the confidence, constant per object across a clip.
- `data=H,W,…` puts **height first**: H = y2−y1+1 and W = x2−x1+1, with the crop placed at (x1, y1).
- The marker is `~` for lossless (custom range coder + base85, foreground at value ≥ 129) or `!` for one-bit.

**Never hand-write the decoder.** Use Meta's PyPI package `meta-sam-parser` (import `meta_sam_parser`):
1. call `video_segmentation_format().create_parser()`;
2. `.push(text)`, then `.finish(CompletedOutcome())`;
3. read the records `SegmentationBoxRecord` / `SegmentationMaskRecord` (`frame.frame_index`, `object_id`, half-open `left/top/right/bottom`, `confidence`);
4. `decode_mask_to_raster(mask)` returns row-major 0/1 bytes of H×W.

Pair box and mask records by (frame, id), then paste each crop into a full-frame boolean array.

**Usage.** The terminal `usage` has `video_frames_processed`, and billing follows it. It is padded to 50 for short cuts, so the ledger bills `max(50, frames, video_frames_processed)`.

**Speed.** Clip A, 466 frames at 352×240, takes ~30 s.

**Retries** follow the Spark policy. A stream cut mid-way is re-requested; the uploaded file is reused.

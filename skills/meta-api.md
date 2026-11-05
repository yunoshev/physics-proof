# Skill — Meta Model API

Facts from the owner's first-attempt notes. If the API disagrees, update this file first, then the owning brief part (04/06/07/14).

- Base: `https://api.meta.ai/v1`, OpenAI-compatible. The agent uses **`/responses` with streaming** (server-sent events).
- **Terminal events** — exactly one ends a response:
  - `response.completed` — success;
  - `response.incomplete` — cut off, with `incomplete_details.reason` (e.g. output limit). **Reasoning/thinking tokens count toward the output limit** — at 4096 max output tokens, high-reasoning replies were truncated. Brief part 06 mandates 32k;
  - `response.failed` — API-side failure with an error payload.
- **Usage appears only in the terminal event**: input, cached input, output, reasoning tokens. Never estimate cost from streamed deltas (brief part 14 counts only from terminal events; a stream that dies without one is `cost_unknown`).
- **The usage fields are subsets, not addends: `cached` is part of `input`, and `reasoning` is part of `output`.** Price a call as `(input − cached) × input-price + cached × cached-price + output × output-price`. Never sum all four fields — that double-counts the cached input and the reasoning tokens.
- **Prices per 1M tokens:**
  - Spark contributor (`muse-spark-1.3-contributor`, the cheap tier — agent, blind checks, classifier): **$0.10 input / $0.002 cached input / $0.20 output**.
  - Spark standard (`muse-spark-1.3`): **$1.25 input / $0.15 cached input / $4.25 output** (only if config ever switches).
  - **Web search: $2.50 per 1000 calls.** **SAM 3.1 video: $0.20 per 1000 frames, billed minimum 50 frames per call** (see `skills/sam-3-1.md`).
- **Video into Spark: mp4 only.** Inline up to **50 MB**; above that use the **Files API**. (Our clips are far below this; re-encode to mp4 for a vision look if the source is HEVC — analysis input itself is never transcoded, brief part 05; only copies for *looking* or for the page are.)
- Practical consequences already encoded in the brief: keep the stable prompt prefix byte-identical across turns (cached-input pricing rewards it, part 06 §1); keep only the last two tool results' images in context (part 06 §4); treat `incomplete` as its own class, never retry it as a network failure (part 14 §4).

## Protocol (owner's notes from the first attempt's live calls, 2026-10-27)

**Request.** `POST {base}/responses` with headers `Authorization: Bearer <META_API_KEY>` and `Accept: text/event-stream`, and a JSON body:
- `model`.
- `input`: a list of items. A message is `{"role":"user","content":[parts]}` with no `type` key. A part is one of:
  - `{"type":"input_text","text":…}`;
  - `{"type":"input_image","image_url":"data:image/png;base64,…"}`;
  - `{"type":"input_video","video_url":"data:video/mp4;base64,…"}`, or `{"type":"input_video","file_id":…}` above 50 MB.
- `stream: true` must be explicit. Without it you get a non-stream reply and a wasted paid call, and long non-stream calls hit a gateway 504.
- `store: false`.
- `max_output_tokens`.
- `instructions`: the system prompt goes here, not as a message.
- `reasoning: {"effort": "low"|"medium"|"high"}`.
- `tools` and `tool_choice: "auto"`. Only `"auto"` is accepted; `"required"` → 400.
- `text.format` for a strict JSON answer.
- `temperature` is not sent (the server uses 1.0).

**Function tools are flat.** The shape is `{"type":"function","name","description","parameters":{…},"strict":true}`. With `strict`, every object level needs `"additionalProperties": false` and lists every property in `required`; otherwise the API returns 400 with `param: parameters`.

**Output items of a tool turn**, in order:
- `{"type":"reasoning", "encrypted_content": …}`, which is opaque;
- optionally a commentary `{"type":"message","role":"assistant","phase":"commentary","content":[{"type":"output_text","text":…}]}`;
- `{"type":"function_call","call_id":"call_…","name":…,"arguments":"<JSON string>"}`.

A plain final answer is a `message` without `phase`.

**Part types by role (live 400 seen 2026-10-28).** In `input`:
- user messages carry `input_text`, `input_image` and `input_video` parts;
- assistant messages carry `output_text` parts only. Anything else returns `HTTP 400: content type input_text is not valid on assistant messages`.

The safest history is the previous response's `output` items replayed verbatim.

**Stateless turns.** Keep your own input list. Append the previous response's `output` items verbatim, reasoning included, then `{"type":"function_call_output","call_id":…,"output":"<string>"}`. Images from a tool go in a separate following user message (`input_text` + `input_image` parts). `previous_response_id` also works, but the first attempt ran stateless with `store:false`. Only one function call per turn was ever seen. The model may answer with no tool call; reply asking for exactly one.

**SSE.** Blocks are separated by blank lines, with `event:` and `data:` lines; skip `:` comment lines and the final `data: [DONE]`. Dispatch on the JSON `type`, not on the `event:` name. Every event has a `sequence_number`. Seen order:
1. `response.created`, `response.in_progress`;
2. `response.output_item.added` / `.done`, `response.content_part.added`, `response.output_text.delta` / `.done`;
3. for calls, `response.function_call_arguments.delta` / `.done`;
4. the terminal event.

**Terminal events** carry the full `response`, with `output` and `usage`.
- `response.completed`.
- `response.incomplete` has `incomplete_details.reason`, e.g. `max_output_tokens`; reasoning tokens count toward the limit. Do not retry it as a network error. The agent retries once at double the limit; any other reason ends the run.
- `response.failed` or a bare `error` event → error, never retried. These shapes were never seen live.
- A stream that ends with no terminal event is truncated: retry the whole request. No usage is reported for that attempt.

**Answer text.** Concatenate the `output_text` of all `message` items in the terminal `output`. A strict-schema answer can still arrive wrapped in prose or a ``` fence, so extract the first JSON object that has the expected keys.

**Usage.** It comes in the terminal response: `usage.input_tokens`, `usage.input_tokens_details.cached_tokens`, `usage.output_tokens`, `usage.output_tokens_details.reasoning_tokens`. Incomplete turns are billed. Caching of a repeated prefix is automatic and needs no field.

**Errors and retries.**
- The error body is `{"error":{"code","message","type","param"}}`.
- 402 `billing_not_configured` means no payment method is set up: never retry it.
- Other 4xx are never retried.
- Retry 429/500/502/503/504, transport errors and truncated streams: 4 attempts in all, backoff `2^attempt + U(0,1)` s, a numeric `Retry-After` wins, any wait is capped at 60 s.
- Use a timeout of 300 s per read. Rate limits are 150 RPM on contributor and 3000 RPM on others.

**Files API.** `POST {base}/files` takes multipart fields `file`, `purpose=user_data`, `expires_after[anchor]=created_at` and `expires_after[seconds]=3600`. The answer is `{"id","bytes","created_at","expires_at","status":"uploaded"}`. Reference the file as `{"type":"input_video","file_id":id}` and remove it with `DELETE {base}/files/{id}`. Uploads and deletes cost $0.

**Web search** is a built-in tool, not an endpoint: add `{"type":"web_search"}` to `tools` with `tool_choice:"auto"`. The first attempt asked for a strict JSON answer `{"facts":[{"text","source_url","quote"}]}` (≤ 5 items, all fields required) and read sources from that answer. [Unverified, docs only] Search results also appear as `web_search_call` items and `url_citation` annotations. Billing is per call, plus tokens.

**Blind checks and the classifier** are single context-free calls: no tools, `effort: low`, `max_output_tokens: 4096`, strict JSON schema, contributor model. An `incomplete` answer is an error.

**The key** lives only in the environment (`META_API_KEY`; the docs call it `MODEL_API_KEY`). It never appears in logs, exception text, results or prompts.

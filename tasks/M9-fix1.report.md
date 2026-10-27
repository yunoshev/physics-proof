# M9 fix 1 report — `schema_doc()` enough to write a valid file

## Files changed
- [physics_proof/schema.py](/Users/ayunoshev/Projects/Personal/physics-proof-wt/m9/physics_proof/schema.py): rewrote `schema_doc()` (one compact line per object, required/optional labels, enums, units, word-safe truncation, ≤ 6000 chars); added `SCHEMA_DOC_LIMIT` and `_short_text()`; de-duplicated `validate()` output; `type`/`schema_version` const checks only fire when the key is present.
- [tests/test_schema_m9.py](/Users/ayunoshev/Projects/Personal/physics-proof-wt/m9/tests/test_schema_m9.py): probe 5 limit 4000 → 6000 chars.
- [config/analysis.schema.json](/Users/ayunoshev/Projects/Personal/physics-proof-wt/m9/config/analysis.schema.json): untouched (source of truth).

## Probe coverage
- Required/optional labels: top-level required/optional lists now read from the schema file (`page_texts` only optional); every section line marked required/optional incl. `timescale` (required, null allowed), `second`/`apex`/`source_url`/`quote` (required keys, null allowed), `page_texts`/`k_sigma` optional.
- Nested names: `reference[].{mask{file,object},mask_check{verdict,covers}}`, `scale.{frame_of_reference` both forms `image` vs `{object,anchor,size_px_per_frame}`, `m_per_px` vs `m_per_ref`, `second{name,m_per_px,m_per_px_err,agree_sigma}}`, `track.points[]{frame,x,y}`, `flights[].{kind,start,apex,end,rise_m,duration_s,fit{a,a_err,rms,v0,n,window{first,last}},accel,accel_err,hypothesis{name,value},decide{state,world,consistent,sigmas,nearest,k,text,g,g_err},ghost[]{frame,y},notes}`, `timescale{method,value,err,unit,expected_range,verdict}`, `verdict{+worlds}`, `overall{label,text}` all named; enums inline (`flight|wall`, `px|ref`, `top|bottom`, mask-check and timescale verdicts, `primary|secondary|estimate`); units inline (`[m]`, `[m/px]`, `[m/s2]`, `[px]`, `[s]`, `[frames/s]`, fraction).
- No mid-word cuts: all truncation goes through word-boundary `_short_text()`; old `desc[:110]` slices (`(blocks`, `(fraction, e`) gone.
- Length: `len(schema_doc())` = 2834 ≤ 6000.
- De-dup: missing top-level field now yields exactly one issue (was two: top-loop `_need` + `_req_*`/const check); final `(path, message)` de-dup covers `verdict` subfields double-checked by `_check_decide_match`.
- Simulated hidden probe: regex-tokenised doc contains every schema-required leaf instantiated in both fixtures (zero missing); minimal filtered rebuild fails only on dynamic keys (`masks` object names, `worlds` names), which the doc documents as `{object_name: …}` / `{name: g}` placeholders.

## Test output
- `uv run pytest -q`: 146 passed, 17 skipped (API-gated), 0 failed.

## Not done / open questions
- None for this task. Optional follow-up: fully auto-generate nested lines by walking the schema instead of curating them, so a future schema field cannot drift from the doc.

# M8 fix 3 report — `finish` enforces an independent second reference

## Built
- `physics_proof/agent.py`: new `finish` gate `_second_independence_error`
  (+ helpers `_object_id`, `_reference_masks`, `_resolve_second_reference`,
  `SAME_OBJECT_IOU = 0.5`). When `scale.second` is present it resolves the
  second reference (`reference_index`, else exact name match for old runs,
  else skip) against the primary (`reference[0]`), loads both masks with
  `blocks.load_masks`, and takes the max IoU over shared frames (empty
  unions skipped). IoU > 0.5 on any shared frame, or both entries pointing
  at the same file and object, refuses: "the second reference is the same
  object as the first (IoU …); use a different object or body, or set
  scale.second to null and give scale.second_missing (…)". No shared
  frame, unresolvable masks, or unmatched old names count as different.
  Removed the ask-once `scale.notes` gate (superseded); `reference_index`
  digit-strings are coerced with a note.
- `physics_proof/schema.py`: `scale.second` accepts optional
  `reference_index` (int ≥ 0, in range of `reference[]`); `second: null`
  requires non-empty `scale.second_missing` (issue at
  `/scale/second_missing`); both documented in `schema_doc()`.
- `config/analysis.schema.json`: optional `reference_index` on `second`,
  optional `second_missing` on `scale` (python-level rule, as with
  `worlds_tested`, so the required-paths walker is unaffected).
- `tests/fixtures/analysis_ball.json`: added `second_missing`.

## Probes
- Same mask for height+width → refused, message names "IoU 1.00"
  (`test_finish_second_same_mask_refused_then_fixed`; message also names
  the `second_missing` remedy, then a fixed file passes).
- Suit + backpack inside it (IoU 0.2) → accepted
  (`test_finish_second_independent_mask_accepted`).
- No shared frame → accepted; identical masks in different files →
  refused with IoU (`test_second_independence_no_shared_frame_and_same_file`).
- `second: null` + `second_missing` → accepted; neither → schema issue at
  `/scale/second_missing` (`test_finish_second_null_needs_second_missing`,
  plus `test_second_null_needs_second_missing`,
  `test_second_reference_index_validated` in `test_schema_m9.py`).
- Old tests: rewritten only the ask-once test it supersedes; rest pass.

## Test output
- `tests/test_schema_m9.py` + `tests/test_agent_m8.py`: 42 passed, 1
  skipped (opt-in API).
- Full suite minus `tests/test_page_m10.py`: 232 passed, 23 skipped.
- `tests/test_page_m10.py`: 10 failed, 1 passed — parallel task, failing
  on missing run dirs; none mention scale/second. Untouched per task.

## Open questions
- Primary reference is `reference[0]` by convention; if the scale is ever
  built on a non-first entry, `scale` needs its own `reference_index`.
- Non-integer mask `object` ids (e.g. `"gate"`) skip the IoU comparison;
  only exact same file+object strings still refuse.

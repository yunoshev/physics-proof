# Task M9 fix 1 — `schema_doc()` must be enough to write a valid file

`schema_doc()` goes into the agent's system prompt; Spark writes `analysis.json` from it alone. The maintainer read the
current output (1 699 characters) and found:

- `reference`, `scale`, `flights`, `masks`, `error_budget` are shown as `optional`, but all are in the top-level
  `required` list (removing them gives "missing required field").
- For arrays of objects (`reference`, `flights`) and for objects with alternatives (`scale` with `anyOf`) the nested
  field names are not listed, so the agent cannot know them (e.g. `flights[].fit`, `accel_err`, `hypothesis`, `ghost`;
  `scale.frame_of_reference` and its two forms; `reference[].mask_check`).
- Descriptions are cut mid-word ("(blocks", "(fraction, e").
- `validate` reports each missing top-level field twice.

## Do
Make `schema_doc()` list, for every section, its required and optional fields down to the leaves (one compact line per
object; enums with their values; units), correct the required/optional labels, never cut a description mid-word, and
stay ≤ 6 000 characters (raise the limit in the test). De-duplicate issues in `validate`.

## Probe
A test builds a minimal valid file **using only the field names that appear in `schema_doc()`** (parse them from the
text) and checks that every required leaf path of both fixtures appears in the doc. Existing tests stay green.

## Done when
Offline tests pass; `tasks/M9-fix1.report.md` written.

# Task M8 fix 3 — `finish` enforces an independent second reference

SPEC §4 rule 2: the second reference must be a different object; two extents of the same object are not independent.
The rule is in the system prompt (verbatim), yet in `runs/2026-10-27-moona-r5` the agent used the height and the width
of the same backpack mask (`sam/white_backpack.250-300.npz`, object `0`) as its two references; the scale "agreed"
(0.08σ) and the result came out g = 1.12 ± 0.60. In `runs/2026-10-27-moona-r2` the same thing happened earlier. A
rule the model keeps breaking is enforced in code, like the mask-check gate.

## Do
1. In `finish`: when `analysis.scale.second` is present, find the reference it uses and the primary reference (the one
   the scale is built on); compare their masks on frames both masks cover. If IoU > 0.5 on any shared frame (or both
   point to the same file and object), the two are the same object → refuse with a readable message: "the second
   reference is the same object as the first (IoU …); use a different object or body, or set scale.second to null and
   give scale.second_missing (why no independent reference exists)". Masks that share no frame count as different.
2. Schema: `scale.second` names the reference it uses (`reference_index`); `scale.second_missing` (string) is allowed
   instead of `second`. Document both in `schema_doc()`. The page (M10) will show "no independent cross-check: …".
3. Do not touch `player/`; keep `build` working on old runs (old runs lack `reference_index`: match by name, else skip
   the check).

## Probes (tests, offline, synthetic masks)
- Height and width of one mask → refused, message names the IoU.
- Suit (large mask) and backpack (small mask inside it, IoU ≈ 0.2) → accepted.
- No shared frame → accepted. `second: null` + `second_missing` → accepted; neither → schema issue.
- Old tests pass.

## Done when
Offline tests pass; `tasks/M8-fix3.report.md` written.

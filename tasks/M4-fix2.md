# Task M4 fix 2 — a classifier layer for the blindness filter

Spec: `SPEC.md` §3 "M4", the updated "Blindness filter" paragraph. After fix 1 the maintainer tried fresh paraphrases
the patterns had never seen:

| query | today | expected |
|---|---|---|
| is this clip real | allowed | refused |
| did the runner really reach the top | allowed | refused |
| was this made with Veo | allowed | refused |
| how high did he get on the wall | refused | refused |
| can a human run on a wall | refused | refused |
| Singapore wall run stunt | refused | refused |
| Marina Bay Sands SkyPark length | allowed | allowed |
| height of a Red Bull banner | allowed | allowed |
| coefficient of friction rubber on aluminium | allowed | allowed |
| how long does a sprinter take to cover 10 m | allowed | allowed |
| typical height of a man in Singapore | allowed | allowed |
| what is a quarter pipe ramp | allowed | allowed |
| is that wall made of steel | allowed | allowed (material of a visible object) |

Patterns alone will keep leaking on paraphrases. Keep them as the fast first layer and add a second one.

## Do
1. `classify(texts) -> list[{kind, reason}]` in `physics_proof/search_tool.py`: one Spark call (contributor tier, no
   context of the run, no web search) with a fixed instruction in `config/prompts/blindness.txt` and a strict schema;
   `kind` is one of `reference` (a general fact: sizes and masses of objects and people, materials, constants, what
   something is), `event` (anything about the specific filmed event, its participants, place-and-action, or its
   measurements), `authenticity` (real, fake, edited, generated, retimed, which tool made it), `feasibility` (whether
   the filmed kind of action is possible). Batch: one call classifies all texts given (a query, or up to 5 facts).
2. `SearchTool.run`: patterns first; a query that passes is classified; anything but `reference` is refused with the
   classifier's reason. Facts returned by the search are classified in one batch; non-`reference` facts are cut and
   logged with the reason.
3. Fail closed: an API error, a malformed answer or a missing item means refuse / cut, logged as such.
4. Costs of the classifier calls go to the ledger and to `SearchResult.cost_usd`; a refused query still costs the
   classifier call — log it.

## Probes
Offline: with a fake client, refusal and cut paths, fail-closed on error and on a malformed answer, batch of 5 facts in
one call. API (`-m api`, < $0.01): the 13 queries above classified as expected (a refusal by either layer counts as
refused).

## Done when
Offline tests pass; the API test passes once; `tasks/M4-fix2.report.md` written.

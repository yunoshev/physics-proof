# M4-fix2 report — a classifier layer for the blindness filter

## What was built
- [config/prompts/blindness.txt](/Users/ayunoshev/Projects/Personal/physics-proof/config/prompts/blindness.txt): fixed classifier instruction defining the four kinds (`reference` general fact, `event` filmed-event specifics/measurements, `authenticity` real/fake/generated/retimed/tool, `feasibility` whether the filmed action is possible), conservative on ambiguity, JSON `items` in input order.
- [physics_proof/search_tool.py](/Users/ayunoshev/Projects/Personal/physics-proof/physics_proof/search_tool.py): `CLASSIFY_SCHEMA` (strict, 1–5 `{kind, reason}` items), `CLASSIFY_MODEL` (contributor tier), `classify(texts, client)` / `classify_with_cost` (one Spark call, no web search, no run context — input is only `TEXTS:` + JSON array), fail-closed `_parse_classify` (bad/missing item → None). `SearchTool.run`: patterns first (no call), then query classified (non-`reference` refused with its reason), then web search, then facts classified in one batch (non-`reference` cut with reason). API errors / malformed / short answers refuse or cut; classifier costs land in `SearchResult.cost_usd` and `search.jsonl`; refused queries log their classifier cost. Search limit still checked before any call and counts only web searches.
- [tests/test_search_tool.py](/Users/ayunoshev/Projects/Personal/physics-proof/tests/test_search_tool.py): routing FakeClient (search vs classifier paths, asserts model/schema/prompt/no-web-search), 7 new offline tests + 13-query API test.

## How each probe is covered
- Refusal path (`event` verdict, no search call, cost logged): `test_fix2_classifier_refuses_query`.
- Cut path (5 facts, one batch, kinds kept/cut with reasons): `test_fix2_classifier_cuts_facts`.
- Fail-closed on error / malformed / missing item: `test_fix2_fail_closed_on_classifier_error`, `..._malformed_answer`, `..._missing_item` (short answer cuts all 5).
- Call shape (contributor tier, prompt file, strict schema, no web search, both arg orders): `test_fix2_classify_call_shape`, `test_fix2_strict_classify_raises_on_bad_item`.
- Existing tests updated for the extra calls (limit counts searches; compact-text cost now includes 2 classifier calls).
- API (`-m api`): `test_fix2_api_classification` — all 13 queries as expected (6 refused by either layer, 7 `reference`), ledger total < $0.01.

## Test output
- `uv run pytest`: 137 passed, 18 skipped (api/slow opt-ins).
- `uv run pytest -m api -k fix2_api`: 1 passed in ~74 s; cost assert (< $0.01) held.

## Could not do / open questions
- Nothing outstanding. Judgment call: a short fact-classifier answer cuts all facts in the batch (alignment uncertain) rather than guessing positions — the safe direction for blindness.

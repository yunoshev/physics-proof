# M4-fix1 report — blindness filter leaks on the second case

## What was built
- [config/blindness.json](/Users/ayunoshev/Projects/Personal/physics-proof/config/blindness.json): new lists `pronoun_terms`, `generative_terms`, `feasibility_action_terms` and patterns `generative_patterns`, `event_name_patterns`, `feasibility_patterns`. All matching stays case-insensitive, in config, not code.
- [physics_proof/search_tool.py](/Users/ayunoshev/Projects/Personal/physics-proof/physics_proof/search_tool.py): `BlindnessRules` + `load_rules` extended; `_refusal_reason` gains four general checks (generative terms/patterns, event-name patterns, quantity×pronoun, feasibility×action, pronoun×measurement). `filter_answer` reuses the same function, so answers get the same rules.
- [tests/test_search_tool.py](/Users/ayunoshev/Projects/Personal/physics-proof/tests/test_search_tool.py): six new tests (table + one per kind + answer-cut coverage).

## How each probe is covered
- Maintainer table (3 allowed, 6 refused): `test_fix1_table_classification`.
- Kind 1 pronoun quantities (`his top speed…`, `how high did they get…`): `test_fix1_pronoun_quantities`; quantity×pronoun or pronoun×measurement refuses, while `how fast does a cheetah run…` stays allowed.
- Kind 2 generative vocab (deepfake, `AI video`, Veo/Sora+context): `test_fix1_generative_vocabulary`; bare `generated`/model names stay allowed without generative context (`Sora rail bird…`, `electricity generated…`, `runway lighting…`).
- Kind 3 event names (`wall run`, `vertical wall`, `Red Bull`+action, Singapore+wall): `test_fix1_event_names`; bare places/brands stay allowed (`Red Bull caffeine…`, `retaining wall…`).
- Kind 4 feasibility (`is it possible`, `can/could a human…`+action): `test_fix1_feasibility_questions`; same phrases without an action stay allowed (`recycle spacesuit materials`).
- Answers: `test_fix1_filter_answer_cuts_each_kind` plants one cut sentence per kind plus the kept PLSS fact.
- Old behavior: the 20 M4 queries still classify exactly (existing tests untouched).

## Test output
- `uv run pytest`: 130 passed, 17 skipped (api/slow opt-ins), 0 failures.
- API probe not run (no live key use for this fix).

## Could not do / open questions
- Nothing outstanding. One judgment call: pronoun+measurement refuses facts like `He ran … at 5 m/s` even without a quantity word; over-cutting a reference sentence is the safe direction for blindness, and no existing probe hits it.

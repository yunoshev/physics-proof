"""M4 probes: blindness classification, answer filter, limit, log (offline).

Plus one opt-in live call (``-m api``, under $0.01). The fake client serves
canned JSON facts and records every ``respond`` call so the limit and
no-API-on-refusal probes can assert that no client call was made.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from physics_proof.search_tool import (
    CLASSIFY_MODEL,
    CLASSIFY_SCHEMA,
    MAX_TEXT_CHARS,
    SEARCH_SCHEMA,
    SearchResult,
    SearchTool,
    check_query,
    classify,
    filter_answer,
)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "config" / "prompts" / "blindness.txt"

ALLOWED_QUERIES = [
    "Apollo A7L spacesuit height and mass",
    "Apollo PLSS backpack dimensions",
    "Lamborghini Aventador height in metres",
    "regulation basketball rim height",
    "average adult male height in Switzerland",
    "standard gravity value in m/s^2",
    "surface gravity of the Moon",
    "inflatable blob airbag length",
    "what is the box on the back of an Apollo astronaut",
    "12 ft trampoline diameter in metres",
]

REFUSED_QUERIES = [
    "how high did the astronaut jump in the Apollo 16 salute",
    "Apollo 16 jump salute hang time",
    "is the moon landing footage slowed down",
    "blobbing world record height",
    "how long was he in the air",
    "was this video faked",
    "IShowSpeed Lamborghini jump real or fake",
    "debunk moon landing slow motion",
    "speed of the car in this viral video",
    "frame rate of the original Apollo 16 broadcast",
]

GOOD_FACT = {
    "text": "The Apollo PLSS backpack is 26 inches tall.",
    "source_url": "https://www.nasa.gov/example/plss",
    "quote": "The PLSS is 26 inches tall",
}


class FakeClient:
    """Fake Spark client: serves canned facts, records every respond call.

    Search calls (``web_search=True``) get the canned facts; classifier
    calls get verdicts from ``verdict`` (one kind for every text, or a
    callable mapping the input texts to kinds).
    """

    def __init__(
        self,
        facts: list[dict[str, str]] | None = None,
        verdict: str | object = "reference",
        classify_cost: float = 0.0004,
        classify_error: Exception | None = None,
        classify_payload: str | None = None,
    ) -> None:
        self.facts = facts if facts is not None else [dict(GOOD_FACT)]
        self.verdict = verdict
        self.classify_cost = classify_cost
        self.classify_error = classify_error
        self.classify_payload = classify_payload
        self.calls: list[tuple[str, dict]] = []

    def _verdict_items(self, texts: list[str]) -> list[dict[str, str]]:
        if callable(self.verdict):
            kinds = self.verdict(texts)
        else:
            kinds = [self.verdict] * len(texts)
        return [{"kind": kind, "reason": "fake " + kind} for kind in kinds]

    def respond(self, query: str, **kwargs) -> SimpleNamespace:
        self.calls.append((query, kwargs))
        if kwargs.get("web_search") is True:
            assert kwargs.get("json_schema") == SEARCH_SCHEMA
            assert isinstance(kwargs.get("instructions"), str) and kwargs["instructions"]
            return SimpleNamespace(
                text=json.dumps({"facts": self.facts}),
                cost_usd=0.0025,
            )
        assert kwargs.get("json_schema") == CLASSIFY_SCHEMA
        assert kwargs.get("model") == CLASSIFY_MODEL
        assert kwargs.get("web_search") is False
        assert kwargs.get("instructions") == PROMPT_PATH.read_text(encoding="utf-8").strip()
        if self.classify_error is not None:
            raise self.classify_error
        if self.classify_payload is not None:
            return SimpleNamespace(text=self.classify_payload, cost_usd=self.classify_cost)
        texts = json.loads(query.split("TEXTS:\n", 1)[1])
        return SimpleNamespace(
            text=json.dumps({"items": self._verdict_items(texts)}),
            cost_usd=self.classify_cost,
        )


def _search_calls(fake: FakeClient) -> list:
    """Calls that hit the web search (classifier calls excluded)."""
    return [call for call in fake.calls if call[1].get("web_search") is True]


def _classify_calls(fake: FakeClient) -> list:
    """Calls that hit the blindness classifier."""
    return [call for call in fake.calls if call[1].get("web_search") is not True]


def _tool(tmp_path: Path, fake: FakeClient, **kwargs) -> SearchTool:
    return SearchTool(fake, tmp_path / "ws", **kwargs)


def test_query_classification_exact(tmp_path: Path) -> None:
    """Probe 1: the 20 fixed queries are classified exactly."""
    tool = _tool(tmp_path, FakeClient())
    for query in ALLOWED_QUERIES:
        allowed, reason = tool.check_query(query)
        assert allowed is True, query + " -> " + reason
    for query in REFUSED_QUERIES:
        allowed, reason = tool.check_query(query)
        assert allowed is False, query + " was allowed"
        assert "\n" not in reason
    assert len(ALLOWED_QUERIES) == 10
    assert len(REFUSED_QUERIES) == 10


def test_module_level_functions_agree() -> None:
    """Module-level check_query/filter_answer match the tool methods."""
    for query in ALLOWED_QUERIES + REFUSED_QUERIES:
        assert check_query(query)[0] is (query in ALLOWED_QUERIES)
    kept, cut = filter_answer([dict(GOOD_FACT)])
    assert len(kept) == 1 and cut == []


def test_filter_answer_plants(tmp_path: Path) -> None:
    """Probe 2: event-quantity and fake sentences are cut and logged."""
    facts = [
        {"text": "The jump reached 0.5 m.", "source_url": "https://x.example/a", "quote": "jump reached 0.5 m"},
        {"text": "Experts say the clip is fake.", "source_url": "https://x.example/b", "quote": "the clip is fake"},
        dict(GOOD_FACT),
    ]
    tool = _tool(tmp_path, FakeClient(facts))
    kept, cut = tool.filter_answer(facts)
    assert [item["text"] for item in kept] == [GOOD_FACT["text"]]
    assert len(cut) == 2
    assert all("reason" in entry and "fact" in entry for entry in cut)
    result = tool.run("Apollo PLSS backpack dimensions")
    assert result.allowed is True
    assert [item["text"] for item in result.facts] == [GOOD_FACT["text"]]
    assert len(result.cut) == 2
    lines = (tmp_path / "ws" / "search.jsonl").read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["cut"] == 2
    assert len(record["cut_reasons"]) == 2


def test_chatter_wrapped_json_parses(tmp_path: Path) -> None:
    """Spark chatter around the JSON object still yields the facts."""
    payload = (
        "I will search for that now. "
        + json.dumps({"facts": [dict(GOOD_FACT)]})
        + " Hope this helps."
    )
    tool = _tool(tmp_path, FakeClient())

    def routed_respond(query: str, **kw: object) -> SimpleNamespace:
        if kw.get("web_search") is True:
            return SimpleNamespace(text=payload, cost_usd=0.001)
        return SimpleNamespace(
            text=json.dumps({"items": [{"kind": "reference", "reason": "fake"}]}),
            cost_usd=0.0004,
        )

    tool.client.respond = routed_respond
    result = tool.run("standard gravity value in m/s^2")
    assert result.allowed is True
    assert [item["text"] for item in result.facts] == [GOOD_FACT["text"]]


def test_limit_refuses_without_client_call(tmp_path: Path) -> None:
    """Probe 3: with limit=2 the third call is refused, client untouched."""
    fake = FakeClient()
    tool = _tool(tmp_path, fake, limit=2)
    first = tool.run("standard gravity value in m/s^2")
    second = tool.run("Apollo PLSS backpack dimensions")
    assert first.allowed and second.allowed
    assert len(_search_calls(fake)) == 2
    calls_after_two = len(fake.calls)
    assert calls_after_two > 2  # each run also pays for classifier calls
    assert tool.searches_made == 2
    third = tool.run("surface gravity of the Moon")
    assert third.allowed is False
    assert isinstance(third, SearchResult)
    assert "limit" in third.reason.lower()
    assert len(fake.calls) == calls_after_two
    assert tool.searches_made == 2


def test_refusal_makes_no_client_call(tmp_path: Path) -> None:
    """A refused query is logged with zero cost and no API call."""
    fake = FakeClient()
    tool = _tool(tmp_path, fake)
    result = tool.run("was this video faked")
    assert result.allowed is False
    assert result.facts == [] and result.cost_usd == 0.0
    assert fake.calls == []
    record = json.loads((tmp_path / "ws" / "search.jsonl").read_text().splitlines()[0])
    assert record["decision"] == "refused"
    assert record["cost_usd"] == 0.0


def test_log_lines_have_query_decision_cut_cost(tmp_path: Path) -> None:
    """Probe 4: one JSON line per call with query, decision, cut and cost."""
    fake = FakeClient()
    tool = _tool(tmp_path, fake)
    tool.run("standard gravity value in m/s^2")
    tool.run("was this video faked")
    lines = (tmp_path / "ws" / "search.jsonl").read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        record = json.loads(line)
        assert isinstance(record["query"], str) and record["query"]
        assert record["decision"] in ("allowed", "refused")
        assert isinstance(record["cut"], int)
        assert isinstance(record["cost_usd"], (int, float))
        assert isinstance(record["reason"], str)
    assert lines[0] != lines[1]


def test_result_text_compact_with_sources(tmp_path: Path) -> None:
    """text() fits 1500 chars and carries every fact's source URL."""
    facts = [
        {"text": "Fact %d about suits." % i, "source_url": "https://x.example/%d" % i, "quote": "quote %d" % i}
        for i in range(5)
    ]
    tool = _tool(tmp_path, FakeClient(facts))
    result = tool.run("Apollo A7L spacesuit height and mass")
    assert result.allowed is True
    assert result.cost_usd == pytest.approx(0.0025 + 2 * 0.0004)
    assert len(_search_calls(tool.client)) == 1
    assert len(_classify_calls(tool.client)) == 2
    body = result.text()
    assert len(body) <= MAX_TEXT_CHARS
    for fact in facts:
        assert fact["source_url"] in body
    refused = SearchResult(allowed=False, reason="refused: demo")
    assert len(refused.text()) <= MAX_TEXT_CHARS


FIX1_ALLOWED_QUERIES = [
    "Marina Bay Sands tower height",
    "shoe rubber friction coefficient on steel",
    "typical sprint step frequency",
]

FIX1_REFUSED_QUERIES = [
    "Red Bull wall run Singapore real or fake",
    "how tall is the wall in this video",
    "how fast did he run up the wall",
    "was this generated by Sora",
    "Red Bull vertical wall run Singapore",
    "is it possible to run up a vertical wall",
]

# Four leak kinds from tasks/M4-fix1.md: own refused queries plus
# allowed look-alikes that share words with the refused ones.
PRONOUN_REFUSED = [
    "what was his top speed on the wall",
    "how high did they get",
    "how long did it take him to reach the top",
]

PRONOUN_ALLOWED = [
    "how fast does a cheetah run at top speed",
    "average running shoe lifespan in kilometres",
    "how tall is the Burj Khalifa tower",
]

GENERATIVE_REFUSED = [
    "was the clip a deepfake",
    "which AI video model made this wall climb",
    "did Veo 3 generate this footage",
]

GENERATIVE_ALLOWED = [
    "how is electricity generated in power stations",
    "Sora rail bird migration range",
    "AI use in video compression standards",
    "runway lighting spacing at airports",
]

EVENT_NAME_REFUSED = [
    "Red Bull soapbox race top speed",
    "Singapore vertical wall climb event",
    "best wall run technique tutorial",
]

EVENT_NAME_ALLOWED = [
    "Singapore Flyer wheel diameter in metres",
    "retaining wall design specifications",
    "Red Bull caffeine content per 100 ml",
]

FEASIBILITY_REFUSED = [
    "can a person climb a sheer wall without ropes",
    "could anyone survive a fall like that",
    "is it humanly possible to sprint up stairs quickly",
]

FEASIBILITY_ALLOWED = [
    "indoor climbing wall standard dimensions",
    "can humans see infrared light",
    "is it possible to recycle spacesuit materials",
]


def test_fix1_table_classification() -> None:
    """M4-fix1 probe: the maintainer's second-case table is classified exactly."""
    for query in FIX1_ALLOWED_QUERIES:
        allowed, reason = check_query(query)
        assert allowed is True, query + " -> " + reason
    for query in FIX1_REFUSED_QUERIES:
        allowed, reason = check_query(query)
        assert allowed is False, query + " was allowed"
        assert "\n" not in reason


def test_fix1_pronoun_quantities() -> None:
    """Kind 1: event quantities asked with a pronoun are refused; references pass."""
    for query in PRONOUN_REFUSED:
        allowed, reason = check_query(query)
        assert allowed is False, query + " was allowed"
    for query in PRONOUN_ALLOWED:
        allowed, reason = check_query(query)
        assert allowed is True, query + " -> " + reason


def test_fix1_generative_vocabulary() -> None:
    """Kind 2: model names, 'generated' with context, deepfake, AI video refuse."""
    for query in GENERATIVE_REFUSED:
        allowed, reason = check_query(query)
        assert allowed is False, query + " was allowed"
    for query in GENERATIVE_ALLOWED:
        allowed, reason = check_query(query)
        assert allowed is True, query + " -> " + reason


def test_fix1_event_names() -> None:
    """Kind 3: queries naming the filmed event/stunt refuse; objects pass."""
    for query in EVENT_NAME_REFUSED:
        allowed, reason = check_query(query)
        assert allowed is False, query + " was allowed"
    for query in EVENT_NAME_ALLOWED:
        allowed, reason = check_query(query)
        assert allowed is True, query + " -> " + reason


def test_fix1_feasibility_questions() -> None:
    """Kind 4: verdict-seeking feasibility questions refuse; plain refs pass."""
    for query in FEASIBILITY_REFUSED:
        allowed, reason = check_query(query)
        assert allowed is False, query + " was allowed"
    for query in FEASIBILITY_ALLOWED:
        allowed, reason = check_query(query)
        assert allowed is True, query + " -> " + reason


def test_fix1_filter_answer_cuts_each_kind() -> None:
    """M4-fix1: the same rules cut answer sentences of every new kind."""
    facts = [
        {"text": "He ran up the wall at 5 m/s.", "source_url": "https://x.example/a", "quote": "ran up the wall at 5 m/s"},
        {"text": "The clip was generated by Sora.", "source_url": "https://x.example/b", "quote": "generated by Sora"},
        {"text": "The Red Bull wall run took place in Singapore.", "source_url": "https://x.example/c", "quote": "Red Bull wall run"},
        {"text": "It is possible to run up a vertical wall, experts say.", "source_url": "https://x.example/d", "quote": "possible to run up"},
        dict(GOOD_FACT),
    ]
    kept, cut = filter_answer(facts)
    assert [item["text"] for item in kept] == [GOOD_FACT["text"]]
    assert len(cut) == 4


def test_fix2_classify_call_shape(tmp_path: Path) -> None:
    """One contributor-tier call, fixed prompt, strict schema, no web search."""
    fake = FakeClient()
    verdicts = classify(["standard gravity value"], fake)
    assert verdicts == [{"kind": "reference", "reason": "fake reference"}]
    assert len(fake.calls) == 1
    query, kwargs = fake.calls[0]
    assert "TEXTS:" in query and "standard gravity value" in query
    assert "clip" not in query.lower()
    assert kwargs["model"] == CLASSIFY_MODEL
    assert kwargs["web_search"] is False
    assert kwargs["json_schema"] == CLASSIFY_SCHEMA
    assert kwargs["instructions"] == PROMPT_PATH.read_text(encoding="utf-8").strip()
    # The other argument order works too.
    assert classify(fake, ["surface gravity of the Moon"])[0]["kind"] == "reference"


def test_fix2_classifier_refuses_query(tmp_path: Path) -> None:
    """A paraphrase the patterns miss is refused by the classifier layer."""
    fake = FakeClient(verdict="event")
    tool = _tool(tmp_path, fake)
    result = tool.run("did the runner really reach the top")
    assert result.allowed is False
    assert result.facts == []
    assert _search_calls(fake) == []
    assert len(_classify_calls(fake)) == 1
    assert result.cost_usd == pytest.approx(0.0004)
    record = json.loads((tmp_path / "ws" / "search.jsonl").read_text().splitlines()[0])
    assert record["decision"] == "refused"
    assert record["cost_usd"] == pytest.approx(0.0004)


def test_fix2_classifier_cuts_facts(tmp_path: Path) -> None:
    """Non-reference facts are cut with the classifier's reason in one batch."""
    facts = [
        {"text": "Fact %d about reference sizes." % i, "source_url": "https://x.example/%d" % i, "quote": "quote %d" % i}
        for i in range(5)
    ]

    def pick(texts: list[str]) -> list[str]:
        if len(texts) == 1:
            return ["reference"]
        assert len(texts) == 5
        return ["reference", "event", "authenticity", "feasibility", "reference"]

    tool = _tool(tmp_path, FakeClient(facts, verdict=pick))
    result = tool.run("standard gravity value in m/s^2")
    assert result.allowed is True
    assert [item["text"] for item in result.facts] == [facts[0]["text"], facts[4]["text"]]
    assert len(result.cut) == 3
    assert any("event" in entry["reason"] for entry in result.cut)
    assert any("authenticity" in entry["reason"] for entry in result.cut)
    assert any("feasibility" in entry["reason"] for entry in result.cut)
    assert len(_search_calls(tool.client)) == 1
    assert len(_classify_calls(tool.client)) == 2  # query + one batch of 5
    assert result.cost_usd == pytest.approx(0.0025 + 2 * 0.0004)
    record = json.loads((tmp_path / "ws" / "search.jsonl").read_text().splitlines()[0])
    assert record["facts_kept"] == 2 and record["cut"] == 3
    assert len(record["cut_reasons"]) == 3


def test_fix2_fail_closed_on_classifier_error(tmp_path: Path) -> None:
    """An API error in the query classifier means refuse with no search."""
    fake = FakeClient(classify_error=RuntimeError("boom"))
    tool = _tool(tmp_path, fake)
    result = tool.run("standard gravity value in m/s^2")
    assert result.allowed is False
    assert result.facts == [] and result.cost_usd == 0.0
    assert _search_calls(fake) == []
    record = json.loads((tmp_path / "ws" / "search.jsonl").read_text().splitlines()[0])
    assert record["decision"] == "refused"


def test_fix2_fail_closed_on_malformed_answer(tmp_path: Path) -> None:
    """A malformed classifier answer still costs the call and refuses."""
    fake = FakeClient(classify_payload="definitely not json {")
    tool = _tool(tmp_path, fake)
    result = tool.run("standard gravity value in m/s^2")
    assert result.allowed is False
    assert result.cost_usd == pytest.approx(0.0004)
    record = json.loads((tmp_path / "ws" / "search.jsonl").read_text().splitlines()[0])
    assert record["decision"] == "refused"
    assert record["cost_usd"] == pytest.approx(0.0004)


def test_fix2_fail_closed_on_missing_item(tmp_path: Path) -> None:
    """A short classifier answer (4 verdicts for 5 facts) cuts every fact."""
    facts = [
        {"text": "Fact %d about reference sizes." % i, "source_url": "https://x.example/%d" % i, "quote": "quote %d" % i}
        for i in range(5)
    ]
    short = json.dumps({"items": [{"kind": "reference", "reason": "fake"}] * 4})

    def routed(query: str, **kw: object) -> SimpleNamespace:
        if kw.get("web_search") is True:
            return SimpleNamespace(text=json.dumps({"facts": facts}), cost_usd=0.0025)
        texts = json.loads(query.split("TEXTS:\n", 1)[1])
        if len(texts) == 1:
            return SimpleNamespace(
                text=json.dumps({"items": [{"kind": "reference", "reason": "ok"}]}),
                cost_usd=0.0004,
            )
        return SimpleNamespace(text=short, cost_usd=0.0004)

    fake = FakeClient(facts)
    tool = _tool(tmp_path, fake)
    tool.client.respond = routed
    result = tool.run("standard gravity value in m/s^2")
    assert result.allowed is True
    assert result.facts == []
    assert len(result.cut) == 5


def test_fix2_strict_classify_raises_on_bad_item() -> None:
    """Module-level classify raises so callers can fail closed."""
    fake = FakeClient(classify_payload=json.dumps({"items": [{"kind": "nope", "reason": "x"}]}))
    with pytest.raises(ValueError):
        classify(["something"], fake)
    with pytest.raises(TypeError):
        classify(["something"])


FIX2_API_REFUSED = [
    "is this clip real",
    "did the runner really reach the top",
    "was this made with Veo",
    "how high did he get on the wall",
    "can a human run on a wall",
    "Singapore wall run stunt",
]

FIX2_API_ALLOWED = [
    "Marina Bay Sands SkyPark length",
    "height of a Red Bull banner",
    "coefficient of friction rubber on aluminium",
    "how long does a sprinter take to cover 10 m",
    "typical height of a man in Singapore",
    "what is a quarter pipe ramp",
    "is that wall made of steel",
]


@pytest.mark.api
def test_fix2_api_classification(tmp_path) -> None:
    """API probe: the 13 fresh paraphrases classify as expected (< $0.01)."""
    from physics_proof.config import Settings
    from physics_proof.ledger import Ledger
    from physics_proof.meta_client import MetaClient

    ledger = Ledger(tmp_path / "run.jsonl", tmp_path / "global.jsonl")
    client = MetaClient(settings=Settings(), ledger=ledger, run="m4-fix2-api")
    tool = SearchTool(client, tmp_path / "ws")
    for query in FIX2_API_REFUSED:
        allowed, _ = tool.check_query(query)
        verdicts = tool.classify([query])
        refused = (not allowed) or verdicts[0]["kind"] != "reference"
        print("\nRefuse? %s kind=%s: %s" % (refused, verdicts[0]["kind"], query), flush=True)
        assert refused, query + " classified as reference"
    for query in FIX2_API_ALLOWED:
        verdicts = tool.classify([query])
        print("\nAllowed kind=%s: %s" % (verdicts[0]["kind"], query), flush=True)
        assert verdicts[0]["kind"] == "reference", query + " -> " + str(verdicts[0])
    total = Ledger.total(tmp_path / "run.jsonl")
    print("Classifier total: $%.6f" % total, flush=True)
    assert total < 0.01


@pytest.mark.api
def test_live_search_returns_cited_fact(tmp_path) -> None:
    """API probe: one real query returns a cited fact; ledger shows a search."""
    from physics_proof.config import Settings
    from physics_proof.ledger import Ledger
    from physics_proof.meta_client import MetaClient

    ledger = Ledger(tmp_path / "run.jsonl", tmp_path / "global.jsonl")
    client = MetaClient(settings=Settings(), ledger=ledger, run="m4-api")
    tool = SearchTool(client, tmp_path / "ws")
    result = tool.run("standard gravity value in m/s^2")
    print("\nSearch: allowed=%s facts=%d cut=%d cost=$%.6f" % (
        result.allowed, len(result.facts), len(result.cut), result.cost_usd), flush=True)
    print(result.text(), flush=True)
    assert result.allowed is True
    assert len(result.facts) >= 1
    fact = result.facts[0]
    assert fact["source_url"].startswith("http")
    assert fact["quote"] and " ".join(fact["quote"].split()) in result.text()
    assert fact["source_url"] in result.text()
    assert any('"searches": 1' in line for line in (tmp_path / "run.jsonl").read_text().splitlines())
    total = Ledger.total(tmp_path / "run.jsonl")
    print("Ledger total: $%.6f" % total, flush=True)
    assert total < 0.01

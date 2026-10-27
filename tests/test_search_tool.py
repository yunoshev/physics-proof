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
    MAX_TEXT_CHARS,
    SEARCH_SCHEMA,
    SearchResult,
    SearchTool,
    check_query,
    filter_answer,
)

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
    """Fake Spark client: serves canned facts, records every respond call."""

    def __init__(self, facts: list[dict[str, str]] | None = None) -> None:
        self.facts = facts if facts is not None else [dict(GOOD_FACT)]
        self.calls: list[tuple[str, dict]] = []

    def respond(self, query: str, **kwargs) -> SimpleNamespace:
        self.calls.append((query, kwargs))
        assert kwargs.get("web_search") is True
        assert kwargs.get("json_schema") == SEARCH_SCHEMA
        assert isinstance(kwargs.get("instructions"), str) and kwargs["instructions"]
        return SimpleNamespace(
            text=json.dumps({"facts": self.facts}),
            cost_usd=0.0025,
        )


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
    tool.client.respond = lambda query, **kw: SimpleNamespace(text=payload, cost_usd=0.001)
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
    assert len(fake.calls) == 2
    assert tool.searches_made == 2
    third = tool.run("surface gravity of the Moon")
    assert third.allowed is False
    assert isinstance(third, SearchResult)
    assert "limit" in third.reason.lower()
    assert len(fake.calls) == 2
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
    assert result.cost_usd == pytest.approx(0.0025)
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

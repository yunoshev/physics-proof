# generated from brief/07 · part 07 owns this file
"""``web_search``: pattern screen, classifier gate, facts passthrough."""

from __future__ import annotations

import json

from src.tools import web_search


def _run(make_run):
    return make_run(frames=10)


def test_pattern_screen_rejects_answer_seeking(make_run, search_ok,
                                                 ledger):
    run = _run(make_run)
    for query in ("moon landing hoax jump",
                  "is the jump footage faked",
                  "debunk Apollo jump",
                  "Apollo 16 jump salute gravity measured",
                  "viral moon jump video real or fake",
                  "jump height of the event in the clip"):
        result = web_search.web_search(
            str(run), 0, query=query, search_client=search_ok,
            classifier=lambda q: "no", ledger=ledger)
        assert not result["ok"], query
        assert result["error"]["code"] == "query_rejected"
        assert result["metrics"]["stage"] == "pattern_screen"
    assert search_ok.calls == [], "refused queries never execute"
    assert ledger.searches == 0


def test_pattern_screen_passes_named_identities(make_run, search_ok,
                                                ledger):
    # Part 07 §17: the screen blocks the answer, not the identity —
    # places, missions, people, models and eras pass the screen.
    run = _run(make_run)
    for query in ("Apollo spacesuit astronaut height metres suited",
                  "John Young astronaut height",
                  "Apollo life support backpack PLSS height dimensions "
                  "metres"):
        assert web_search.pattern_hit(query) == "", query
        result = web_search.web_search(
            str(run), 0, query=query, search_client=search_ok,
            classifier=lambda q: "no", ledger=ledger)
        assert result["ok"], (query, result)
    assert ledger.searches == 3


def test_answer_patterns_are_answer_shaped():
    # Generic in structure: answer-seeking forms, never names,
    # missions or places.
    lowered = " ".join(web_search.ANSWER_SEEKING_PATTERNS).lower()
    for dropped in ("apollo", "alsj", "armstrong", "aldrin",
                    "lunar surface journal"):
        assert dropped not in lowered, dropped
    for kept in ("hoax", "fake", "faked", "debunk"):
        assert kept in lowered, kept


def test_classifier_question_is_about_video_or_answer():
    assert "specific video" in web_search.CLASSIFIER_QUESTION
    assert "what gravity it shows" in web_search.CLASSIFIER_QUESTION
    assert "sizes, dimensions, rates" in web_search.CLASSIFIER_QUESTION


def test_pattern_screen_rejects_hashes_and_run_tokens(make_run,
                                                      search_ok):
    run = _run(make_run)
    hashed = web_search.web_search(
        str(run), 0, query="backpack 9f3a1c2e dimensions",
        search_client=search_ok, classifier=lambda q: "no")
    assert not hashed["ok"]
    assert hashed["metrics"]["stage"] == "pattern_screen"
    stem = next((run / "input").glob("clip*")).stem
    tokened = web_search.web_search(
        str(run), 0, query=f"dimensions of {stem} frame",
        search_client=search_ok, classifier=lambda q: "no")
    assert not tokened["ok"]


def test_classifier_rejects_yes_and_uncertain(make_run, search_ok,
                                              ledger):
    run = _run(make_run)
    for verdict in ("yes", "uncertain"):
        result = web_search.web_search(
            str(run), 0, query="backpack height in metres",
            search_client=search_ok,
            classifier=lambda q, v=verdict: v, ledger=ledger)
        assert not result["ok"]
        assert result["error"]["code"] == "query_rejected"
        assert result["metrics"]["stage"] == "classifier"
        assert result["metrics"]["verdict"] == verdict
    assert search_ok.calls == []
    assert ledger.searches == 0


def test_classifier_failure_and_absence_fail_closed(make_run,
                                                    search_ok):
    run = _run(make_run)

    def _boom(query):
        raise RuntimeError("classifier down")

    failed = web_search.web_search(
        str(run), 0, query="backpack height in metres",
        search_client=search_ok, classifier=_boom)
    assert not failed["ok"]
    assert failed["error"]["code"] == "classifier_failed"
    absent = web_search.web_search(
        str(run), 0, query="backpack height in metres",
        search_client=search_ok, classifier=None)
    assert not absent["ok"]
    assert absent["error"]["code"] == "classifier_unavailable"
    assert search_ok.calls == []


def test_allowed_query_passes_every_fact_through(make_run, search_ok,
                                                 ledger):
    run = _run(make_run)
    result = web_search.web_search(
        str(run), 2, query="life support backpack height in metres",
        search_client=search_ok, classifier=lambda q: "no",
        ledger=ledger)
    assert result["ok"], result
    facts = result["metrics"]["facts"]
    assert len(facts) == 2
    for fact in facts:
        assert set(fact) == {"text", "url", "quote"}
    assert facts[0] == {"text": "life-support backpack height 0.66 m",
                       "url": "https://example.com/plss",
                       "quote": "backpack height 0.66 m"}
    assert facts[1]["url"] == "https://example.org/other"
    assert result["files"][0].startswith("artifacts/t2_web_search_")
    saved = json.loads((run / result["files"][0]).read_text(
        encoding="utf-8"))
    assert saved["facts"] == facts
    assert ledger.searches == 1


def test_queries_and_decisions_are_logged(make_run, search_ok):
    run = _run(make_run)
    web_search.web_search(str(run), 0,
                          query="life support backpack height",
                          search_client=search_ok,
                          classifier=lambda q: "no")
    web_search.web_search(str(run), 1, query="moon landing hoax jump",
                          search_client=search_ok,
                          classifier=lambda q: "no")
    log = (run / "logs" / "search.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in log.splitlines()]
    assert [row["allowed"] for row in rows] == [True, False]
    assert rows[1]["stage"] == "pattern_screen"
    assert rows[0]["fact_count"] == 2

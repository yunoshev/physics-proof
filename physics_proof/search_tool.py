"""M4. Search tool with a blindness filter (SPEC.md M4, Principle 7).

The agent may look up reference facts (sizes, constants, equipment) but must
never be handed the answer. Queries about the filmed event's own quantities
or the clip's authenticity are refused before any API call, and matching
sentences are cut from answers. Word lists and patterns live in
``config/blindness.json``, not in code; all matching is case-insensitive.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import REPO_ROOT

__all__ = [
    "BLINDNESS_PATH",
    "MAX_FACTS",
    "MAX_TEXT_CHARS",
    "SEARCH_INSTRUCTION",
    "SEARCH_SCHEMA",
    "SearchResult",
    "SearchTool",
    "check_query",
    "filter_answer",
    "load_rules",
]

#: Default blindness word lists and patterns.
BLINDNESS_PATH = REPO_ROOT / "config" / "blindness.json"

#: Short instruction for the separate Spark call (task M4 wording).
SEARCH_INSTRUCTION = "Return facts with their source URL and a verbatim quote; no opinions."

#: Strict schema for the Spark call: at most five cited facts.
SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "source_url": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["text", "source_url", "quote"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["facts"],
    "additionalProperties": False,
}

#: Maximum facts kept per search (mirrors the schema).
MAX_FACTS = 5
#: Maximum characters of ``SearchResult.text()``.
MAX_TEXT_CHARS = 1500


@dataclass
class BlindnessRules:
    """Compiled blindness lists and patterns from ``blindness.json``."""

    always_terms: list[str] = field(default_factory=list)
    event_terms: list[str] = field(default_factory=list)
    quantity_terms: list[str] = field(default_factory=list)
    pronoun_terms: list[str] = field(default_factory=list)
    generative_terms: list[str] = field(default_factory=list)
    feasibility_action_terms: list[str] = field(default_factory=list)
    measurement_pattern: str = ""
    authenticity_patterns: list[str] = field(default_factory=list)
    generative_patterns: list[str] = field(default_factory=list)
    event_name_patterns: list[str] = field(default_factory=list)
    feasibility_patterns: list[str] = field(default_factory=list)
    event_quantity_patterns: list[str] = field(default_factory=list)


def _term_regex(term: str) -> str:
    """Word-boundary regex for one term (multi-word terms included)."""
    return r"\b" + re.escape(term) + r"\b"


def load_rules(path: str | Path = BLINDNESS_PATH) -> BlindnessRules:
    """Load and compile the blindness lists from JSON."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return BlindnessRules(
        always_terms=[str(v) for v in raw.get("always_refuse_terms", [])],
        event_terms=[str(v) for v in raw.get("event_terms", [])],
        quantity_terms=[str(v) for v in raw.get("quantity_terms", [])],
        pronoun_terms=[str(v) for v in raw.get("pronoun_terms", [])],
        generative_terms=[str(v) for v in raw.get("generative_terms", [])],
        feasibility_action_terms=[str(v) for v in raw.get("feasibility_action_terms", [])],
        measurement_pattern=str(raw.get("measurement_pattern", "")),
        authenticity_patterns=[str(v) for v in raw.get("authenticity_patterns", [])],
        generative_patterns=[str(v) for v in raw.get("generative_patterns", [])],
        event_name_patterns=[str(v) for v in raw.get("event_name_patterns", [])],
        feasibility_patterns=[str(v) for v in raw.get("feasibility_patterns", [])],
        event_quantity_patterns=[str(v) for v in raw.get("event_quantity_patterns", [])],
    )


_DEFAULT_RULES: BlindnessRules | None = None


def _rules(rules: BlindnessRules | None) -> BlindnessRules:
    """Default rules, loaded once from ``config/blindness.json``."""
    global _DEFAULT_RULES
    if rules is not None:
        return rules
    if _DEFAULT_RULES is None:
        _DEFAULT_RULES = load_rules()
    return _DEFAULT_RULES


def _refusal_reason(text: str, rules: BlindnessRules) -> str | None:
    """Return a single-line refusal reason, or None when the text is clean."""
    for term in rules.always_terms:
        if re.search(_term_regex(term), text, re.IGNORECASE):
            return "refused: asks about authenticity or the event itself (" + term + ")"
    for term in rules.generative_terms:
        if re.search(_term_regex(term), text, re.IGNORECASE):
            return "refused: asks about generative video (" + term + ")"
    for pattern in rules.authenticity_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "refused: matches an authenticity pattern (" + pattern + ")"
    for pattern in rules.generative_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "refused: matches a generative-video pattern (" + pattern + ")"
    for pattern in rules.event_name_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "refused: names the filmed event or stunt (" + pattern + ")"
    event_hit = next(
        (t for t in rules.event_terms if re.search(_term_regex(t), text, re.IGNORECASE)),
        None,
    )
    quantity_hit = next(
        (t for t in rules.quantity_terms if re.search(_term_regex(t), text, re.IGNORECASE)),
        None,
    )
    if event_hit is not None and quantity_hit is not None:
        return (
            "refused: asks about the event's own quantities "
            + "(quantity " + quantity_hit + ", event " + event_hit + ")"
        )
    pronoun_hit = next(
        (t for t in rules.pronoun_terms if re.search(_term_regex(t), text, re.IGNORECASE)),
        None,
    )
    if pronoun_hit is not None and quantity_hit is not None:
        return (
            "refused: asks about the filmed subject's own quantities "
            + "(quantity " + quantity_hit + ", pronoun " + pronoun_hit + ")"
        )
    feasibility_hit = next(
        (p for p in rules.feasibility_patterns if re.search(p, text, re.IGNORECASE)),
        None,
    )
    if feasibility_hit is not None:
        action_hit = next(
            (
                t
                for t in rules.feasibility_action_terms
                if re.search(_term_regex(t), text, re.IGNORECASE)
            ),
            None,
        )
        if action_hit is not None:
            return (
                "refused: asks for a verdict on the filmed action "
                + "(feasibility pattern, action " + action_hit + ")"
            )
    if rules.measurement_pattern and re.search(
        rules.measurement_pattern, text, re.IGNORECASE
    ):
        if event_hit is not None:
            return (
                "refused: states a measured quantity of the event "
                + "(event " + event_hit + ")"
            )
        pronoun_for_measure = next(
            (
                t
                for t in rules.pronoun_terms
                if re.search(_term_regex(t), text, re.IGNORECASE)
            ),
            None,
        )
        if pronoun_for_measure is not None:
            return (
                "refused: states a measured quantity of the filmed subject "
                + "(pronoun " + pronoun_for_measure + ")"
            )
    for pattern in rules.event_quantity_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "refused: matches an event-quantity pattern (" + pattern + ")"
    return None


def check_query(query: str, rules: BlindnessRules | None = None) -> tuple[bool, str]:
    """Classify a query: ``(allowed, reason)`` with a single-line reason."""
    if not isinstance(query, str) or not query.strip():
        return False, "refused: empty query"
    reason = _refusal_reason(query, _rules(rules))
    if reason is not None:
        return False, reason
    return True, "allowed"


def _as_fact(raw: Any) -> dict[str, str]:
    """Coerce one fact to ``{text, source_url, quote}`` plain strings."""
    if isinstance(raw, dict):
        get = raw.get
    else:
        get = lambda key: getattr(raw, key, "")  # noqa: E731
    return {
        "text": str(get("text") or ""),
        "source_url": str(get("source_url") or ""),
        "quote": str(get("quote") or ""),
    }


def filter_answer(
    facts: list[Any], rules: BlindnessRules | None = None
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Split facts into ``(kept, cut)``; each cut carries fact and reason."""
    compiled = _rules(rules)
    kept: list[dict[str, str]] = []
    cut: list[dict[str, Any]] = []
    for raw in facts:
        fact = _as_fact(raw)
        reason = _refusal_reason(fact["text"] + " " + fact["quote"], compiled)
        if reason is None:
            kept.append(fact)
        else:
            cut.append({"fact": fact, "reason": reason})
    return kept, cut


def _extract_json_object(text: str) -> Any:
    """Return the first top-level JSON object holding a 'facts' list.

    Spark sometimes wraps the schema object in a sentence or two of chatter,
    so a whole-payload ``json.loads`` is only tried first; failing that, each
    ``{`` position is decoded until one yields the expected shape.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("facts"), list):
        return data
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            candidate, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get("facts"), list):
            return candidate
    raise ValueError("search response holds no JSON object with a 'facts' list")


def _parse_facts(payload: str) -> list[dict[str, str]]:
    """Parse the Spark payload into at most MAX_FACTS coerced facts."""
    text = payload.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    data = _extract_json_object(text)
    return [_as_fact(item) for item in data["facts"][:MAX_FACTS]]


def _one_line(value: str) -> str:
    """Collapse whitespace runs to single spaces for compact display."""
    return " ".join(value.split())


@dataclass
class SearchResult:
    """One ``search(query)`` call: verdict, facts, cuts and cost."""

    allowed: bool
    reason: str
    facts: list[dict[str, str]] = field(default_factory=list)
    cut: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: float = 0.0

    def text(self) -> str:
        """Compact agent text (at most 1500 chars) with each source URL."""
        if not self.facts:
            if self.allowed:
                return "search: no facts kept."
            return ("search refused: " + self.reason)[:MAX_TEXT_CHARS]
        lines = []
        for i, fact in enumerate(self.facts, 1):
            quote = _one_line(fact.get("quote", ""))
            lines.append(
                str(i)
                + ". "
                + _one_line(fact.get("text", ""))
                + " (source: "
                + _one_line(fact.get("source_url", ""))
                + ') Quote: "'
                + quote
                + '"'
            )
        out = "\n".join(lines)
        facts = [dict(item) for item in self.facts]
        while len(out) > MAX_TEXT_CHARS and any(len(_one_line(v.get("quote", ""))) > 40 for v in facts):
            longest = max(range(len(facts)), key=lambda k: len(facts[k].get("quote", "")))
            quote = facts[longest].get("quote", "")
            facts[longest]["quote"] = quote[: max(40, len(quote) // 2)] + "..."
            rebuilt = []
            for i, item in enumerate(facts, 1):
                rebuilt.append(
                    str(i)
                    + ". "
                    + _one_line(item.get("text", ""))
                    + " (source: "
                    + _one_line(item.get("source_url", ""))
                    + ') Quote: "'
                    + _one_line(item.get("quote", ""))
                    + '"'
                )
            out = "\n".join(rebuilt)
            lines = rebuilt
        if len(out) > MAX_TEXT_CHARS:
            out = out[: MAX_TEXT_CHARS - 3] + "..."
        return out


class SearchTool:
    """The agent's ``search(query)`` entry point with per-run limit."""

    def __init__(
        self,
        client: Any,
        workspace: str | Path,
        *,
        limit: int = 6,
        rules: BlindnessRules | None = None,
    ) -> None:
        """Bind a Spark client and a run workspace; sets the search budget."""
        self.client = client
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.limit = int(limit)
        self.rules = _rules(rules)
        self.log_path = self.workspace / "search.jsonl"
        self._used = 0

    @property
    def searches_made(self) -> int:
        """API-backed searches made so far against the limit."""
        return self._used

    def check_query(self, query: str) -> tuple[bool, str]:
        """Classify a query without calling the API."""
        return check_query(query, self.rules)

    def filter_answer(
        self, facts: list[Any]
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        """Split facts into ``(kept, cut)`` with the shared rules."""
        return filter_answer(facts, self.rules)

    def _log(
        self,
        query: str,
        allowed: bool,
        reason: str,
        kept_count: int,
        cut_count: int,
        cut_reasons: list[str],
        sources: list[str],
        cost_usd: float,
    ) -> None:
        """Append one JSON line per call to ``workspace/search.jsonl``."""
        record = {
            "query": query,
            "allowed": allowed,
            "decision": "allowed" if allowed else "refused",
            "reason": reason,
            "facts_kept": kept_count,
            "cut": cut_count,
            "cut_reasons": cut_reasons,
            "sources": sources,
            "cost_usd": cost_usd,
        }
        with open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def run(self, query: str) -> SearchResult:
        """Run one agent search: filter, Spark call with web_search, filter."""
        allowed, reason = self.check_query(query)
        if not allowed:
            self._log(query, False, reason, 0, 0, [], [], 0.0)
            return SearchResult(allowed=False, reason=reason, cost_usd=0.0)
        if self._used >= self.limit:
            reason = (
                "refused: search limit reached ("
                + str(self._used)
                + " of "
                + str(self.limit)
                + " used); query was not sent and no API call was made"
            )
            self._log(query, False, reason, 0, 0, [], [], 0.0)
            return SearchResult(allowed=False, reason=reason, cost_usd=0.0)
        response = self.client.respond(
            query,
            instructions=SEARCH_INSTRUCTION,
            web_search=True,
            json_schema=SEARCH_SCHEMA,
            note="search",
        )
        facts = _parse_facts(response.text)
        kept, cut = self.filter_answer(facts)
        self._used += 1
        sources = [item["source_url"] for item in kept]
        self._log(
            query,
            True,
            reason,
            len(kept),
            len(cut),
            [entry["reason"] for entry in cut],
            sources,
            float(response.cost_usd),
        )
        return SearchResult(
            allowed=True,
            reason=reason,
            facts=kept,
            cut=cut,
            cost_usd=float(response.cost_usd),
        )

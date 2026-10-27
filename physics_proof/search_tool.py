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
from .meta_client import raise_if_incomplete

__all__ = [
    "BLINDNESS_PATH",
    "CLASSIFY_KINDS",
    "CLASSIFY_MODEL",
    "CLASSIFY_PROMPT_PATH",
    "CLASSIFY_SCHEMA",
    "MAX_FACTS",
    "MAX_TEXT_CHARS",
    "SEARCH_INSTRUCTION",
    "SEARCH_SCHEMA",
    "SearchResult",
    "SearchTool",
    "check_query",
    "classify",
    "classify_with_cost",
    "filter_answer",
    "load_rules",
]

#: Default blindness word lists and patterns.
BLINDNESS_PATH = REPO_ROOT / "config" / "blindness.json"

#: Fixed instruction for the blindness classifier call (task M4-fix2).
CLASSIFY_PROMPT_PATH = REPO_ROOT / "config" / "prompts" / "blindness.txt"

#: Contributor-tier model for the classifier: cheap, and clips stay ours.
CLASSIFY_MODEL = "muse-spark-1.3-contributor"

#: Allowed classifier verdicts.
CLASSIFY_KINDS = ("reference", "event", "authenticity", "feasibility")

#: Strict schema for the classifier call: one verdict per input text.
CLASSIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,  # mirrors MAX_FACTS below
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(CLASSIFY_KINDS)},
                    "reason": {"type": "string"},
                },
                "required": ["kind", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

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


def _extract_json_object(text: str, key: str = "facts") -> Any:
    """Return the first top-level JSON object holding a ``key`` list.

    Spark sometimes wraps the schema object in a sentence or two of chatter,
    so a whole-payload ``json.loads`` is only tried first; failing that, each
    ``{`` position is decoded until one yields the expected shape.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and isinstance(data.get(key), list):
        return data
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            candidate, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get(key), list):
            return candidate
    raise ValueError("response holds no JSON object with a '" + key + "' list")


def _strip_fences(payload: str) -> str:
    """Remove one Markdown code fence around a JSON payload, if present."""
    text = payload.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


_CLASSIFY_INSTRUCTION: str | None = None


def _classify_instruction(path: str | Path = CLASSIFY_PROMPT_PATH) -> str:
    """Load the fixed classifier instruction (once) from ``blindness.txt``."""
    global _CLASSIFY_INSTRUCTION
    if _CLASSIFY_INSTRUCTION is None:
        text = Path(path).read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError("classifier instruction is empty: " + str(path))
        _CLASSIFY_INSTRUCTION = text
    return _CLASSIFY_INSTRUCTION


def _check_batch(texts: list[str]) -> None:
    """Batches are one query or up to MAX_FACTS facts; anything else is ours."""
    if not 1 <= len(texts) <= MAX_FACTS:
        raise ValueError(
            "classifier batch holds 1..%d texts, got %d" % (MAX_FACTS, len(texts))
        )


def _parse_classify(payload: str, count: int) -> list[dict[str, str] | None]:
    """Parse one classifier payload into per-text verdicts (fail-closed).

    Returns one entry per input text in order; an entry is None when its
    verdict is missing or malformed. A payload with no ``items`` list at
    all yields all None. Never raises on content: callers refuse or cut
    every None entry.
    """
    try:
        data = _extract_json_object(_strip_fences(payload), "items")
        items = data["items"]
    except ValueError:
        return [None] * count
    if not isinstance(items, list):
        return [None] * count
    verdicts: list[dict[str, str] | None] = []
    for index in range(count):
        item = items[index] if index < len(items) else None
        if not isinstance(item, dict):
            verdicts.append(None)
            continue
        kind = item.get("kind")
        reason = item.get("reason")
        if kind not in CLASSIFY_KINDS or not isinstance(reason, str):
            verdicts.append(None)
            continue
        flat = " ".join(reason.split())
        if not flat:
            verdicts.append(None)
            continue
        verdicts.append({"kind": str(kind), "reason": flat})
    return verdicts


def _classify_respond(client: Any, texts: list[str]) -> Any:
    """One classifier Spark call for all texts (contributor tier).

    A cut-off turn is a clear error (fail-closed callers refuse or cut);
    small limits stay, so this surfaces instead of retrying.
    """
    _check_batch(texts)
    user = "TEXTS:\n" + json.dumps(texts, ensure_ascii=False)
    response = client.respond(
        user,
        instructions=_classify_instruction(),
        json_schema=CLASSIFY_SCHEMA,
        model=CLASSIFY_MODEL,
        web_search=False,
        note="blindness-classify",
    )
    raise_if_incomplete(response)
    return response


def classify_with_cost(
    client: Any, texts: list[str]
) -> tuple[list[dict[str, str] | None], float]:
    """Classify every text in one Spark call; return ``(verdicts, cost)``."""
    fixed = [str(item) for item in texts]
    response = _classify_respond(client, fixed)
    return _parse_classify(response.text, len(fixed)), float(response.cost_usd)


def classify(texts: Any, client: Any = None) -> list[dict[str, str]]:
    """Classify texts in one Spark call; ``[{kind, reason}]`` in order.

    Accepts ``classify(texts, client)`` or ``classify(client, texts)``.
    Raises TypeError without a client and ValueError when any verdict is
    missing or malformed; callers fail closed (refuse or cut).
    """
    if client is not None and hasattr(texts, "respond") and isinstance(
        client, (list, tuple)
    ):
        texts, client = client, texts
    if client is None or not hasattr(client, "respond"):
        raise TypeError("classify needs a Spark client with respond()")
    fixed = [str(item) for item in texts]
    verdicts, _ = classify_with_cost(client, fixed)
    bad = [index for index, item in enumerate(verdicts) if item is None]
    if bad:
        raise ValueError("classifier gave no verdict for item(s): " + str(bad))
    return [dict(item) for item in verdicts if item is not None]


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

    def classify(self, texts: list[str]) -> list[dict[str, str]]:
        """Classify texts with one contributor-tier Spark call, in order."""
        return classify(list(texts), self.client)

    def _classify_batch(
        self, texts: list[str]
    ) -> tuple[list[dict[str, str] | None] | None, float, str]:
        """One classifier call: ``(verdicts, cost, error)``; never raises.

        ``verdicts`` is None when the call itself failed; otherwise one
        entry per text with None for each missing or malformed verdict.
        ``error`` is empty on a clean call.
        """
        try:
            response = _classify_respond(self.client, [str(item) for item in texts])
        except Exception as exc:
            detail = _one_line(str(exc))[:160]
            error = "blindness classifier call failed"
            if detail:
                error += ": " + detail
            billed = float(getattr(exc, "cost_usd", 0.0) or 0.0)
            return None, billed, error
        cost = float(getattr(response, "cost_usd", 0.0) or 0.0)
        verdicts = _parse_classify(str(response.text), len(texts))
        if any(item is None for item in verdicts):
            return verdicts, cost, "blindness classifier answer malformed or short"
        return verdicts, cost, ""

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
        """Run one agent search: patterns, classifier, web search, filter.

        Patterns refuse first with no API call; a query that passes them is
        classified (anything but ``reference`` is refused with the
        classifier's reason); returned facts are classified in one batch and
        non-``reference`` facts are cut. Fail closed throughout.
        """
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
        verdicts, query_cost, error = self._classify_batch([query])
        if error or not verdicts or verdicts[0] is None:
            detail = error or "blindness classifier gave no verdict for the query"
            refusal = "refused: " + detail
            self._log(query, False, refusal, 0, 0, [detail], [], query_cost)
            return SearchResult(allowed=False, reason=refusal, cost_usd=query_cost)
        verdict = verdicts[0]
        assert verdict is not None
        if verdict["kind"] != "reference":
            refusal = (
                "refused: not a reference question "
                + "("
                + verdict["kind"]
                + ": "
                + verdict["reason"]
                + ")"
            )
            self._log(query, False, refusal, 0, 0, [refusal], [], query_cost)
            return SearchResult(allowed=False, reason=refusal, cost_usd=query_cost)
        try:
            response = self.client.respond(
                query,
                instructions=SEARCH_INSTRUCTION,
                web_search=True,
                json_schema=SEARCH_SCHEMA,
                note="search",
            )
            raise_if_incomplete(response)
        except Exception as exc:
            detail = _one_line(str(exc))[:160]
            refusal = "refused: search call failed"
            if detail:
                refusal += ": " + detail
            self._log(query, False, refusal, 0, 0, [refusal], [], query_cost)
            return SearchResult(allowed=False, reason=refusal, cost_usd=query_cost)
        search_cost = float(response.cost_usd)
        self._used += 1
        try:
            facts = _parse_facts(response.text)
        except Exception as exc:
            detail = _one_line(str(exc))[:160]
            cut_reason = "cut: search answer holds no usable facts"
            if detail:
                cut_reason += ": " + detail
            total = query_cost + search_cost
            self._log(query, True, reason, 0, 1, [cut_reason], [], total)
            return SearchResult(
                allowed=True,
                reason=reason,
                facts=[],
                cut=[{"fact": {}, "reason": cut_reason}],
                cost_usd=total,
            )
        kept, cut = self.filter_answer(facts)
        facts_cost = 0.0
        if kept:
            fact_verdicts, facts_cost, error = self._classify_batch(
                [item["text"] for item in kept]
            )
            if error or fact_verdicts is None:
                detail = error or "blindness classifier gave no fact verdicts"
                cut = list(cut) + [
                    {"fact": item, "reason": "cut: " + detail} for item in kept
                ]
                kept = []
            else:
                surviving: list[dict[str, str]] = []
                for item, fact_verdict in zip(kept, fact_verdicts):
                    if fact_verdict is None:
                        cut.append(
                            {
                                "fact": item,
                                "reason": "cut: blindness classifier gave no verdict",
                            }
                        )
                    elif fact_verdict["kind"] != "reference":
                        cut.append(
                            {
                                "fact": item,
                                "reason": (
                                    "cut: not a reference fact "
                                    + "("
                                    + fact_verdict["kind"]
                                    + ": "
                                    + fact_verdict["reason"]
                                    + ")"
                                ),
                            }
                        )
                    else:
                        surviving.append(item)
                kept = surviving
        total = query_cost + search_cost + facts_cost
        sources = [item["source_url"] for item in kept]
        self._log(
            query,
            True,
            reason,
            len(kept),
            len(cut),
            [entry["reason"] for entry in cut],
            sources,
            total,
        )
        return SearchResult(
            allowed=True,
            reason=reason,
            facts=kept,
            cut=cut,
            cost_usd=total,
        )

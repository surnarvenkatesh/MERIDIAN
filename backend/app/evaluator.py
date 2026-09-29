"""
Evaluation layer.

Two responsibilities:
1. Score each retrieved Source on credibility (is this a trustworthy
   publisher/domain, does it look primary vs. derivative) and relevance
   (does it actually address the query) — via the LLM, with a fast
   heuristic fallback.
2. Score the final synthesized answer for groundedness — how well its
   claims are supported by the retrieved sources — which becomes part
   of the reward signal fed to the RL policy.
"""
from __future__ import annotations

import re

from .llm import llm_client
from .models import Source

_REPUTABLE_TLD_HINTS = (".gov", ".edu", "nature.", "arxiv.", "acm.", "ieee.", "reuters.", "apnews.")
_LOW_TRUST_HINTS = ("blogspot", "medium.com", "random-blog", "forum", "pinterest")


def evaluate_source(query: str, source: Source) -> Source:
    """Attach credibility_score, relevance_score, rationale to a Source."""
    system = (
        "You evaluate web sources for a research assistant. Judge credibility (publisher "
        "reputation, evidence of editorial rigor, primary vs derivative) and relevance "
        "(does the content address the query) independently, each 0.0-1.0."
    )
    prompt = f"Query: {query}\nSource title: {source.title}\nDomain: {source.domain}\nSnippet: {source.snippet}"
    result = llm_client.complete_json(
        system,
        prompt,
        schema_hint='{"credibility_score": float, "relevance_score": float, "rationale": string}',
    )
    cred = result.get("credibility_score")
    rel = result.get("relevance_score")
    rationale = result.get("rationale")

    if cred is None or rel is None:
        cred, rel, rationale = _heuristic_score(query, source)

    source.credibility_score = _clamp(cred)
    source.relevance_score = _clamp(rel)
    source.rationale = rationale or "Heuristic domain/keyword based scoring."
    return source


def _heuristic_score(query: str, source: Source) -> tuple[float, float, str]:
    domain = source.domain.lower()
    cred = 0.5
    if any(h in domain for h in _REPUTABLE_TLD_HINTS):
        cred = 0.85
    elif any(h in domain for h in _LOW_TRUST_HINTS):
        cred = 0.25

    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    text_terms = set(re.findall(r"[a-z0-9]+", (source.title + " " + source.snippet).lower()))
    overlap = len(query_terms & text_terms) / max(len(query_terms), 1)
    rel = min(1.0, 0.3 + overlap)

    return cred, rel, f"Heuristic: domain reputation ~{cred:.2f}, keyword overlap ~{overlap:.2f}."


def evaluate_groundedness(answer: str, sources: list[Source]) -> float:
    """Rough groundedness proxy: fraction of answer sentences that share
    meaningful vocabulary with at least one retrieved source. This feeds
    the RL reward signal; it is a proxy, not a hallucination detector."""
    if not sources:
        return 0.3
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    if not sentences:
        return 0.0
    source_vocab = set()
    for src in sources:
        source_vocab |= set(re.findall(r"[a-z0-9]{4,}", (src.title + " " + src.snippet).lower()))

    supported = 0
    for sent in sentences:
        sent_vocab = set(re.findall(r"[a-z0-9]{4,}", sent.lower()))
        if sent_vocab & source_vocab:
            supported += 1
    return round(supported / len(sentences), 3)


def _clamp(x: float) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.5

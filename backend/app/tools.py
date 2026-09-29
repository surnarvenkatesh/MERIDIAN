"""
External tools available to the agent: web search and page fetch.

Uses Exa (neural search API built for LLM/agent retrieval) when
EXA_API_KEY is set. Falls back to a deterministic offline mock corpus
otherwise, so the agent's control flow, RAG pipeline, and RL policy can
all be exercised without any external account.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

from .config import settings
from .models import Source

logger = logging.getLogger("research_agent.tools")

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

_EXA_HEADERS = {"x-api-key": settings.exa_api_key or "", "Content-Type": "application/json"}


def web_search(query: str, max_results: int = 5) -> list[Source]:
    """Search the web for a query, returning ranked Source stubs."""
    if settings.search_is_live and httpx is not None:
        try:
            return _exa_search(query, max_results)
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Live Exa search failed (%s), falling back to mock corpus", exc)
    return _mock_search(query, max_results)


def fetch_page(url: str) -> str:
    """Fetch and lightly clean the text content of a page."""
    if settings.search_is_live and httpx is not None and url.startswith("http"):
        try:
            return _exa_contents(url)
        except Exception as exc:  # pragma: no cover
            logger.warning("Live Exa fetch failed for %s: %s", url, exc)
    return _mock_page_body(url)


# ---------------------------------------------------------------------
# Live provider: Exa
# ---------------------------------------------------------------------
def _exa_search(query: str, max_results: int) -> list[Source]:
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            "https://api.exa.ai/search",
            headers=_EXA_HEADERS,
            json={
                "query": query,
                "type": "auto",
                "numResults": max_results,
                "contents": {"text": {"maxCharacters": 600}},
            },
        )
        resp.raise_for_status()
        data = resp.json()
    sources = []
    for r in data.get("results", [])[:max_results]:
        url = r.get("url", "")
        sources.append(
            Source(
                title=r.get("title") or url,
                url=url,
                snippet=(r.get("text") or "")[:600],
                published=r.get("publishedDate"),
                domain=_domain(url),
            )
        )
    return sources


def _exa_contents(url: str) -> str:
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            "https://api.exa.ai/contents",
            headers=_EXA_HEADERS,
            json={"urls": [url], "text": True},
        )
        resp.raise_for_status()
        data = resp.json()
    results = data.get("results", [])
    if results:
        return (results[0].get("text") or "")[:20000]
    return ""


# ---------------------------------------------------------------------
# Offline mock corpus — deterministic, seeded by query hash, so repeated
# runs of the same query in demo mode are stable (useful for the RL
# policy to actually learn something across "episodes").
# ---------------------------------------------------------------------
_MOCK_DOMAINS = [
    ("arxiv.org", 0.9),
    ("nature.com", 0.95),
    ("wikipedia.org", 0.75),
    ("medium.com", 0.35),
    ("github.com", 0.7),
    ("reuters.com", 0.85),
    ("a-random-blog.net", 0.2),
    ("acm.org", 0.9),
]


def _mock_search(query: str, max_results: int) -> list[Source]:
    seed = int(hashlib.sha256(query.encode()).hexdigest(), 16)
    sources = []
    for i in range(max_results):
        domain, base_cred = _MOCK_DOMAINS[(seed + i) % len(_MOCK_DOMAINS)]
        days_ago = (seed >> (i + 1)) % 900
        published = (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        title = f"{query.strip().capitalize()} — perspective {i + 1} from {domain}"
        sources.append(
            Source(
                title=title,
                url=f"https://{domain}/articles/{abs(seed + i) % 99999}",
                snippet=(
                    f"An overview discussing {query.strip()}, covering methodology, "
                    f"key findings, and open questions relevant to the topic. "
                    f"Source reliability tends to track domain reputation ({domain})."
                ),
                published=published,
                domain=domain,
            )
        )
    return sources


def _mock_page_body(url: str) -> str:
    seed = int(hashlib.sha256(url.encode()).hexdigest(), 16)
    domain = _domain(url)
    paragraphs = [
        f"This page ({domain}) presents an analysis relevant to the research query.",
        "The methodology section describes how data was collected and the limitations "
        "of the approach, noting that findings should be interpreted with appropriate caveats.",
        "Key results indicate a moderate-to-strong pattern consistent with prior work in the "
        "area, though sample size and scope constrain generalizability.",
        "The discussion contrasts these findings against alternative explanations and flags "
        "two open questions for future research.",
    ]
    if seed % 2 == 0:
        paragraphs.reverse()
    return " ".join(paragraphs)


def _domain(url: str) -> str:
    try:
        return url.split("//", 1)[-1].split("/", 1)[0].replace("www.", "")
    except Exception:
        return url

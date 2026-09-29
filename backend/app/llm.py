"""
Thin LLM client. Groq (free, no-credit-card, OpenAI-compatible endpoint)
if GROQ_API_KEY is set, otherwise a deterministic offline mock so the
whole app — agent loop, RAG, RL policy, frontend — still runs.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from .config import settings

logger = logging.getLogger("research_agent.llm")

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None


class LLMClient:
    """Synchronous LLM facade used by the agent, RAG layer, and evaluator."""

    def __init__(self) -> None:
        self.live = settings.llm_is_live and httpx is not None

    # ------------------------------------------------------------------
    def complete(self, system: str, prompt: str, max_tokens: int | None = None) -> str:
        """Free-form text completion."""
        if self.live:
            try:
                return self._groq_complete(system, prompt, max_tokens)
            except Exception as exc:  # pragma: no cover - network dependent
                logger.warning("Groq call failed (%s), falling back to mock", exc)
        return self._mock_complete(system, prompt)

    # ------------------------------------------------------------------
    def _groq_complete(self, system: str, prompt: str, max_tokens: int | None) -> str:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": settings.groq_model,
                "max_tokens": max_tokens or settings.llm_max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    # ------------------------------------------------------------------
    def complete_json(self, system: str, prompt: str, schema_hint: str) -> dict[str, Any]:
        """Ask the model for strict JSON and parse it defensively."""
        full_system = (
            f"{system}\n\nRespond with ONLY valid JSON matching this shape, no prose, "
            f"no markdown fences:\n{schema_hint}"
        )
        raw = self.complete(full_system, prompt)
        return self._safe_json(raw)

    # ------------------------------------------------------------------
    @staticmethod
    def _safe_json(raw: str) -> dict[str, Any]:
        cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            logger.warning("Could not parse LLM JSON, returning empty object. Raw: %.200s", raw)
            return {}

    # ------------------------------------------------------------------
    # Deterministic offline mock — keeps the whole pipeline runnable
    # without any API key, useful for local dev, CI, and demos.
    # ------------------------------------------------------------------
    def _mock_complete(self, system: str, prompt: str) -> str:
        lower_system = system.lower()
        if "credibility" in lower_system or "evaluate" in lower_system:
            return json.dumps(
                {
                    "credibility_score": 0.72,
                    "relevance_score": 0.68,
                    "rationale": "Domain has an editorial track record; content directly addresses the query "
                    "but relies on a single primary source.",
                }
            )
        if "plan" in lower_system or "next action" in lower_system:
            return json.dumps(
                {
                    "thought": "I have partial coverage of the topic; one more targeted search "
                    "on recent developments would fill the gap before synthesizing.",
                    "action": "search_web",
                    "action_input": {"query": _mock_followup_query(prompt)},
                }
            )
        if "synthesize" in lower_system or "final answer" in lower_system:
            return (
                "Based on the gathered sources, the current consensus is that this topic has "
                "several well-supported dimensions along with some open questions. Key findings "
                "converge across independent sources, while a minority view highlights nuance "
                "worth flagging.\n\n[Demo mode: add a free GROQ_API_KEY for grounded, "
                "source-specific synthesis.]"
            )
        return "[Demo mode response — add a free GROQ_API_KEY for live reasoning.]"


def _mock_followup_query(prompt: str) -> str:
    first_line = prompt.strip().splitlines()[0][:60]
    return f"{first_line} latest developments"


llm_client = LLMClient()

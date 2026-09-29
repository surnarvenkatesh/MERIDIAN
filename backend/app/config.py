"""
Central configuration for the research agent backend.

Everything has a safe default so the service boots in "demo mode" (mocked
LLM + mocked web search) with zero configuration, and upgrades to Groq
the moment GROQ_API_KEY is set.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- LLM provider: Groq only (free, no credit card required) ---------
    groq_api_key: str | None = field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    llm_max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "2048")))

    # --- Web search provider (Tavily is used because it returns clean,
    # citation-friendly snippets; falls back to a deterministic offline
    # mock corpus when no key is configured). --------------------------
    exa_api_key: str | None = field(default_factory=lambda: os.getenv("EXA_API_KEY"))

    # --- Vector store -------------------------------------------------
    chroma_persist_dir: str = field(default_factory=lambda: os.getenv("CHROMA_DIR", "./data/chroma"))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )

    # --- Relational store (sessions, feedback, RL replay log) ----------
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/agent.db"))

    # --- RL policy ------------------------------------------------------
    rl_policy_path: str = field(default_factory=lambda: os.getenv("RL_POLICY_PATH", "./data/rl_policy.json"))
    rl_learning_rate: float = field(default_factory=lambda: float(os.getenv("RL_LR", "0.05")))
    rl_discount: float = field(default_factory=lambda: float(os.getenv("RL_GAMMA", "0.95")))
    rl_entropy_coef: float = field(default_factory=lambda: float(os.getenv("RL_ENTROPY_COEF", "0.01")))

    # --- Agent loop -----------------------------------------------------
    max_agent_steps: int = field(default_factory=lambda: int(os.getenv("MAX_AGENT_STEPS", "8")))
    max_sources_per_query: int = field(default_factory=lambda: int(os.getenv("MAX_SOURCES", "5")))

    # --- Demo / offline mode --------------------------------------------
    force_mock_llm: bool = field(default_factory=lambda: _bool("FORCE_MOCK_LLM", False))

    @property
    def llm_is_live(self) -> bool:
        return bool(self.groq_api_key) and not self.force_mock_llm

    @property
    def search_is_live(self) -> bool:
        return bool(self.exa_api_key)


settings = Settings()

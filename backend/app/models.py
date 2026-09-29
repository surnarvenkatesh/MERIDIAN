"""Pydantic schemas shared across the API, agent loop, and RL policy."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ActionType(str, Enum):
    SEARCH_WEB = "search_web"
    RETRIEVE_MEMORY = "retrieve_memory"
    FETCH_PAGE = "fetch_page"
    EVALUATE_SOURCES = "evaluate_sources"
    REFLECT = "reflect"
    SYNTHESIZE = "synthesize"
    STOP = "stop"


class Source(BaseModel):
    id: str = Field(default_factory=lambda: _id("src"))
    title: str
    url: str
    snippet: str
    published: str | None = None
    domain: str = ""
    credibility_score: float | None = None  # 0..1, filled by evaluator
    relevance_score: float | None = None  # 0..1, filled by evaluator
    rationale: str | None = None


class TraceStep(BaseModel):
    id: str = Field(default_factory=lambda: _id("step"))
    index: int
    action: ActionType
    thought: str
    input: dict[str, Any] = Field(default_factory=dict)
    output_summary: str = ""
    sources: list[Source] = Field(default_factory=list)
    reward: float | None = None
    duration_ms: int = 0
    timestamp: float = Field(default_factory=time.time)


class UploadedDocument(BaseModel):
    filename: str
    text: str




class ConversationTurn(BaseModel):
    query: str
    answer: str


class ResearchRequest(BaseModel):
    query: str
    session_id: str | None = None
    max_steps: int | None = None
    max_sources: int | None = None
    uploaded_documents: list[UploadedDocument] = Field(default_factory=list)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    uploaded_documents: list[UploadedDocument] = Field(default_factory=list)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class ResearchResult(BaseModel):
    session_id: str
    query: str
    answer: str
    confidence: float
    steps: list[TraceStep]
    sources: list[Source]
    total_reward: float
    elapsed_ms: int


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AuthResponse(BaseModel):
    token: str
    email: str


class RenameSessionRequest(BaseModel):
    title: str


class FeedbackRequest(BaseModel):
    session_id: str
    rating: Literal["helpful", "not_helpful"]
    comment: str | None = None


class PolicySnapshot(BaseModel):
    weights: dict[str, list[float]]
    action_names: list[str]
    episodes_trained: int
    running_avg_reward: float
    reward_history: list[float]
    action_distribution: dict[str, int]
    updated_at: float

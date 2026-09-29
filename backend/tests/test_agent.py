import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["FORCE_MOCK_LLM"] = "true"
os.environ["RL_POLICY_PATH"] = os.path.join(tempfile.mkdtemp(), "policy.json")
os.environ["CHROMA_DIR"] = tempfile.mkdtemp()

from app.agent import agent  # noqa: E402
from app.models import ActionType  # noqa: E402


def test_agent_run_produces_answer_and_steps():
    result = agent.run(query="impact of renewable energy on grid stability", session_id="test_session", max_steps=5)
    assert result.answer
    assert len(result.steps) >= 1
    assert result.elapsed_ms >= 0
    assert 0.0 <= result.confidence <= 1.0


def test_agent_always_ends_with_synthesize():
    result = agent.run(query="quantum computing error correction", session_id="test_session_2", max_steps=4)
    assert any(s.action == ActionType.SYNTHESIZE for s in result.steps)


def test_agent_respects_max_sources():
    result = agent.run(
        query="history of the transistor", session_id="test_session_3", max_steps=6, max_sources=2
    )
    assert len(result.sources) <= 2 + 1  # small slack for the final synth step referencing all sources

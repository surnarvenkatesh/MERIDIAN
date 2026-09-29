import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["FORCE_MOCK_LLM"] = "true"

from app.evaluator import evaluate_groundedness, evaluate_source  # noqa: E402
from app.models import Source  # noqa: E402


def test_evaluate_source_fills_scores():
    src = Source(title="A study on X", url="https://nature.com/articles/1", snippet="Discusses X in depth.", domain="nature.com")
    scored = evaluate_source("X", src)
    assert scored.credibility_score is not None
    assert scored.relevance_score is not None
    assert 0.0 <= scored.credibility_score <= 1.0


def test_groundedness_zero_sources():
    assert evaluate_groundedness("Some answer.", []) == 0.3


def test_groundedness_higher_with_overlap():
    sources = [
        Source(title="Photosynthesis basics", url="https://a.com", snippet="chlorophyll sunlight energy conversion", domain="a.com")
    ]
    grounded_answer = "Photosynthesis relies on chlorophyll to convert sunlight into energy."
    ungrounded_answer = "Bananas are a good source of potassium."
    assert evaluate_groundedness(grounded_answer, sources) >= evaluate_groundedness(ungrounded_answer, sources)

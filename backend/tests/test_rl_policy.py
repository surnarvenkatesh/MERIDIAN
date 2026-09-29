import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["RL_POLICY_PATH"] = os.path.join(tempfile.mkdtemp(), "policy.json")
os.environ["FORCE_MOCK_LLM"] = "true"

from app.rl_policy import Episode, PolicyGradientAgent, Transition, build_features, compute_reward  # noqa: E402


def test_softmax_sums_to_one():
    agent = PolicyGradientAgent()
    feats = build_features(0, 8, 0, 5, 0.0, 0.0, False, False, 0)
    probs = agent._softmax(feats)
    assert abs(sum(probs) - 1.0) < 1e-6
    assert all(p >= 0 for p in probs)


def test_policy_learns_to_prefer_rewarded_action():
    agent = PolicyGradientAgent()
    feats = [1.0, 0.5, 0.5, 0.5, 0.5, 0.0, 0.0, 0.5]
    target_action = 0  # SEARCH_WEB index

    # Repeatedly reward the same action for the same state and confirm its
    # probability mass increases — this is the core learning-signal check.
    initial_probs = agent._softmax(feats)
    for _ in range(60):
        ep = Episode(
            transitions=[
                Transition(features=feats, action_idx=target_action, action_probs=agent._softmax(feats), reward=1.0)
            ]
        )
        agent.update(ep)
    final_probs = agent._softmax(feats)
    assert final_probs[target_action] > initial_probs[target_action]


def test_compute_reward_penalizes_excess_steps():
    low_step_reward = compute_reward(
        new_sources_added=1, avg_credibility_delta=0.1, groundedness=0.5, steps_used=2, max_steps=8
    )
    high_step_reward = compute_reward(
        new_sources_added=1, avg_credibility_delta=0.1, groundedness=0.5, steps_used=8, max_steps=8
    )
    assert high_step_reward < low_step_reward


def test_feedback_blend_direction():
    positive = compute_reward(
        new_sources_added=0, avg_credibility_delta=0, groundedness=0, steps_used=1, max_steps=1, user_feedback=1.0
    )
    negative = compute_reward(
        new_sources_added=0, avg_credibility_delta=0, groundedness=0, steps_used=1, max_steps=1, user_feedback=-1.0
    )
    assert positive > negative


def test_snapshot_serializable():
    agent = PolicyGradientAgent()
    snap = agent.snapshot()
    assert snap.action_names
    assert len(snap.weights) == len(snap.action_names)

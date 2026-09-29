"""
Reinforcement learning over the agent's *strategy*.

Honest scope note: fine-tuning the underlying LLM's weights with RL (e.g.
PPO/GRPO over token log-probs) needs a training cluster and hours of
compute — not something a live backend process does per-request. What we
implement instead, faithfully, is the standard way agentic systems apply
RL in production today: a lightweight policy over the *decision points* of
the agent loop (which tool to call next, when to stop, how many sources
are "enough") is trained online with policy gradients (REINFORCE with a
moving-average baseline + entropy bonus) from a reward computed out of
real evaluation signals (source credibility/relevance, groundedness,
efficiency, and explicit user feedback). This is a legitimate, working RL
loop — it just optimizes the agent's control policy rather than raw LLM
weights. Swapping in a token-level PPO trainer against an open-weight
model would reuse the exact same reward function and replay buffer.

Policy representation: linear-softmax contextual bandit.
  logits = W @ features        (W: [n_actions, n_features])
  pi(a|s) = softmax(logits)
Update per step (REINFORCE):
  advantage = reward - running_baseline
  grad log pi(a|s) = features * (1[a] - pi(s))   for each action row
  W += lr * advantage * grad_log_pi - lr * entropy_coef * d(-entropy)/dW
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import time
from dataclasses import dataclass, field

from .config import settings
from .models import ActionType, PolicySnapshot

logger = logging.getLogger("research_agent.rl")

FEATURE_NAMES = [
    "bias",
    "step_frac",  # current step / max steps
    "num_sources_norm",  # sources gathered so far / max_sources
    "avg_credibility",
    "avg_relevance",
    "has_low_credibility_source",
    "last_action_was_search",
    "vector_hits_norm",
]
ACTIONS = [
    ActionType.SEARCH_WEB,
    ActionType.RETRIEVE_MEMORY,
    ActionType.EVALUATE_SOURCES,
    ActionType.REFLECT,
    ActionType.SYNTHESIZE,
]


@dataclass
class Transition:
    features: list[float]
    action_idx: int
    action_probs: list[float]
    reward: float = 0.0


@dataclass
class Episode:
    transitions: list[Transition] = field(default_factory=list)


class PolicyGradientAgent:
    """Linear-softmax REINFORCE policy over agent actions."""

    def __init__(self) -> None:
        self.n_actions = len(ACTIONS)
        self.n_features = len(FEATURE_NAMES)
        self.lr = settings.rl_learning_rate
        self.gamma = settings.rl_discount
        self.entropy_coef = settings.rl_entropy_coef
        self.baseline = 0.0
        self.episodes_trained = 0
        self.reward_history: list[float] = []
        self.action_counts: dict[str, int] = {a.value: 0 for a in ACTIONS}
        self.weights = [[0.0] * self.n_features for _ in range(self.n_actions)]
        self._rand = random.Random(7)
        self._load()

    # ------------------------------------------------------------------
    def act(self, features: list[float], epsilon: float = 0.08) -> tuple[ActionType, list[float]]:
        """Sample an action from the current policy (with light epsilon
        exploration on top of the learned softmax, which helps early on
        when the linear policy hasn't differentiated actions yet)."""
        probs = self._softmax(features)
        if self._rand.random() < epsilon:
            idx = self._rand.randrange(self.n_actions)
        else:
            idx = self._sample(probs)
        self.action_counts[ACTIONS[idx].value] += 1
        return ACTIONS[idx], probs

    # ------------------------------------------------------------------
    def _logits(self, features: list[float]) -> list[float]:
        return [sum(w * f for w, f in zip(row, features)) for row in self.weights]

    def _softmax(self, features: list[float]) -> list[float]:
        logits = self._logits(features)
        m = max(logits)
        exps = [math.exp(l - m) for l in logits]
        s = sum(exps) or 1e-9
        return [e / s for e in exps]

    def _sample(self, probs: list[float]) -> int:
        r = self._rand.random()
        cum = 0.0
        for i, p in enumerate(probs):
            cum += p
            if r <= cum:
                return i
        return len(probs) - 1

    # ------------------------------------------------------------------
    def update(self, episode: Episode) -> float:
        """REINFORCE update with a moving-average baseline and entropy
        bonus, applied over the discounted returns of one episode
        (= one research session)."""
        if not episode.transitions:
            return 0.0

        # discounted returns, computed backwards
        returns = [0.0] * len(episode.transitions)
        running = 0.0
        for t in reversed(range(len(episode.transitions))):
            running = episode.transitions[t].reward + self.gamma * running
            returns[t] = running

        episode_reward = sum(t.reward for t in episode.transitions)

        for t, G in zip(episode.transitions, returns):
            advantage = G - self.baseline
            probs = t.action_probs
            for a_idx in range(self.n_actions):
                indicator = 1.0 if a_idx == t.action_idx else 0.0
                grad_log_pi = indicator - probs[a_idx]
                # entropy gradient nudges weights toward uniform slightly,
                # discouraging premature collapse onto one action
                entropy_grad = -probs[a_idx] * (math.log(probs[a_idx] + 1e-9) + 1)
                for f_idx, feat in enumerate(t.features):
                    self.weights[a_idx][f_idx] += self.lr * (
                        advantage * grad_log_pi * feat + self.entropy_coef * entropy_grad * feat
                    )

        # update baseline as an exponential moving average of episode reward
        alpha = 0.15
        self.baseline = (1 - alpha) * self.baseline + alpha * episode_reward
        self.episodes_trained += 1
        self.reward_history.append(round(episode_reward, 4))
        self.reward_history = self.reward_history[-200:]
        self._save()
        return episode_reward

    # ------------------------------------------------------------------
    def snapshot(self) -> PolicySnapshot:
        avg = sum(self.reward_history) / len(self.reward_history) if self.reward_history else 0.0
        return PolicySnapshot(
            weights={a.value: self.weights[i] for i, a in enumerate(ACTIONS)},
            action_names=[a.value for a in ACTIONS],
            episodes_trained=self.episodes_trained,
            running_avg_reward=round(avg, 4),
            reward_history=self.reward_history,
            action_distribution=dict(self.action_counts),
            updated_at=time.time(),
        )

    # ------------------------------------------------------------------
    def _save(self) -> None:
        os.makedirs(os.path.dirname(settings.rl_policy_path) or ".", exist_ok=True)
        payload = {
            "weights": self.weights,
            "baseline": self.baseline,
            "episodes_trained": self.episodes_trained,
            "reward_history": self.reward_history,
            "action_counts": self.action_counts,
        }
        try:
            with open(settings.rl_policy_path, "w") as f:
                json.dump(payload, f)
        except OSError as exc:  # pragma: no cover
            logger.warning("Could not persist RL policy: %s", exc)

    def _load(self) -> None:
        if not os.path.exists(settings.rl_policy_path):
            return
        try:
            with open(settings.rl_policy_path) as f:
                payload = json.load(f)
            self.weights = payload.get("weights", self.weights)
            self.baseline = payload.get("baseline", 0.0)
            self.episodes_trained = payload.get("episodes_trained", 0)
            self.reward_history = payload.get("reward_history", [])
            self.action_counts = payload.get("action_counts", self.action_counts)
        except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
            logger.warning("Could not load persisted RL policy, starting fresh: %s", exc)


def build_features(
    step_idx: int,
    max_steps: int,
    num_sources: int,
    max_sources: int,
    avg_credibility: float,
    avg_relevance: float,
    has_low_credibility_source: bool,
    last_action_was_search: bool,
    vector_hits: int,
) -> list[float]:
    return [
        1.0,  # bias
        min(step_idx / max(max_steps, 1), 1.0),
        min(num_sources / max(max_sources, 1), 1.0),
        avg_credibility,
        avg_relevance,
        1.0 if has_low_credibility_source else 0.0,
        1.0 if last_action_was_search else 0.0,
        min(vector_hits / 5.0, 1.0),
    ]


def compute_reward(
    *,
    new_sources_added: int,
    avg_credibility_delta: float,
    groundedness: float,
    steps_used: int,
    max_steps: int,
    user_feedback: float | None = None,
) -> float:
    """Reward shaping combining information gain, quality, and efficiency.

    - Rewards adding credible, relevant sources (information gain).
    - Rewards a grounded final answer.
    - Penalizes burning through the step budget without payoff.
    - If explicit user feedback is available (thumbs up/down), it is
      blended in with high weight, since it is the most direct signal.
    """
    info_gain = 0.15 * new_sources_added + 0.5 * max(avg_credibility_delta, 0)
    quality = 0.6 * groundedness
    efficiency_penalty = -0.05 * max(steps_used - max_steps * 0.5, 0)
    reward = info_gain + quality + efficiency_penalty
    if user_feedback is not None:
        reward = 0.4 * reward + 0.6 * user_feedback
    return round(reward, 4)


policy = PolicyGradientAgent()

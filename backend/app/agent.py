"""
Autonomous research agent orchestrator.

Runs a bounded ReAct-style loop where, at every step, an RL-trained policy
(app.rl_policy) chooses the next action given the current research state,
the action is executed (web search, RAG memory retrieval, source
evaluation, reflection, or synthesis), and the resulting information gain
/ quality signals are turned into a reward that trains the policy at the
end of the episode. This is the seam where "agentic workflow" and
"reinforcement learning" meet: the LLM does the reasoning inside each
action, the RL policy decides the *sequence* of actions.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from . import tools
from .config import settings
from .evaluator import evaluate_groundedness, evaluate_source
from .llm import llm_client
from .models import ActionType, ConversationTurn, ResearchResult, Source, TraceStep, UploadedDocument
from .rl_policy import Episode, Transition, build_features, compute_reward, policy
from .vectorstore import index_sources, vector_store

logger = logging.getLogger("research_agent.agent")

ProgressCallback = Callable[[TraceStep], None]


class ResearchState:
    def __init__(self, query: str, max_steps: int, max_sources: int, conversation_history: list[ConversationTurn] | None = None) -> None:
        self.query = query
        self.max_steps = max_steps
        self.conversation_history: list[ConversationTurn] = conversation_history or []
        self.max_sources = max_sources
        self.sources: list[Source] = []
        self.page_bodies: dict[str, str] = {}
        self.notes: list[str] = []
        self.last_action_was_search = False
        self.vector_hits_last = 0
        self.consecutive_searches = 0
        self.last_action = None
        self.last_source_count = 0
        self.last_scored_count = 0

    @property
    def avg_credibility(self) -> float:
        scored = [s.credibility_score for s in self.sources if s.credibility_score is not None]
        return sum(scored) / len(scored) if scored else 0.0

    @property
    def avg_relevance(self) -> float:
        scored = [s.relevance_score for s in self.sources if s.relevance_score is not None]
        return sum(scored) / len(scored) if scored else 0.0

    @property
    def has_low_credibility_source(self) -> bool:
        return any((s.credibility_score or 1.0) < 0.4 for s in self.sources)

    def features(self, step_idx: int) -> list[float]:
        return build_features(
            step_idx=step_idx,
            max_steps=self.max_steps,
            num_sources=len(self.sources),
            max_sources=self.max_sources,
            avg_credibility=self.avg_credibility,
            avg_relevance=self.avg_relevance,
            has_low_credibility_source=self.has_low_credibility_source,
            last_action_was_search=self.last_action_was_search,
            vector_hits=self.vector_hits_last,
        )


class ResearchAgent:
    def run(
        self,
        query: str,
        session_id: str,
        max_steps: int | None = None,
        max_sources: int | None = None,
        on_step: ProgressCallback | None = None,
        uploaded_documents: list[UploadedDocument] | None = None,
        conversation_history: list[ConversationTurn] | None = None,
    ) -> ResearchResult:
        start = time.time()
        max_steps = max_steps or settings.max_agent_steps
        max_sources = max_sources or settings.max_sources_per_query
        effective_query = query
        if conversation_history:
            effective_query = self._expand_query(query, conversation_history)

        state = ResearchState(effective_query, max_steps, max_sources, conversation_history)

        if uploaded_documents:
            # User-provided documents are trusted, pre-scored sources: they
            # skip web search entirely and are marked maximally credible and
            # relevant, since the user explicitly chose to hand them to the
            # agent as research material.
            for doc in uploaded_documents:
                src = Source(
                    title=doc.filename,
                    url=f"upload://{doc.filename}",
                    snippet=doc.text[:600],
                    domain="uploaded file",
                    credibility_score=1.0,
                    relevance_score=1.0,
                    rationale="User-provided document, trusted by default.",
                )
                state.sources.append(src)
                state.page_bodies[src.url] = doc.text
            index_sources(state.sources, state.page_bodies)
        episode = Episode()
        steps: list[TraceStep] = []

        for step_idx in range(max_steps):
            prev_avg_cred = state.avg_credibility
            prev_source_count = len(state.sources)

            features = state.features(step_idx)
            action, probs = policy.act(features)
            if action == ActionType.SEARCH_WEB and state.consecutive_searches >= 2:
                # Never allow 3+ identical searches in a row - by this point
                # there are almost always unscored sources sitting idle.
                action = ActionType.EVALUATE_SOURCES if any(
                    s.credibility_score is None for s in state.sources
                ) else ActionType.REFLECT
            if action == ActionType.SYNTHESIZE and not state.sources:
                # Intercept BEFORE executing, not after: running a synthesis
                # with zero sources still costs a real LLM call and leaves a
                # bogus, ungrounded answer sitting in the trace that could
                # later get picked as "the final answer" if the step budget
                # runs out before a real synthesis happens. Redirect to a
                # search instead of ever letting the wasted call happen.
                action = ActionType.SEARCH_WEB
            state.consecutive_searches = state.consecutive_searches + 1 if action == ActionType.SEARCH_WEB else 0
            # General no-progress-repeat guard: if the same action is
            # about to run again with nothing having changed since last
            # time (no new sources, no newly-scored sources), it would be
            # wasted work - e.g. Recall-Recall or Reflect-Reflect with
            # nothing new to recall or reflect on. Redirect instead.
            current_scored = sum(1 for s in state.sources if s.credibility_score is not None)
            no_progress = (
                action == state.last_action
                and len(state.sources) == state.last_source_count
                and current_scored == state.last_scored_count
                and action in (ActionType.RETRIEVE_MEMORY, ActionType.REFLECT)
            )
            if no_progress:
                action = ActionType.SEARCH_WEB if not state.sources else ActionType.SYNTHESIZE
            state.last_action = action
            state.last_source_count = len(state.sources)
            state.last_scored_count = current_scored

            if action == ActionType.SYNTHESIZE and any(
                s.credibility_score is None for s in state.sources
            ):
                # Guarantee: never let synthesis run against unscored
                # sources. Made visible in the trace rather than hidden.
                eval_t0 = time.time()
                eval_trace = self._evaluate_sources(state, step_idx)
                eval_trace.duration_ms = int((time.time() - eval_t0) * 1000)
                steps.append(eval_trace)
                if on_step:
                    on_step(eval_trace)
                episode.transitions.append(
                    Transition(
                        features=features,
                        action_idx=_action_idx(ActionType.EVALUATE_SOURCES),
                        action_probs=probs,
                        reward=0.0,
                    )
                )
            t0 = time.time()
            trace = self._execute(action, state, step_idx, probs)
            trace.duration_ms = int((time.time() - t0) * 1000)
            steps.append(trace)
            if on_step:
                on_step(trace)

            groundedness = 0.0
            if action == ActionType.SYNTHESIZE:
                groundedness = evaluate_groundedness(trace.output_summary, state.sources)

            reward = compute_reward(
                new_sources_added=len(state.sources) - prev_source_count,
                avg_credibility_delta=state.avg_credibility - prev_avg_cred,
                groundedness=groundedness,
                steps_used=step_idx + 1,
                max_steps=max_steps,
            )
            trace.reward = reward
            episode.transitions.append(
                Transition(features=features, action_idx=_action_idx(action), action_probs=probs, reward=reward)
            )

            state.last_action_was_search = action == ActionType.SEARCH_WEB
            if action == ActionType.STOP or action == ActionType.SYNTHESIZE:
                break

        # ensure we always end with a synthesized answer
        final_answer = next((s.output_summary for s in reversed(steps) if s.action == ActionType.SYNTHESIZE), None)
        if final_answer is None:
            synth_trace = self._synthesize(state, len(steps))
            steps.append(synth_trace)
            groundedness = evaluate_groundedness(synth_trace.output_summary, state.sources)
            reward = compute_reward(
                new_sources_added=0,
                avg_credibility_delta=0.0,
                groundedness=groundedness,
                steps_used=len(steps),
                max_steps=max_steps,
            )
            synth_trace.reward = reward
            episode.transitions.append(
                Transition(
                    features=state.features(len(steps)),
                    action_idx=_action_idx(ActionType.SYNTHESIZE),
                    action_probs=[1.0 / len(policy.weights)] * len(policy.weights),
                    reward=reward,
                )
            )
            final_answer = synth_trace.output_summary

        total_reward = policy.update(episode)
        confidence = round(min(0.95, 0.4 + 0.3 * state.avg_credibility + 0.25 * groundedness), 3)

        return ResearchResult(
            session_id=session_id,
            query=query,
            answer=final_answer,
            confidence=confidence,
            steps=steps,
            sources=state.sources,
            total_reward=total_reward,
            elapsed_ms=int((time.time() - start) * 1000),
        )

    # ------------------------------------------------------------------
    def _execute(self, action: ActionType, state: ResearchState, step_idx: int, probs: list[float]) -> TraceStep:
        if action == ActionType.SEARCH_WEB:
            return self._search_web(state, step_idx)
        if action == ActionType.RETRIEVE_MEMORY:
            return self._retrieve_memory(state, step_idx)
        if action == ActionType.EVALUATE_SOURCES:
            return self._evaluate_sources(state, step_idx)
        if action == ActionType.REFLECT:
            return self._reflect(state, step_idx)
        if action == ActionType.SYNTHESIZE:
            return self._synthesize(state, step_idx)
        return TraceStep(index=step_idx, action=ActionType.STOP, thought="Policy elected to stop.", output_summary="Stopped.")

    # ------------------------------------------------------------------
    def _search_web(self, state: ResearchState, step_idx: int) -> TraceStep:
        remaining = max(state.max_sources - len(state.sources), 1)
        results = tools.web_search(state.query, max_results=min(3, remaining))
        new_sources = [s for s in results if s.url not in {x.url for x in state.sources}]
        for src in new_sources:
            state.page_bodies[src.url] = tools.fetch_page(src.url)
        state.sources.extend(new_sources)
        if new_sources:
            index_sources(new_sources, state.page_bodies)
        return TraceStep(
            index=step_idx,
            action=ActionType.SEARCH_WEB,
            thought=f"Searching the web for information on: '{state.query}'.",
            input={"query": state.query},
            output_summary=f"Found {len(new_sources)} new source(s).",
            sources=new_sources,
        )

    def _retrieve_memory(self, state: ResearchState, step_idx: int) -> TraceStep:
        hits = vector_store.query(state.query, k=4)
        state.vector_hits_last = len(hits)
        summary = f"Retrieved {len(hits)} relevant passage(s) from the indexed research notes."
        return TraceStep(
            index=step_idx,
            action=ActionType.RETRIEVE_MEMORY,
            thought="Checking prior indexed knowledge before searching further.",
            input={"query": state.query},
            output_summary=summary,
        )

    def _evaluate_sources(self, state: ResearchState, step_idx: int) -> TraceStep:
        unscored = [s for s in state.sources if s.credibility_score is None]
        for src in unscored:
            evaluate_source(state.query, src)
        summary = (
            f"Scored {len(unscored)} source(s). Average credibility now "
            f"{state.avg_credibility:.2f}, average relevance {state.avg_relevance:.2f}."
        )
        return TraceStep(
            index=step_idx,
            action=ActionType.EVALUATE_SOURCES,
            thought="Assessing credibility and relevance of gathered sources before relying on them.",
            output_summary=summary,
            sources=unscored,
        )

    def _reflect(self, state: ResearchState, step_idx: int) -> TraceStep:
        system = (
            "You are an autonomous research agent reflecting on progress so far. Decide what, "
            "if anything, is still missing before you can answer confidently."
        )
        prompt = (
            f"Query: {state.query}\n"
            f"Sources gathered: {len(state.sources)}\n"
            f"Average credibility: {state.avg_credibility:.2f}\n"
            f"Titles: {[s.title for s in state.sources]}\n"
            "In 1-2 sentences, note the biggest remaining gap."
        )
        thought = llm_client.complete(system, prompt)
        return TraceStep(
            index=step_idx,
            action=ActionType.REFLECT,
            thought=thought,
            output_summary=thought,
        )

    def _expand_query(self, query: str, history: list[ConversationTurn]) -> str:
        """Rewrite a vague follow-up ("what about his salary") into a
        self-contained search query using the conversation so far, since
        the raw text is what actually gets sent to web search - an
        unresolved pronoun there would return irrelevant results."""
        history_text = "\n\n".join(
            f"Q: {turn.query}\nA: {turn.answer[:500]}" for turn in history[-3:]
        )
        system = (
            "You rewrite a follow-up question into a fully self-contained, standalone "
            "question, resolving any pronouns or implicit references using the conversation "
            "history. If the question is already self-contained, return it unchanged. "
            "Respond with ONLY the rewritten question, no explanation, no quotes."
        )
        prompt = f"Conversation so far:\n{history_text}\n\nFollow-up question: {query}"
        expanded = llm_client.complete(system, prompt, max_tokens=100).strip()
        return expanded if expanded else query

    def _synthesize(self, state: ResearchState, step_idx: int) -> TraceStep:
        # Source evaluation is now guaranteed and made visible in the main
        # run() loop before this method is ever called - see the check
        # right before _execute() is invoked for SYNTHESIZE.
        context = "\n\n".join(
            f"[{i+1}] {s.title} ({s.domain}, credibility={s.credibility_score or 0:.2f}): {s.snippet}"
            for i, s in enumerate(state.sources)
        ) or "No sources were gathered."
        system = (
            "You are an autonomous research agent writing a final answer for the user. "
            "Synthesize across the provided sources, note points of agreement and disagreement, "
            "and flag uncertainty honestly. Cite sources inline as plain [n] only - e.g. [1], [2] - never use any other bracket style or symbols around citation numbers. Keep the answer focused — 3 to 5 sections at most, no padding sections with no real content. Always end with a short closing paragraph (2-3 sentences, no heading) that directly summarizes the answer to the original question. Write in clean, standard Markdown only — use actual newlines between list items instead of <br> tags, and use blank lines between paragraphs."
        )
        history_context = ""
        if state.conversation_history:
            history_context = "\n\nPrior conversation in this session (for context - the current question may build on this):\n" + "\n\n".join(
                f"Q: {turn.query}\nA: {turn.answer[:800]}" for turn in state.conversation_history[-3:]
            )

        prompt = f"Research question: {state.query}{history_context}\n\nSources:\n{context}\n\nWrite the final answer."
        answer = llm_client.complete(system, prompt, max_tokens=1800)
        return TraceStep(
            index=step_idx,
            action=ActionType.SYNTHESIZE,
            thought="Sufficient credible information gathered; synthesizing the final answer.",
            output_summary=answer,
            sources=state.sources,
        )


def _action_idx(action: ActionType) -> int:
    from .rl_policy import ACTIONS

    if action in ACTIONS:
        return ACTIONS.index(action)
    return 0


agent = ResearchAgent()

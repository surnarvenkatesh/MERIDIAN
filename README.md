# Meridian — Autonomous Research Agent

An agent that plans its own research path: it decides whether to search
the web, check its own memory, evaluate the sources it's found, reflect
on gaps, or write up an answer — and a reinforcement-learning policy
improves that decision-making from session to session based on real
feedback signals (source credibility, answer groundedness, efficiency,
and explicit thumbs up/down).

```
┌──────────────┐   REST + WS   ┌───────────────────┐        ┌──────────────┐
│  React (Vite) │◄─────────────►│   FastAPI backend  │◄──────►│  Anthropic   │
│  console UI   │               │  agent orchestrator │       │  LLM API     │
└──────────────┘               │  + RL policy        │        └──────────────┘
                                │  + evaluator         │        ┌──────────────┐
                                │  + RAG (Chroma)      │◄──────►│ Web search   │
                                └───────────┬──────────┘        │ (Tavily)     │
                                            │
                                    ┌───────▼────────┐
                                    │ SQLite (sessions,│
                                    │ feedback, policy)│
                                    └─────────────────┘
```

## What's actually implemented (and what isn't)

This is a real, runnable system, not a mockup — but one part of the brief
deserves an honest scoping note up front:

**"RL fine-tuning of an LLM"** most often means updating a model's actual
weights (PPO/GRPO over token log-probabilities) using a training cluster
and hours-to-days of compute. That's not something a request/response
backend does per-session, and no production app does it live either.

What we built instead is the way RL is *actually* used in agentic
products today: **a lightweight policy trained online over the agent's
decision points** — which action to take next (search, retrieve from
memory, evaluate sources, reflect, or synthesize), via policy-gradient
REINFORCE with a moving-average baseline and an entropy bonus, using a
reward computed from real signals (source credibility/relevance deltas,
answer groundedness, step efficiency, and blended user feedback). See
`backend/app/rl_policy.py` for the full implementation and the docstring
explaining the scope decision. The reward function and replay structure
are written so that swapping in a token-level PPO trainer against an
open-weight model later is a drop-in change, not a rewrite.

Everything else — the agentic loop, RAG pipeline, source evaluation, and
the full-stack app around it — is implemented for real:

- **Agentic loop** (`agent.py`): a bounded ReAct-style loop where the RL
  policy chooses each action and the LLM does the reasoning inside it.
- **RAG** (`vectorstore.py`): fetched pages are chunked and embedded into
  a persistent ChromaDB collection (sentence-transformers embeddings),
  with a dependency-free TF-IDF fallback so the app still runs if those
  optional packages aren't installed.
- **Evaluation** (`evaluator.py`): LLM-graded source credibility/relevance
  scoring (heuristic fallback if the LLM call fails), plus a groundedness
  proxy for the final answer.
- **Live streaming**: a WebSocket (`/ws/research`) streams each trace step
  to the frontend as it happens, with a REST fallback if the socket can't
  connect.
- **Persistence**: SQLite for session history and feedback; the RL policy
  weights persist to disk (`data/rl_policy.json`) across restarts.

## Running it

### Zero-config demo mode (no API keys needed)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. With no keys set, the LLM and web search
calls are served by deterministic offline mocks (see `llm.py` / `tools.py`)
— the agent loop, RAG indexing, evaluation, and RL policy all run for
real, so you can watch the reward curve move and the action-preference
bars shift over a handful of sessions.

### With live providers

Copy `.env.example` to `backend/.env` and set:

```
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
```

Restart the backend. The header badge in the UI ("demo mode…") disappears
once live reasoning is active.

### Docker

```bash
cp .env.example .env   # fill in keys, optional
docker compose up --build
```

Frontend at `http://localhost:5173`, backend at `http://localhost:8000`.

## Tests

```bash
cd backend
pip install -r requirements.txt pytest
FORCE_MOCK_LLM=true pytest tests/ -v
```

Covers: REINFORCE math (policy actually shifts probability toward
rewarded actions — this is checked numerically, not just smoke-tested),
reward shaping, the end-to-end agent loop in offline mode, and the
evaluator's heuristic fallback.

## API surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/research` | Run a research session synchronously, get the full result |
| `WS` | `/ws/research` | Stream trace steps live, then the final result |
| `GET` | `/api/sessions` | List past sessions |
| `GET` | `/api/sessions/{id}` | Full detail for one session |
| `POST` | `/api/feedback` | Submit thumbs up/down, feeds the RL reward signal |
| `GET` | `/api/policy` | Current RL policy snapshot (weights, reward history, action mix) |
| `GET` | `/api/health` | Liveness + whether live LLM/search providers are configured |

## Design notes

The frontend intentionally avoids the generic "AI dashboard" kit — no
cream-and-terracotta hero, no identical rounded cards everywhere. It's
built around a single idea: the agent's live reasoning trace is a real
sequence, so it's rendered as a connected timeline (the one place a
sequential/numbered treatment is earned), everything else is quiet
supporting chrome. A warm serif carries the editorial "research desk"
tone, a plain sans handles UI copy, and a monospace face is reserved for
actual telemetry — scores, timestamps, rewards — because that's real
system data, not decoration.

## Extending this

- **Real PPO over an open-weight model**: reuse `compute_reward()` and the
  `Episode`/`Transition` structures in `rl_policy.py` as your reward
  function and rollout buffer; swap the linear-softmax policy for a
  LoRA-adapted policy head and train with TRL/veRL against vLLM rollouts.
- **More tools**: add entries to `tools.py` and a new `ActionType`; the
  policy will start exploring the new action automatically (its feature
  vector doesn't need to change).
- **Multi-agent**: `ResearchState` is intentionally the only mutable
  shared object in a run — spinning up parallel `ResearchAgent` workers
  against sub-questions and merging their `Source` lists is a natural
  next step.

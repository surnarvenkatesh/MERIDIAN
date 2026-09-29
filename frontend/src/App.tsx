import { useEffect, useState } from "react";
import { AlertCircle, CircleDot, MessageSquarePlus } from "lucide-react";
import ProfileMenu from "./components/ProfileMenu";
import Sidebar from "./components/Sidebar";
import TraceTimeline from "./components/TraceTimeline";
import QuestionBubble from "./components/QuestionBubble";
import AnswerCard from "./components/AnswerCard";
import SourcesPanel from "./components/SourcesPanel";
import PolicyPanel from "./components/PolicyPanel";
import AuthScreen from "./components/AuthScreen";
import { clearToken, fetchHealth, fetchPolicy, fetchSessions, getToken, setToken, streamResearch } from "./lib/api";
import type { PolicySnapshot, ResearchResult, SessionSummary, Source, TraceStep, UploadedDocument } from "./lib/types";

interface ConversationTurn {
  id: string;
  question: string;
  steps: TraceStep[];
  result: ResearchResult | null;
  error: string | null;
}

const STORAGE_KEY = "meridian_conversation_v1";
const EMAIL_KEY = "meridian_auth_email";

function loadConversation(): ConversationTurn[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ConversationTurn[]) : [];
  } catch {
    return [];
  }
}

export default function App() {
  const [authed, setAuthed] = useState<boolean>(() => Boolean(getToken()));
  const [email, setEmail] = useState<string | null>(() => localStorage.getItem(EMAIL_KEY));

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [turns, setTurns] = useState<ConversationTurn[]>(() => loadConversation());
  const [isRunning, setIsRunning] = useState(false);
  const [policy, setPolicy] = useState<PolicySnapshot | null>(null);
  const [health, setHealth] = useState<{ llm_live: boolean; search_live: boolean } | null>(null);

  const refreshSessions = () => fetchSessions().then(setSessions).catch(() => {});
  const refreshPolicy = () => fetchPolicy().then(setPolicy).catch(() => {});

  useEffect(() => {
    if (!authed) return;
    refreshSessions();
    refreshPolicy();
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, [authed]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(turns));
  }, [turns]);

  const handleAuthenticated = (token: string, userEmail: string) => {
    setToken(token);
    localStorage.setItem(EMAIL_KEY, userEmail);
    setEmail(userEmail);
    setAuthed(true);
  };

  const handleLogout = () => {
    clearToken();
    localStorage.removeItem(EMAIL_KEY);
    localStorage.removeItem(STORAGE_KEY);
    setEmail(null);
    setAuthed(false);
    setTurns([]);
    setSessions([]);
  };

  const startNewConversation = () => {
    setTurns([]);
    localStorage.removeItem(STORAGE_KEY);
  };

  const runQuery = (query: string, uploadedDocuments: UploadedDocument[] = []) => {
    const turnId = `turn_${Date.now()}`;
    const conversationHistory = turns
      .filter((t) => t.result)
      .map((t) => ({ query: t.question, answer: t.result!.answer }));

    setTurns((prev) => [...prev, { id: turnId, question: query, steps: [], result: null, error: null }]);
    setIsRunning(true);

    streamResearch(query, uploadedDocuments, conversationHistory, {
      onStep: (step) =>
        setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, steps: [...t.steps, step] } : t))),
      onResult: (res) => {
        setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, result: res } : t)));
        setIsRunning(false);
        refreshSessions();
        refreshPolicy();
      },
      onError: (message) => {
        setTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, error: message } : t)));
        setIsRunning(false);
      },
    });
  };

  const editTurn = (turnId: string, newQuestion: string) => {
    setTurns((prev) => {
      const idx = prev.findIndex((t) => t.id === turnId);
      return idx === -1 ? prev : prev.slice(0, idx);
    });
    runQuery(newQuestion);
  };

  const selectSession = async (id: string) => {
    try {
      const res: ResearchResult = await fetch(`/api/sessions/${id}`).then((r) => r.json());
      if (res && res.steps) {
        setTurns([{ id: res.session_id, question: res.query, steps: res.steps, result: res, error: null }]);
        setIsRunning(false);
      }
    } catch {
      /* ignore */
    }
  };

  if (!authed) {
    return <AuthScreen onAuthenticated={handleAuthenticated} />;
  }

  const lastTurn = turns[turns.length - 1];
  const sourcesForDisplay: Source[] = lastTurn
    ? lastTurn.result
      ? lastTurn.result.sources
      : lastTurn.steps.flatMap((s) => s.sources)
    : [];

  return (
    <div className="flex h-screen w-full overflow-hidden">
      <Sidebar
        sessions={sessions}
        activeSessionId={null}
        isRunning={isRunning}
        onSubmit={runQuery}
        onSelectSession={selectSession}
        onSessionsChanged={refreshSessions}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-ink-line px-8 py-4">
          <div className="min-w-0">
            <h1 className="truncate font-display text-[18px] text-parchment">Autonomous research console</h1>
            <p className="text-[12.5px] text-parchment-faint">
              Every run plans its own path, scores its sources, and reports what it's still unsure about.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            {health && !health.llm_live && (
              <span className="flex items-center gap-1.5 rounded-full border border-signal-amberDim/50 bg-signal-amberDim/10 px-2.5 py-1 text-[11px] text-signal-amber">
                <AlertCircle className="h-3 w-3" /> demo mode — add a free GROQ_API_KEY for live reasoning
              </span>
            )}
            {isRunning && (
              <span className="flex items-center gap-1.5 text-[12px] text-signal-teal">
                <CircleDot className="h-3.5 w-3.5 animate-pulseDot" /> researching
              </span>
            )}
            {turns.length > 0 && (
              <button
                onClick={startNewConversation}
                disabled={isRunning}
                title="Start a new conversation"
                className="flex items-center gap-1.5 rounded-md border border-ink-line px-2.5 py-1 text-[12px] text-parchment-faint transition-colors hover:border-ink-lineStrong hover:text-parchment-dim disabled:opacity-40"
              >
                <MessageSquarePlus className="h-3.5 w-3.5" /> New conversation
              </button>
            )}
            <div className="border-l border-ink-line pl-3">
              {email && <ProfileMenu email={email} onLogout={handleLogout} />}
            </div>
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          <section className="min-w-0 flex-[2.1] overflow-y-auto px-8 py-7">
            {turns.length === 0 && !isRunning && <TraceTimeline steps={[]} isRunning={false} />}
            {turns.map((turn) => (
              <div key={turn.id} className="mb-8">
                <QuestionBubble
                  question={turn.question}
                  disabled={isRunning}
                  onEdit={(newQuestion) => editTurn(turn.id, newQuestion)}
                />
                {turn.error && (
                  <div className="mb-5 rounded-md border border-signal-clayDim/50 bg-signal-clayDim/10 px-4 py-3 text-[13px] text-signal-clay">
                    {turn.error}
                  </div>
                )}
                <TraceTimeline steps={turn.steps} isRunning={isRunning && turn.id === lastTurn?.id} />
                {turn.result && <AnswerCard result={turn.result} />}
              </div>
            ))}
          </section>

          <aside className="flex w-[340px] shrink-0 flex-col gap-4 overflow-y-auto border-l border-ink-line bg-ink-panel/40 px-4 py-6">
            <PolicyPanel policy={policy} />
            <div className="rounded-lg border border-ink-line bg-ink-panel px-4 py-4">
              <SourcesPanel sources={sourcesForDisplay} />
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}

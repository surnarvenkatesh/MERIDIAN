import type { PolicySnapshot, ResearchResult, SessionSummary, StreamEvent, TraceStep } from "./types";

const WS_BASE = (() => {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
})();

const TOKEN_KEY = "meridian_auth_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface AuthResponse {
  token: string;
  email: string;
}

export async function register(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch("/api/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Registration failed");
  return data;
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const res = await fetch("/api/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to change password");
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Login failed");
  return data;
}

export async function fetchPolicy(): Promise<PolicySnapshot> {
  const res = await fetch("/api/policy", { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to fetch policy snapshot");
  return res.json();
}

export async function fetchSessions(): Promise<SessionSummary[]> {
  const res = await fetch("/api/sessions", { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to fetch sessions");
  return res.json();
}

export async function uploadFile(file: File): Promise<{ filename: string; text: string } | null> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", headers: authHeaders(), body: formData });
  const data = await res.json();
  if (data.status !== "ok") {
    throw new Error(data.message || "Upload failed");
  }
  return { filename: data.filename, text: data.text };
}

export async function fetchHealth(): Promise<{ status: string; llm_live: boolean; search_live: boolean }> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("Failed to fetch health");
  return res.json();
}

export async function renameSession(sessionId: string, title: string): Promise<void> {
  await fetch(`/api/sessions/${sessionId}/rename`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ title }),
  });
}

export async function pinSession(sessionId: string, pinned: boolean): Promise<void> {
  await fetch(`/api/sessions/${sessionId}/pin?pinned=${pinned}`, { method: "PATCH", headers: authHeaders() });
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`/api/sessions/${sessionId}`, { method: "DELETE", headers: authHeaders() });
}

export async function shareSession(sessionId: string): Promise<string | null> {
  const res = await fetch(`/api/sessions/${sessionId}/share`, { method: "POST", headers: authHeaders() });
  const data = await res.json();
  return data.share_token ?? null;
}

export async function submitFeedback(
  session_id: string,
  rating: "helpful" | "not_helpful",
  comment?: string
): Promise<void> {
  await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ session_id, rating, comment }),
  });
}

export interface ConversationHistoryEntry {
  query: string;
  answer: string;
}

/**
 * Opens a streaming research session over WebSocket. Falls back to a
 * single POST /api/research call (no live trace) if the socket fails to
 * connect, so the app keeps working behind proxies that block WS upgrades.
 */
export function streamResearch(
  query: string,
  uploadedDocuments: import("./types").UploadedDocument[],
  conversationHistory: ConversationHistoryEntry[],
  handlers: {
    onStep: (step: TraceStep) => void;
    onResult: (result: ResearchResult) => void;
    onError: (message: string) => void;
  }
): () => void {
  let closed = false;
  let usedFallback = false;
  const token = getToken();

  const fallback = async () => {
    if (usedFallback || closed) return;
    usedFallback = true;
    try {
      const res = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ query, uploaded_documents: uploadedDocuments, conversation_history: conversationHistory }),
      });
      if (!res.ok) throw new Error(`Research request failed (${res.status})`);
      const result: ResearchResult = await res.json();
      result.steps.forEach((s) => handlers.onStep(s));
      handlers.onResult(result);
    } catch (err) {
      handlers.onError(err instanceof Error ? err.message : "Research request failed");
    }
  };

  try {
    const ws = new WebSocket(`${WS_BASE}/ws/research`);
    const timeout = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        ws.close();
        fallback();
      }
    }, 2500);

    ws.onopen = () => {
      clearTimeout(timeout);
      ws.send(
        JSON.stringify({
          query,
          uploaded_documents: uploadedDocuments,
          conversation_history: conversationHistory,
          token,
        })
      );
    };
    ws.onmessage = (event) => {
      const msg: StreamEvent = JSON.parse(event.data);
      if (msg.type === "step") handlers.onStep(msg.data);
      else if (msg.type === "result") handlers.onResult(msg.data);
      else if (msg.type === "error") handlers.onError(msg.message);
    };
    ws.onerror = () => {
      clearTimeout(timeout);
      fallback();
    };
    return () => {
      closed = true;
      ws.close();
    };
  } catch {
    fallback();
    return () => {
      closed = true;
    };
  }
}

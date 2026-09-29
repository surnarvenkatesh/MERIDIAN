export type ActionType =
  | "search_web"
  | "retrieve_memory"
  | "fetch_page"
  | "evaluate_sources"
  | "reflect"
  | "synthesize"
  | "stop";

export interface Source {
  id: string;
  title: string;
  url: string;
  snippet: string;
  published?: string | null;
  domain: string;
  credibility_score?: number | null;
  relevance_score?: number | null;
  rationale?: string | null;
}

export interface TraceStep {
  id: string;
  index: number;
  action: ActionType;
  thought: string;
  input: Record<string, unknown>;
  output_summary: string;
  sources: Source[];
  reward?: number | null;
  duration_ms: number;
  timestamp: number;
}

export interface ResearchResult {
  session_id: string;
  query: string;
  answer: string;
  confidence: number;
  steps: TraceStep[];
  sources: Source[];
  total_reward: number;
  elapsed_ms: number;
}

export interface PolicySnapshot {
  weights: Record<string, number[]>;
  action_names: string[];
  episodes_trained: number;
  running_avg_reward: number;
  reward_history: number[];
  action_distribution: Record<string, number>;
  updated_at: number;
}

export interface SessionSummary {
  id: string;
  query: string;
  answer: string;
  confidence: number;
  total_reward: number;
  elapsed_ms: number;
  num_sources: number;
  created_at: number;
  custom_title: string | null;
  pinned: number;
}

export interface UploadedDocument {
  filename: string;
  text: string;
}


export type StreamEvent =
  | { type: "step"; data: TraceStep }
  | { type: "result"; data: ResearchResult }
  | { type: "error"; message: string };

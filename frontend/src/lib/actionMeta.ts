import { BookOpen, Compass, Feather, Globe, ScanSearch, SquareCheck, type LucideIcon } from "lucide-react";
import type { ActionType } from "./types";

export interface ActionMeta {
  label: string;
  icon: LucideIcon;
  dotClass: string;
}

export const ACTION_META: Record<ActionType, ActionMeta> = {
  search_web: { label: "Searching the web", icon: Globe, dotClass: "bg-signal-amber" },
  retrieve_memory: { label: "Recalling indexed notes", icon: BookOpen, dotClass: "bg-signal-teal" },
  fetch_page: { label: "Reading source", icon: ScanSearch, dotClass: "bg-signal-amber" },
  evaluate_sources: { label: "Evaluating sources", icon: SquareCheck, dotClass: "bg-signal-teal" },
  reflect: { label: "Reflecting on progress", icon: Compass, dotClass: "bg-parchment-dim" },
  synthesize: { label: "Synthesizing answer", icon: Feather, dotClass: "bg-signal-amber" },
  stop: { label: "Concluding", icon: SquareCheck, dotClass: "bg-parchment-dim" },
};

export function credibilityColor(score?: number | null): string {
  if (score == null) return "border-l-ink-lineStrong";
  if (score >= 0.65) return "border-l-signal-teal";
  if (score >= 0.4) return "border-l-signal-amber";
  return "border-l-signal-clay";
}

export function credibilityLabel(score?: number | null): string {
  if (score == null) return "unscored";
  if (score >= 0.65) return "high";
  if (score >= 0.4) return "moderate";
  return "low";
}

import { useEffect, useState } from "react";
import { Compass } from "lucide-react";
import AnswerCard from "./AnswerCard";
import SourcesPanel from "./SourcesPanel";
import { fetchSharedSession } from "../lib/api";
import type { ResearchResult } from "../lib/types";

export default function SharedView({ token }: { token: string }) {
  const [state, setState] = useState<"loading" | "ready" | "missing" | "error">("loading");
  const [result, setResult] = useState<ResearchResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSharedSession(token)
      .then((r) => {
        if (cancelled) return;
        if (r) {
          setResult(r);
          setState("ready");
        } else {
          setState("missing");
        }
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="min-h-screen w-full bg-ink">
      <header className="flex items-center justify-between border-b border-ink-line px-8 py-4">
        <div className="flex items-center gap-2">
          <Compass className="h-5 w-5 text-signal-amber" strokeWidth={1.75} />
          <span className="font-display text-lg tracking-tight text-parchment">Meridian</span>
          <span className="ml-3 rounded-full border border-ink-line px-2.5 py-0.5 text-[11px] text-parchment-faint">
            Shared research
          </span>
        </div>
        <a href="/" className="text-[12.5px] text-signal-amber hover:underline">
          Open Meridian
        </a>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-8">
        {state === "loading" && (
          <p className="text-[13px] text-parchment-faint">
            Loading shared research… the server can take up to a minute to wake up.
          </p>
        )}
        {state === "missing" && (
          <p className="text-[13.5px] text-parchment-dim">
            This shared link is invalid, or its owner has stopped sharing it.
          </p>
        )}
        {state === "error" && (
          <p className="text-[13.5px] text-signal-clay">
            Couldn't reach the server. Please try again in a moment.
          </p>
        )}
        {state === "ready" && result && (
          <>
            <div className="mb-6 flex justify-end">
              <div className="max-w-[80%] rounded-lg rounded-tr-sm bg-ink-raised px-4 py-2.5 text-[14px] leading-relaxed text-parchment">
                {result.query}
              </div>
            </div>
            <AnswerCard result={result} readOnly />
            <div className="mt-6 rounded-lg border border-ink-line bg-ink-panel px-4 py-4">
              <SourcesPanel sources={result.sources} />
            </div>
          </>
        )}
      </main>
    </div>
  );
}

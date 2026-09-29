import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { TraceStep } from "../lib/types";
import { ACTION_META } from "../lib/actionMeta";

function StepNode({ step, isLast, isStreaming }: { step: TraceStep; isLast: boolean; isStreaming: boolean }) {
  const [open, setOpen] = useState(false);
  const meta = ACTION_META[step.action];
  const Icon = meta.icon;

  return (
    <div className="relative flex gap-3.5 pl-1 animate-riseIn">
      <div className="flex flex-col items-center">
        <div
          className={`z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-ink-lineStrong bg-ink-raised ${
            isStreaming ? "animate-pulseDot" : ""
          }`}
        >
          <Icon className="h-3.5 w-3.5 text-parchment-dim" strokeWidth={1.75} />
        </div>
        {!isLast && <div className="w-px flex-1 bg-ink-line" />}
      </div>

      <div className="min-w-0 flex-1 pb-6">
        <button onClick={() => setOpen((o) => !o)} className="flex w-full items-start justify-between gap-2 text-left">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className={`h-1.5 w-1.5 rounded-full ${meta.dotClass}`} />
              <span className="text-[12px] font-medium uppercase tracking-wide text-parchment-faint">
                {meta.label}
              </span>
              <span className="font-mono text-[10.5px] text-parchment-faint">
                {step.duration_ms > 0 ? `${step.duration_ms}ms` : ""}
              </span>
            </div>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-parchment">{step.thought}</p>
          </div>
          {(step.output_summary || step.sources.length > 0) && (
            <ChevronDown
              className={`mt-1 h-4 w-4 shrink-0 text-parchment-faint transition-transform ${open ? "rotate-180" : ""}`}
            />
          )}
        </button>

        {open && (
          <div className="mt-2.5 rounded-md border border-ink-line bg-ink px-3.5 py-3">
            {step.output_summary && step.action !== "synthesize" && (
              <p className="text-[13px] leading-relaxed text-parchment-dim">{step.output_summary}</p>
            )}
            {step.sources.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1.5">
                {step.sources.map((s) => (
                  <li key={s.id} className="truncate font-mono text-[11.5px] text-parchment-faint">
                    {s.domain} — {s.title}
                  </li>
                ))}
              </ul>
            )}
            {step.reward != null && (
              <div className="mt-2 font-mono text-[10.5px] text-signal-tealDim">reward {step.reward.toFixed(3)}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function TraceTimeline({ steps, isRunning }: { steps: TraceStep[]; isRunning: boolean }) {
  if (steps.length === 0 && !isRunning) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <p className="font-display text-xl text-parchment-dim">The desk is clear.</p>
        <p className="max-w-sm text-[13.5px] text-parchment-faint">
          Ask a research question and watch the agent plan, search, weigh its sources, and write up findings — live.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {steps.map((step, i) => (
        <StepNode key={step.id} step={step} isLast={i === steps.length - 1 && !isRunning} isStreaming={isRunning && i === steps.length - 1} />
      ))}
      {isRunning && steps.length === 0 && (
        <div className="flex items-center gap-3 pl-1">
          <div className="h-7 w-7 animate-pulseDot rounded-full border border-ink-lineStrong bg-ink-raised" />
          <span className="text-[13px] text-parchment-faint">Planning the first move…</span>
        </div>
      )}
    </div>
  );
}

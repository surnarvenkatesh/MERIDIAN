import { useState } from "react";
import { Check, Copy, Share2, ThumbsDown, ThumbsUp } from "lucide-react";
import ReactMarkdown from "react-markdown";
import CodeBlock from "./CodeBlock";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import type { ResearchResult } from "../lib/types";
import { shareSession, submitFeedback } from "../lib/api";

export default function AnswerCard({ result }: { result: ResearchResult }) {
  const [given, setGiven] = useState<"helpful" | "not_helpful" | null>(null);
  const [copied, setCopied] = useState(false);
  const [shared, setShared] = useState(false);

  const rate = async (rating: "helpful" | "not_helpful") => {
    setGiven(rating);
    await submitFeedback(result.session_id, rating);
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleShare = async () => {
    const token = await shareSession(result.session_id);
    if (token) {
      const url = `${window.location.origin}/shared/${token}`;
      await navigator.clipboard.writeText(url);
      setShared(true);
      setTimeout(() => setShared(false), 1500);
    }
  };

  return (
    <div className="mt-2 animate-riseIn rounded-lg border border-ink-lineStrong bg-ink-raised px-6 py-5 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wide text-signal-amber">Final answer</span>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] text-parchment-faint">
            confidence {(result.confidence * 100).toFixed(0)}% · {(result.elapsed_ms / 1000).toFixed(1)}s ·{" "}
            {result.sources.length} sources
          </span>
          <div className="flex items-center gap-1 border-l border-ink-line pl-2.5">
            <button
              onClick={handleCopy}
              title="Copy answer"
              className="flex h-6 w-6 items-center justify-center rounded text-parchment-faint hover:bg-ink hover:text-parchment-dim"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-signal-teal" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
            <button
              onClick={handleShare}
              title="Copy share link"
              className="flex h-6 w-6 items-center justify-center rounded text-parchment-faint hover:bg-ink hover:text-parchment-dim"
            >
              {shared ? <Check className="h-3.5 w-3.5 text-signal-teal" /> : <Share2 className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
      </div>

      <div className="answer-markdown text-[14.5px] leading-relaxed text-parchment">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          components={{
            h1: (p) => <h2 className="mb-2 mt-4 font-display text-[18px] text-parchment first:mt-0" {...p} />,
            h2: (p) => <h3 className="mb-2 mt-4 font-display text-[16px] text-parchment first:mt-0" {...p} />,
            h3: (p) => <h4 className="mb-1.5 mt-3 text-[14px] font-semibold text-parchment first:mt-0" {...p} />,
            p: (p) => <p className="mb-3 last:mb-0" {...p} />,
            strong: (p) => <strong className="font-semibold text-parchment" {...p} />,
            ul: (p) => <ul className="mb-3 ml-4 list-disc space-y-1" {...p} />,
            ol: (p) => <ol className="mb-3 ml-4 list-decimal space-y-1" {...p} />,
            li: (p) => <li className="pl-1" {...p} />,
            hr: () => <hr className="my-4 border-ink-line" />,
            a: (p) => (
              <a className="text-signal-amber underline decoration-signal-amberDim hover:text-[#eeb156]" target="_blank" rel="noreferrer" {...p} />
            ),
            table: (p) => (
              <div className="mb-4 overflow-x-auto rounded-md border border-ink-line">
                <table className="w-full border-collapse text-[13px]" {...p} />
              </div>
            ),
            thead: (p) => <thead className="bg-ink-panel" {...p} />,
            th: (p) => (
              <th className="border-b border-ink-lineStrong px-3 py-2 text-left font-medium text-parchment-dim" {...p} />
            ),
            td: (p) => <td className="border-b border-ink-line px-3 py-2 align-top text-parchment-dim" {...p} />,
            code: ({ className, ...p }) => {
              // react-markdown gives fenced code blocks a language-xxx class
              // and inline code no className at all - use that to tell them
              // apart, since fenced blocks need very different treatment
              // (dark box, padding, scroll) from a short inline snippet.
              const isBlock = Boolean(className);
              if (isBlock) {
                return <code className={`${className ?? ""} font-mono text-[12.5px] text-parchment`} {...p} />;
              }
              return (
                <code className="rounded bg-ink px-1.5 py-0.5 font-mono text-[12.5px] text-signal-teal" {...p} />
              );
            },
            pre: (p) => <CodeBlock>{p.children}</CodeBlock>,
            blockquote: (p) => (
              <blockquote className="mb-3 border-l-2 border-signal-amberDim pl-3 text-parchment-dim italic" {...p} />
            ),
          }}
        >
          {result.answer.replace(/【(\d+)[^】]*】/g, "[$1]")}
        </ReactMarkdown>
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-ink-line pt-3.5">
        <span className="text-[12px] text-parchment-faint">Was this research useful?</span>
        <div className="flex gap-1.5">
          <button
            onClick={() => rate("helpful")}
            title="Helpful"
            className={`flex h-7 w-7 items-center justify-center rounded-md border transition-colors ${
              given === "helpful"
                ? "border-signal-tealDim bg-signal-tealDim/20 text-signal-teal"
                : "border-ink-line text-parchment-faint hover:border-ink-lineStrong hover:text-parchment-dim"
            }`}
          >
            <ThumbsUp className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
          <button
            onClick={() => rate("not_helpful")}
            title="Not helpful"
            className={`flex h-7 w-7 items-center justify-center rounded-md border transition-colors ${
              given === "not_helpful"
                ? "border-signal-clayDim bg-signal-clayDim/20 text-signal-clay"
                : "border-ink-line text-parchment-faint hover:border-ink-lineStrong hover:text-parchment-dim"
            }`}
          >
            <ThumbsDown className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
        </div>
      </div>
      {given && (
        <p className="mt-2 text-right text-[11px] text-parchment-faint">
          Thanks — this feeds directly back into the agent's policy.
        </p>
      )}
    </div>
  );
}

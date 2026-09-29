import type { Source } from "../lib/types";
import { credibilityColor, credibilityLabel } from "../lib/actionMeta";

export default function SourcesPanel({ sources }: { sources: Source[] }) {
  const deduped = Array.from(new Map(sources.map((s) => [s.url, s])).values());
  const sorted = deduped.sort((a, b) => (b.credibility_score ?? 0) - (a.credibility_score ?? 0));

  return (
    <div className="flex flex-col gap-2">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wide text-parchment-faint">Sources</span>
        <span className="font-mono text-[10.5px] text-parchment-faint">{sorted.length}</span>
      </div>
      {sorted.length === 0 && (
        <p className="text-[12.5px] text-parchment-faint">No sources gathered yet.</p>
      )}
      {sorted.map((s) => {
        const cls =
          "group rounded-r-md border-l-2 bg-ink-raised px-3 py-2.5 transition-colors hover:bg-ink-raised/70 " +
          credibilityColor(s.credibility_score);
        return (
          <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className={cls}>
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-mono text-[11px] text-parchment-faint">{s.domain}</span>
              <span className="shrink-0 font-mono text-[10px] text-parchment-faint">
                {credibilityLabel(s.credibility_score)}
              </span>
            </div>
            <p className="mt-1 truncate text-[12.5px] text-parchment-dim group-hover:text-parchment">
              {s.title}
            </p>
          </a>
        );
      })}
    </div>
  );
}

import { useState } from "react";
import { Check, Copy, Pencil, X } from "lucide-react";

interface Props {
  question: string;
  disabled: boolean;
  onEdit: (newQuestion: string) => void;
}

export default function QuestionBubble({ question, disabled, onEdit }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(question);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(question);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const startEdit = () => {
    setDraft(question);
    setEditing(true);
  };

  const saveEdit = () => {
    if (draft.trim() && draft.trim() !== question) {
      onEdit(draft.trim());
    }
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="mb-6 flex justify-end">
        <div className="w-full max-w-[80%] rounded-lg border border-signal-amberDim bg-ink-raised p-3">
          <textarea
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                saveEdit();
              }
              if (e.key === "Escape") setEditing(false);
            }}
            rows={2}
            className="w-full resize-none rounded bg-ink px-2.5 py-2 text-[14px] text-parchment outline-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button
              onClick={() => setEditing(false)}
              className="flex items-center gap-1 rounded px-2 py-1 text-[11.5px] text-parchment-faint hover:text-parchment-dim"
            >
              <X className="h-3.5 w-3.5" /> Cancel
            </button>
            <button
              onClick={saveEdit}
              className="flex items-center gap-1 rounded bg-signal-amber px-2.5 py-1 text-[11.5px] font-medium text-ink hover:bg-[#eeb156]"
            >
              <Check className="h-3.5 w-3.5" /> Save & rerun
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="group mb-6 flex justify-end">
      <div className="max-w-[80%]">
        <div className="rounded-lg rounded-tr-sm bg-ink-raised px-4 py-2.5 text-[14px] leading-relaxed text-parchment">
          {question}
        </div>
        <div className="mt-1.5 flex justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <button
            onClick={handleCopy}
            title="Copy question"
            className="flex h-6 w-6 items-center justify-center rounded text-parchment-faint hover:bg-ink-raised hover:text-parchment-dim"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-signal-teal" /> : <Copy className="h-3.5 w-3.5" />}
          </button>
          {!disabled && (
            <button
              onClick={startEdit}
              title="Edit and rerun"
              className="flex h-6 w-6 items-center justify-center rounded text-parchment-faint hover:bg-ink-raised hover:text-parchment-dim"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

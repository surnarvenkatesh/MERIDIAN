import { useEffect, useRef, useState } from "react";
import { MoreHorizontal, Pencil, Pin, PinOff, Share2, Trash2, Check, X } from "lucide-react";
import type { SessionSummary } from "../lib/types";
import { deleteSession, pinSession, renameSession, shareSession } from "../lib/api";

interface Props {
  session: SessionSummary;
  onChanged: () => void;
}

export default function SessionMenu({ session, onChanged }: Props) {
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState(session.custom_title ?? session.query);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
        setShareUrl(null);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const handlePin = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await pinSession(session.id, session.pinned === 0);
    setOpen(false);
    onChanged();
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this session permanently? This can't be undone.")) return;
    await deleteSession(session.id);
    setOpen(false);
    onChanged();
  };

  const handleShare = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const token = await shareSession(session.id);
    if (token) {
      const url = `${window.location.origin}/shared/${token}`;
      setShareUrl(url);
      navigator.clipboard.writeText(url).catch(() => {});
    }
  };

  const startRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setTitleDraft(session.custom_title ?? session.query);
    setRenaming(true);
  };

  const confirmRename = async (e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (titleDraft.trim()) {
      await renameSession(session.id, titleDraft.trim());
    }
    setRenaming(false);
    setOpen(false);
    onChanged();
  };

  if (renaming) {
    return (
      <form onSubmit={confirmRename} className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
        <input
          autoFocus
          value={titleDraft}
          onChange={(e) => setTitleDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Escape" && setRenaming(false)}
          className="w-full rounded border border-signal-amberDim bg-ink px-1.5 py-0.5 text-[12px] text-parchment outline-none"
        />
        <button type="submit" className="shrink-0 text-signal-teal">
          <Check className="h-3.5 w-3.5" />
        </button>
        <button type="button" onClick={() => setRenaming(false)} className="shrink-0 text-parchment-faint">
          <X className="h-3.5 w-3.5" />
        </button>
      </form>
    );
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        className="rounded p-1 text-parchment-faint opacity-0 transition-opacity hover:bg-ink hover:text-parchment-dim group-hover:opacity-100"
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className="absolute right-0 top-6 z-20 w-40 rounded-md border border-ink-lineStrong bg-ink-raised py-1 shadow-panel">
          {shareUrl ? (
            <div className="px-3 py-2 text-[11px] text-signal-teal">Link copied!</div>
          ) : (
            <button
              onClick={handleShare}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[12.5px] text-parchment-dim hover:bg-ink"
            >
              <Share2 className="h-3.5 w-3.5" /> Share
            </button>
          )}
          <button
            onClick={startRename}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[12.5px] text-parchment-dim hover:bg-ink"
          >
            <Pencil className="h-3.5 w-3.5" /> Rename
          </button>
          <button
            onClick={handlePin}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[12.5px] text-parchment-dim hover:bg-ink"
          >
            {session.pinned ? <PinOff className="h-3.5 w-3.5" /> : <Pin className="h-3.5 w-3.5" />}
            {session.pinned ? "Unpin" : "Pin"}
          </button>
          <div className="my-1 border-t border-ink-line" />
          <button
            onClick={handleDelete}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[12.5px] text-signal-clay hover:bg-ink"
          >
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </button>
        </div>
      )}
    </div>
  );
}

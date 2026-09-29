import { useEffect, useRef, useState } from "react";
import { Compass, FileText, Mic, MicOff, Paperclip, Pin, Send, X } from "lucide-react";
import SessionMenu from "./SessionMenu";
import { uploadFile } from "../lib/api";
import type { SessionSummary, UploadedDocument } from "../lib/types";

interface Props {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  isRunning: boolean;
  onSubmit: (query: string, uploadedDocuments: UploadedDocument[]) => void;
  onSelectSession: (id: string) => void;
  onSessionsChanged: () => void;
}

// The Web Speech API isn't in TypeScript's default lib types, so we declare
// just enough of it here to use it safely without pulling in a full package.
interface SpeechRecognitionResultLike {
  0: { transcript: string };
  isFinal: boolean;
}
interface SpeechRecognitionEventLike {
  results: ArrayLike<SpeechRecognitionResultLike>;
  resultIndex: number;
}
interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export default function Sidebar({
  sessions,
  activeSessionId,
  isRunning,
  onSubmit,
  onSelectSession,
  onSessionsChanged,
}: Props) {
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<UploadedDocument[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const baseTextRef = useRef("");

  useEffect(() => {
    setVoiceSupported(getSpeechRecognition() !== null);
  }, []);

  const submit = () => {
    if (!draft.trim() || isRunning) return;
    onSubmit(draft.trim(), attachments);
    setDraft("");
    setAttachments([]);
  };

  const handleFilesSelected = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploadError(null);
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const result = await uploadFile(file);
        if (result) {
          setAttachments((prev) => [...prev, result]);
        }
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const removeAttachment = (filename: string) => {
    setAttachments((prev) => prev.filter((a) => a.filename !== filename));
  };

  const toggleListening = () => {
    const SpeechRecognitionCtor = getSpeechRecognition();
    if (!SpeechRecognitionCtor) {
      setVoiceSupported(false);
      return;
    }

    if (listening) {
      recognitionRef.current?.stop();
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    baseTextRef.current = draft ? draft.trim() + " " : "";

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      setDraft(baseTextRef.current + transcript);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  };

  return (
    <aside className="flex h-full w-[300px] shrink-0 flex-col border-r border-ink-line bg-ink-panel">
      <div className="flex items-center gap-2 px-5 pt-6 pb-4">
        <Compass className="h-5 w-5 text-signal-amber" strokeWidth={1.75} />
        <span className="font-display text-lg tracking-tight text-parchment">Meridian</span>
      </div>
      <p className="px-5 pb-5 text-[13px] leading-relaxed text-parchment-dim">
        An autonomous agent that plans its own research path, weighs sources, and gets sharper with every session.
      </p>

      <div className="px-5">
        <div className="relative rounded-md border border-ink-line bg-ink focus-within:border-signal-amberDim">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={listening ? "Listening…" : "Ask a research question…"}
            rows={4}
            disabled={isRunning}
            className="w-full resize-none rounded-md bg-transparent px-3 pt-2.5 pb-9 text-[13.5px] leading-relaxed text-parchment placeholder:text-parchment-faint outline-none disabled:opacity-50"
          />
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.png,.jpg,.jpeg,.webp,.bmp,.tiff"
            className="hidden"
            onChange={(e) => handleFilesSelected(e.target.files)}
          />
          <div className="absolute bottom-2 left-2 flex items-center gap-1">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isRunning || uploading}
              title="Attach files (PDF, DOCX, image)"
              className="flex h-6 w-6 items-center justify-center rounded-md text-parchment-faint transition-colors hover:bg-ink-raised hover:text-parchment-dim disabled:opacity-40"
            >
              <Paperclip className="h-3.5 w-3.5" strokeWidth={1.75} />
            </button>
            <button
              type="button"
              onClick={toggleListening}
              disabled={isRunning || !voiceSupported}
              title={voiceSupported ? "Speak your question" : "Voice input not supported in this browser"}
              className={`flex h-6 w-6 items-center justify-center rounded-md transition-colors disabled:opacity-40 ${
                listening
                  ? "animate-pulseDot bg-signal-clayDim/30 text-signal-clay"
                  : "text-parchment-faint hover:bg-ink-raised hover:text-parchment-dim"
              }`}
            >
              {listening ? <MicOff className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
            </button>
          </div>
          {uploading && (
            <span className="absolute bottom-2 left-16 text-[10.5px] text-parchment-faint">Reading file…</span>
          )}
        </div>

        {uploadError && <p className="mt-1.5 text-[11.5px] text-signal-clay">{uploadError}</p>}
        {!voiceSupported && (
          <p className="mt-1.5 text-[11px] text-parchment-faint">
            Voice input isn't supported in this browser — try Chrome, Edge, or Safari.
          </p>
        )}

        {attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {attachments.map((a) => (
              <span
                key={a.filename}
                className="flex items-center gap-1.5 rounded-full border border-ink-lineStrong bg-ink-raised px-2.5 py-1 text-[11px] text-parchment-dim"
              >
                <FileText className="h-3 w-3 shrink-0 text-signal-amber" />
                <span className="max-w-[140px] truncate">{a.filename}</span>
                <button onClick={() => removeAttachment(a.filename)} className="text-parchment-faint hover:text-parchment">
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        <button
          onClick={submit}
          disabled={isRunning || !draft.trim()}
          className="mt-2.5 flex w-full items-center justify-center gap-1.5 rounded-md bg-signal-amber py-2 text-[13px] font-medium text-ink transition-colors hover:bg-[#eeb156] disabled:cursor-not-allowed disabled:bg-ink-raised disabled:text-parchment-faint"
        >
          <Send className="h-4 w-4" strokeWidth={2} />
          {isRunning ? "Researching…" : "Send"}
        </button>
      </div>

      <div className="mt-6 flex-1 overflow-y-auto border-t border-ink-line px-5 pt-4">
        <div className="mb-2 text-[11px] font-medium text-parchment-faint">Session history</div>
        <div className="flex flex-col gap-1">
          {sessions.length === 0 && (
            <p className="text-[12.5px] text-parchment-faint">No sessions yet — your research runs will appear here.</p>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => onSelectSession(s.id)}
              className={`group flex cursor-pointer items-start justify-between gap-1 rounded-md px-2.5 py-2 text-left transition-colors ${
                activeSessionId === s.id ? "bg-ink-raised" : "hover:bg-ink-raised/60"
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  {s.pinned ? <Pin className="h-3 w-3 shrink-0 text-signal-amber" /> : null}
                  <div className="truncate text-[12.5px] text-parchment-dim">{s.custom_title || s.query}</div>
                </div>
                <div className="mt-0.5 flex items-center gap-2 font-mono text-[10.5px] text-parchment-faint">
                  <span>conf {(s.confidence * 100).toFixed(0)}%</span>
                  <span>·</span>
                  <span>{s.num_sources} src</span>
                </div>
              </div>
              <SessionMenu session={s} onChanged={onSessionsChanged} />
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}

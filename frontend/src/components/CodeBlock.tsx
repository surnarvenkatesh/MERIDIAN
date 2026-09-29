import { useState, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";

// react-markdown hands the <pre> component's children as React nodes (the
// nested <code> element with the actual text inside it). To copy the real
// code text we need to walk that tree and pull out plain strings.
function extractText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (node && typeof node === "object" && "props" in node) {
    return extractText((node as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

export default function CodeBlock({ children }: { children: ReactNode }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(extractText(children).replace(/\n$/, ""));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="group/code relative mb-3">
      <pre className="overflow-x-auto rounded-md border border-ink-line bg-ink px-4 py-3 text-[12.5px] leading-relaxed">
        {children}
      </pre>
      <button
        onClick={handleCopy}
        title="Copy code"
        className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded text-parchment-faint opacity-0 transition-opacity hover:bg-ink-raised hover:text-parchment-dim group-hover/code:opacity-100"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-signal-teal" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

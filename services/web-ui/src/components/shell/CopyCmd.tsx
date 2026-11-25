"use client";
import { Check, Copy } from "lucide-react";
import { useState } from "react";
import "./settings.css";

/** A shell command on a ruled line with a copy button; announces the copy politely. */
export function CopyCmd({ cmd }: { cmd: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(cmd).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }, () => undefined);
  };
  return (
    <span className="cmd">
      <span className="cmd-prompt rec" aria-hidden>$</span>
      <code>{cmd}</code>
      <button type="button" className="btn btn-ghost btn-sm" onClick={copy} aria-label={`Copy ${cmd}`}>
        {copied ? <Check size={16} aria-hidden /> : <Copy size={16} aria-hidden />}
        <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
      </button>
    </span>
  );
}

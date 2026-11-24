"use client";
import { ChevronRight } from "lucide-react";
import { useState } from "react";

export function Thinking({ text, live }: { text: string; live: boolean }) {
  const [open, setOpen] = useState<boolean | null>(null);
  const expanded = open ?? live;
  return (
    <div className="thinking" data-live={live}>
      <button type="button" className="disclosure" aria-expanded={expanded} onClick={() => setOpen(!expanded)}>
        <ChevronRight size={14} aria-hidden className="chev" />
        <span>{live ? "Thinking" : "Thought"}</span>
        {!expanded && <span className="muted">{text.length.toLocaleString("en")} chars</span>}
      </button>
      {expanded && <div className="thinking-body">{text}</div>}
    </div>
  );
}

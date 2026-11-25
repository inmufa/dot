"use client";
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { useApp } from "@/lib/state/app";
import "./Thinking.css";

interface Props {
  text: string;
  live: boolean;
  startedAt?: number;
  ms?: number;
}

const secs = (n: number): string => (n < 60 ? `${n}s` : `${Math.floor(n / 60)}m ${n % 60}s`);

/** A muted line: "Thinking 12s" while streaming, "Thought for 12s" after. Click expands the text. */
export function Thinking({ text, live, startedAt, ms }: Props) {
  const { settings } = useApp();
  const [open, setOpen] = useState<boolean | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!live) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [live]);
  const expanded = open ?? (settings.verbose || (live && settings.showThinking));
  const s = startedAt !== undefined ? Math.max(0, Math.round((now - startedAt) / 1000)) : null;
  const label = live ? `Thinking${s !== null ? ` ${secs(s)}` : ""}` : ms === undefined ? "Thought" : `Thought for ${secs(Math.max(1, Math.round(ms / 1000)))}`;
  return (
    <div className="think" data-live={live}>
      <button type="button" className="think-pill press" aria-expanded={expanded} onClick={() => setOpen(!expanded)}>
        <span className="think-label">{label}</span>
        <ChevronRight size={12} aria-hidden className="chev" />
      </button>
      {expanded && <div className="thinking-body anim-fade" tabIndex={0}>{text}</div>}
    </div>
  );
}

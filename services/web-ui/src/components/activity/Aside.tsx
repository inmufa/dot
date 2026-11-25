"use client";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { compactTokens } from "@/lib/util/format";
import type { Item } from "@/lib/stream/reducer";
import { Markdown } from "@/components/chat/Markdown";

/** Compaction as one mono log line: "context compacted 12.1k to 4.3k". */
export function CompactionLine({ c }: { c: Extract<Item, { kind: "compaction" }> }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="cmp rec" role="separator" aria-label="Context compacted">
      {c.summary ? (
        <button type="button" className="cmp-btn rec" aria-expanded={open} onClick={() => setOpen(!open)}>
          <ChevronRight size={12} aria-hidden className="chev" /> earlier context summarized
        </button>
      ) : (
        <span>context compacted</span>
      )}
      {c.before > 0 && (
        <span>
          {compactTokens(c.before)} <span aria-hidden>{"->"}</span><span className="sr-only"> to </span> {compactTokens(c.after)}
        </span>
      )}
      {open && c.summary && (
        <div className="cmp-body anim-fade">
          <Markdown text={c.summary} settled />
        </div>
      )}
    </div>
  );
}

export function PlanBlock({ text }: { text: string }) {
  return (
    <section className="plan" aria-label="Plan">
      <h3 className="plan-title rec">plan</h3>
      <div className="plan-text" tabIndex={0} role="region" aria-label="Plan text">
        <Markdown text={text} settled />
      </div>
    </section>
  );
}

const QSTATE = { open: "waiting for you", answered: "answered", expired: "timed out", closed: "not answered" } as const;

export function QuestionLine({ q }: { q: Extract<Item, { kind: "question" }> }) {
  return (
    <div className="qline">
      <span className="qline-text" dir="auto">{q.text}</span>
      <span className="rec qline-state">{q.status === "answered" && q.answer ? `answered: ${q.answer}` : QSTATE[q.status]}</span>
    </div>
  );
}

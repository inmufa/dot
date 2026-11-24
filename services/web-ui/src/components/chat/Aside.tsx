"use client";
import { ArrowRight, ChevronRight, HelpCircle, ListChecks } from "lucide-react";
import { useState } from "react";
import { compactTokens } from "@/lib/format";
import type { Item } from "@/lib/stream/reducer";
import { Markdown } from "./Markdown";

/** Quiet transcript items that are not messages: compaction dividers, plan blocks, answered questions. */
export function CompactionDivider({ c }: { c: Extract<Item, { kind: "compaction" }> }) {
  const [open, setOpen] = useState(false);
  const known = c.before > 0;
  return (
    <div className="divider" role="separator" aria-label="Context compacted">
      <span className="divider-rule" aria-hidden />
      {c.summary ? (
        <button type="button" className="divider-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
          <ChevronRight size={12} aria-hidden className="chev" />
          Earlier context summarized
        </button>
      ) : (
        <span className="divider-text">
          Context compacted
          {known && (
            <>
              {" "}
              <span className="num">{compactTokens(c.before)}</span> <ArrowRight size={12} aria-hidden className="divider-arrow" />
              <span className="sr-only"> to </span> <span className="num">{compactTokens(c.after)}</span>
            </>
          )}
        </span>
      )}
      <span className="divider-rule" aria-hidden />
      {open && c.summary && (
        <div className="divider-body">
          <Markdown text={c.summary} settled />
        </div>
      )}
    </div>
  );
}

export function PlanBlock({ text }: { text: string }) {
  return (
    <section className="plan" aria-label="Plan">
      <h3 className="plan-title"><ListChecks size={14} aria-hidden /> Plan</h3>
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
      <HelpCircle size={14} aria-hidden />
      <span className="qline-text" dir="auto">{q.text}</span>
      <span className="muted qline-state">
        {q.status === "answered" && q.answer ? `answered: ${q.answer}` : QSTATE[q.status]}
      </span>
    </div>
  );
}

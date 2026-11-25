"use client";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { clip } from "@/lib/util/format";
import type { Item, SubagentState } from "@/lib/stream/reducer";

type Sub = Extract<Item, { kind: "subagent" }>;
const WORD: Record<SubagentState, string> = { queued: "queued", running: "working", done: "finished", error: "failed", cancelled: "cancelled" };

export function SubagentLine({ sub }: { sub: Sub }) {
  const [open, setOpen] = useState(false);
  const last = sub.steps[sub.steps.length - 1];
  return (
    <div className="sub" data-status={sub.status}>
      <button type="button" className="sub-row" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="sub-label">{clip(sub.label, 40)}</span>
        <span className="sub-meta rec">
          {WORD[sub.status]}
          {sub.status === "running" && last ? ` - ${clip(last, 28)}` : ""}
          {sub.stepCount > 0 ? ` - ${sub.stepCount} ${sub.stepCount === 1 ? "step" : "steps"}` : ""}
        </span>
        <ChevronRight size={14} aria-hidden className="chev" />
      </button>
      {open && (
        <div className="sub-detail">
          {sub.steps.length === 0 ? (
            <p className="muted">No tool calls yet.</p>
          ) : (
            <ol className="sub-steps" aria-label={`Tools used by ${sub.label}`}>
              {sub.steps.map((t, i) => (
                <li key={i} className="sub-step rec">{clip(t, 40)}</li>
              ))}
            </ol>
          )}
          {sub.stepCount > sub.steps.length && <p className="muted">Showing the last {sub.steps.length} of {sub.stepCount}.</p>}
        </div>
      )}
    </div>
  );
}

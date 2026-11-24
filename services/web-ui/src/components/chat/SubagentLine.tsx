"use client";
import { AlertCircle, Check, ChevronRight, Clock, LoaderCircle, Slash } from "lucide-react";
import { useState } from "react";
import { clip } from "@/lib/format";
import type { Item, SubagentState } from "@/lib/stream/reducer";

type Sub = Extract<Item, { kind: "subagent" }>;
const WORD: Record<SubagentState, string> = { queued: "queued", running: "working", done: "finished", error: "failed", cancelled: "cancelled" };
const ICON = { queued: Clock, running: LoaderCircle, done: Check, error: AlertCircle, cancelled: Slash } as const;

export function SubagentLine({ sub }: { sub: Sub }) {
  const [open, setOpen] = useState(false);
  const Icon = ICON[sub.status];
  const last = sub.steps[sub.steps.length - 1];
  return (
    <div className="sub" data-status={sub.status}>
      <button type="button" className="sub-row" aria-expanded={open} onClick={() => setOpen(!open)}>
        <ChevronRight size={14} aria-hidden className="chev" />
        <Icon size={14} aria-hidden className={sub.status === "running" ? "spin sub-ico" : "sub-ico"} />
        <span className="sub-label">{clip(sub.label, 40)}</span>
        <span className="sub-meta">
          {WORD[sub.status]}
          {sub.status === "running" && last ? ` - ${clip(last, 28)}` : ""}
          {sub.stepCount > 0 ? ` - ${sub.stepCount} ${sub.stepCount === 1 ? "step" : "steps"}` : ""}
        </span>
      </button>
      {open && (
        <div className="sub-detail">
          {sub.steps.length === 0 ? (
            <p className="muted">No tool calls yet.</p>
          ) : (
            <ol className="sub-steps" aria-label={`Tools used by ${sub.label}`}>
              {sub.steps.map((t, i) => (
                <li key={i} className="badge">{clip(t, 40)}</li>
              ))}
            </ol>
          )}
          {sub.stepCount > sub.steps.length && <p className="muted">Showing the last {sub.steps.length} of {sub.stepCount}.</p>}
        </div>
      )}
    </div>
  );
}

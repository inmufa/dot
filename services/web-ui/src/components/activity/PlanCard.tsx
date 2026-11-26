"use client";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/chat/Markdown";
import { Button, IconButton, Kbd, StateDot, Textarea } from "@/components/ui";
import type { Approval } from "@/lib/stream/reducer";
import type { Decision } from "@/lib/state/types";
import { PendRail } from "./PendParts";

export const AUTO_MS = 10_000;

/** Plan approval. A research plan shows in full, can be edited, and starts itself after 10 s unless cancelled or edited. */
export function PlanCard({ approval, onDecide, research }: { approval: Approval; onDecide: (d: Decision, note?: string) => void; research: boolean }) {
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState("");
  const [auto, setAuto] = useState(research);
  const [sent, setSent] = useState(false);
  const card = useRef<HTMLDivElement>(null);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const send = (d: Decision, n?: string) => { if (sent) return; setSent(true); onDecide(d, n); };

  useEffect(() => { card.current?.focus(); }, [approval.id]);
  useEffect(() => { if (editing) noteRef.current?.focus(); }, [editing]);
  useEffect(() => {
    if (!auto || editing) return;
    const t = window.setTimeout(() => send("allow"), AUTO_MS);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- send is stable enough for a one-shot timer
  }, [auto, editing, approval.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat || (e.target as HTMLElement).closest("input, textarea")) return;
      if (e.key === "a") { e.preventDefault(); send("allow"); }
      else if (e.key === "e") { e.preventDefault(); setEditing(true); setAuto(false); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sent]);

  const title = research ? "Research plan" : "Plan ready for approval";
  const counting = auto && !editing && !sent;
  return (
    <div className="pend approval plan-card" ref={card} tabIndex={-1} role="alertdialog" aria-labelledby="pc-title">
      <PendRail />
      <div className="pend-body">
        <div className="approval-head">
          <span className="pend-inline"><StateDot state="waiting" /></span>
          <h2 id="pc-title">{title}</h2>
        </div>
        <div className="plan-body plan-full" role="region" aria-label="Proposed plan" tabIndex={0}>
          <Markdown text={approval.diff ?? ""} settled />
        </div>
        {editing && (
          <div className="plan-edit">
            <Textarea ref={noteRef} rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What should change? e.g. focus on EU salaries, skip crypto" aria-label="Changes to the plan" />
            <div className="plan-edit-row">
              <Button variant="ghost" size="sm" onClick={() => { setEditing(false); setNote(""); }}>Cancel</Button>
              <Button size="sm" variant="solid" aria-disabled={!note.trim() || sent} onClick={() => note.trim() && send("reject", note.trim())}>Update plan</Button>
            </div>
          </div>
        )}
        {!editing && (
          <div className="approval-actions plan-actions">
            {!research && <Button variant="ghost" className="ap-reject" onClick={() => send("reject")}>Keep planning</Button>}
            <Button variant="ghost" onClick={() => { setEditing(true); setAuto(false); }}>Edit plan <Kbd>e</Kbd></Button>
            <span className="plan-go" data-counting={counting || undefined}>
              <Button variant="solid" className="plan-start" onClick={() => send("allow")} aria-disabled={sent}>
                {counting && <span className="plan-fill" aria-hidden style={{ animationDuration: `${AUTO_MS}ms` }} />}
                <span className="arm-label">{research ? "Start research" : "Approve plan"} <Kbd>a</Kbd></span>
              </Button>
              {counting && <IconButton size="sm" label="Cancel auto start" className="plan-stop" onClick={() => setAuto(false)}><X size={16} aria-hidden /></IconButton>}
            </span>
          </div>
        )}
        <span className="sr-only" role="status">{counting ? "Research starts automatically in 10 seconds." : ""}</span>
      </div>
    </div>
  );
}

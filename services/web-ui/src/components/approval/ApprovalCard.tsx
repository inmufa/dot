"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { shortArgs } from "@/lib/format";
import type { Approval } from "@/lib/stream/reducer";
import { Markdown } from "../chat/Markdown";
import { StateDot } from "../ui/StateDot";
import { DiffView } from "./DiffView";
import { VerdictBadge } from "./VerdictBadge";

export type Decision = "allow" | "always" | "reject";
export const ARM_MS = 700;

interface Action {
  key: string;
  decision: Decision;
  label: string;
  primary?: boolean;
}

const ACTIONS: Action[] = [
  { key: "r", decision: "reject", label: "Reject" },
  { key: "s", decision: "always", label: "Allow for session" },
  { key: "a", decision: "allow", label: "Allow once", primary: true },
];
const PLAN_ACTIONS: Action[] = [
  { key: "r", decision: "reject", label: "Keep planning" },
  { key: "a", decision: "allow", label: "Approve plan", primary: true },
];

export function ApprovalCard({ approval, onDecide }: { approval: Approval; onDecide: (d: Decision) => void }) {
  const [armed, setArmed] = useState(false);
  const [sent, setSent] = useState(false);
  const card = useRef<HTMLDivElement>(null);
  const { invocation: inv } = approval;
  const command = typeof inv.arguments.command === "string" ? inv.arguments.command : null;
  const isPlan = inv.name === "ExitPlanMode" && approval.diff !== null;
  const actions = isPlan ? PLAN_ACTIONS : ACTIONS;

  useEffect(() => {
    setArmed(false);
    setSent(false);
    card.current?.focus();
    const t = window.setTimeout(() => setArmed(true), ARM_MS);
    return () => window.clearTimeout(t);
  }, [approval.id]);

  const decide = useCallback(
    (d: Decision) => {
      // Reject is always immediate; only the variants that let something run wait for the arming delay.
      if (sent || (!armed && d !== "reject")) return;
      setSent(true);
      onDecide(d);
    },
    [armed, sent, onDecide],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
      const a = actions.find((x) => x.key === e.key.toLowerCase());
      if (!a) return;
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, select, [contenteditable]")) return;
      e.preventDefault();
      decide(a.decision);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide, actions]);

  return (
    <div className="approval" ref={card} tabIndex={-1} role="alertdialog" aria-labelledby="ap-title" aria-describedby="ap-desc" data-verdict={approval.verdict?.decision}>
      <div className="approval-head">
        <StateDot state="waiting" />
        <h2 id="ap-title">{isPlan ? "Plan ready for approval" : "Approval needed"}</h2>
        {approval.subagent && <span className="badge" title="This request comes from a subagent">from {approval.subagent}</span>}
        {approval.verdict && <VerdictBadge verdict={approval.verdict} />}
      </div>
      <p className="approval-call" id="ap-desc">
        <strong>{inv.name}</strong> <span className="muted">{command || isPlan ? "" : shortArgs(inv.arguments, 140)}</span>
      </p>
      {command && <pre className="approval-cmd" tabIndex={0}>{command}</pre>}
      {approval.verdict?.reason && <p className="approval-reason muted">{approval.verdict.reason}</p>}
      {approval.diff && (isPlan ? <div className="plan-body" role="region" aria-label="Proposed plan" tabIndex={0}><Markdown text={approval.diff} settled /></div> : <DiffView diff={approval.diff} />)}
      <div className="approval-actions">
        {actions.map((a) => {
          const gated = a.decision !== "reject";
          return (
            <button
              key={a.key}
              type="button"
              className={a.primary ? "btn btn-primary" : "btn"}
              data-arming={gated && !armed && !sent ? "true" : undefined}
              aria-disabled={sent || (gated && !armed)}
              onClick={() => decide(a.decision)}
            >
              {gated && <span className="arm-fill" aria-hidden />}
              <span className="arm-label">{a.label} <kbd>{a.key}</kbd></span>
            </button>
          );
        })}
        <span className="sr-only" role="status">{armed ? "Allow keys are active." : "Allow keys activate in a moment. Reject works now."}</span>
      </div>
    </div>
  );
}

"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { shortArgs } from "@/lib/util/format";
import type { Approval } from "@/lib/stream/reducer";
import { Markdown } from "@/components/chat/Markdown";
import { Badge, Button, Kbd, StateDot } from "@/components/ui";
import { PendRail } from "./PendParts";
import { PlanCard } from "./PlanCard";
import { DiffView } from "./DiffView";
import { VerdictBadge } from "./VerdictBadge";

export type Decision = "allow" | "always" | "reject";
export const ARM_MS = 700;

interface Action {
  key: string;
  decision: Decision;
  label: string;
  short?: string;
  primary?: boolean;
}

const ACTIONS: Action[] = [
  { key: "r", decision: "reject", label: "Reject" },
  { key: "s", decision: "always", label: "Allow for session", short: "For session" },
  { key: "a", decision: "allow", label: "Allow once", primary: true },
];
/** BrowserLogin: "always" covers this saved login for this chat only; there is no permanent allow. */
const LOGIN_ACTIONS: Action[] = [
  { key: "r", decision: "reject", label: "Reject" },
  { key: "s", decision: "always", label: "Allow for this session", short: "This session" },
  { key: "a", decision: "allow", label: "Allow once", primary: true },
];
const PLAN_ACTIONS: Action[] = [
  { key: "r", decision: "reject", label: "Keep planning" },
  { key: "a", decision: "allow", label: "Approve plan", primary: true },
];

export function ApprovalCard({ approval, onDecide, research = false }: { approval: Approval; onDecide: (d: Decision, note?: string) => void; research?: boolean }) {
  if (approval.invocation.name === "ExitPlanMode" && approval.diff !== null) return <PlanCard approval={approval} onDecide={onDecide} research={research} />;
  return <ToolApprovalCard approval={approval} onDecide={onDecide} />;
}

function ToolApprovalCard({ approval, onDecide }: { approval: Approval; onDecide: (d: Decision) => void }) {
  const [armed, setArmed] = useState(false);
  const [sent, setSent] = useState(false);
  const card = useRef<HTMLDivElement>(null);
  const { invocation: inv } = approval;
  const command = typeof inv.arguments.command === "string" ? inv.arguments.command : null;
  const isPlan = inv.name === "ExitPlanMode" && approval.diff !== null;
  const isLogin = inv.name === "BrowserLogin";
  const actions = isPlan ? PLAN_ACTIONS : isLogin ? LOGIN_ACTIONS : ACTIONS;

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
    <div className="pend approval" ref={card} tabIndex={-1} role="alertdialog" aria-labelledby="ap-title" aria-describedby="ap-desc" data-verdict={approval.verdict?.decision}>
      <PendRail />
      <div className="pend-body">
      <div className="approval-head">
        <span className="pend-inline"><StateDot state="waiting" /></span>
        <h2 id="ap-title">{isPlan ? "Plan ready for approval" : isLogin ? "Sign in with a saved login?" : "Approval needed"}</h2>
        {approval.subagent && <Badge title="This request comes from a subagent">from {approval.subagent}</Badge>}
        {approval.verdict && <VerdictBadge verdict={approval.verdict} />}
      </div>
      {!isPlan && (<p className="approval-call" id="ap-desc">
        <strong>{inv.name}</strong> <span className="muted">{command ? "" : shortArgs(inv.arguments, 140)}</span>
      </p>)}
      {command && <pre className="approval-cmd" tabIndex={0}>{command}</pre>}
      {approval.verdict?.reason && <p className="approval-reason muted">{approval.verdict.reason}</p>}
      {isLogin && (approval.diff
        ? <pre className="approval-cmd approval-login" tabIndex={0}>{approval.diff}</pre>
        : null)}
      {isLogin && <p className="approval-reason muted">The backend types the stored password; the model never sees it. &quot;This session&quot; covers this login in this chat only, nothing is remembered after.</p>}
      {approval.diff && !isLogin && (isPlan ? <div className="plan-body" role="region" aria-label="Proposed plan" tabIndex={0}><Markdown text={approval.diff} settled /></div> : <DiffView diff={approval.diff} />)}
      <div className="approval-actions">
        {actions.map((a) => {
          const gated = a.decision !== "reject";
          return (
            <Button
              key={a.key}
              className={a.decision === "reject" ? "ap-reject" : undefined}
              variant={a.primary ? "solid" : a.decision === "reject" ? "ghost" : "soft"}
              data-arming={gated && !armed && !sent ? "true" : undefined}
              aria-disabled={sent || (gated && !armed)}
              onClick={() => decide(a.decision)}
            >
              {gated && <span className="arm-fill" aria-hidden />}
              <span className="arm-label">{a.short ? <><span className="lbl-long">{a.label}</span><span className="lbl-short">{a.short}</span></> : a.label} <Kbd>{a.key}</Kbd></span>
            </Button>
          );
        })}
        <span className="sr-only" role="status">{armed ? "Allow keys are active." : "Allow keys activate in a moment. Reject works now."}</span>
      </div>
      </div>
    </div>
  );
}

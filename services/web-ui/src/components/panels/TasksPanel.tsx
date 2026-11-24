"use client";
import { Check, CircleDashed, LoaderCircle, RefreshCw } from "lucide-react";
import { useMemo } from "react";
import { useResource } from "@/hooks/useResource";
import { api, type TaskInfo } from "@/lib/api/client";
import { clip } from "@/lib/format";
import { Sheet } from "../ui/Sheet";
import { ErrorBox, Skeletons, StateBox } from "../ui/StateBox";

const ICON = { pending: CircleDashed, in_progress: LoaderCircle, completed: Check } as const;
const WORD = { pending: "pending", in_progress: "in progress", completed: "done" } as const;

function Task({ t, byId }: { t: TaskInfo; byId: Map<string, TaskInfo> }) {
  const Icon = ICON[t.status];
  const open = t.blocked_by.filter((b) => byId.get(b)?.status !== "completed");
  const blocked = t.status === "pending" && open.length > 0;
  return (
    <li className="row task" data-status={t.status} data-blocked={blocked}>
      <div className="row-main">
        <Icon size={14} aria-hidden className={t.status === "in_progress" ? "spin task-ico" : "task-ico"} />
        <span className="mono muted task-id">{t.id}</span>
        <span className="row-title" dir="auto">{clip(t.subject, 160)}</span>
      </div>
      <div className="chips">
        <span className="badge" data-tone={t.status === "completed" ? "ok" : t.status === "in_progress" ? "ask" : undefined}>{WORD[t.status]}</span>
        {blocked && <span className="badge" data-tone="warn">blocked</span>}
        {t.blocked_by.map((b) => {
          const done = byId.get(b)?.status === "completed";
          return (
            <span key={b} className="badge chip" data-done={done} title={byId.get(b)?.subject ?? "Unknown task"}>
              after {b}
              <span className="sr-only">{done ? " (done)" : " (open)"}</span>
            </span>
          );
        })}
      </div>
      {t.description && <p className="row-desc muted" dir="auto">{clip(t.description, 400)}</p>}
    </li>
  );
}

export function TasksPanel({ open, onClose, sessionId, running }: { open: boolean; onClose: () => void; sessionId: string | null; running: boolean }) {
  const r = useResource(() => (sessionId ? api.tasks(sessionId) : Promise.resolve([] as TaskInfo[])), open, running ? 4000 : 0);
  const byId = useMemo(() => new Map((r.data ?? []).map((t) => [t.id, t])), [r.data]);
  const count = (s: TaskInfo["status"]) => (r.data ?? []).filter((t) => t.status === s).length;
  return (
    <Sheet open={open} onClose={onClose} title="Tasks">
      {r.error ? (
        <ErrorBox error={r.error} onRetry={r.reload} />
      ) : !r.data ? (
        <Skeletons />
      ) : r.data.length === 0 ? (
        <StateBox title="No tasks in this session">When Dot plans a multi-step job it lists the steps here, with what blocks what.</StateBox>
      ) : (
        <>
          <div className="panel-bar">
            <p className="help-text">
              {r.data.length} tasks: {count("in_progress")} in progress, {count("pending")} pending, {count("completed")} done.
            </p>
            <button type="button" className="btn btn-sm btn-ghost" onClick={r.reload} aria-label="Refresh tasks"><RefreshCw size={14} aria-hidden /></button>
          </div>
          <ul className="rows">{r.data.map((t) => <Task key={t.id} t={t} byId={byId} />)}</ul>
        </>
      )}
    </Sheet>
  );
}

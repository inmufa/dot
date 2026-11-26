"use client";
import { RefreshCw } from "lucide-react";
import { useMemo } from "react";
import { Entry, IconButton, Progress, Sheet } from "@/components/ui";
import { ErrorBox } from "@/components/ui/StateBox";
import { useResource } from "@/hooks/useResource";
import { api, type TaskInfo } from "@/lib/api/client";
import { clip } from "@/lib/util/format";
import { Empty, Loading, Meta, PanelBar, Status } from "./parts";

const WORD = { pending: "pending", in_progress: "in progress", completed: "done" } as const;
const TONE = { pending: "idle", in_progress: "info", completed: "ok" } as const;

function Task({ t, byId, i }: { t: TaskInfo; byId: Map<string, TaskInfo>; i: number }) {
  const blocked = t.status === "pending" && t.blocked_by.some((b) => byId.get(b)?.status !== "completed");
  return (
    <Entry time={`#${t.id}`} state={t.status === "in_progress" ? "thinking" : undefined} i={Math.min(i, 6)} className="pn-entry">
      <div className="pn-body" data-done={t.status === "completed"} data-status={t.status}>
        <span className="pn-title" dir="auto" title={t.subject}>{clip(t.subject, 160)}</span>
        <Status tone={blocked ? "warn" : TONE[t.status]}>{blocked ? "blocked" : WORD[t.status]}</Status>
        <Meta
          items={t.blocked_by.map((b) => {
            const done = byId.get(b)?.status === "completed";
            return <span key={b} title={byId.get(b)?.subject ?? "Unknown task"}>after #{b}<span className="sr-only">{done ? " (done)" : " (open)"}</span></span>;
          })}
        />
        {t.description && <p className="pn-desc" dir="auto">{clip(t.description, 400)}</p>}
      </div>
    </Entry>
  );
}

/** Task log body; shared by the side panel and any inline host. */
export function TasksBody({ sessionId, running, enabled }: { sessionId: string | null; running: boolean; enabled: boolean }) {
  const r = useResource(() => (sessionId ? api.tasks(sessionId) : Promise.resolve([] as TaskInfo[])), enabled, running ? 4000 : 0, sessionId ?? "");
  const byId = useMemo(() => new Map((r.data ?? []).map((t) => [t.id, t])), [r.data]);
  if (r.error && !r.data) return <ErrorBox error={r.error} onRetry={r.reload} />;
  if (!r.data) return <Loading />;
  if (!sessionId || r.data.length === 0) return <Empty title="Nothing planned yet.">{sessionId ? "On a long job Dot writes its steps here and ticks them off." : "Open a chat to see its steps."}</Empty>;
  const done = r.data.filter((t) => t.status === "completed").length;
  const live = r.data.filter((t) => t.status === "in_progress").length;
  return (
    <>
      <PanelBar count={`${r.data.length} steps · ${live} running · ${done} done`}>
        <IconButton label="Refresh tasks" size="sm" onClick={r.reload}><RefreshCw size={16} aria-hidden /></IconButton>
      </PanelBar>
      <Progress label="Tasks done" value={done / r.data.length} tone={done === r.data.length ? "ok" : "accent"} />
      <div className="pn-log">{r.data.map((t, i) => <Task key={t.id} t={t} byId={byId} i={i} />)}</div>
    </>
  );
}

export function TasksPanel({ open, onClose, sessionId, running }: { open: boolean; onClose: () => void; sessionId: string | null; running: boolean }) {
  return (
    <Sheet open={open} onClose={onClose} title="Tasks" description="The steps Dot planned for this chat and where each one stands.">
      <TasksBody sessionId={sessionId} running={running} enabled={open} />
    </Sheet>
  );
}

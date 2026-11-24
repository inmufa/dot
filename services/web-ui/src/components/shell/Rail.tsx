"use client";
import { BookOpen, Brain, CalendarClock, ListChecks, Plug, Plus, ScrollText, Search, Settings, Wrench } from "lucide-react";
import { useMemo, useState } from "react";
import type { SessionInfo } from "@/lib/api/client";
import type { DotErrorInfo } from "@/lib/api/errors";
import { relativeTime, sessionTitle } from "@/lib/format";
import type { DotPhase } from "@/lib/stream/reducer";
import { ErrorBox, Skeletons, StateBox } from "../ui/StateBox";
import { StateDot } from "../ui/StateDot";

export type PanelId = "skills" | "audit" | "rewind" | "tasks" | "memory" | "mcp" | "schedules" | "tools" | "settings";

interface Props {
  open: boolean;
  sessions: SessionInfo[];
  loading: boolean;
  error: DotErrorInfo | null;
  activeId: string | null;
  phases: Record<string, DotPhase>;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRetry: () => void;
  onPanel: (p: PanelId) => void;
  onClose: () => void;
}

const LINKS: { id: PanelId; label: string; Icon: typeof Brain }[] = [
  { id: "tasks", label: "Tasks", Icon: ListChecks },
  { id: "memory", label: "Memory", Icon: Brain },
  { id: "skills", label: "Skills", Icon: BookOpen },
  { id: "tools", label: "Tools", Icon: Wrench },
  { id: "mcp", label: "MCP", Icon: Plug },
  { id: "schedules", label: "Schedules", Icon: CalendarClock },
  { id: "audit", label: "Audit log", Icon: ScrollText },
  { id: "settings", label: "Settings", Icon: Settings },
];

export function Rail(p: Props) {
  const [q, setQ] = useState("");
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return needle ? p.sessions.filter((s) => sessionTitle(s.title).toLowerCase().includes(needle)) : p.sessions;
  }, [p.sessions, q]);

  return (
    <aside className="rail" data-open={p.open} aria-label="Sessions">
      <div className="rail-head">
        <img className="brand brand-light" src="/lockup-horizontal-color-darktile.svg" alt="Dot" width={112} height={32} />
        <img className="brand brand-dark" src="/lockup-horizontal-color-lighttile.svg" alt="Dot" width={112} height={32} />
      </div>
      <div className="rail-actions">
        <button type="button" className="btn rail-new" onClick={p.onNew}>
          <Plus size={16} aria-hidden /> New session
        </button>
      </div>
      {p.sessions.length > 8 && (
        <div className="rail-search">
          <Search size={14} aria-hidden />
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter sessions" aria-label="Filter sessions" />
        </div>
      )}
      <div className="rail-list">
        {p.loading ? (
          <Skeletons n={6} />
        ) : p.error && p.sessions.length === 0 ? (
          <ErrorBox error={p.error} onRetry={p.onRetry} />
        ) : p.sessions.length === 0 ? (
          <StateBox title="No sessions yet">Start one to give Dot a task.</StateBox>
        ) : shown.length === 0 ? (
          <StateBox title="No match">Nothing named like that.</StateBox>
        ) : (
          <ul>
            {shown.map((s) => {
              const phase = p.phases[s.id] ?? "idle";
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    className="session"
                    aria-current={s.id === p.activeId ? "true" : undefined}
                    onClick={() => p.onSelect(s.id)}
                  >
                    <StateDot state={phase} />
                    <span className="session-title">{sessionTitle(s.title)}</span>
                    <span className="session-time">{relativeTime(s.created_at)}</span>
                    {phase !== "idle" && <span className="sr-only">{phase === "waiting" ? "Needs approval" : "Thinking"}</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <nav className="rail-foot" aria-label="Tools">
        {LINKS.map(({ id, label, Icon }) => (
          <button key={id} type="button" className="rail-link" onClick={() => p.onPanel(id)}>
            <Icon size={16} aria-hidden /> {label}
          </button>
        ))}
      </nav>
    </aside>
  );
}

"use client";
import { ChevronRight, PanelLeftClose, Search, SquarePen, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import "./Sidebar.css";
import { MORE, NAV } from "./AccountMenu";
import { SessionRow } from "./SessionRow";
import { SidebarRail } from "./SidebarRail";
import { SidebarResize } from "./SidebarResize";
import { ErrorBox, IconButton, Kbd, ListRow, Mark, Skeletons, StateBox, useToast } from "@/components/ui";
import { api, type ProjectInfo } from "@/lib/api/client";
import { feature, useCap } from "@/lib/api/caps";
import type { PanelId } from "@/lib/commands/runner";
import { playSound } from "@/lib/sound/engine";
import { useApp } from "@/lib/state/app";
import type { DotPhase } from "@/lib/stream/reducer";
import { groupByDay } from "@/lib/util/days";
import { GROUP_LABEL } from "@/lib/util/indexTime";

export type { PanelId } from "@/lib/commands/runner";

const STATE_PHASE = { idle: "idle", running: "thinking", waiting: "waiting" } as const;

function useProjects(up: boolean): ProjectInfo[] {
  const on = useCap("projects");
  const [list, setList] = useState<ProjectInfo[]>([]);
  useEffect(() => {
    if (!up || !on) return;
    void feature("projects", api.projects).then((p) => p && setList(p), () => undefined);
  }, [up, on]);
  return list;
}

export function Sidebar() {
  const { S, phases, ui, conn, composer } = useApp();
  const toast = useToast();
  const rail = ui.sidebar === "rail";
  const pinOk = useCap("pin");
  const [projOpen, setProjOpen] = useState(false);
  const projects = useProjects(conn.link === "online" || conn.link === "degraded");
  // A chat joins the list with its first message: untitled (never used) ones stay out
  const groups = useMemo(() => groupByDay(S.sessions.filter((s) => s.title || s.pinned || (phases[s.id] && phases[s.id] !== "idle") || (s.state && s.state !== "idle"))), [S.sessions, phases]);
  const phaseOf = (id: string, st?: keyof typeof STATE_PHASE): DotPhase => phases[id] && phases[id] !== "idle" ? phases[id] : STATE_PHASE[st ?? "idle"];
  const close = () => ui.setDrawer(false);
  const fail = (e: { title: string } | null) => { if (e) toast({ title: e.title, tone: "bad" }); };
  const newChat = () => { playSound("newChat"); void S.create(); composer.current?.focus(); close(); };
  const search = (e: { detail: number }) => { if (e.detail > 0) document.documentElement.dataset.palettePointer = "1"; ui.openOverlay("palette"); close(); };
  const pick = (id: PanelId) => { ui.setPanel(id); close(); };
  const patch = (id: string, p: { title?: string; pinned?: boolean; archived?: boolean }) => {
    void S.patch(id, p).then((e) => {
      fail(e);
      if (!e && p.archived) toast({ title: "Archived.", action: { label: "Undo", onClick: () => void S.patch(id, { archived: false }).then(fail) } });
    });
  };

  return (
    <aside className="sb" data-mode={rail ? "rail" : "open"} aria-label="Chats and tools">
      {!rail && <SidebarResize />}
      <div className="sb-full">
        <div className="sb-head">
          <span className="sb-brand"><Mark size={24} /><span className="sb-brand-name">Dot</span></span>
          <IconButton label="Search (Ctrl K)" onClick={search}><Search size={18} aria-hidden /></IconButton>
          <IconButton className="sb-collapse" label="Collapse sidebar" onClick={ui.toggleSidebar}><PanelLeftClose size={18} aria-hidden /></IconButton>
          <IconButton className="sb-close" label="Close sidebar" onClick={close}><X size={18} aria-hidden /></IconButton>
        </div>
        <button type="button" className="sb-new" onClick={newChat}>
          <SquarePen size={16} aria-hidden /><span>New chat</span><Kbd>Ctrl Shift O</Kbd>
        </button>
        <nav className="sb-nav" aria-label="Workspace">
          {NAV.map(({ id, label, Icon }) => (
            <ListRow key={id} className="sb-navrow" lead={<Icon size={16} aria-hidden />} title={label} onSelect={() => pick(id)} />
          ))}
        </nav>

        {projects.length > 0 && (
          <section className="sb-projects" aria-label="Projects">
            <button type="button" className="sb-group sb-group-btn rec" aria-expanded={projOpen} onClick={() => setProjOpen((v) => !v)}>
              <ChevronRight size={12} aria-hidden data-open={projOpen} />projects <span>{projects.length}</span>
            </button>
            {projOpen && projects.map((p) => (
              <ListRow key={p.id} className="sb-projrow" title={<span dir="auto" title={`New chat in ${p.name}`}>{p.name}</span>} leader time={p.session_count} onSelect={() => { void S.create(undefined, p.id); close(); }} />
            ))}
          </section>
        )}

        <div className="sb-list">
          {S.loading ? (
            <Skeletons n={6} />
          ) : S.error && S.sessions.length === 0 ? (
            <ErrorBox error={S.error} onRetry={() => { void S.reload(); conn.recheck(); }} />
          ) : groups.length === 0 ? (
            <StateBox title="Nothing logged yet.">Your chats will list here.</StateBox>
          ) : (
            groups.map((g) => (
              <section key={g.bucket} aria-label={GROUP_LABEL[g.bucket]}>
                <h2 className="sb-group rec">{GROUP_LABEL[g.bucket]} <span>{g.items.length}</span></h2>
                <ul>
                  {g.items.map((s) => (
                    <SessionRow
                      key={s.id}
                      s={s}
                      phase={phaseOf(s.id, s.state)}
                      current={s.id === S.activeId}
                      actions={pinOk}
                      onSelect={() => { S.select(s.id); close(); }}
                      onPatch={(p) => patch(s.id, p)}
                      onDelete={() => void S.remove(s.id).then(fail)}
                    />
                  ))}
                </ul>
              </section>
            ))
          )}
        </div>

        <div className="sb-foot">
          <nav className="sb-foot-nav" aria-label="Settings and tools">
            {MORE.map(({ id, label, Icon }) => (
              <ListRow key={id} className="sb-navrow" lead={<Icon size={16} aria-hidden />} title={label} onSelect={() => pick(id)} />
            ))}
          </nav>
        </div>
      </div>
      <SidebarRail onNew={newChat} onSearch={search} onPick={pick} />
    </aside>
  );
}

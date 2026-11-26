"use client";
import { Check, ChevronRight, ListChecks, Minus, PanelLeftClose, Search, SquarePen, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import "./Sidebar.css";
import { LiveBuddy } from "@/components/buddy/LiveBuddy";
import { MORE, NAV } from "./AccountMenu";
import { SessionRow } from "./SessionRow";
import { SidebarRail } from "./SidebarRail";
import { SidebarResize } from "./SidebarResize";
import { Dialog, ErrorBox, IconButton, ListRow, Skeletons, StateBox, useToast } from "@/components/ui";
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
  const [selecting, setSelecting] = useState(false);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [bulkAsk, setBulkAsk] = useState(false);
  const visible = useMemo(() => groups.flatMap((g) => g.items.map((s) => s.id)), [groups]);
  const allOn = visible.length > 0 && visible.every((id) => picked.has(id));
  const stopSelecting = () => { setSelecting(false); setPicked(new Set()); };
  const toggle = (id: string) => setPicked((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const deleteBulk = async () => {
    setBulkAsk(false);
    const ids = [...picked];
    let failed = 0;
    for (const id of ids) { const e = await S.remove(id); if (e) failed += 1; }
    stopSelecting();
    toast({ title: failed ? `Deleted ${ids.length - failed}, ${failed} failed.` : `Deleted ${ids.length} ${ids.length === 1 ? "chat" : "chats"}.`, tone: failed ? "warn" : "neutral" });
  };
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
          <span className="sb-brand"><LiveBuddy size={28} /><span className="sb-brand-name">Dot</span></span>
          <IconButton label="Search (Ctrl K)" onClick={search}><Search size={18} aria-hidden /></IconButton>
          <IconButton className="sb-collapse" label="Collapse sidebar" onClick={ui.toggleSidebar}><PanelLeftClose size={18} aria-hidden /></IconButton>
          <IconButton className="sb-close" label="Close sidebar" onClick={close}><X size={18} aria-hidden /></IconButton>
        </div>
        <nav className="sb-nav" aria-label="Workspace">
          <ListRow className="sb-navrow sb-newrow" lead={<SquarePen size={16} aria-hidden />} title="New chat" time="Ctrl Shift O" onSelect={newChat} />
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

        {selecting ? (
          <div className="sb-bulk" role="toolbar" aria-label="Select chats">
            <button type="button" className="sb-bulk-all" onClick={() => setPicked(allOn ? new Set() : new Set(visible))} aria-label={allOn ? "Unselect all" : "Select all"}>
              <span className="sb-check" data-on={picked.size > 0 || undefined}>{allOn ? <Check size={12} strokeWidth={3} aria-hidden /> : picked.size > 0 ? <Minus size={12} strokeWidth={3} aria-hidden /> : null}</span>
              <span className="sb-bulk-label">{picked.size > 0 ? `${picked.size} selected` : "Select all"}</span>
            </button>
            <button type="button" className="sb-bulk-del" aria-disabled={picked.size === 0} onClick={() => picked.size > 0 && setBulkAsk(true)}><Trash2 size={14} aria-hidden /> Delete</button>
            <IconButton size="sm" label="Done selecting" onClick={stopSelecting}><X size={16} aria-hidden /></IconButton>
          </div>
        ) : groups.length > 0 && (
          <div className="sb-chats-head">
            <h2 className="sb-chats-title">Chats</h2>
            <button type="button" className="sb-select" onClick={() => setSelecting(true)}><ListChecks size={14} aria-hidden /> Select</button>
          </div>
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
                      selecting={selecting}
                      checked={picked.has(s.id)}
                      onToggle={() => toggle(s.id)}
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
      <Dialog open={bulkAsk} onClose={() => setBulkAsk(false)} title={`Delete ${picked.size} ${picked.size === 1 ? "chat" : "chats"}?`} confirmLabel="Delete" danger onConfirm={() => void deleteBulk()}>
        They and their messages will be removed for good.
      </Dialog>
      <SidebarRail onNew={newChat} onSearch={search} onPick={pick} />
    </aside>
  );
}

"use client";
import { Cpu, MessageSquare, PanelRight, Search, SquareSlash, Sparkles } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import "./Palette.css";
import { api, type ModelInfo, type SearchHit } from "@/lib/api/client";
import { lastActive } from "@/lib/util/days";
import { indexTime } from "@/lib/util/indexTime";
import { feature, useCap } from "@/lib/api/caps";
import { filterCommands } from "@/lib/commands/registry";
import { runCommand, type PanelId } from "@/lib/commands/runner";
import { useApp } from "@/lib/state/app";
import { sessionTitle } from "@/lib/util/format";

interface Item {
  id: string;
  group: string;
  label: string;
  hint?: string;
  /** Hint is a record (time, size): mono. */
  rec?: boolean;
  icon: ReactNode;
  disabled?: string | null;
  run: () => void;
}

const PANELS: [PanelId, string][] = [["tasks", "Tasks"], ["memory", "Memory"], ["skills", "Skills"], ["mcp", "MCP servers"], ["passwords", "Passwords"], ["schedules", "Schedules"], ["tools", "Tools"], ["audit", "Audit log"], ["settings", "Settings"], ["rewind", "Rewind"]];
const has = (s: string, q: string) => s.toLowerCase().includes(q);

/** Ctrl+K palette. Default export for dynamic import. */
export default function Palette() {
  const { S, phases, ui, commands, host, composer } = useApp();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const dlg = useRef<HTMLDialogElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const listId = useId();
  const searchOk = useCap("search");
  const modelsOk = useCap("models");
  const chatsOnly = ui.paletteScope === "chats";
  const [pointer] = useState(() => document.documentElement.dataset.palettePointer === "1");

  useEffect(() => {
    delete document.documentElement.dataset.palettePointer;
    const d = dlg.current;
    if (d && !d.open) d.showModal();
    if (modelsOk && !chatsOnly) void feature("models", api.models).then((m) => m && setModels(m), () => undefined);
  }, [modelsOk, chatsOnly]);

  const needle = q.trim().toLowerCase();
  useEffect(() => {
    if (!searchOk || needle.length < 2) { setHits([]); return; }
    let live = true;
    const t = window.setTimeout(() => void feature("search", () => api.search(needle)).then((h) => live && setHits(h ?? []), () => undefined), 220);
    return () => { live = false; window.clearTimeout(t); };
  }, [needle, searchOk]);

  const close = () => ui.closeOverlay();
  const done = (fn: () => void) => () => { close(); fn(); };

  const items = useMemo<Item[]>(() => {
    const out: Item[] = [];
    const chats = S.sessions.filter((s) => !s.archived && (s.title || s.pinned || (phases[s.id] && phases[s.id] !== "idle") || (s.state && s.state !== "idle")) && (!needle || has(sessionTitle(s.title), needle)));
    for (const s of chats.slice(0, needle ? 12 : 6)) {
      out.push({ id: `c:${s.id}`, group: "chats", label: sessionTitle(s.title), hint: indexTime(lastActive(s)), rec: true, icon: <MessageSquare size={16} aria-hidden />, run: done(() => S.select(s.id)) });
    }
    for (const h of hits.filter((x) => !chats.some((c) => c.id === x.session_id)).slice(0, 6)) {
      out.push({ id: `h:${h.session_id}:${h.seq}`, group: "in messages", label: sessionTitle(h.title), hint: h.snippet, icon: <Search size={16} aria-hidden />, run: done(() => S.select(h.session_id)) });
    }
    if (chatsOnly) return out;
    for (const [id, label] of PANELS.filter(([, l]) => !needle || has(l, needle))) {
      out.push({ id: `p:${id}`, group: "panels", label, icon: <PanelRight size={16} aria-hidden />, run: done(() => ui.setPanel(id)) });
    }
    for (const c of filterCommands(commands.filter((x) => x.kind === "command"), needle.replace(/^\//, ""), needle ? 12 : 8)) {
      out.push({
        id: `m:${c.name}`, group: "commands", label: `/${c.name}`, hint: c.args ? `${c.args}  ${c.description}` : c.description, icon: <SquareSlash size={16} aria-hidden />, disabled: c.available ? null : (c.reason ?? "Not available"),
        run: done(() => (c.args ? composer.current?.setText(`/${c.name} `) : void runCommand(c.name, "", host, `/${c.name}`))),
      });
    }
    for (const c of filterCommands(commands.filter((x) => x.kind === "skill"), needle, needle ? 8 : 4)) {
      out.push({ id: `s:${c.name}`, group: "skills", label: `/${c.name}`, hint: c.description, icon: <Sparkles size={16} aria-hidden />, disabled: c.available ? null : (c.reason ?? "Not available"), run: done(() => composer.current?.setText(`/${c.name} `)) });
    }
    for (const m of models.filter((x) => x.listed && (!needle || has(x.display_name || x.name, needle)))) {
      out.push({
        id: `d:${m.name}`, group: "models", label: m.display_name || m.name, hint: m.active ? "active" : "how to switch", rec: true, icon: <Cpu size={16} aria-hidden />,
        run: done(() => ui.openOverlay("model")),
      });
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [S.sessions, phases, needle, hits, commands, models, chatsOnly]);

  const idx = Math.min(active, Math.max(0, items.length - 1));
  useEffect(() => {
    list.current?.querySelector(`[data-i="${idx}"]`)?.scrollIntoView({ block: "nearest" });
  }, [idx]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (items.length) setActive((idx + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const it = items[idx];
      if (it && !it.disabled) it.run();
    }
  };

  let lastGroup = "";
  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions -- backdrop click; Esc closes natively
    <dialog ref={dlg} className="pal" data-motion={pointer ? "pop" : "none"} aria-label="Command palette" onClose={close} onClick={(e) => { if (e.target === dlg.current) close(); }}>
      <div className="pal-box">
        <div className="pal-input">
          <Search size={18} aria-hidden />
          <input
            // eslint-disable-next-line jsx-a11y/no-autofocus -- the palette exists to type
            autoFocus role="combobox" aria-expanded="true" aria-controls={listId} aria-activedescendant={items.length ? `${listId}-${idx}` : undefined} aria-autocomplete="list" aria-label="Search chats, panels and commands"
            placeholder={chatsOnly ? "Find a chat" : "Search chats, panels, commands"} value={q} autoComplete="off" spellCheck={false}
            onChange={(e) => { setQ(e.target.value); setActive(0); }} onKeyDown={onKey}
          />
          <kbd>Esc</kbd>
        </div>
        <div className="pal-list" id={listId} role="listbox" aria-label="Results" ref={list}>
          {items.length === 0 && <p className="pal-empty">Nothing matches &quot;{q}&quot;. Try a chat title or a command name.</p>}
          {items.map((it, i) => {
            const head = it.group !== lastGroup;
            lastGroup = it.group;
            return (
              <div key={it.id} role="presentation">
                {head && <p className="pal-group rec" aria-hidden>{it.group}</p>}
                {/* keyboard handled by the combobox input (aria-activedescendant) */}
                {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/interactive-supports-focus */}
                <div id={`${listId}-${i}`} data-i={i} role="option" aria-selected={i === idx} aria-disabled={it.disabled ? true : undefined} className="pal-item" data-active={i === idx} onMouseMove={() => setActive(i)} onClick={() => { if (!it.disabled) it.run(); }}>
                  {it.icon}
                  <span className="pal-label" dir="auto">{it.label}</span>
                  {(it.disabled ?? it.hint) && <><span className="pal-leader" aria-hidden /><span className={it.rec && !it.disabled ? "pal-hint rec" : "pal-hint"}>{it.disabled ?? it.hint}</span></>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </dialog>
  );
}

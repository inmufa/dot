"use client";
import { ArrowLeft, ArrowRight, Plus, RefreshCw, X } from "lucide-react";
import { useRef, useState, type KeyboardEvent, type MouseEvent, type SyntheticEvent } from "react";
import { Bullet, IconButton, Input } from "@/components/ui";
import { normalizeUrl, type BrowserState } from "@/lib/api/browser";
import type { BrowserPending } from "./useBrowser";

export type BrowserAct = (action: "navigate" | "back" | "forward" | "reload" | "tabs/new" | "tabs/switch" | "tabs/close", body?: object) => Promise<boolean>;

const MAX_TABS = 8;
const blank = (url: string) => !url || url === "about:blank";

/** Address bar and tabs. `locked` while the agent drives; `pending` during an owner load. */
export function BrowserBar({ state, act, locked, pending }: { state: BrowserState; act: BrowserAct; locked: boolean; pending: BrowserPending | null }) {
  const [draft, setDraft] = useState<string | null>(null);
  const addr = useRef<HTMLInputElement>(null);
  const strip = useRef<HTMLDivElement>(null);
  const current = pending?.url ?? (blank(state.url) ? "" : state.url);
  const shown = draft ?? current;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const v = (draft ?? current).trim();
    setDraft(null);
    if (!v) return;
    addr.current?.blur();
    void act("navigate", { url: normalizeUrl(v) });
  };
  const onAddrKey = (e: KeyboardEvent<HTMLInputElement>) => {
    // Escape drops the edit (and must not close the canvas)
    if (e.key === "Escape" && draft !== null) {
      e.preventDefault();
      setDraft(null);
    }
  };
  const why = locked ? "Dot is using the browser" : !state.open ? "No page open" : "";
  const nav = (label: string, can = true) => (why ? `${label} (${why.toLowerCase()})` : can ? label : `${label} (nothing to go to)`);
  const canBack = state.can_back ?? true, canFwd = state.can_forward ?? true;
  const newTab = async () => {
    if (await act("tabs/new")) addr.current?.focus();
  };
  const close = (tab: string) => void act("tabs/close", { tab });
  const onTabKey = (e: KeyboardEvent<HTMLButtonElement>, tab: string) => {
    if (e.key === "Delete") {
      e.preventDefault();
      if (!locked) close(tab);
      return;
    }
    const all = [...(strip.current?.querySelectorAll<HTMLButtonElement>(".bv-tab-main") ?? [])];
    const i = all.indexOf(e.currentTarget);
    const to = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? all.length - 1 : null;
    if (to === null || !all.length) return;
    e.preventDefault();
    all[(to + all.length) % all.length]?.focus();
  };
  // middle click closes a tab, like browsers; mousedown is cancelled so Linux autoscroll does not start
  const onAux = (e: MouseEvent, tab: string) => {
    if (e.button !== 1) return;
    e.preventDefault();
    if (!locked) close(tab);
  };
  return (
    <>
      <form className="bv-bar" onSubmit={submit}>
        <IconButton label={nav("Back", canBack)} size="sm" onClick={() => void act("back")} disabled={!!why || !canBack}><ArrowLeft size={18} aria-hidden /></IconButton>
        <IconButton label={nav("Forward", canFwd)} size="sm" onClick={() => void act("forward")} disabled={!!why || !canFwd}><ArrowRight size={18} aria-hidden /></IconButton>
        <IconButton label={nav("Reload")} size="sm" onClick={() => void act("reload")} disabled={!!why}><RefreshCw size={16} aria-hidden /></IconButton>
        <Input
          ref={addr}
          className="bv-url"
          aria-label="Address"
          placeholder={locked ? "Dot is using the browser" : "Enter an address"}
          inputMode="url"
          enterKeyHint="go"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          dir="auto"
          title={state.url || undefined}
          disabled={locked}
          value={shown}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onAddrKey}
          onFocus={(e) => e.currentTarget.select()}
          onBlur={() => setDraft(null)}
        />
        <IconButton label={state.tabs.length >= MAX_TABS ? `New tab (limit ${MAX_TABS})` : locked ? "New tab (dot is using the browser)" : "New tab"} size="sm" onClick={() => void newTab()} disabled={locked || state.tabs.length >= MAX_TABS}><Plus size={18} aria-hidden /></IconButton>
      </form>
      {state.tabs.length > 1 && (
        <div ref={strip} className="bv-tabs" role="tablist" aria-label="Browser tabs">
          {state.tabs.map((t) => {
            const on = t.tab === state.active;
            const name = t.title || (blank(t.url) ? "New tab" : t.url);
            return (
              // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- middle click is a mouse shortcut; the close button and Delete cover keyboard
              <div key={t.tab} className="bv-tab" data-active={on || undefined} onAuxClick={(e) => onAux(e, t.tab)} onMouseDown={(e) => e.button === 1 && e.preventDefault()}>
                <button type="button" role="tab" aria-selected={on} aria-keyshortcuts="Delete" className="bv-tab-main" title={`${name}${blank(t.url) ? "" : `\n${t.url}`}`} disabled={locked} onClick={() => !on && void act("tabs/switch", { tab: t.tab })} onKeyDown={(e) => onTabKey(e, t.tab)}>
                  {on && <Bullet />}
                  <span dir="auto">{name}</span>
                </button>
                <button type="button" className="bv-tab-x" aria-label={`Close ${name}`} title="Close tab (middle click)" disabled={locked} onClick={() => close(t.tab)}><X size={16} aria-hidden /></button>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}

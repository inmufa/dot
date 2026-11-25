"use client";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { Bullet, Button, IconButton, Progress, StateBox, StateDot } from "@/components/ui";
import { ErrorBox, Skeletons } from "@/components/ui/StateBox";
import { CopyCmd } from "@/components/shell/CopyCmd";
import { BROWSER_DOWN, type BrowserState } from "@/lib/api/browser";
import { useApp } from "@/lib/state/app";
import "./browser.css";
import { BrowserBar } from "./BrowserBar";
import { BrowserFrame } from "./BrowserFrame";
import { SaveSession } from "./SaveSession";
import { useBrowser, type BrowserPending } from "./useBrowser";

type Size = { width: number; height: number };

/** CSS size of an element that may mount later (callback ref). */
function useElementSize(): [(el: HTMLElement | null) => void, Size | null] {
  const [el, setEl] = useState<HTMLElement | null>(null);
  const [size, setSize] = useState<Size | null>(null);
  useEffect(() => {
    if (!el) return;
    const ro = new ResizeObserver(([e]) => {
      if (!e) return;
      const width = Math.floor(e.contentRect.width), height = Math.floor(e.contentRect.height);
      setSize((s) => (s?.width === width && s.height === height ? s : { width, height }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [el]);
  return [setEl, size];
}

const hostOf = (url: string) => { try { return new URL(url).host; } catch { return ""; } };

function NotRunning({ onRetry }: { onRetry: () => void }) {
  return (
    <StateBox grid quiet title="The browser is off." action={<><CopyCmd cmd="make up-browser" /><Button variant="ghost" size="sm" onClick={onRetry}>Check again</Button></>}>
      Dot&apos;s own browser is optional. Run this in the project folder, then check again.
    </StateBox>
  );
}

/** Footer line: who has the page. The dot is the actor. */
function Footer({ state, acting, pending, sessionId }: { state: BrowserState; acting: boolean; pending: BrowserPending | null; sessionId: string }) {
  const host = hostOf(state.url);
  const opening = pending ? (pending.url ? `Opening ${hostOf(pending.url) || pending.url}` : "Loading") : null;
  const web = /^https?:/i.test(state.url);
  return (
    <footer className="bv-foot" data-acting={acting || undefined}>
      <span className="bv-foot-state" role="status">
        {acting ? <><StateDot state="thinking" /><span>Dot is using the browser</span></> : opening || state.loading ? <><StateDot state="thinking" /><span>{opening ?? "Loading"}</span></> : <><Bullet tone="faint" /><span>{state.open ? "You have the page" : "No page open"}</span></>}
      </span>
      <span className="bv-foot-end rec" title={state.title || undefined}>{acting ? `call ${state.agent_seq + 1}` : host}</span>
      {state.open && web && <SaveSession sessionId={sessionId} host={host} disabled={acting} />}
    </footer>
  );
}

export function BrowserTab() {
  const { id, ui } = useApp();
  const [stageRef, size] = useElementSize();
  const b = useBrowser(ui.canvas.open && ui.canvas.tab === "browser", size);
  const { state, frame, error, notice, pending, acting, act } = b;
  if (!b.available) return <StateBox grid quiet title="No browser view.">This backend cannot show Dot&apos;s browser.</StateBox>;
  if (!id) return <StateBox grid quiet title="No chat open.">The browser belongs to a chat. Open one first.</StateBox>;
  if (error?.code === BROWSER_DOWN) return <NotRunning onRetry={b.retry} />;
  if (error && !state) return <ErrorBox error={error} onRetry={b.retry} />;
  if (!state) return <Skeletons n={4} />;
  const warn = notice ?? (state.blocked ? { kind: "blocked" as const, text: `Blocked by the browser rules: ${state.blocked}` } : null);
  return (
    <div className="bv">
      <BrowserBar state={state} act={act} locked={acting} pending={pending} />
      {warn && (
        <p className="bv-note" data-kind={warn.kind} role="alert">
          <span className="bv-note-text">{warn.text}</span>
          {notice && <IconButton label="Dismiss" size="sm" onClick={b.dismiss}><X size={16} aria-hidden /></IconButton>}
        </p>
      )}
      {error && <p className="bv-note" data-kind="error" role="status"><span className="bv-note-text">Connection problem: {error.title}</span></p>}
      <div ref={stageRef} className="bv-stage" data-busy={acting || undefined} data-pending={pending ? true : undefined} title={acting ? "Dot is using the browser" : undefined}>
        {(pending || state.loading) && <div className="bv-load"><Progress label={pending ? "Opening page" : "Loading page"} /></div>}
        {frame && state.open && state.viewport ? (
          <BrowserFrame
            src={frame}
            viewport={state.viewport}
            input={{
              click: (x, y, button) => void act("click", { x, y, button }),
              type: (text) => void act("type", { text }),
              press: (key) => void act("press", { key }),
              scroll: (x, y, dy) => void act("scroll", { x, y, dy }),
            }}
          />
        ) : state.open && acting ? (
          <StateBox grid quiet title="Dot is using the browser.">The view pauses while a saved login is typed, so keystrokes stay hidden.</StateBox>
        ) : state.open ? (
          <Skeletons n={3} />
        ) : pending ? (
          <StateBox grid quiet title={pending.url ? `Opening ${hostOf(pending.url) || pending.url}` : "Opening the page"}>The page shows here as soon as it starts drawing.</StateBox>
        ) : (
          <StateBox grid quiet title="No page open.">Type an address above, or ask Dot to look something up.</StateBox>
        )}
      </div>
      <Footer state={state} acting={acting} pending={pending} sessionId={id} />
    </div>
  );
}

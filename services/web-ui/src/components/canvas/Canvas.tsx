"use client";
import { X } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { IconButton, Tabs } from "@/components/ui";
import { CANVAS_MAX, CANVAS_MIN } from "@/hooks/useUiState";
import type { CanvasTab } from "@/lib/commands/runner";
import { useApp } from "@/lib/state/app";
import "./canvas.css";
import { BrowserTab } from "./BrowserTab";
import { FilesTab } from "./FilesTab";
import { PreviewTab } from "./PreviewTab";
import { useBrowserAutoOpen } from "./useBrowserAutoOpen";

const TABS: { id: CanvasTab; label: string; View: () => React.JSX.Element }[] = [
  { id: "preview", label: "Preview", View: PreviewTab },
  { id: "files", label: "Files", View: FilesTab },
  { id: "browser", label: "Browser", View: BrowserTab },
];

/** Keep content mounted for `ms` after it closes so the exit animation has something to show. */
function useLingering(open: boolean, ms: number): boolean {
  const [on, setOn] = useState(open);
  useEffect(() => {
    if (open) { setOn(true); return; }
    const t = window.setTimeout(() => setOn(false), ms);
    return () => window.clearTimeout(t);
  }, [open, ms]);
  return open || on;
}

function ResizeHandle() {
  const { ui } = useApp();
  const w = ui.canvas.width;
  const drag = useRef<{ app: HTMLElement; w: number } | null>(null);
  const limit = (v: number) => Math.max(CANVAS_MIN, Math.min(CANVAS_MAX, Math.min(v, window.innerWidth - 640)));

  const onDown = (e: PointerEvent<HTMLDivElement>) => {
    const app = e.currentTarget.closest<HTMLElement>(".app");
    if (!app) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    app.dataset.resizing = "true";
    drag.current = { app, w };
  };
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d) return;
    d.w = limit(window.innerWidth - e.clientX);
    d.app.style.setProperty("--canvas-w", `${d.w}px`);
  };
  const onUp = () => {
    const d = drag.current;
    if (!d) return;
    delete d.app.dataset.resizing;
    drag.current = null;
    ui.setCanvasWidth(d.w);
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 96 : 24;
    const next = e.key === "ArrowLeft" ? w + step : e.key === "ArrowRight" ? w - step : e.key === "Home" ? CANVAS_MAX : e.key === "End" ? CANVAS_MIN : null;
    if (next === null) return;
    e.preventDefault();
    ui.setCanvasWidth(limit(next));
  };
  return (
    // window-splitter: a focusable separator is interactive per WAI-ARIA
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <div
      className="cv-resize"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize canvas"
      aria-valuemin={CANVAS_MIN}
      aria-valuemax={CANVAS_MAX}
      aria-valuenow={w}
      tabIndex={0}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerCancel={onUp}
      onKeyDown={onKey}
      title="Drag to resize. Arrow keys nudge, Home and End jump."
    >
      <span className="cv-grip" aria-hidden><i /><i /><i /></span>
    </div>
  );
}

export default function Canvas() {
  const { ui } = useApp();
  const open = ui.canvas.open;
  const mounted = useLingering(open, 420);
  const tab = ui.canvas.tab;
  useBrowserAutoOpen();
  const View = TABS.find((t) => t.id === tab)?.View ?? PreviewTab;

  useEffect(() => {
    if (!open) return;
    const k = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape" && !e.defaultPrevented && !document.querySelector("dialog[open], [role=dialog]")) ui.closeCanvas(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, ui]);

  useEffect(() => {
    document.getElementById(`cv-${tab}`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [tab, mounted]);

  return (
    <aside className="canvas" aria-label="Canvas" data-open={open} inert={!open}>
      {mounted && (
        <div className="cv-inner">
          <ResizeHandle />
          <div className="cv-head">
            <Tabs
              label="Canvas tabs"
              idBase="cv"
              value={tab}
              onChange={ui.setCanvasTab}
              tabs={TABS.map(({ id, label }) => ({ id, label }))}
            />
            <IconButton label="Close canvas" onClick={ui.closeCanvas}><X size={18} aria-hidden /></IconButton>
          </div>
          <div className="cv-body" role="tabpanel" id={`cv-${tab}-panel`} aria-labelledby={`cv-${tab}`} tabIndex={-1} key={tab}>
            <View />
          </div>
        </div>
      )}
    </aside>
  );
}

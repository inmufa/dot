"use client";
import { useRef, type KeyboardEvent, type PointerEvent } from "react";
import { SIDEBAR_MAX, SIDEBAR_MIN } from "@/hooks/useUiState";
import { useApp } from "@/lib/state/app";

const clamp = (v: number) => Math.max(SIDEBAR_MIN, Math.min(SIDEBAR_MAX, Math.min(v, window.innerWidth - 640)));

/** Drag handle on the sidebar's right edge (desktop, open state only). */
export function SidebarResize() {
  const { ui } = useApp();
  const w = ui.sidebarWidth;
  const drag = useRef<{ app: HTMLElement; w: number } | null>(null);
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
    d.w = clamp(e.clientX);
    d.app.style.setProperty("--sb-open-w", `${d.w}px`);
  };
  const onUp = () => {
    const d = drag.current;
    if (!d) return;
    delete d.app.dataset.resizing;
    drag.current = null;
    ui.setSidebarWidth(d.w);
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 48 : 16;
    const next = e.key === "ArrowRight" ? w + step : e.key === "ArrowLeft" ? w - step : null;
    if (next === null) return;
    e.preventDefault();
    ui.setSidebarWidth(clamp(next));
  };
  return (
    // focusable separator is interactive per WAI-ARIA
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <div className="sb-resize" role="separator" aria-orientation="vertical" aria-label="Resize sidebar" aria-valuemin={SIDEBAR_MIN} aria-valuemax={SIDEBAR_MAX} aria-valuenow={w} tabIndex={0} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onKeyDown={onKey} />
  );
}

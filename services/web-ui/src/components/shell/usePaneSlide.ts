"use client";
import { useLayoutEffect, useRef, type RefObject } from "react";

const EASE = "cubic-bezier(0.32, 0.72, 0, 1)";

/** The grid snaps on sidebar toggle; slide panes from their old position with transforms to avoid per-frame reflow. */
export function usePaneSlide(app: RefObject<HTMLElement | null>, mode: string): void {
  const prev = useRef<{ mode: string; w: number } | null>(null);
  useLayoutEffect(() => {
    const el = app.current;
    const wrap = el?.querySelector<HTMLElement>(".sidebar-wrap");
    const main = el?.querySelector<HTMLElement>(".main");
    const sb = el?.querySelector<HTMLElement>(".sb");
    if (!el || !wrap || !main || !sb) return;
    const w = wrap.getBoundingClientRect().width;
    const before = prev.current;
    prev.current = { mode, w };
    if (!before || before.mode === mode || el.dataset.resizing) return;
    if (window.matchMedia("(max-width: 56rem), (prefers-reduced-motion: reduce)").matches) return;
    const d = before.w - w;
    if (!d) return;
    const opts = { duration: 320, easing: EASE };
    main.animate([{ transform: `translateX(${d}px)` }, { transform: "none" }], opts);
    if (d < 0) sb.animate([{ transform: `translateX(${d}px)` }, { transform: "none" }], opts);
  }, [app, mode]);
}

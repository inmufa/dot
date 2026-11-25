"use client";
import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";
import { animateHeight } from "@/lib/motion";

/** Textarea grows with a spring; the dock height is published as --dock-h so the transcript reserves it. */
export function useComposerLayout(text: string): { area: RefObject<HTMLTextAreaElement | null>; root: RefObject<HTMLDivElement | null> } {
  const area = useRef<HTMLTextAreaElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const lastH = useRef(0);
  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    const to = Math.min(el.scrollHeight, window.innerHeight * 0.4);
    el.style.height = `${to}px`;
    if (lastH.current) animateHeight(el, lastH.current, to);
    lastH.current = to;
  }, [text]);
  useEffect(() => {
    const dock = root.current?.closest<HTMLElement>(".dock");
    const stage = dock?.parentElement;
    if (!dock || !stage) return;
    const ro = new ResizeObserver(() => stage.style.setProperty("--dock-h", `${dock.offsetHeight}px`));
    ro.observe(dock);
    return () => ro.disconnect();
  }, []);
  return { area, root };
}

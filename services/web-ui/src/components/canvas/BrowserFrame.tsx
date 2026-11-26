"use client";
import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent, type MouseEvent } from "react";

export interface FrameInput {
  click: (x: number, y: number, button: "left" | "right") => void;
  type: (text: string) => void;
  press: (key: string) => void;
  scroll: (x: number, y: number, dy: number) => void;
}

/** Ctrl shortcuts forwarded to the page (select all, undo, redo); paste arrives as text. */
const COMBOS = new Set(["a", "z", "y"]);
const KEYS = new Set(["Enter", "Backspace", "Delete", "Tab", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"]);
const TYPE_MS = 140;
const WHEEL_MS = 90;

/** Live page frame: clicks are scaled to the worker viewport, keys go to the page while focused (Escape or Shift+Tab leaves), typing is batched. */
export function BrowserFrame({ src, viewport, input }: { src: string; viewport: { width: number; height: number }; input: FrameInput }) {
  const box = useRef<HTMLDivElement>(null);
  const img = useRef<HTMLImageElement>(null);
  const live = useRef(input);
  const buf = useRef({ text: "", timer: 0 });
  useEffect(() => { live.current = input; });

  const flush = () => {
    window.clearTimeout(buf.current.timer);
    const text = buf.current.text;
    buf.current.text = "";
    if (text) live.current.type(text);
  };
  useEffect(() => () => window.clearTimeout(buf.current.timer), []);

  // scale by the frame's natural size: state.viewport can be newer than the captured image
  const point = (e: { clientX: number; clientY: number }): [number, number] | null => {
    const el = img.current;
    const r = el?.getBoundingClientRect();
    if (!el || !r || r.width === 0 || r.height === 0) return null;
    const nw = el.naturalWidth || viewport.width, nh = el.naturalHeight || viewport.height;
    const k = Math.min(r.width / nw, r.height / nh);
    const x = (e.clientX - r.left) / k, y = (e.clientY - r.top) / k;
    return x < 0 || y < 0 || x > nw || y > nh ? null : [x, y];
  };
  // wheel needs preventDefault, which React's passive handler cannot do
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    let acc = 0, at: [number, number] = [0, 0], timer = 0;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const p = point(e);
      if (!p) return;
      at = p;
      acc += e.deltaMode === 1 ? e.deltaY * 32 : e.deltaY;
      if (timer) return;
      timer = window.setTimeout(() => {
        timer = 0;
        const dy = Math.max(-5000, Math.min(5000, Math.round(acc)));
        acc = 0;
        if (dy) live.current.scroll(at[0], at[1], dy);
      }, WHEEL_MS);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => { el.removeEventListener("wheel", onWheel); window.clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- point reads refs and viewport
  }, [viewport.width, viewport.height]);

  const [ping, setPing] = useState<{ x: number; y: number; k: number } | null>(null);
  const onClick = (e: MouseEvent) => {
    box.current?.focus();
    const p = point(e);
    if (!p) return;
    const b = box.current?.getBoundingClientRect();
    if (b) setPing({ x: e.clientX - b.left, y: e.clientY - b.top, k: Date.now() });
    live.current.click(p[0], p[1], "left");
  };
  const onContext = (e: MouseEvent) => {
    e.preventDefault();
    const p = point(e);
    if (p) live.current.click(p[0], p[1], "right");
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.nativeEvent.isComposing || e.altKey) return;
    if (e.ctrlKey || e.metaKey) {
      const k = e.key.toLowerCase();
      if (!COMBOS.has(k)) return;
      e.preventDefault();
      flush();
      live.current.press(`${e.shiftKey ? "Shift+" : ""}Control+${k}`);
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      box.current?.blur();
      return;
    }
    if (e.key === "Tab" && e.shiftKey) return;
    if (KEYS.has(e.key)) {
      e.preventDefault();
      flush();
      live.current.press(e.key);
    } else if (e.key.length === 1) {
      e.preventDefault();
      buf.current.text += e.key;
      window.clearTimeout(buf.current.timer);
      buf.current.timer = window.setTimeout(flush, TYPE_MS);
    }
  };
  const onPaste = (e: ClipboardEvent) => {
    const text = e.clipboardData.getData("text/plain").slice(0, 2000);
    if (!text) return;
    e.preventDefault();
    flush();
    live.current.type(text);
  };

  return (
    // the frame is a remote screen: a focusable group that forwards pointer and keys
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <div
      ref={box}
      className="bv-screen"
      role="group"
      aria-label="Browser page. Click to focus, then type. Escape leaves the page."
      tabIndex={0}
      onKeyDown={onKey}
      onBlur={flush}
      onPaste={onPaste}
    >
      {ping && <span key={ping.k} className="bv-ping" style={{ left: ping.x, top: ping.y }} aria-hidden />}
      {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions -- blob frame, keys handled on the group */}
      <img ref={img} src={src} alt="Live view of the page" draggable={false} className="bv-img" onClick={onClick} onContextMenu={onContext} />
    </div>
  );
}

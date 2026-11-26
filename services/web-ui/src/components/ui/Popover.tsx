"use client";
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { place, type Align, type Placed, type Side } from "./position";

interface Props {
  open: boolean;
  onClose: () => void;
  anchorRef: RefObject<HTMLElement | null>;
  children: ReactNode;
  side?: Side | "auto";
  align?: Align;
  /** Match the anchor width (selects). */
  matchWidth?: boolean;
  role?: string;
  label?: string;
  className?: string;
  /** Focus the panel itself instead of the first menu item. */
  focusPanel?: boolean;
  id?: string;
}

/** Fixed-position floating panel (not a native popover). Flips up/down, closes on outside press and Esc. */
export function Popover({ open, onClose, anchorRef, children, side = "auto", align = "start", matchWidth, role = "dialog", label, className, focusPanel, id }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<Placed | null>(null);
  const [mounted, setMounted] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [anchorW, setAnchorW] = useState<number>();
  const [host, setHost] = useState<Element | null>(null);
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; });
  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (open) { setLeaving(false); return; }
    setLeaving(true);
    const t = window.setTimeout(() => setLeaving(false), 110);
    return () => window.clearTimeout(t);
  }, [open]);

  // inside a modal <dialog> the rest of the page is inert and below the top layer, so stay in the dialog
  useLayoutEffect(() => {
    if (open) setHost(anchorRef.current?.closest("dialog[open]") ?? document.body);
  }, [open, anchorRef]);

  useLayoutEffect(() => {
    if (!open || !host) return;
    const measure = () => {
      const a = anchorRef.current, p = ref.current;
      if (!a || !p) return;
      const r = a.getBoundingClientRect();
      const next = place(r, { width: matchWidth ? r.width : p.offsetWidth, height: p.scrollHeight }, window.innerWidth, window.innerHeight, { side, align });
      if (matchWidth) setAnchorW(r.width);
      setPos((prev) => (prev && prev.top === next.top && prev.left === next.left && prev.side === next.side ? prev : next));
    };
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => { window.removeEventListener("resize", measure); window.removeEventListener("scroll", measure, true); };
  }, [open, host, anchorRef, side, align, matchWidth]);

  useEffect(() => {
    if (!open) return;
    const a = anchorRef.current;
    const down = (e: PointerEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t) || a?.contains(t)) return;
      closeRef.current();
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopPropagation(); closeRef.current(); }
      if (e.key === "Tab") closeRef.current();
    };
    document.addEventListener("pointerdown", down, true);
    document.addEventListener("keydown", key, true);
    return () => { document.removeEventListener("pointerdown", down, true); document.removeEventListener("keydown", key, true); };
  }, [open, anchorRef]);

  useEffect(() => {
    if (!open || !pos) return;
    const p = ref.current;
    if (!p || p.contains(document.activeElement)) return;
    const first = focusPanel ? null : p.querySelector<HTMLElement>('[role^="menuitem"]:not([aria-disabled="true"]), [data-autofocus]');
    (first ?? p).focus({ preventScroll: true });
  }, [open, pos, focusPanel]);
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open) wasOpen.current = true;
    else if (wasOpen.current) { wasOpen.current = false; const a = anchorRef.current; if (a && document.activeElement !== a && (!document.activeElement || document.activeElement === document.body || ref.current?.contains(document.activeElement))) a.focus({ preventScroll: true }); }
  }, [open, anchorRef]);

  if ((!open && !leaving) || !mounted || !host) return null;
  const style: CSSProperties = pos
    ? { top: pos.top, left: pos.left, maxHeight: pos.maxHeight, width: matchWidth ? anchorW : undefined, visibility: "visible" }
    : { top: 0, left: 0, visibility: "hidden" };
  const origin = pos ? `${pos.side === "bottom" ? "top" : "bottom"}-${pos.align === "start" ? "left" : "right"}` : "top-left";
  return createPortal(
    <div ref={ref} id={id} role={role} aria-label={label} tabIndex={-1} className={`floating anim-pop${className ? ` ${className}` : ""}`} data-origin={origin} data-state={open ? "open" : "closed"} style={style}>
      {children}
    </div>,
    host,
  );
}

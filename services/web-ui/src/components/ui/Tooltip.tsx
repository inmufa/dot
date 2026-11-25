"use client";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { place, type Placed } from "./position";

let lastHide = 0;
const showDelay = (): number => (Date.now() - lastHide < 400 ? 0 : 450);
const markHide = () => { lastHide = Date.now(); };

interface Props {
  text: string;
  children: ReactNode;
  side?: "top" | "bottom";
}

/** Wraps one control. Hover/focus label with a 450ms delay, instant when another was just shown. Hidden on touch. */
export function Tooltip({ text, children, side = "top" }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<Placed | null>(null);
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const tip = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const show = () => {
    if (window.matchMedia("(pointer: coarse)").matches) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setOpen(true), showDelay());
  };
  const hide = () => {
    clearTimeout(timer.current);
    setOpen((o) => { if (o) markHide(); return false; });
    setPos(null);
  };
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && hide();
    document.addEventListener("keydown", esc);
    window.addEventListener("scroll", hide, true);
    return () => { document.removeEventListener("keydown", esc); window.removeEventListener("scroll", hide, true); };
  }, [open]);
  useEffect(() => {
    if (!open || !anchor || !tip.current) return;
    const r = anchor.getBoundingClientRect();
    const w = tip.current.offsetWidth;
    const p = place(r, { width: w, height: tip.current.offsetHeight }, window.innerWidth, window.innerHeight, { side, align: "start" });
    setPos({ ...p, left: Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - 8 - w) });
  }, [open, side, anchor]);

  return (
    <>
      {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions -- wrapper only forwards hover and focus from the control inside */}
      <span ref={setAnchor} className="tip-anchor" onPointerEnter={show} onPointerLeave={hide} onFocus={show} onBlur={hide} onPointerDown={hide}>{children}</span>
      {open && createPortal(
        <div ref={tip} id={id} role="tooltip" className="tip" style={pos ? { top: pos.top, left: pos.left, visibility: "visible" } : { top: 0, left: 0, visibility: "hidden" }}>{text}</div>,
        document.body,
      )}
    </>
  );
}

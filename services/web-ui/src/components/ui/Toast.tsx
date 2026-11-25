"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { Button } from "./Button";

type ToastTone = "neutral" | "ok" | "warn" | "bad" | "info";
export interface ToastInput { title: string; description?: string; tone?: ToastTone; action?: { label: string; onClick: () => void }; ms?: number }
interface Item extends ToastInput { id: number; closing?: boolean }

const Ctx = createContext<(t: ToastInput) => void>(() => {});
/** `const toast = useToast(); toast({ title: "Saved", tone: "ok" })`. */
export const useToast = () => useContext(Ctx);

const ICON = { ok: CheckCircle2, warn: AlertTriangle, bad: XCircle, info: Info, neutral: null } as const;

function ToastRow({ t, onDone }: { t: Item; onDone: (id: number) => void }) {
  const [closing, setClosing] = useState(false);
  const hover = useRef(false);
  const close = useCallback(() => { setClosing(true); window.setTimeout(() => onDone(t.id), 110); }, [onDone, t.id]);
  useEffect(() => {
    const ms = t.ms ?? (t.action ? 8000 : 4500);
    let timer = window.setTimeout(function tick() { if (hover.current) timer = window.setTimeout(tick, 800); else close(); }, ms);
    return () => window.clearTimeout(timer);
  }, [t.ms, t.action, close]);
  const Icon = ICON[t.tone ?? "neutral"];
  return (
    <div className="toast anim-toast" data-tone={t.tone ?? "neutral"} data-state={closing ? "closed" : "open"} onPointerEnter={() => { hover.current = true; }} onPointerLeave={() => { hover.current = false; }}>
      {Icon && <Icon size={16} aria-hidden className="toast-ic" />}
      <div className="toast-text"><strong>{t.title}</strong>{t.description && <span>{t.description}</span>}</div>
      {t.action && <Button size="sm" variant="ghost" onClick={() => { t.action?.onClick(); close(); }}>{t.action.label}</Button>}
    </div>
  );
}

/** Mount once near the root. Quiet bottom-centre snackbars, polite live region, pause on hover, newest last. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const seq = useRef(0);
  const host = useRef<HTMLDivElement>(null);
  // top layer: stays above modal sheets and dialogs
  useEffect(() => { try { host.current?.showPopover(); } catch { /* already open */ } }, []);
  const push = useCallback((t: ToastInput) => setItems((l) => [...l.slice(-3), { ...t, id: ++seq.current }]), []);
  const drop = useCallback((id: number) => setItems((l) => l.filter((x) => x.id !== id)), []);
  const value = useMemo(() => push, [push]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div ref={host} className="toasts" role="status" aria-live="polite" popover="manual">{items.map((t) => <ToastRow key={t.id} t={t} onDone={drop} />)}</div>
    </Ctx.Provider>
  );
}

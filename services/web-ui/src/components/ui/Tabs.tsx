"use client";
import { useLayoutEffect, useRef, type KeyboardEvent, type ReactNode } from "react";

interface Tab<T extends string> { id: T; label: ReactNode; count?: number }
interface Props<T extends string> {
  tabs: Tab<T>[];
  value: T;
  onChange: (id: T) => void;
  label: string;
  /** Prefix for tab and panel ids so a panel can use aria-labelledby. */
  idBase?: string;
}

/** Underline tabs with roving tabindex and arrow keys. The indicator is a bottom bar only, no box. */
export function Tabs<T extends string>({ tabs, value, onChange, label, idBase = "tab" }: Props<T>) {
  const list = useRef<HTMLDivElement>(null);
  // One indicator slides to the selected tab (transform only; vars read by .ind in motion.css).
  useLayoutEffect(() => {
    const l = list.current;
    if (!l) return;
    const measure = () => {
      const el = l.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
      if (!el) return;
      l.style.setProperty("--ind-x", `${el.offsetLeft}px`);
      l.style.setProperty("--ind-s", String(el.offsetWidth / 100));
    };
    measure();
    const ro = new ResizeObserver(measure);
    l.querySelectorAll('[role="tab"]').forEach((t) => ro.observe(t));
    return () => ro.disconnect();
  }, [value, tabs.length]);
  const key = (e: KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === value);
    const n = e.key === "ArrowRight" ? (i + 1) % tabs.length : e.key === "ArrowLeft" ? (i + tabs.length - 1) % tabs.length : e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : -1;
    if (n < 0) return;
    e.preventDefault();
    const t = tabs[n];
    if (t) onChange(t.id);
    list.current?.querySelectorAll<HTMLElement>('[role="tab"]')[n]?.focus();
  };
  return (
    // eslint-disable-next-line jsx-a11y/interactive-supports-focus -- tabs inside are focusable
    <div ref={list} className="tabs" role="tablist" aria-label={label} onKeyDown={key}>
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" id={`${idBase}-${t.id}`} aria-selected={t.id === value} aria-controls={`${idBase}-${t.id}-panel`} tabIndex={t.id === value ? 0 : -1} className="tab" onClick={() => onChange(t.id)}>
          {t.label}
          {t.count != null && <span className="tab-count">{t.count}</span>}
        </button>
      ))}
      <span className="ind" aria-hidden />
    </div>
  );
}

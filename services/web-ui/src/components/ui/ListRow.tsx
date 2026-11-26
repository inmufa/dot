"use client";
import type { ReactNode } from "react";

interface Props {
  title: ReactNode;
  /** Second line, muted. */
  meta?: ReactNode;
  /** Left slot: icon, dot, avatar. Fixed 20px column so titles align with and without it. */
  lead?: ReactNode;
  /** Mono record at the right end (relative time). With `leader` a dotted line runs from the title to it, like an index. */
  time?: ReactNode;
  leader?: boolean;
  /** Right slot, always visible but faint until hover or focus (menu button, count). */
  actions?: ReactNode;
  selected?: boolean;
  onSelect?: () => void;
  href?: string;
  className?: string;
}

/** The shared list row. Actions sit outside the main button so interactives never nest. */
export function ListRow({ title, meta, lead, actions, time, leader, selected, onSelect, href, className }: Props) {
  const inner = (
    <>
      <span className="lr-lead" aria-hidden={!lead}>{lead}</span>
      <span className="lr-main"><span className="lr-title">{title}</span>{meta && <span className="lr-meta">{meta}</span>}</span>
      {leader && <span className="lr-leader" aria-hidden />}
      {time && <span className="lr-time rec">{time}</span>}
    </>
  );
  return (
    <div className={`lr${className ? ` ${className}` : ""}`} data-selected={selected ? "true" : undefined}>
      {href ? <a className="lr-hit" href={href} aria-current={selected ? "true" : undefined}>{inner}</a>
        : <button type="button" className="lr-hit" aria-current={selected ? "true" : undefined} onClick={onSelect}>{inner}</button>}
      {actions && <span className="lr-actions">{actions}</span>}
    </div>
  );
}

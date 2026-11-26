"use client";
import { MoreHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import { DropdownMenu, IconButton, Progress, Skeletons, StateBox } from "@/components/ui";

export type Tone = "ok" | "warn" | "bad" | "info" | "idle";

/** Dot plus word: status never relies on colour alone. */
export function Status({ tone = "idle", children }: { tone?: Tone; children: ReactNode }) {
  return <span className="pn-status" data-tone={tone}>{children}</span>;
}

/** Dot-separated metadata line; falsy items are dropped. */
export function Meta({ items }: { items: ReactNode[] }) {
  const list = items.filter((i) => i !== null && i !== undefined && i !== false && i !== "");
  if (list.length === 0) return null;
  return <p className="pn-meta">{list.map((i, n) => <span key={n}>{i}</span>)}</p>;
}

/** The "..." menu at the end of a row. */
export function RowMenu({ label, children }: { label: string; children: ReactNode }) {
  return (
    <DropdownMenu align="end" label={label} trigger={(p) => <IconButton label={label} size="sm" {...p}><MoreHorizontal size={16} aria-hidden /></IconButton>}>
      {children}
    </DropdownMenu>
  );
}

/** Tools row (search, filters, primary action) over a quiet count line. */
export function PanelBar({ count, children }: { count: ReactNode; children?: ReactNode }) {
  return (
    <div className="pn-bar">
      {children && <div className="pn-tools">{children}</div>}
      <p className="pn-count" aria-live="polite">{count}</p>
    </div>
  );
}

/** Section heading inside a panel, with an optional count. */
export function GroupLabel({ children, n }: { children: ReactNode; n?: number }) {
  return <h3 className="pn-group">{children}{n !== undefined && <span>{n}</span>}</h3>;
}

/** Loading: the dot travels on a hairline over skeleton lines. */
export function Loading({ n = 4 }: { n?: number }) {
  return (
    <div className="pn-loading" aria-busy="true">
      <Progress label="Loading" />
      <Skeletons n={n} />
    </div>
  );
}

/** Empty state: dot matrix, one sentence, optional action. */
export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <StateBox grid quiet title={title} action={action}>{children}</StateBox>;
}

interface ItemProps {
  /** Plain text of the title; used for the tooltip when it is cut off. */
  text: string;
  /** Code-like names (commands, tool ids) in the mono face. */
  mono?: boolean;
  lead?: ReactNode;
  /** Short tag after the title (source, kind, count). */
  time?: ReactNode;
  actions?: ReactNode;
  /** Detail lines under the title. */
  children?: ReactNode;
}

/** One entry: title with a soft tag, actions on the right, details underneath. No leaders, no rules. */
export function Item({ text, mono, lead, time, actions, children }: ItemProps) {
  return (
    <li className="pn-item">
      <div className="pn-row">
        {lead && <span className="pn-lead">{lead}</span>}
        <span className={`pn-name${mono ? " mono" : ""}`} title={text} dir="auto">{text}</span>
        {time && <span className="pn-tag">{time}</span>}
        {actions && <span className="pn-acts">{actions}</span>}
      </div>
      {children && <div className="pn-sub">{children}</div>}
    </li>
  );
}

const pad = (n: number) => String(n).padStart(2, "0");
/** Gutter stamp: clock for today, "Nov 18" otherwise. */
export function stampOf(iso: string, secs = false): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  if (d.toDateString() === new Date().toDateString()) return `${pad(d.getHours())}:${pad(d.getMinutes())}${secs ? `:${pad(d.getSeconds())}` : ""}`;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

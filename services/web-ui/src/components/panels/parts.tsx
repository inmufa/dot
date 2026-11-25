"use client";
import { MoreHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import { DropdownMenu, IconButton, ListRow, Progress, Skeletons, StateBox } from "@/components/ui";

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

/** Register header: mono count on the left, the primary action (and search) on the right. Sits under the sheet title. */
export function PanelBar({ count, children }: { count: ReactNode; children?: ReactNode }) {
  return (
    <div className="pn-bar">
      <span className="pn-count rec" aria-live="polite">{count}</span>
      {children}
    </div>
  );
}

/** Mono lowercase group label with a count, like the sidebar's "today 5". */
export function GroupLabel({ children, n }: { children: ReactNode; n?: number }) {
  return <p className="pn-group rec">{children}{n !== undefined && <span> {n}</span>}</p>;
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
  mono?: boolean;
  lead?: ReactNode;
  time?: ReactNode;
  actions?: ReactNode;
  selected?: boolean;
  onSelect?: () => void;
  /** Detail lines under the row, aligned with the title. */
  children?: ReactNode;
}

/** One register line: ListRow with a dotted leader to a mono value, details underneath. */
export function Item({ text, mono, lead, time, actions, selected, onSelect, children }: ItemProps) {
  return (
    <li className="pn-item">
      <ListRow title={<span className={mono ? "mono" : undefined} title={text} dir="auto">{text}</span>} lead={lead} time={time} leader actions={actions} selected={selected} onSelect={onSelect} />
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

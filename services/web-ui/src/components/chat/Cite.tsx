"use client";
import { createContext, useContext, type ReactNode } from "react";
import type { SourceItem } from "@/lib/api/types";
import { clip } from "@/lib/util/format";

export const SourcesCtx = createContext<ReadonlyMap<number, SourceItem>>(new Map());

const safe = (u: string): string | null => {
  try {
    const x = new URL(u);
    return x.protocol === "http:" || x.protocol === "https:" ? x.href : null;
  } catch {
    return null;
  }
};
const host = (u: string): string => {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return u;
  }
};

/** Inline citation chip: site name in the accent colour, hover or focus shows title and snippet. */
export function Cite({ s }: { s: SourceItem }) {
  const href = safe(s.url);
  const h = host(s.url);
  const chip = <span className="cite-chip">{clip(h, 22)}</span>;
  return (
    <span className="cite">
      {href ? <a href={href} target="_blank" rel="noreferrer noopener" aria-label={`Source ${s.n}: ${s.title || h}`}>{chip}</a> : chip}
      <span className="cite-card" role="tooltip">
        <span className="cite-host">{h}</span>
        <span className="cite-title">{clip(s.title || h, 90)}</span>
        {s.snippet && <span className="cite-snip">{clip(s.snippet, 160)}</span>}
      </span>
    </span>
  );
}

/** One pill for adjacent citations: first source name plus "+N"; the card lists every source. */
export function CiteGroup({ list }: { list: SourceItem[] }) {
  const first = list[0] as SourceItem;
  const h = host(first.url);
  return (
    <span className="cite">
      <span className="cite-chip" tabIndex={0}>{clip(h, 18)} <span className="cite-more">+{list.length - 1}</span></span>
      <span className="cite-card cite-list" role="tooltip">
        {list.map((s) => {
          const href = safe(s.url);
          const body = (
            <>
              <span className="cite-host">{host(s.url)}</span>
              <span className="cite-title">{clip(s.title || host(s.url), 90)}</span>
            </>
          );
          return href ? <a key={s.n} className="cite-row" href={href} target="_blank" rel="noreferrer noopener">{body}</a> : <span key={s.n} className="cite-row">{body}</span>;
        })}
      </span>
    </span>
  );
}

/** Text with [n] markers swapped for citation chips; adjacent markers merge into one grouped chip. */
export function CitedText({ text }: { text: string }) {
  const map = useContext(SourcesCtx);
  if (map.size === 0 || !text.includes("[")) return <>{text}</>;
  const out: ReactNode[] = [];
  let run: SourceItem[] = [];
  let gap = "";
  const flush = (k: number) => {
    if (run.length === 1) out.push(<Cite key={k} s={run[0] as SourceItem} />);
    else if (run.length > 1) out.push(<CiteGroup key={k} list={run} />);
    run = [];
    gap = "";
  };
  text.split(/(\[\d{1,3}\])/).forEach((part, i) => {
    const n = /^\[(\d{1,3})\]$/.exec(part)?.[1];
    const s = n ? map.get(Number(n)) : undefined;
    if (s) {
      if (!run.some((r) => r.n === s.n)) run.push(s);
      gap = "";
    } else if (run.length && part.trim() === "" && part.length < 3) {
      gap = part;
    } else {
      flush(i);
      out.push(part);
    }
  });
  flush(text.length);
  if (gap) out.push(gap);
  return <>{out}</>;
}

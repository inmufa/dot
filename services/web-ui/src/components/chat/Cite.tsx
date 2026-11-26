"use client";
import { createContext, useContext } from "react";
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

/** Text with [n] markers swapped for citation chips when the turn has that source. */
export function CitedText({ text }: { text: string }) {
  const map = useContext(SourcesCtx);
  if (map.size === 0 || !text.includes("[")) return <>{text}</>;
  return (
    <>
      {text.split(/(\[\d{1,3}\])/).map((part, i) => {
        const n = /^\[(\d{1,3})\]$/.exec(part)?.[1];
        const s = n ? map.get(Number(n)) : undefined;
        return s ? <Cite key={i} s={s} /> : part;
      })}
    </>
  );
}

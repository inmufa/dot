"use client";
import { ExternalLink } from "lucide-react";
import { useState } from "react";
import type { SourceItem } from "@/lib/api/types";
import { clip } from "@/lib/util/format";

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

/** Numbered source chips under a research answer; the last chip shows the rest inline. */
export function Sources({ items }: { items: SourceItem[] }) {
  const [all, setAll] = useState(false);
  if (items.length === 0) return null;
  return (
    <div className="sources" role="group" aria-label="Sources">
      {(all ? items : items.slice(0, 6)).map((s) => {
        const href = safe(s.url);
        const body = (
          <>
            <span className="src-n">{s.n}</span>
            <span className="src-t">{clip(s.title || host(s.url), 36)}</span>
            <span className="src-h muted">{host(s.url)}</span>
          </>
        );
        return href ? (
          <a key={s.n} className="src-chip press" href={href} target="_blank" rel="noreferrer noopener" title={s.snippet ?? s.title}>{body}<ExternalLink size={12} aria-hidden /></a>
        ) : (
          <span key={s.n} className="src-chip">{body}</span>
        );
      })}
      {items.length > 6 && (
        <button type="button" className="src-chip src-all press" aria-expanded={all} onClick={() => setAll((v) => !v)}>{all ? "Show fewer" : `All sources (${items.length})`}</button>
      )}
    </div>
  );
}

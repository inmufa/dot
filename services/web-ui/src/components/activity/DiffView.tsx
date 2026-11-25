"use client";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui";
import { parseDiff } from "@/lib/util/diff";

const FIRST = 400;

/** Lightweight unified-diff renderer (no Monaco: keeps the bundle small). */
export function DiffView({ diff }: { diff: string }) {
  const parsed = useMemo(() => parseDiff(diff), [diff]);
  const [all, setAll] = useState(false);
  const lines = all ? parsed.lines : parsed.lines.slice(0, FIRST);
  const numbered = parsed.lines.some((l) => l.oldNo !== null || l.newNo !== null);
  return (
    <div className="diff">
      <div className="diff-stat">
        <span data-tone="allow">+{parsed.added}</span> <span data-tone="deny">-{parsed.removed}</span>
        <span> changed lines</span>
      </div>
      <div className="diff-body" role="region" aria-label="Proposed changes" tabIndex={0} data-numbered={numbered}>
        {lines.map((l, i) => (
          <div key={i} className="dl" data-kind={l.kind}>
            {numbered && <span className="dn" aria-hidden>{l.oldNo ?? ""}</span>}
            {numbered && <span className="dn" aria-hidden>{l.newNo ?? ""}</span>}
            <span className="ds" aria-hidden>{l.kind === "add" ? "+" : l.kind === "del" ? "-" : " "}</span>
            <span className="dt">
              {l.kind === "add" && <span className="sr-only">added: </span>}
              {l.kind === "del" && <span className="sr-only">removed: </span>}
              {l.text || " "}
            </span>
          </div>
        ))}
      </div>
      {!all && parsed.lines.length > FIRST && (
        <Button size="sm" onClick={() => setAll(true)}>
          Show {(parsed.lines.length - FIRST).toLocaleString("en")} more lines
        </Button>
      )}
    </div>
  );
}

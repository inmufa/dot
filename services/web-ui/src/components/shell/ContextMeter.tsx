"use client";
import { useId, useState } from "react";
import { compactTokens, percent } from "@/lib/format";
import { ContextPopover } from "./ContextPopover";

interface Props {
  usage: { tokens: number; limit: number } | null;
  sessionId: string | null;
  running: boolean;
}

export function ContextMeter({ usage, sessionId, running }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const has = usage !== null && usage.limit > 0;
  const pct = has ? percent(usage.tokens, usage.limit) : 0;
  const tone = pct >= 92 ? "bad" : pct >= 80 ? "warn" : "ok";
  return (
    <>
      <button
        type="button"
        className="ctx ctx-btn"
        popoverTarget={id}
        disabled={!sessionId}
        data-tone={has ? tone : undefined}
        data-empty={has ? undefined : "true"}
        title={has ? `${usage.tokens.toLocaleString("en")} of ${usage.limit.toLocaleString("en")} tokens` : "Context details"}
      >
        <span className="ctx-label">ctx</span>
        <span className="ctx-track" aria-hidden>
          <span className="ctx-fill" style={{ transform: `scaleX(${pct / 100})` }} />
        </span>
        <span className="ctx-num">
          {has ? (
            <>
              {pct}% <span className="ctx-abs">{compactTokens(usage.tokens)}/{compactTokens(usage.limit)}</span>
            </>
          ) : (
            "-"
          )}
          <span className="sr-only"> context used, show details</span>
        </span>
      </button>
      <ContextPopover id={id} open={open} onOpen={setOpen} sessionId={sessionId} running={running} usage={usage} />
    </>
  );
}

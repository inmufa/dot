"use client";
import { useEffect, useId, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { chatStore } from "@/lib/state/store";
import { percent } from "@/lib/util/format";
import { ContextPopover } from "./ContextPopover";
import "./context.css";

interface Props {
  usage: { tokens: number; limit: number } | null;
  sessionId: string | null;
  running: boolean;
  /** Kept for callers; the meter is always the text button "Context 12%". */
  compact?: boolean;
}

/** Text button under the composer; the breakdown opens in a native popover. */
export function ContextMeter({ usage, sessionId, running }: Props) {
  const id = useId();
  const ref = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const has = usage !== null && usage.limit > 0;
  // A reloaded chat has no usage event yet: ask the backend once so the button is not stuck at 0%
  useEffect(() => {
    if (!sessionId || has || running) return;
    api.context(sessionId).then((c) => chatStore.noteUsage(sessionId, c.used, c.limit), () => undefined);
  }, [sessionId, has, running]);
  const pct = has ? percent(usage.tokens, usage.limit) : 0;
  const tone = pct >= 92 ? "bad" : pct >= 80 ? "warn" : "ok";
  return (
    <>
      <button
        ref={ref}
        type="button"
        data-context-trigger
        className="ctx ctx-btn ctx-compact"
        popoverTarget={sessionId ? id : undefined}
        aria-disabled={!sessionId || undefined}
        data-tone={has ? tone : undefined}
        title={!sessionId ? "Start a chat first" : has ? `${usage.tokens.toLocaleString("en")} of ${usage.limit.toLocaleString("en")} tokens` : "Context details"}
      >
        <span className="ctx-num">Context {pct}%</span>
      </button>
      <ContextPopover id={id} anchor={ref} open={open} onOpen={setOpen} sessionId={sessionId} running={running} usage={usage} />
    </>
  );
}

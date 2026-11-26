"use client";
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { duration } from "@/components/activity/Steps";
import { LiveBuddy } from "@/components/buddy/LiveBuddy";
import { Shine } from "@/components/ui";
import { setLiveOpen, useLiveOpen } from "@/lib/state/liveOpen";
import type { Item } from "@/lib/stream/reducer";
import type { LiveStatus } from "@/lib/stream/status";
import { isStep } from "@/lib/stream/turns";

/** The one live line of a running turn: buddy, what it is doing, time, steps; click expands the steps. */
export function LiveLine({ status, items, startedAt }: { status: LiveStatus | null; items: Item[]; startedAt: number | null }) {
  const open = useLiveOpen();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  useEffect(() => () => setLiveOpen(false), []); // the next turn starts collapsed

  const turn = items.slice(items.map((i) => i.kind).lastIndexOf("user") + 1);
  const steps = turn.filter(isStep).length;
  const thought = turn.some((i) => i.kind === "assistant" && i.thinking);
  const canOpen = steps > 0 || thought;
  const label = status?.label ?? "Writing the answer";
  const took = startedAt !== null ? duration(Math.max(0, now - startedAt)) : null;
  const meta = [took, steps ? `${steps} ${steps === 1 ? "step" : "steps"}` : null].filter(Boolean).join(" · ");

  return (
    <div className="live-line" role="status" data-kind={status?.kind ?? "answer"}>
      <LiveBuddy size={22} />
      <button type="button" className="live-hit press" aria-expanded={canOpen ? open : undefined} aria-disabled={!canOpen || undefined} onClick={() => canOpen && setLiveOpen(!open)}>
        <span className="live-text" key={label}><Shine text={`${label}...`} /></span>
        {meta && <span className="live-meta rec">{meta}</span>}
        {canOpen && <ChevronRight size={14} aria-hidden className="chev" />}
      </button>
    </div>
  );
}

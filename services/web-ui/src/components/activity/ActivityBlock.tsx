"use client";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { Markdown } from "@/components/chat/Markdown";
import { Entry } from "@/components/ui";
import { useApp } from "@/lib/state/app";
import type { ActivityGroup } from "@/lib/stream/turns";
import { SubagentLine } from "./SubagentLine";
import { duration, ToolStep } from "./Steps";
import { Thinking } from "./Thinking";
import "./ActivityBlock.css";

/** A turn's tool steps as a collapsible log group: one head entry, then one rail entry per step.
 * `standalone`: this is the whole turn - no reply text came out of it - so the head reads as a
 * centered status line instead of a left-aligned log row with nothing else to anchor it to. */
export function ActivityBlock({ group, i = 0, time, standalone = false }: { group: ActivityGroup; i?: number; time?: React.ReactNode; standalone?: boolean }) {
  const { settings } = useApp();
  const [open, setOpen] = useState<boolean | null>(null);
  const expanded = open ?? (settings.verbose || group.needsYou);
  const took = duration(group.ms ?? undefined);
  const steps = `${group.steps} ${group.steps === 1 ? "step" : "steps"}`;
  const label = `${group.live ? "working" : "worked"}${took ? ` ${took}` : ""} · ${steps}`;
  let n = 0;
  const head = (
    <button type="button" className="activity-head press" aria-expanded={expanded} onClick={() => setOpen(!expanded)}>
      <span className="act-label rec">{label}</span>
      {group.live && group.current && <span className="act-now">{group.needsYou ? `${group.current} needs approval` : group.current}</span>}
      <ChevronRight size={14} aria-hidden className="chev" />
    </button>
  );
  return (
    <section className="activity" data-live={group.live} data-needs={group.needsYou} aria-label="Activity">
      {standalone ? <div className="activity-head-solo">{head}</div> : (
        <Entry time={time} i={i} state={group.needsYou ? "waiting" : group.live ? "thinking" : undefined} className="e-group">
          {head}
        </Entry>
      )}
      {expanded &&
        group.items.map((it) => {
          switch (it.kind) {
            case "tool":
              return <ToolStep key={it.id} tool={it} i={Math.min(n, 6)} n={++n} />;
            case "subagent":
              return (
                <Entry key={it.id} time={String(++n).padStart(2, "0")} i={Math.min(n, 6)} className="e-step">
                  <SubagentLine sub={it} />
                </Entry>
              );
            case "assistant":
              return it.thinking || it.text ? (
                <Entry key={it.id} time="" className="e-step e-note">
                  <div className="act-text">
                    {it.thinking && <Thinking text={it.thinking} live={it.streaming && !it.text} startedAt={it.thinkStartedAt} ms={it.thinkMs} />}
                    {it.text && <Markdown text={it.text} settled={!it.streaming} />}
                  </div>
                </Entry>
              ) : null;
            default:
              return null;
          }
        })}
    </section>
  );
}

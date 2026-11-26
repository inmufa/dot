"use client";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { Markdown } from "@/components/chat/Markdown";
import { Entry, Shine } from "@/components/ui";
import { useApp } from "@/lib/state/app";
import type { ActivityGroup } from "@/lib/stream/turns";
import { SubagentLine } from "./SubagentLine";
import { duration, ToolStep } from "./Steps";
import { Thinking } from "./Thinking";
import "./ActivityBlock.css";

/** Collapsible group of a turn's tool steps, always on the log rail. */
export function ActivityBlock({ group, i = 0, time }: { group: ActivityGroup; i?: number; time?: React.ReactNode }) {
  const { settings } = useApp();
  const [open, setOpen] = useState<boolean | null>(null);
  const expanded = open ?? (settings.verbose || group.needsYou);
  const took = duration(group.ms ?? undefined);
  const steps = `${group.steps} ${group.steps === 1 ? "step" : "steps"}`;
  const label = `${group.live ? "working" : "worked"}${took ? ` ${took}` : ""} · ${steps}`;
  if (group.steps === 0) return null;
  let n = 0;
  const head = (
    <button type="button" className="activity-head press" aria-expanded={expanded} onClick={() => setOpen(!expanded)}>
      <span className="act-label rec">{group.live ? <Shine text={label} /> : label}</span>
      {group.live && group.current && <span className="act-now">{group.needsYou ? `${group.current} needs approval` : group.current}</span>}
      <ChevronRight size={14} aria-hidden className="chev" />
    </button>
  );
  return (
    <section className="activity" data-live={group.live} data-needs={group.needsYou} aria-label="Activity">
      <Entry time={time} i={i} state={group.needsYou ? "waiting" : group.live ? "thinking" : undefined} className="e-group">
        {head}
      </Entry>
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
                    {it.thinking && <Thinking text={it.thinking} live={it.streaming && !it.text && it.thinkMs === undefined} startedAt={it.thinkStartedAt} ms={it.thinkMs} />}
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

"use client";
import { AlertTriangle, ArrowDown, ArrowUp, Check, CheckCircle2, Info, Minus, OctagonAlert, X } from "lucide-react";
import { useCallback } from "react";
import { reducedMotion, useCountUp, useFirstView } from "./hooks";
import { formatNum, type CalloutP, type CardsP, type ChecklistP, type StatsP, type StepsP } from "./schema";

function Num({ value, unit, play }: { value: number; unit?: string; play: boolean }) {
  const dec = Number.isInteger(value) ? 0 : 2;
  const fmt = useCallback((n: number) => formatNum(dec ? n : Math.round(n)), [dec]);
  const ref = useCountUp(value, play, fmt);
  return <><span ref={ref}>{formatNum(value)}</span>{unit && <span className="wg-unit">{unit}</span>}</>;
}

export function StatsWidget({ p }: { p: StatsP }) {
  const [ref, seen] = useFirstView<HTMLDivElement>();
  return (
    <div className="wg-stats" ref={ref}>
      {p.items.map((s, i) => (
        <div key={i} className="wg-stat" data-play={seen} style={{ "--i": i } as React.CSSProperties}>
          <span className="wg-stat-l">{s.label}</span>
          <span className="wg-stat-v">{typeof s.value === "number" ? <Num value={s.value} unit={s.unit} play={seen} /> : <>{s.value}{s.unit && <span className="wg-unit">{s.unit}</span>}</>}</span>
          {(s.delta !== undefined || s.hint) && (
            <span className="wg-stat-d">
              {s.delta !== undefined && (
                <span className="wg-delta" data-dir={s.delta > 0 ? "up" : s.delta < 0 ? "down" : "flat"}>
                  {s.delta > 0 ? <ArrowUp size={12} aria-hidden /> : s.delta < 0 ? <ArrowDown size={12} aria-hidden /> : <Minus size={12} aria-hidden />}
                  {Math.abs(s.delta)}%<span className="sr-only">{s.delta > 0 ? " up" : s.delta < 0 ? " down" : " unchanged"}</span>
                </span>
              )}
              {s.hint && <span className="muted">{s.hint}</span>}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

const STEP_LABEL = { done: "Done", active: "In progress", todo: "Not started", error: "Failed" } as const;

export function StepsWidget({ p }: { p: StepsP }) {
  const [ref, seen] = useFirstView<HTMLOListElement>();
  return (
    <ol className="wg-steps" ref={ref} data-play={seen}>
      {p.items.map((s, i) => (
        <li key={i} data-status={s.status} style={{ "--i": i } as React.CSSProperties}>
          <span className="wg-node" aria-hidden>
            {s.status === "done" ? <Check size={13} strokeWidth={3} /> : s.status === "error" ? <X size={13} strokeWidth={3} /> : s.status === "active" ? <i className="wg-spin" /> : null}
          </span>
          <span className="wg-step-t" dir="auto">{s.title}<span className="sr-only">. {STEP_LABEL[s.status]}</span></span>
          {s.detail && <span className="wg-step-d muted" dir="auto">{s.detail}</span>}
        </li>
      ))}
    </ol>
  );
}

export function ChecklistWidget({ p }: { p: ChecklistP }) {
  const [ref, seen] = useFirstView<HTMLUListElement>();
  const done = p.items.filter((x) => x.done).length;
  return (
    <div className="wg-check-wrap">
      <p className="muted wg-check-n">{done} of {p.items.length} done</p>
      <ul className="wg-checklist" ref={ref} data-play={seen || reducedMotion()}>
        {p.items.map((x, i) => (
          <li key={i} data-done={x.done} style={{ "--i": i } as React.CSSProperties}>
            <span className="wg-box" aria-hidden>{x.done && <Check size={12} strokeWidth={3} />}</span>
            <span className="wg-ck-t" dir="auto">{x.text}<span className="sr-only">{x.done ? " (done)" : " (open)"}</span></span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CardsWidget({ p }: { p: CardsP }) {
  return (
    <div className="wg-cards">
      {p.items.map((c, i) => (
        <article key={i} className="wg-card" style={{ "--i": i } as React.CSSProperties}>
          <header><h4 dir="auto">{c.title}</h4>{c.badge && <span className="badge">{c.badge}</span>}</header>
          {c.body && <p dir="auto">{c.body}</p>}
          {c.meta.length > 0 && <dl>{c.meta.map((m, j) => <div key={j}><dt>{m.label}</dt><dd>{m.value}</dd></div>)}</dl>}
        </article>
      ))}
    </div>
  );
}

const CALLOUT = { info: [Info, "Note"], success: [CheckCircle2, "Success"], warning: [AlertTriangle, "Warning"], danger: [OctagonAlert, "Danger"] } as const;

export function CalloutWidget({ p }: { p: CalloutP }) {
  const [Icon, label] = CALLOUT[p.level];
  return (
    <div className="wg-callout" data-level={p.level} role="note">
      <Icon size={18} aria-hidden />
      <div>
        <p className="wg-callout-t" dir="auto">{p.title ?? label}{!p.title ? null : <span className="sr-only"> ({label})</span>}</p>
        <p dir="auto">{p.body}</p>
      </div>
    </div>
  );
}

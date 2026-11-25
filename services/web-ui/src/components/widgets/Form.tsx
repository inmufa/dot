"use client";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useId } from "react";
import { Checkbox, Input, Radio, Switch, Textarea } from "@/components/ui";
import type { Draft, Field } from "./fields";
import "./fm.css";

interface Props { fields: Field[]; draft: Draft; errors: Record<string, string>; disabled?: boolean; onChange: (id: string, v: unknown) => void }

function Rank({ f, value, disabled, onChange, describedBy }: { f: Field; value: string[]; disabled?: boolean; onChange: (v: string[]) => void; describedBy: string }) {
  const move = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= value.length) return;
    const next = [...value];
    [next[i], next[j]] = [next[j] as string, next[i] as string];
    onChange(next);
    requestAnimationFrame(() => document.getElementById(`${describedBy}-r${j}`)?.focus());
  };
  return (
    <ol className="fm-rank" aria-label={f.label}>
      {value.map((l, i) => (
        <li key={l} className="fm-rank-row">
          <span className="fm-rank-n" aria-hidden>{i + 1}</span>
          <span className="fm-rank-l" dir="auto">{l}</span>
          <button type="button" id={`${describedBy}-r${i}`} className="btn btn-ghost btn-icon btn-sm press" disabled={disabled || i === 0} aria-label={`Move ${l} up`} onClick={() => move(i, -1)} onKeyDown={(e) => { if (e.altKey && e.key === "ArrowDown") { e.preventDefault(); move(i, 1); } }}><ArrowUp size={14} aria-hidden /></button>
          <button type="button" className="btn btn-ghost btn-icon btn-sm press" disabled={disabled || i === value.length - 1} aria-label={`Move ${l} down`} onClick={() => move(i, 1)}><ArrowDown size={14} aria-hidden /></button>
        </li>
      ))}
    </ol>
  );
}

function Opt({ multi, children, ...rest }: { multi: boolean; name: string; checked: boolean; disabled?: boolean; onChange: () => void; children: React.ReactNode }) {
  const C = multi ? Checkbox : Radio;
  return <C {...rest}>{children}</C>;
}

function Control({ f, v, disabled, onChange, uid }: { f: Field; v: unknown; disabled?: boolean; onChange: (v: unknown) => void; uid: string }) {
  const err = `${uid}-e`, desc = `${uid}-d`;
  const common = { id: uid, disabled, "aria-describedby": `${desc} ${err}` } as const;
  switch (f.type) {
    case "single_select":
    case "multi_select": {
      const multi = f.type === "multi_select";
      const cur = multi ? (v as string[]) : [v as string | null];
      return (
        <div className="fm-opts" role={multi ? "group" : "radiogroup"} aria-labelledby={`${uid}-l`} aria-describedby={`${desc} ${err}`}>
          {f.options.map((o) => {
            const on = cur.includes(o.label);
            return (
              <Opt key={o.label} multi={multi} name={uid} checked={on} disabled={disabled}
                onChange={() => onChange(multi ? (on ? cur.filter((x) => x !== o.label) : [...cur, o.label]) : o.label)}>
                <span className="q-opt-text">
                  <span className="q-opt-label" dir="auto">{o.label}</span>
                  {o.description && <span className="q-opt-desc muted" dir="auto">{o.description}</span>}
                </span>
              </Opt>
            );
          })}
        </div>
      );
    }
    case "text":
      return f.multiline
        ? <Textarea {...common} rows={3} value={v as string} maxLength={f.max} placeholder={f.placeholder} dir="auto" onChange={(e) => onChange(e.target.value)} />
        : <Input {...common} type="text" value={v as string} maxLength={f.max} placeholder={f.placeholder} dir="auto" autoComplete="off" onChange={(e) => onChange(e.target.value)} />;
    case "number":
      return <Input {...common} className="fm-num" type="number" inputMode="decimal" value={v as string} min={f.min} max={f.max} step={f.step ?? "any"} placeholder={f.placeholder} onChange={(e) => onChange(e.target.value)} />;
    case "slider":
      return (
        <div className="fm-slider">
          <input {...common} type="range" min={f.min ?? 0} max={f.max ?? 100} step={f.step ?? 1} value={v as string} onChange={(e) => onChange(e.target.value)} aria-valuetext={String(v)} />
          <output htmlFor={uid}>{String(v)}</output>
        </div>
      );
    case "toggle":
      return (
        <div className="fm-toggle">
          <Switch {...common} checked={v === true} onChange={(e) => onChange(e.target.checked)} />
          <span className="fm-state">{v === true ? "On" : "Off"}</span>
        </div>
      );
    case "date":
      return <Input {...common} className="fm-date" type="date" value={v as string} onChange={(e) => onChange(e.target.value)} />;
    case "rank":
      return <Rank f={f} value={v as string[]} disabled={disabled} onChange={onChange} describedBy={uid} />;
  }
}

export function FormFields({ fields, draft, errors, disabled, onChange }: Props) {
  const base = useId();
  return (
    <div className="fm">
      {fields.map((f) => {
        const uid = `${base}${f.id.replace(/[^\w-]/g, "_")}`;
        const group = f.type === "single_select" || f.type === "multi_select" || f.type === "rank";
        const e = errors[f.id];
        return (
          <div key={f.id} className="fm-field" data-invalid={!!e}>
            {group || f.type === "toggle"
              ? <div className="fm-label" id={`${uid}-l`}>{f.label}{f.required && <span className="fm-req" aria-hidden> *</span>}{f.required && <span className="sr-only"> (required)</span>}</div>
              : <label className="fm-label" id={`${uid}-l`} htmlFor={uid}>{f.label}{f.required && <span className="fm-req" aria-hidden> *</span>}{f.required && <span className="sr-only"> (required)</span>}</label>}
            {f.help && <p className="fm-help muted" id={`${uid}-d`} dir="auto">{f.help}</p>}
            {!f.help && <span id={`${uid}-d`} hidden />}
            <Control f={f} v={draft[f.id]} disabled={disabled} uid={uid} onChange={(v) => onChange(f.id, v)} />
            <p className="q-err fm-err" id={`${uid}-e`} role={e ? "alert" : undefined}>{e}</p>
          </div>
        );
      })}
    </div>
  );
}

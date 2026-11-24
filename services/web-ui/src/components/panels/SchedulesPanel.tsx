"use client";
import { useState } from "react";
import { useResource } from "@/hooks/useResource";
import { api, type ScheduleInfo } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/api/errors";
import { describeCronText, parseCron, describeCron } from "@/lib/cron";
import { clip, relativeTime } from "@/lib/format";
import { Sheet } from "../ui/Sheet";
import { ErrorBox, Skeletons, StateBox } from "../ui/StateBox";

const stamp = (d: Date | string | null): string =>
  d ? new Date(d).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "none";

function human(cron: string): string {
  const r = parseCron(cron);
  return r.ok ? describeCron(r.fields) : "Custom schedule";
}

function Row({ s, onDelete }: { s: ScheduleInfo; onDelete: (id: string) => void }) {
  const [ask, setAsk] = useState(false);
  return (
    <li className="row">
      <div className="row-main">
        <span className="row-title" dir="auto">{human(s.cron)}</span>
        <span className="badge mono">{clip(s.cron, 40)}</span>
        {s.kind === "builtin" && <span className="badge">built-in</span>}
        {!s.enabled && <span className="badge" data-tone="warn">paused</span>}
      </div>
      <p className="row-desc" dir="auto">{clip(s.prompt, 220)}</p>
      <p className="row-desc muted">
        Next: {stamp(s.next_run_at)}. Last: {s.last_run_at ? `${relativeTime(s.last_run_at)} ago` : "never"}
        {s.last_status ? `, ${s.last_status}` : ""}.
      </p>
      {s.kind === "user" &&
        (ask ? (
          <div className="tl-confirm" role="group" aria-label="Delete this schedule?">
            <span className="row-desc">Delete this schedule?</span>
            <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(s.id)}>Delete</button>
            <button type="button" className="btn btn-sm" onClick={() => setAsk(false)}>Keep</button>
          </div>
        ) : (
          <button type="button" className="btn btn-sm" onClick={() => setAsk(true)} aria-label={`Delete schedule ${clip(s.cron, 30)}`}>Delete</button>
        ))}
    </li>
  );
}

function CreateForm({ onDone }: { onDone: () => void }) {
  const [cron, setCron] = useState("");
  const [prompt, setPrompt] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const prev = cron.trim() ? describeCronText(cron) : null;
  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.scheduleAdd(cron.trim(), prompt.trim());
      setCron("");
      setPrompt("");
      onDone();
    } catch (x) {
      const i = toErrorInfo(x);
      setErr(`${i.title}${i.code !== null ? ` (code ${i.code})` : ""}`);
    }
    setBusy(false);
  };
  const valid = prev !== null && !("error" in prev);
  return (
    <form
      className="mem-form"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <div className="field">
        <label>Cron (minute hour day month weekday)
          <input className="input mono" value={cron} maxLength={100} placeholder="30 3 * * *" spellCheck={false} autoComplete="off" onChange={(e) => setCron(e.target.value)} aria-describedby="cron-prev" />
        </label>
        <p id="cron-prev" className="help" role="status">
          {prev === null ? "Examples: */15 * * * *, 0 9 * * mon-fri, @daily." : "error" in prev ? prev.error : `${prev.text}. ${prev.next ? `Next: ${stamp(prev.next)} (this browser's time zone).` : "It never runs."}`}
        </p>
      </div>
      <div className="field"><label>Prompt<textarea className="input area" rows={3} maxLength={20000} value={prompt} onChange={(e) => setPrompt(e.target.value)} /></label></div>
      {err && <p className="q-err" role="alert">{err}</p>}
      <button type="submit" className="btn btn-primary" disabled={!valid || !prompt.trim() || busy}>Create schedule</button>
    </form>
  );
}

export function SchedulesPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const r = useResource(api.schedules, open);
  const [note, setNote] = useState<string | null>(null);
  const del = async (id: string) => {
    try {
      await api.scheduleDelete(id);
      r.reload();
    } catch (e) {
      setNote(toErrorInfo(e).title);
    }
  };
  return (
    <Sheet open={open} onClose={onClose} title="Schedules">
      <p className="help-text">Dot runs each prompt in a fresh session, in Default mode. Calls that need approval wait for you or fail.</p>
      <CreateForm onDone={r.reload} />
      {note && <p className="q-err" role="alert">{note}</p>}
      {r.error && !r.data ? (
        <ErrorBox error={r.error} onRetry={r.reload} />
      ) : !r.data ? (
        <Skeletons />
      ) : r.data.length === 0 ? (
        <StateBox title="No schedules">Create one above, for example a daily summary at 09:00.</StateBox>
      ) : (
        <ul className="rows">{r.data.map((s) => <Row key={s.id} s={s} onDelete={(id) => void del(id)} />)}</ul>
      )}
    </Sheet>
  );
}

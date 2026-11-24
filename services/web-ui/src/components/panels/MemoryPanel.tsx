"use client";
import { Plus, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useResource } from "@/hooks/useResource";
import { api, type MemoryDraft, type MemoryFact } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/api/errors";
import { clip, relativeTime } from "@/lib/format";
import { Sheet } from "../ui/Sheet";
import { ErrorBox, Skeletons, StateBox } from "../ui/StateBox";

const KINDS: MemoryFact["kind"][] = ["user", "feedback", "project", "reference"];
const EMPTY: MemoryDraft = { name: "", description: "", kind: "project", body: "" };

function Form({ init, onSave, onCancel }: { init: MemoryDraft; onSave: (d: MemoryDraft) => Promise<string | null>; onCancel: () => void }) {
  const [d, setD] = useState(init);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    setErr(await onSave({ ...d, name: d.name.trim(), body: d.body.trim() }));
    setBusy(false);
  };
  const ok = d.name.trim() !== "" && d.body.trim() !== "";
  const set = <K extends keyof MemoryDraft>(k: K, v: MemoryDraft[K]) => setD((p) => ({ ...p, [k]: v }));
  return (
    <form
      className="mem-form"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <div className="field"><label>Name<input className="input" value={d.name} maxLength={80} required onChange={(e) => set("name", e.target.value)} /></label></div>
      <div className="field"><label>Description<input className="input" value={d.description} maxLength={200} onChange={(e) => set("description", e.target.value)} /></label></div>
      <div className="field"><label>Kind<select className="input" value={d.kind} onChange={(e) => set("kind", e.target.value as MemoryFact["kind"])}>{KINDS.map((k) => <option key={k}>{k}</option>)}</select></label></div>
      <div className="field"><label>Fact<textarea className="input area" value={d.body} maxLength={8000} rows={5} required onChange={(e) => set("body", e.target.value)} /></label></div>
      {err && <p className="q-err" role="alert">{err}</p>}
      <div className="confirm-actions">
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={!ok || busy}>Save fact</button>
      </div>
    </form>
  );
}

export function MemoryPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const r = useResource(() => api.memory(term), open, 0, term);
  const { reload } = r;
  useEffect(() => {
    const t = window.setTimeout(() => setTerm(q.trim()), 250);
    return () => window.clearTimeout(t);
  }, [q]);

  const save = (id: string | null) => async (d: MemoryDraft): Promise<string | null> => {
    try {
      if (id === null) await api.memoryAdd(d);
      else await api.memoryUpdate(id, d);
      setEditing(null);
      setAdding(false);
      reload();
      return null;
    } catch (e) {
      const i = toErrorInfo(e);
      return `${i.title}${i.code !== null ? ` (code ${i.code})` : ""}`;
    }
  };
  const remove = async (id: string) => {
    try {
      await api.memoryDelete(id);
      setConfirm(null);
      reload();
    } catch (e) {
      setNote(toErrorInfo(e).title);
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title="Memory">
      <p className="help-text">Facts Dot saved about you and your projects. They are notes, never instructions. Edits apply from the next turn.</p>
      {adding ? (
        <Form init={EMPTY} onSave={save(null)} onCancel={() => setAdding(false)} />
      ) : (
        <div className="panel-bar">
          <div className="rail-search grow">
            <Search size={14} aria-hidden />
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search facts" aria-label="Search facts" />
          </div>
          <button type="button" className="btn" onClick={() => setAdding(true)}><Plus size={16} aria-hidden /> Add</button>
        </div>
      )}
      {note && <p className="q-err" role="alert">{note}</p>}
      {r.error ? (
        <ErrorBox error={r.error} onRetry={r.reload} />
      ) : !r.data ? (
        <Skeletons />
      ) : r.data.length === 0 ? (
        <StateBox title={term ? "No match" : "No facts yet"}>{term ? "No fact matches that search." : "Dot adds facts when you tell it to remember something. You can add one here too."}</StateBox>
      ) : (
        <ul className="rows">
          {r.data.map((f) => (
            <li key={f.id} className="row fact">
              {editing === f.id ? (
                <Form init={f} onSave={save(f.id)} onCancel={() => setEditing(null)} />
              ) : (
                <>
                  <div className="row-main">
                    <span className="row-title" dir="auto">{clip(f.name, 120)}</span>
                    <span className="badge">{f.kind}</span>
                    <span className="muted row-time">{relativeTime(f.updated_at)}</span>
                  </div>
                  {f.description && <p className="row-desc" dir="auto">{clip(f.description, 200)}</p>}
                  <p className="row-desc muted fact-body" dir="auto">{f.body}</p>
                  {confirm === f.id ? (
                    <div className="tl-confirm" role="group" aria-label={`Delete ${clip(f.name, 40)}?`}>
                      <span className="row-desc">Delete this fact for good?</span>
                      <button type="button" className="btn btn-sm btn-danger" onClick={() => void remove(f.id)}>Delete</button>
                      <button type="button" className="btn btn-sm" onClick={() => setConfirm(null)}>Keep</button>
                    </div>
                  ) : (
                    <div className="tl-confirm">
                      <button type="button" className="btn btn-sm" onClick={() => { setEditing(f.id); setConfirm(null); }} aria-label={`Edit ${clip(f.name, 40)}`}>Edit</button>
                      <button type="button" className="btn btn-sm" onClick={() => setConfirm(f.id)} aria-label={`Delete ${clip(f.name, 40)}`}>Delete</button>
                    </div>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

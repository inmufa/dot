"use client";
import { useState } from "react";
import { Button, Field, Input, Segmented, Textarea } from "@/components/ui";
import type { MemoryDraft, MemoryFact } from "@/lib/api/client";

export const KINDS: MemoryFact["kind"][] = ["user", "feedback", "project", "reference"];
export const EMPTY: MemoryDraft = { name: "", description: "", kind: "project", body: "" };

export function MemoryForm({ init, onSave, onCancel }: { init: MemoryDraft; onSave: (d: MemoryDraft) => Promise<string | null>; onCancel: () => void }) {
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
    <form className="pn-form" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <Field label="Name">{(p) => <Input {...p} dir="auto" value={d.name} maxLength={80} required onChange={(e) => set("name", e.target.value)} />}</Field>
      <Field label="Description" help="One line on when this fact matters.">{(p) => <Input {...p} dir="auto" value={d.description} maxLength={200} onChange={(e) => set("description", e.target.value)} />}</Field>
      <Field label="Kind">{() => <Segmented label="Kind" value={d.kind} options={KINDS.map((k) => ({ value: k, label: k }))} onChange={(k) => set("kind", k)} size="sm" />}</Field>
      <Field label="Fact" error={err}>{(p) => <Textarea {...p} dir="auto" value={d.body} maxLength={8000} rows={5} required onChange={(e) => set("body", e.target.value)} />}</Field>
      <div className="pn-actions">
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" variant="solid" loading={busy} disabled={!ok}>Save fact</Button>
      </div>
    </form>
  );
}

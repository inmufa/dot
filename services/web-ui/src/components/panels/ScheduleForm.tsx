"use client";
import { useState } from "react";
import { Button, Field, Input, Textarea, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/api/errors";
import { describeCronText } from "@/lib/util/cron";

export const stamp = (d: Date | string | null): string =>
  d ? new Date(d).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "none";

export function ScheduleForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [cron, setCron] = useState("");
  const [prompt, setPrompt] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const prev = cron.trim() ? describeCronText(cron) : null;
  const valid = prev !== null && !("error" in prev);
  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.scheduleAdd(cron.trim(), prompt.trim());
      toast({ title: "Schedule created", tone: "ok" });
      onDone();
    } catch (x) {
      const i = toErrorInfo(x);
      setErr(`${i.title}${i.code !== null ? ` (code ${i.code})` : ""}`);
    }
    setBusy(false);
  };
  const help = prev === null ? "Examples: */15 * * * *, 0 9 * * mon-fri, @daily." : "error" in prev ? null : `${prev.text}. ${prev.next ? `Next: ${stamp(prev.next)} (this browser's time zone).` : "It never runs."}`;
  return (
    <form className="pn-form" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <Field label="Cron (minute hour day month weekday)" help={help} error={prev && "error" in prev ? prev.error : null}>
        {(p) => <Input {...p} className="mono" value={cron} maxLength={100} placeholder="30 3 * * *" spellCheck={false} autoComplete="off" onChange={(e) => setCron(e.target.value)} />}
      </Field>
      <Field label="Prompt" error={err}>{(p) => <Textarea {...p} dir="auto" rows={3} maxLength={20000} value={prompt} onChange={(e) => setPrompt(e.target.value)} />}</Field>
      <div className="pn-actions">
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" variant="solid" loading={busy} disabled={!valid || !prompt.trim()}>Create schedule</Button>
      </div>
    </form>
  );
}

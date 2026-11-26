"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, Kbd, StateDot } from "@/components/ui";
import { PendRail } from "@/components/activity/PendParts";
import { FormFields } from "./Form";
import { initialDraft, toAnswer, validateDraft, type Field } from "./fields";

const TIMEOUT_S = 300;
const clock = (s: number): string => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

interface Props {
  text: string;
  fields: Field[];
  at: number;
  onSubmit: (answer: Record<string, unknown>) => Promise<string | null>;
  onExpire: () => void;
}

/** Blocking Ask form (question.fields). Submits {id: value}; Ctrl+Enter sends. */
export function FormQuestion({ text, fields, at, onSubmit, onExpire }: Props) {
  const [draft, setDraft] = useState(() => initialDraft(fields));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [tried, setTried] = useState(false);
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [left, setLeft] = useState(TIMEOUT_S);
  const card = useRef<HTMLFieldSetElement>(null);

  useEffect(() => {
    card.current?.focus();
    const tick = () => {
      const l = Math.max(0, TIMEOUT_S - Math.round((Date.now() - at) / 1000));
      setLeft(l);
      if (l === 0) onExpire();
    };
    tick();
    const t = window.setInterval(tick, 1000);
    return () => window.clearInterval(t);
  }, [at, onExpire]);

  const change = useCallback((id: string, v: unknown) => {
    setErr(null);
    setDraft((d) => ({ ...d, [id]: v }));
  }, []);
  // After a failed submit, errors follow the draft live.
  const live = useMemo(() => (tried ? validateDraft(fields, draft) : errors), [tried, fields, draft, errors]);

  const submit = useCallback(async () => {
    if (sent) return;
    const e = validateDraft(fields, draft);
    setTried(true);
    setErrors(e);
    const first = fields.find((f) => e[f.id]);
    if (first) {
      card.current?.querySelector<HTMLElement>(`[aria-invalid], [id$="${first.id.replace(/[^\w-]/g, "_")}"], .fm-field[data-invalid="true"] input, .fm-field[data-invalid="true"] textarea`)?.focus();
      return;
    }
    setSent(true);
    const r = await onSubmit(toAnswer(fields, draft));
    if (r) { setErr(r); setSent(false); }
  }, [sent, fields, draft, onSubmit]);

  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <fieldset className="pend approval question" ref={card} tabIndex={-1} aria-describedby="q-hint" disabled={sent}
      onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void submit(); } }}>
      <legend className="sr-only">{text}</legend>
      <PendRail />
      <div className="pend-body">
      <div className="approval-head">
        <span className="pend-inline"><StateDot state="waiting" /></span>
        <h2>Dot is asking</h2>
        <Badge title="The turn continues without an answer after this">{clock(left)} left</Badge>
      </div>
      <p className="q-text" dir="auto">{text}</p>
      <FormFields fields={fields} draft={draft} errors={live} disabled={sent} onChange={change} />
      {err && <p className="q-err" role="alert">{err}</p>}
      <div className="approval-actions">
        <Button variant="solid" onClick={() => void submit()}>Send answer <Kbd>Ctrl</Kbd>+<Kbd>Enter</Kbd></Button>
        <span id="q-hint" className="muted q-hint">Fields marked * are required. <span className="sr-only">{clock(left)} left to answer.</span></span>
      </div>
      </div>
    </fieldset>
  );
}

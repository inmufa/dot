"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Item } from "@/lib/stream/reducer";
import { StateDot } from "../ui/StateDot";

type Q = Extract<Item, { kind: "question" }>;
export const QUESTION_TIMEOUT_S = 300;

const clock = (s: number): string => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

interface Props {
  q: Q;
  onAnswer: (selected: string[], other: string | null) => Promise<string | null>;
  onExpire: () => void;
}

export function QuestionCard({ q, onAnswer, onExpire }: Props) {
  const [picked, setPicked] = useState<string[]>([]);
  const [other, setOther] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [left, setLeft] = useState(QUESTION_TIMEOUT_S);
  const card = useRef<HTMLFieldSetElement>(null);

  useEffect(() => {
    card.current?.focus();
    const tick = () => {
      const l = Math.max(0, QUESTION_TIMEOUT_S - Math.round((Date.now() - q.at) / 1000));
      setLeft(l);
      if (l === 0) onExpire();
    };
    tick();
    const t = window.setInterval(tick, 1000);
    return () => window.clearInterval(t);
  }, [q.at, onExpire]);

  const toggle = useCallback(
    (label: string) => {
      setErr(null);
      if (q.multi) setPicked((p) => (p.includes(label) ? p.filter((x) => x !== label) : [...p, label]));
      else {
        setPicked([label]);
        setOther("");
      }
    },
    [q.multi],
  );

  const text = other.trim();
  const can = !sent && (picked.length > 0 || text.length > 0);
  const submit = useCallback(async () => {
    if (!can) return;
    setSent(true);
    const e = await onAnswer(picked, text || null);
    if (e) {
      setErr(e);
      setSent(false);
    }
  }, [can, onAnswer, picked, text]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
      const t = e.target as HTMLElement;
      if (t.closest("input[type=text], textarea, select, [contenteditable]")) return;
      const n = Number(e.key);
      if (n >= 1 && n <= q.options.length) {
        e.preventDefault();
        const o = q.options[n - 1];
        if (o) toggle(o.label);
      } else if (e.key === "Enter" && !t.closest("button")) {
        e.preventDefault();
        void submit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [q.options, toggle, submit]);

  return (
    <fieldset className="approval question" ref={card} tabIndex={-1} aria-describedby="q-hint">
      <legend className="sr-only">{q.text}</legend>
      <div className="approval-head">
        <StateDot state="waiting" />
        <h2 id="q-title">Dot is asking</h2>
        <span className="badge" aria-hidden title="The turn continues without an answer after this">{clock(left)} left</span>
      </div>
      <p className="q-text" dir="auto">{q.text}</p>
      <ul className="q-opts">
        {q.options.map((o, i) => {
          const on = picked.includes(o.label);
          return (
            <li key={o.label}>
              <label className="q-opt" data-on={on}>
                <input type={q.multi ? "checkbox" : "radio"} name="q" checked={on} onChange={() => toggle(o.label)} />
                <kbd aria-hidden>{i + 1}</kbd>
                <span className="q-opt-text">
                  <span className="q-opt-label">{o.label}</span>
                  {o.description && <span className="q-opt-desc muted">{o.description}</span>}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      <div className="q-other">
        <label htmlFor="q-other">Other</label>
        <input
          id="q-other"
          className="input"
          type="text"
          value={other}
          maxLength={500}
          placeholder="Type your own answer"
          autoComplete="off"
          dir="auto"
          onChange={(e) => {
            setOther(e.target.value);
            setErr(null);
            if (!q.multi && e.target.value) setPicked([]);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void submit();
            }
          }}
        />
      </div>
      {err && <p className="q-err" role="alert">{err}</p>}
      <div className="approval-actions">
        <button type="button" className="btn btn-primary" aria-disabled={!can} onClick={() => void submit()}>
          Send answer <kbd>Enter</kbd>
        </button>
        <span id="q-hint" className="muted q-hint">
          {q.multi ? "Pick any number." : "Pick one."} Keys <kbd>1</kbd>-<kbd>{q.options.length}</kbd> select. <span className="sr-only">{clock(left)} left to answer.</span>
        </span>
      </div>
    </fieldset>
  );
}

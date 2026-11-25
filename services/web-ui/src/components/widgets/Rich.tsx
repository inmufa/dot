"use client";
import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";
import { Button, Tabs } from "@/components/ui";
import { Markdown } from "@/components/chat/Markdown";
import { useApp } from "@/lib/state/app";
import type { AccordionP, ChoicesP, TabsP } from "./schema";

export function TabsWidget({ p }: { p: TabsP }) {
  const [i, setI] = useState(0);
  const uid = useId();
  return (
    <div className="wg-tabs">
      <Tabs label="Tabs" idBase={uid} value={String(i)} onChange={(v) => setI(Number(v))} tabs={p.tabs.map((t, k) => ({ id: String(k), label: t.label }))} />
      <div role="tabpanel" id={`${uid}-${i}-panel`} aria-labelledby={`${uid}-${i}`} className="wg-panel" key={i}>
        <Markdown text={p.tabs[i]?.body ?? ""} settled />
      </div>
    </div>
  );
}

export function AccordionWidget({ p }: { p: AccordionP }) {
  const uid = useId();
  const [open, setOpen] = useState<Set<number>>(new Set());
  const flip = (k: number) => setOpen((s) => { const n = new Set(s); if (!n.delete(k)) n.add(k); return n; });
  return (
    <div className="wg-acc">
      {p.items.map((x, k) => (
        <section key={k} data-open={open.has(k)}>
          <h4><button type="button" aria-expanded={open.has(k)} aria-controls={`${uid}${k}`} onClick={() => flip(k)}><span dir="auto">{x.title}</span><ChevronDown size={16} aria-hidden /></button></h4>
          <div className="wg-acc-body" id={`${uid}${k}`} inert={!open.has(k)}><div><Markdown text={x.body} settled /></div></div>
        </section>
      ))}
    </div>
  );
}

/** Quick replies: the visible label is exactly what is sent. Frozen once one is used. */
export function ChoicesWidget({ p }: { p: ChoicesP }) {
  const { send, id } = useApp();
  const [used, setUsed] = useState<string | null>(null);
  return (
    <div className="wg-choices" role="group" aria-label="Quick replies">
      {p.options.map((o, i) => (
        <Button key={i} className="wg-choice" data-used={used === o} disabled={used !== null || !id} dir="auto"
          onClick={() => { if (send(o)) setUsed(o); }}>{o}</Button>
      ))}
    </div>
  );
}

"use client";
import { useEffect, useRef, useState, type RefObject } from "react";
import { Button, Progress, useToast } from "@/components/ui";
import { useResource } from "@/hooks/useResource";
import { api } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/api/errors";
import { compactTokens, percent } from "@/lib/util/format";
import { chatStore } from "@/lib/state/store";
import "./context.css";

interface Usage { tokens: number; limit: number }

function Rows({ title, data }: { title: string; data: Record<string, number> }) {
  const rows = Object.entries(data).filter(([, v]) => v > 0);
  if (rows.length === 0) return null;
  return (
    <section className="cx-sect">
      <h3 className="rec">{title}</h3>
      <ul className="cx-rows">
        {rows.map(([k, v]) => (
          <li key={k}>
            <span className="cx-name" title={k}>{k}</span>
            <span className="cx-lead" aria-hidden />
            <span className="cx-val rec">{compactTokens(v)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

interface BodyProps { enabled: boolean; sessionId: string | null; running: boolean; usage: Usage | null }

/** Context breakdown and compact action; shared by the popover and the canvas tab. */
export function ContextBody({ enabled, sessionId, running, usage }: BodyProps) {
  const r = useResource(() => (sessionId ? api.context(sessionId) : Promise.reject(new Error("none"))), enabled && sessionId !== null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const c = r.data;
  const toast = useToast();

  const compact = async () => {
    if (!sessionId) return;
    setBusy(true);
    setNote(null);
    try {
      const out = await api.compact(sessionId);
      const msg = out.compacted ? `Compacted ${compactTokens(out.tokens_before)} to ${compactTokens(out.tokens_after)}.` : out.reason === "blocked" ? "A hook blocked compaction." : "Nothing to compact yet.";
      setNote(msg);
      toast({ title: msg, tone: out.compacted ? "ok" : "neutral" });
      if (out.compacted && usage) chatStore.noteUsage(sessionId, out.tokens_after, usage.limit);
      r.reload();
    } catch (e) {
      const i = toErrorInfo(e);
      setNote(`${i.title}${i.hint ? ` ${i.hint}` : ""}`);
      toast({ title: "Could not compact", description: i.title, tone: "bad" });
    }
    setBusy(false);
  };

  return (
    <>
      {r.error ? (
        <p className="cx-muted" role="alert">{r.error.title}</p>
      ) : !c ? (
        <Progress label="Loading context" />
      ) : (
        <>
          <div className="cx-meter">
            <div className="cx-gauge">
              <Progress label="Context used" value={percent(c.used, c.limit) / 100} tone={percent(c.used, c.limit) >= 92 ? "bad" : percent(c.used, c.limit) >= 80 ? "warn" : "accent"} />
              <span className="cx-mark" style={{ left: `${percent(c.threshold, c.limit)}%` }} title={`Compacts at ${compactTokens(c.threshold)}`} />
            </div>
            <p className="cx-sum">
              <strong className="rec">{compactTokens(c.used)}</strong> of {compactTokens(c.limit)} tokens, {percent(c.used, c.limit)}%{c.source === "estimated" ? " (estimated)" : ""}.
              {" "}Compacts by itself at {compactTokens(c.threshold)}.
            </p>
          </div>
          <Rows title="prompt layers" data={c.tiers} />
          <Rows title="messages" data={c.messages} />
          {c.compactions.length > 0 && (
            <section className="cx-sect">
              <h3 className="rec">compactions <span>{c.compactions.length}</span></h3>
              <ul className="cx-rows">
                {c.compactions.slice(-4).reverse().map((k) => (
                  <li key={k.id}>
                    <span className="cx-name">{k.trigger}{k.undone ? ", undone by rewind" : ""}</span>
                    <span className="cx-lead" aria-hidden />
                    <span className="cx-val rec">{compactTokens(k.tokens_before)} to {compactTokens(k.tokens_after)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      {(note || (c && Object.values(c.messages).some((v) => v > 0))) && <div className="cx-foot">
        <Button size="sm" variant="solid" disabled={!sessionId || running || busy} loading={busy} title={running ? "Wait for the turn to finish" : undefined} onClick={() => void compact()}>Compact now</Button>
        <span className="cx-muted cx-note" role="status">{running ? "Wait for the turn to finish." : (note ?? "Summarizes older messages to free space.")}</span>
      </div>}
    </>
  );
}

interface Props { id: string; anchor: RefObject<HTMLElement | null>; open: boolean; onOpen: (o: boolean) => void; sessionId: string | null; running: boolean; usage: Usage | null }

/** Native popover placed against the trigger just before it shows (above it when there is room, composer sits at the bottom). */
export function ContextPopover({ id, anchor, open, onOpen, sessionId, running, usage }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const place = (e: Event) => {
      if ((e as ToggleEvent).newState !== "open") return;
      const a = anchor.current?.getBoundingClientRect();
      if (!a) return;
      const w = Math.min(22 * 16, window.innerWidth - 16);
      const up = a.top > window.innerHeight - a.bottom;
      el.style.width = `${w}px`;
      el.style.left = `${Math.max(8, Math.min(a.left, window.innerWidth - w - 8))}px`;
      el.style.maxHeight = `${(up ? a.top : window.innerHeight - a.bottom) - 16}px`;
      el.style.top = up ? "auto" : `${a.bottom + 8}px`;
      el.style.bottom = up ? `${window.innerHeight - a.top + 8}px` : "auto";
      el.dataset.origin = up ? "bottom-left" : "top-left";
    };
    el.addEventListener("beforetoggle", place);
    return () => el.removeEventListener("beforetoggle", place);
  }, [anchor]);
  return (
    <div ref={ref} id={id} popover="auto" className="ctx-pop" aria-label="Context details" onToggle={(e) => onOpen(e.newState === "open")}>
      <h2 className="cx-title">Context</h2>
      <ContextBody enabled={open} sessionId={sessionId} running={running} usage={usage} />
    </div>
  );
}

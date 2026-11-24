"use client";
import { useState } from "react";
import { useResource } from "@/hooks/useResource";
import { api } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/api/errors";
import { compactTokens, percent } from "@/lib/format";
import { chatStore } from "@/lib/store";

interface Props {
  id: string;
  open: boolean;
  onOpen: (o: boolean) => void;
  sessionId: string | null;
  running: boolean;
  usage: { tokens: number; limit: number } | null;
}

function Bars({ title, data }: { title: string; data: Record<string, number> }) {
  const rows = Object.entries(data).filter(([, v]) => v > 0);
  const max = Math.max(1, ...rows.map(([, v]) => v));
  if (rows.length === 0) return null;
  return (
    <section>
      <h3 className="pop-h">{title}</h3>
      <ul className="bars">
        {rows.map(([k, v]) => (
          <li key={k}>
            <span className="bar-name">{k}</span>
            <span className="bar-track" aria-hidden><span className="bar-fill" style={{ transform: `scaleX(${v / max})` }} /></span>
            <span className="num">{compactTokens(v)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ContextPopover({ id, open, onOpen, sessionId, running, usage }: Props) {
  const r = useResource(() => (sessionId ? api.context(sessionId) : Promise.reject(new Error("none"))), open && sessionId !== null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const c = r.data;

  const compact = async () => {
    if (!sessionId) return;
    setBusy(true);
    setNote(null);
    try {
      const out = await api.compact(sessionId);
      setNote(out.compacted ? `Compacted ${compactTokens(out.tokens_before)} to ${compactTokens(out.tokens_after)}.` : out.reason === "blocked" ? "A hook blocked compaction." : "Nothing to compact yet.");
      if (out.compacted && usage) chatStore.noteUsage(sessionId, out.tokens_after, usage.limit);
      r.reload();
    } catch (e) {
      const i = toErrorInfo(e);
      setNote(`${i.title}${i.hint ? ` ${i.hint}` : ""}`);
    }
    setBusy(false);
  };

  return (
    <div id={id} popover="auto" className="pop ctx-pop" aria-label="Context details" onToggle={(e) => onOpen(e.newState === "open")}>
      <h2 className="pop-title">Context</h2>
      {r.error ? (
        <p className="muted">{r.error.title}</p>
      ) : !c ? (
        <div className="skeleton" style={{ width: "70%" }} />
      ) : (
        <>
          <div className="pop-meter">
            <span className="ctx-track wide" aria-hidden>
              <span className="ctx-fill" style={{ transform: `scaleX(${percent(c.used, c.limit) / 100})` }} />
              <span className="ctx-mark" style={{ left: `${percent(c.threshold, c.limit)}%` }} />
            </span>
            <p className="pop-sum">
              <span className="num">{compactTokens(c.used)}</span> of <span className="num">{compactTokens(c.limit)}</span> tokens ({percent(c.used, c.limit)}%
              {c.source === "estimated" ? ", estimated" : ""}). Compacts automatically at <span className="num">{compactTokens(c.threshold)}</span>.
            </p>
          </div>
          <Bars title="Prompt layers" data={c.tiers} />
          <Bars title="Messages" data={c.messages} />
          {c.compactions.length > 0 && (
            <section>
              <h3 className="pop-h">Compactions</h3>
              <ul className="pop-list">
                {c.compactions.slice(-4).reverse().map((k) => (
                  <li key={k.id}>
                    <span className="num">{compactTokens(k.tokens_before)} to {compactTokens(k.tokens_after)}</span>{" "}
                    <span className="muted">{k.trigger}{k.undone ? ", undone by rewind" : ""}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      <div className="pop-actions">
        <button type="button" className="btn btn-sm" disabled={!sessionId || running || busy} onClick={() => void compact()}>
          {busy ? "Compacting..." : "Compact now"}
        </button>
        <span className="muted pop-note" role="status">{running ? "Wait for the turn to finish." : (note ?? "Summarizes older messages to free space.")}</span>
      </div>
    </div>
  );
}

"use client";
import { useCallback, useEffect, useState } from "react";
import { api, type AuditEntry } from "@/lib/api/client";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";
import { relativeTime, shortArgs } from "@/lib/format";
import { Sheet } from "../ui/Sheet";
import { ErrorBox, Skeletons, StateBox } from "../ui/StateBox";

export function AuditPanel({ open, onClose, sessionId }: { open: boolean; onClose: () => void; sessionId: string | null }) {
  const [items, setItems] = useState<AuditEntry[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<DotErrorInfo | null>(null);
  const [mine, setMine] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (more: boolean, next: string | null) => {
      setBusy(true);
      try {
        const page = await api.audit(more ? next : null, mine && sessionId ? sessionId : undefined);
        setItems((prev) => (more && prev ? [...prev, ...page.items] : page.items));
        setCursor(page.next_cursor);
        setError(null);
      } catch (e) {
        setError(toErrorInfo(e));
      } finally {
        setBusy(false);
      }
    },
    [mine, sessionId],
  );

  useEffect(() => {
    if (open) {
      setItems(null);
      void load(false, null);
    }
  }, [open, load]);

  return (
    <Sheet open={open} onClose={onClose} title="Audit log">
      <label className="check">
        <input type="checkbox" checked={mine} disabled={!sessionId} onChange={(e) => setMine(e.target.checked)} /> Only this session
      </label>
      {error ? (
        <ErrorBox error={error} onRetry={() => void load(false, null)} />
      ) : !items ? (
        <Skeletons />
      ) : items.length === 0 ? (
        <StateBox title="Nothing recorded">Every tool call and every answer you give is logged here.</StateBox>
      ) : (
        <>
          <ul className="rows">
            {items.map((a) => (
              <li key={a.id} className="row">
                <div className="row-main">
                  <span className="badge" data-tone={a.decision}>{a.decision}</span>
                  <span className="row-title">{a.tool}</span>
                  <span className="muted row-time">{relativeTime(a.created_at)}</span>
                </div>
                <p className="row-desc mono">{shortArgs(a.args, 160)}</p>
                <p className="row-desc muted">{a.source} in {a.mode} mode: {a.reason}</p>
              </li>
            ))}
          </ul>
          {cursor && (
            <button type="button" className="btn" disabled={busy} onClick={() => void load(true, cursor)}>
              {busy ? "Loading..." : "Load older"}
            </button>
          )}
        </>
      )}
    </Sheet>
  );
}

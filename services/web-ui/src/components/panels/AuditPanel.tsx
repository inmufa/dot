"use client";
import { Fragment, useCallback, useEffect, useState } from "react";
import { Button, Entry, Sheet, Switch } from "@/components/ui";
import { ErrorBox } from "@/components/ui/StateBox";
import { api, type AuditEntry } from "@/lib/api/client";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";
import { shortArgs } from "@/lib/util/format";
import { Empty, GroupLabel, Loading, PanelBar, Status, stampOf, type Tone } from "./parts";

const TONE: Record<string, Tone> = { allow: "ok", ask: "warn", deny: "bad" };
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }).toLowerCase();

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
      <PanelBar count={items ? `${items.length}${cursor ? "+" : ""} entries` : "reading"}>
        <Switch checked={mine} disabled={!sessionId} title={sessionId ? undefined : "Open a chat first"} onChange={(e) => setMine(e.target.checked)}>Only this chat</Switch>
      </PanelBar>
      {error ? (
        <ErrorBox error={error} onRetry={() => void load(false, null)} />
      ) : !items ? (
        <Loading />
      ) : items.length === 0 ? (
        <Empty title="Nothing logged yet.">Every tool call and every answer you give is written here, newest first.</Empty>
      ) : (
        <>
          <div className="pn-log">
            {items.map((a, i) => (
              <Fragment key={a.id}>
                {(i === 0 || day(a.created_at) !== day(items[i - 1]?.created_at ?? "")) && <GroupLabel>{day(a.created_at)}</GroupLabel>}
                <Entry time={stampOf(a.created_at, true)} i={Math.min(i, 6)} className="pn-entry">
                  <div className="pn-body">
                    <div className="pn-entry-head">
                      <span className="pn-title" title={a.tool}>{a.tool}</span>
                      <Status tone={TONE[a.decision] ?? "idle"}>{a.decision}</Status>
                    </div>
                    <p className="pn-args" title={shortArgs(a.args, 400)}>{shortArgs(a.args, 160)}</p>
                    <p className="pn-desc">{a.source} · {a.mode} mode · {a.reason}</p>
                  </div>
                </Entry>
              </Fragment>
            ))}
          </div>
          {cursor && <div className="pn-more"><Button variant="ghost" loading={busy} onClick={() => void load(true, cursor)}>Load older</Button></div>}
        </>
      )}
    </Sheet>
  );
}

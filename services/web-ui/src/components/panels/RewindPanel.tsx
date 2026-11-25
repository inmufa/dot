"use client";
import { useEffect, useState } from "react";
import { Bullet, Button, Dialog, Sheet, useToast } from "@/components/ui";
import { ErrorBox } from "@/components/ui/StateBox";
import { api, type RewindOut } from "@/lib/api/client";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";
import { chatStore } from "@/lib/state/store";
import type { WireMessage } from "@/lib/stream/history";
import { clip } from "@/lib/util/format";
import { Empty, Item, Loading, PanelBar } from "./parts";

interface Turn {
  seq: number;
  before: number;
  text: string;
}

function turnsOf(msgs: WireMessage[]): Turn[] {
  const users = msgs.filter((m) => m.role === "user" && !m.rewound);
  // Rewinding to "before prompt N" keeps the turn that contains the previous prompt (or nothing for the first).
  return users.map((m, i) => ({ seq: m.seq, before: users[i - 1]?.seq ?? 0, text: m.content })).reverse();
}

export function RewindPanel({ open, onClose, sessionId, running }: { open: boolean; onClose: () => void; sessionId: string | null; running: boolean }) {
  const [turns, setTurns] = useState<Turn[] | null>(null);
  const [error, setError] = useState<DotErrorInfo | null>(null);
  const [confirm, setConfirm] = useState<Turn | null>(null);
  const [result, setResult] = useState<RewindOut | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (!open || !sessionId) return;
    setTurns(null);
    setResult(null);
    setConfirm(null);
    setError(null);
    api.messages(sessionId).then((m) => setTurns(turnsOf(m)), (e: unknown) => setError(toErrorInfo(e)));
  }, [open, sessionId]);

  const restore = async () => {
    if (!sessionId || !confirm) return;
    setBusy(true);
    try {
      const out = await api.rewind(sessionId, confirm.before);
      setResult(out);
      toast({ title: `Rewound ${out.rewound_messages} messages`, description: `${out.restored.length} ${out.restored.length === 1 ? "file" : "files"} rolled back`, tone: "ok" });
      chatStore.reset(sessionId);
      void chatStore.load(sessionId);
      setTurns(null);
    } catch (e) {
      setError(toErrorInfo(e));
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title="Rewind">
      <p className="pn-intro">Pick a prompt to go back to just before it. Later messages are hidden from the model and files Dot changed after that point are restored.</p>
      {turns && turns.length > 0 && <PanelBar count={`${turns.length} prompts`} />}
      {result && (
        <div className="pn-result" role="status">
          <Bullet tone="ok" />
          <div>
            Rewound {result.rewound_messages} messages. {result.restored.length} {result.restored.length === 1 ? "file" : "files"} restored.
            {result.restored.length > 0 && <code className="rec">{result.restored.map((r) => `${r.action} ${r.path}`).join("\n")}</code>}
          </div>
        </div>
      )}
      {error ? (
        <ErrorBox error={error} onRetry={() => setError(null)} />
      ) : !sessionId ? (
        <Empty title="No chat open.">Open a chat first, then rewind it from here or from the top bar.</Empty>
      ) : !turns ? (
        <Loading />
      ) : turns.length === 0 ? (
        <Empty title="Nothing to rewind.">This chat has no prompts yet.</Empty>
      ) : (
        <ol className="pn-list">
          {turns.map((t) => (
            <Item
              key={t.seq}
              text={clip(t.text, 160)}
              time={`#${t.seq}`}
              actions={<Button variant="ghost" size="sm" disabled={running} title={running ? "Wait for the turn to finish" : undefined} aria-label={`Rewind to before: ${clip(t.text, 40)}`} onClick={() => setConfirm(t)}>Rewind here</Button>}
            />
          ))}
        </ol>
      )}
      {running && <p className="pn-intro">Rewind is off while a turn is running.</p>}
      <Dialog open={confirm !== null} onClose={() => setConfirm(null)} title="Rewind to before this prompt?" confirmLabel="Confirm rewind" danger busy={busy} onConfirm={() => void restore()}>
        {confirm ? `"${clip(confirm.text, 100)}" and everything after it is hidden, and later file changes are restored.` : null}
      </Dialog>
    </Sheet>
  );
}

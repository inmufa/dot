"use client";
import { useEffect, useState } from "react";
import { api, type RewindOut } from "@/lib/api/client";
import { toErrorInfo, type DotErrorInfo } from "@/lib/api/errors";
import { clip } from "@/lib/format";
import { chatStore } from "@/lib/store";
import type { WireMessage } from "@/lib/stream/history";
import { Sheet } from "../ui/Sheet";
import { ErrorBox, Skeletons, StateBox } from "../ui/StateBox";

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
  const [confirm, setConfirm] = useState<number | null>(null);
  const [result, setResult] = useState<RewindOut | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || !sessionId) return;
    setTurns(null);
    setResult(null);
    setConfirm(null);
    api.messages(sessionId).then((m) => setTurns(turnsOf(m)), (e: unknown) => setError(toErrorInfo(e)));
  }, [open, sessionId]);

  const restore = async (t: Turn) => {
    if (!sessionId) return;
    setBusy(true);
    try {
      setResult(await api.rewind(sessionId, t.before));
      chatStore.reset(sessionId);
      void chatStore.load(sessionId);
      setTurns(null);
      setConfirm(null);
    } catch (e) {
      setError(toErrorInfo(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title="Rewind">
      <p className="help-text">Pick a prompt to go back to just before it. Later messages are hidden from the model and files Dot changed after that point are restored.</p>
      {result && (
        <div className="notice" data-level="info" role="status">
          <span>
            Rewound {result.rewound_messages} messages. {result.restored.length} file{result.restored.length === 1 ? "" : "s"} restored.
            {result.restored.length > 0 && <code className="restored">{result.restored.map((r) => `${r.action} ${r.path}`).join("\n")}</code>}
          </span>
        </div>
      )}
      {error ? (
        <ErrorBox error={error} onRetry={() => setError(null)} />
      ) : !sessionId ? (
        <StateBox title="No session open">Open a session to rewind it.</StateBox>
      ) : !turns ? (
        <Skeletons />
      ) : turns.length === 0 ? (
        <StateBox title="Nothing to rewind">This session has no prompts yet.</StateBox>
      ) : (
        <ol className="timeline">
          {turns.map((t) => (
            <li key={t.seq} className="tl-item">
              <p className="tl-text" dir="auto">{clip(t.text, 160)}</p>
              {confirm === t.seq ? (
                <div className="tl-confirm">
                  <button type="button" className="btn btn-sm btn-danger" disabled={busy || running} onClick={() => void restore(t)}>
                    {busy ? "Rewinding..." : "Confirm rewind"}
                  </button>
                  <button type="button" className="btn btn-sm" onClick={() => setConfirm(null)}>Cancel</button>
                </div>
              ) : (
                <button type="button" className="btn btn-sm" disabled={running} onClick={() => setConfirm(t.seq)} aria-label={`Rewind to before: ${clip(t.text, 40)}`}>
                  Rewind here
                </button>
              )}
            </li>
          ))}
        </ol>
      )}
      {running && <p className="help-text">Rewind is disabled while a turn is running.</p>}
    </Sheet>
  );
}

"use client";
import { ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useResource } from "@/hooks/useResource";
import { api, type McpServer } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/api/errors";
import { clip } from "@/lib/format";
import { Sheet } from "../ui/Sheet";
import { ErrorBox, Skeletons, StateBox } from "../ui/StateBox";

const TONE = { connected: "ok", connecting: "ask", failed: "bad", needs_trust: "warn", stopped: undefined } as const;
const WORD = { connected: "connected", connecting: "connecting", failed: "failed", needs_trust: "needs trust", stopped: "stopped" } as const;

function Server({ s, busy, onAct }: { s: McpServer; busy: boolean; onAct: (name: string, a: "reconnect" | "trust") => void }) {
  const [ask, setAsk] = useState(false);
  return (
    <li className="row">
      <div className="row-main">
        <span className="row-title mono">{clip(s.name, 60)}</span>
        <span className="badge">{s.transport}</span>
        <span className="badge">{s.scope}</span>
        <span className="badge" data-tone={TONE[s.status]}>{WORD[s.status]}</span>
      </div>
      <p className="row-desc muted">{s.tool_count} {s.tool_count === 1 ? "tool" : "tools"}{s.status === "connected" ? " available to Dot" : ""}</p>
      {s.error && <p className="row-desc q-err">{clip(s.error, 400)}</p>}
      {s.status === "needs_trust" && !ask && (
        <button type="button" className="btn btn-sm" onClick={() => setAsk(true)}><ShieldAlert size={14} aria-hidden /> Review and trust</button>
      )}
      {s.status === "needs_trust" && ask && (
        <div className="trust" role="group" aria-label={`Trust ${s.name}?`}>
          <p><strong>Trust this project server?</strong></p>
          <p className="row-desc">
            It comes from this workspace&apos;s <code>.dot/settings.json</code>, a file the agent itself could have written. Trusting it starts the command
            inside the sandbox and gives Dot every tool it offers, and its output is always treated as untrusted.
          </p>
          <p className="row-desc">Trust only what you wrote or read. Any change to its config asks again.</p>
          <div className="tl-confirm">
            <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={() => onAct(s.name, "trust")}>Trust and start</button>
            <button type="button" className="btn btn-sm" onClick={() => setAsk(false)}>Cancel</button>
          </div>
        </div>
      )}
      {s.status !== "needs_trust" && (
        <button type="button" className="btn btn-sm" disabled={busy || s.status === "connecting"} onClick={() => onAct(s.name, "reconnect")}>Reconnect</button>
      )}
    </li>
  );
}

export function McpPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const r = useResource(api.mcp, open, 3000);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const act = async (name: string, a: "reconnect" | "trust") => {
    setBusy(true);
    setNote(null);
    try {
      await api.mcpAct(name, a);
      r.reload();
    } catch (e) {
      setNote(toErrorInfo(e).title);
    }
    setBusy(false);
  };
  const tools = (r.data ?? []).reduce((n, s) => n + s.tool_count, 0);
  return (
    <Sheet open={open} onClose={onClose} title="MCP servers">
      {note && <p className="q-err" role="alert">{note}</p>}
      {r.error && !r.data ? (
        <ErrorBox error={r.error} onRetry={r.reload} />
      ) : !r.data ? (
        <Skeletons />
      ) : r.data.length === 0 ? (
        <StateBox title="No MCP servers">Add <code>mcpServers</code> to ~/.dot/settings.json or the workspace .dot/settings.json. Changes show up within a few seconds.</StateBox>
      ) : (
        <>
          <p className="help-text">{r.data.length} servers, {tools} tools. Their tools are loaded on demand with ToolSearch.</p>
          <ul className="rows">{r.data.map((s) => <Server key={s.name} s={s} busy={busy} onAct={(n, a) => void act(n, a)} />)}</ul>
        </>
      )}
    </Sheet>
  );
}

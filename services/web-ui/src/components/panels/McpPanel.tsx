"use client";
import { RefreshCw, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, MenuItem, Sheet, useToast } from "@/components/ui";
import { ErrorBox } from "@/components/ui/StateBox";
import { useResource } from "@/hooks/useResource";
import { api, type McpServer } from "@/lib/api/client";
import { toErrorInfo } from "@/lib/api/errors";
import { clip } from "@/lib/util/format";
import { Empty, Item, Loading, Meta, PanelBar, RowMenu, Status, type Tone } from "./parts";

const TONE: Record<McpServer["status"], Tone> = { connected: "ok", connecting: "info", failed: "bad", needs_trust: "warn", stopped: "idle" };
const WORD = { connected: "connected", connecting: "connecting", failed: "failed", needs_trust: "needs trust", stopped: "stopped" } as const;
type Act = "reconnect" | "trust";

function Server({ s, busy, onAct, onTrust }: { s: McpServer; busy: boolean; onAct: (name: string, a: Act) => void; onTrust: (name: string) => void }) {
  return (
    <Item
      text={clip(s.name, 60)}
      mono
      time={`${s.tool_count} ${s.tool_count === 1 ? "tool" : "tools"}`}
      actions={
        <RowMenu label={`Actions for ${clip(s.name, 40)}`}>
          <MenuItem icon={<RefreshCw size={16} />} disabled={busy || s.status === "connecting" || s.status === "needs_trust"} onSelect={() => onAct(s.name, "reconnect")}>Reconnect</MenuItem>
          {s.status === "needs_trust" && <MenuItem icon={<ShieldAlert size={16} />} onSelect={() => onTrust(s.name)}>Review and trust</MenuItem>}
        </RowMenu>
      }
    >
      <div>
        <Status tone={TONE[s.status]}>{WORD[s.status]}</Status>
        {s.status === "needs_trust" && <Button className="pn-trust" variant="ghost" size="sm" icon={<ShieldAlert size={16} />} onClick={() => onTrust(s.name)}>Review and trust</Button>}
      </div>
      <Meta items={[s.transport, s.scope]} />
      {s.error && <p className="pn-err" title={s.error}>{clip(s.error, 400)}</p>}
    </Item>
  );
}

export function McpPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const r = useResource(api.mcp, open, 3000);
  const [busy, setBusy] = useState(false);
  const [trust, setTrust] = useState<string | null>(null);
  const toast = useToast();
  const act = async (name: string, a: Act) => {
    setBusy(true);
    try {
      await api.mcpAct(name, a);
      toast({ title: a === "trust" ? `Trusted ${clip(name, 40)}` : `Reconnecting ${clip(name, 40)}`, tone: "ok" });
      r.reload();
    } catch (e) {
      toast({ title: `Could not ${a} ${clip(name, 40)}`, description: toErrorInfo(e).title, tone: "bad" });
    }
    setBusy(false);
  };
  const tools = (r.data ?? []).reduce((n, s) => n + s.tool_count, 0);
  return (
    <Sheet open={open} onClose={onClose} title="MCP servers" description="Extra tool servers. Their tools load only when Dot needs them.">
      {r.error && !r.data ? (
        <ErrorBox error={r.error} onRetry={r.reload} />
      ) : !r.data ? (
        <Loading />
      ) : r.data.length === 0 ? (
        <Empty title="No MCP servers.">Add mcpServers to ~/.dot/settings.json or the workspace .dot/settings.json.</Empty>
      ) : (
        <>
          <PanelBar count={`${r.data.length} servers · ${tools} tools`} />
          <ul className="pn-list">{r.data.map((s) => <Server key={s.name} s={s} busy={busy} onAct={(n, a) => void act(n, a)} onTrust={setTrust} />)}</ul>
        </>
      )}
      <Dialog open={trust !== null} onClose={() => setTrust(null)} title="Trust this project server?" confirmLabel="Trust and start" busy={busy} onConfirm={() => { const n = trust; setTrust(null); if (n) void act(n, "trust"); }}>
        <span className="pn-warn">
          <p>It comes from this workspace&apos;s <code>.dot/settings.json</code>, a file the agent itself could have written. Trusting it starts the command inside the sandbox and gives Dot every tool it offers. Its output is always treated as untrusted.</p>
          <p>Trust only what you wrote or read. Any change to its config asks again.</p>
        </span>
      </Dialog>
    </Sheet>
  );
}

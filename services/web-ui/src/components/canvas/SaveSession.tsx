"use client";
import { KeyRound } from "lucide-react";
import { useState } from "react";
import { Button, Field, Input, Select, Sheet, Skeletons, useToast } from "@/components/ui";
import { ErrorBox } from "@/components/ui/StateBox";
import { CopyCmd } from "@/components/shell/CopyCmd";
import { useResource } from "@/hooks/useResource";
import { toErrorInfo } from "@/lib/api/errors";
import { vaultApi, type Credential } from "@/lib/api/vault";
import { clip } from "@/lib/util/format";

const NEW = "__new";

async function load(): Promise<{ list: Credential[] | null }> {
  const s = await vaultApi.status();
  return { list: s.enabled ? await vaultApi.list() : null };
}

/** "Save this session": attach the open page's cookies to a saved login, or create a session-only one. */
export function SaveSession({ sessionId, host, disabled }: { sessionId: string; host: string; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button size="sm" variant="ghost" icon={<KeyRound size={16} />} disabled={disabled} onClick={() => setOpen(true)} title={disabled ? "Dot is using the browser" : undefined}>
        <span className="bv-save-long">Save this session</span><span className="bv-save-short">Save session</span>
      </Button>
      <Sheet open={open} onClose={() => setOpen(false)} title="Save this session" center>
        {open && <Picker sessionId={sessionId} host={host} onDone={() => setOpen(false)} />}
      </Sheet>
    </>
  );
}

function Picker({ sessionId, host, onDone }: { sessionId: string; host: string; onDone: () => void }) {
  const r = useResource(load, true);
  const [pick, setPick] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  if (r.error) return <ErrorBox error={r.error} onRetry={r.reload} />;
  if (!r.data) return <Skeletons n={2} />;
  if (r.data.list === null) {
    return (
      <div className="dlg-body vault-save">
        <p>The password vault is locked. Set up its key first, restart the backend, then try again.</p>
        <CopyCmd cmd="make vault-key" />
      </div>
    );
  }
  const list = r.data.list;
  // Default: the login already bound to this page's host, else a new one.
  const bound = list.find((c) => c.origins.some((o) => { try { return new URL(o).host === host; } catch { return false; } }));
  const choice = pick ?? bound?.id ?? NEW;
  const isNew = choice === NEW;
  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      const c = await vaultApi.saveSession(sessionId, isNew ? { label: label.trim() } : { credential: choice });
      toast({ title: `Session saved to ${clip(c.label, 40)}`, tone: "ok" });
      onDone();
    } catch (e) {
      const i = toErrorInfo(e);
      setErr(`${i.title}${i.code !== null ? ` (code ${i.code})` : ""}`);
    }
    setBusy(false);
  };
  return (
    <form className="dlg-body vault-save" autoComplete="off" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <p className="pn-desc">Stores the cookies of {host ? <span className="mono">{host}</span> : "the open page"} in the vault, so Dot can come back signed in. Nothing secret is shown.</p>
      <Field label="Save to" error={isNew ? null : err}>
        {(p) => (
          <Select {...p} value={choice} onChange={(e) => { setPick(e.target.value); setErr(null); }}>
            <option value={NEW}>New login...</option>
            {list.map((c) => <option key={c.id} value={c.id}>{clip(c.label, 60)}{c.has_session ? " (replaces its session)" : ""}</option>)}
          </Select>
        )}
      </Field>
      {isNew && (
        <Field label="Name" help="A session-only login bound to this site." error={err}>
          {(p) => <Input {...p} dir="auto" value={label} maxLength={80} autoComplete="off" placeholder={host || "My account"} onChange={(e) => { setLabel(e.target.value); setErr(null); }} />}
        </Field>
      )}
      <div className="dlg-actions">
        <Button variant="ghost" onClick={onDone}>Cancel</Button>
        <Button type="submit" variant="solid" loading={busy} disabled={isNew && !label.trim()}>Save session</Button>
      </div>
    </form>
  );
}

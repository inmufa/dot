"use client";
import { Eraser, KeyRound, MoreHorizontal, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Dialog, DropdownMenu, Entry, IconButton, MenuItem, Sheet, StateBox, useToast } from "@/components/ui";
import { ErrorBox } from "@/components/ui/StateBox";
import { CopyCmd } from "@/components/shell/CopyCmd";
import { useResource } from "@/hooks/useResource";
import { isMissing } from "@/lib/api/caps";
import { DotApiError, toErrorInfo } from "@/lib/api/errors";
import { createBody, draftOf, EMPTY_DRAFT, fieldForCode, patchBody, VAULT_OFF, vaultApi, type Credential, type VaultDraft } from "@/lib/api/vault";
import { clip } from "@/lib/util/format";
import { stamp } from "./ScheduleForm";
import { Empty, Loading, PanelBar, RowMenu, stampOf } from "./parts";
import { VaultForm, type FieldErrors } from "./VaultForm";

type State = { kind: "off" } | { kind: "missing" } | { kind: "on"; list: Credential[] };

/** Status first; the list only when the vault has a key. */
async function load(): Promise<State> {
  try {
    const s = await vaultApi.status();
    if (!s.enabled) return { kind: "off" };
  } catch (e) {
    if (isMissing(e)) return { kind: "missing" };
    throw e;
  }
  try {
    return { kind: "on", list: await vaultApi.list() };
  } catch (e) {
    if (e instanceof DotApiError && e.info.code === VAULT_OFF) return { kind: "off" };
    throw e;
  }
}

const errText = (e: unknown) => {
  const i = toErrorInfo(e);
  return `${i.title}${i.code !== null ? ` (code ${i.code})` : ""}`;
};

function Row({ c, onEdit, onDelete, onClear }: { c: Credential; onEdit: () => void; onDelete: () => void; onClear: () => void }) {
  return (
    <div className="pn-body vault-row">
      <div className="pn-entry-head">
        <span className="pn-title" dir="auto" title={c.label}>{clip(c.label, 80)}</span>
        <span className="pn-act">
          <RowMenu label={`Actions for ${clip(c.label, 40)}`}>
            <MenuItem icon={<Pencil size={16} />} onSelect={onEdit}>Edit</MenuItem>
            {c.has_session && <MenuItem icon={<Eraser size={16} />} onSelect={onClear}>Clear session</MenuItem>}
            <MenuItem icon={<Trash2 size={16} />} danger onSelect={onDelete}>Delete</MenuItem>
          </RowMenu>
        </span>
      </div>
      {c.username && <p className="vault-user" dir="auto" title={c.username}>{c.username}</p>}
      <ul className="vault-origins" aria-label="Sites">
        {c.origins.map((o) => <li key={o} className="mono" title={o}>{o}</li>)}
      </ul>
      {(c.has_totp || c.has_session || !c.has_password) && (
        <p className="vault-badges">
          {c.has_session && <Badge tone="ok">session</Badge>}
          {c.has_totp && <Badge tone="info">TOTP</Badge>}
          {!c.has_password && <Badge>no password</Badge>}
        </p>
      )}
      {c.has_session && (c.session_saved_at || c.session_expires_at) && (
        <p className="vault-when">Session saved {c.session_saved_at ? stamp(c.session_saved_at) : "earlier"}{c.session_expires_at ? `, expires ${stamp(c.session_expires_at)}` : ""}</p>
      )}
      <p className="vault-when">{c.last_used ? `Last used ${stamp(c.last_used)}` : "Never used"}</p>
      {c.notes && <p className="pn-desc pn-clamp" dir="auto">{c.notes}</p>}
    </div>
  );
}

export function PasswordsPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const r = useResource(load, open);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<Credential | null>(null);
  const [clearAll, setClearAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const save = (orig: Credential | null) => async (d: VaultDraft): Promise<FieldErrors> => {
    try {
      if (orig === null) await vaultApi.create(createBody(d));
      else {
        const body = patchBody(orig, d);
        if (Object.keys(body).length > 0) await vaultApi.update(orig.id, body);
      }
      setAdding(false);
      setEditing(null);
      r.reload();
      toast({ title: orig === null ? "Login saved" : "Login updated", tone: "ok" });
      return {};
    } catch (e) {
      const f = fieldForCode(toErrorInfo(e).code);
      return { [f ?? "form"]: toErrorInfo(e).title };
    }
  };
  const remove = async () => {
    if (!confirm) return;
    setBusy(true);
    try {
      await vaultApi.remove(confirm.id);
      toast({ title: "Login deleted", tone: "ok" });
      r.reload();
    } catch (e) {
      toast({ title: "Could not delete the login", description: errText(e), tone: "bad" });
    }
    setBusy(false);
    setConfirm(null);
  };
  const clearOne = async (c: Credential) => {
    try {
      await vaultApi.clearSession(c.id);
      toast({ title: `Session cleared for ${clip(c.label, 40)}`, tone: "ok" });
      r.reload();
    } catch (e) {
      toast({ title: "Could not clear the session", description: errText(e), tone: "bad" });
    }
  };
  const clearEvery = async () => {
    setBusy(true);
    try {
      const { cleared } = await vaultApi.clearAllSessions();
      toast({ title: cleared === 1 ? "1 session cleared" : `${cleared} sessions cleared`, tone: "ok" });
      r.reload();
    } catch (e) {
      toast({ title: "Could not clear the sessions", description: errText(e), tone: "bad" });
    }
    setBusy(false);
    setClearAll(false);
  };

  const s = r.data;
  const list = s?.kind === "on" ? s.list : null;
  const sessions = list?.filter((c) => c.has_session).length ?? 0;

  return (
    <Sheet open={open} onClose={onClose} title="Passwords">
      {r.error && !s ? (
        <ErrorBox error={r.error} onRetry={r.reload} />
      ) : !s ? (
        <Loading />
      ) : s.kind === "missing" ? (
        <StateBox grid quiet title="No password vault.">This backend has no credential vault yet. Update it to save logins.</StateBox>
      ) : s.kind === "off" ? (
        <StateBox grid quiet title="The vault is locked." action={<><CopyCmd cmd="make vault-key" /><Button variant="ghost" size="sm" onClick={r.reload}>Check again</Button></>}>
          Set up the vault key first: run this in the project folder, restart the backend, then check again.
        </StateBox>
      ) : (
        <>
          <p className="pn-intro">Logins Dot can use to sign in with its browser. Each sign-in asks you first. Passwords are write-only: nobody can read them back here.</p>
          {adding ? (
            <VaultForm init={EMPTY_DRAFT} orig={null} onSave={save(null)} onCancel={() => setAdding(false)} />
          ) : (
            <PanelBar count={`${s.list.length} ${s.list.length === 1 ? "login" : "logins"}${sessions ? `, ${sessions} with a session` : ""}`}>
              <Button variant="solid" icon={<Plus size={16} />} onClick={() => { setEditing(null); setAdding(true); }}>Add</Button>
              <DropdownMenu align="end" label="More vault actions" trigger={(p) => <IconButton label="More vault actions" {...p}><MoreHorizontal size={18} aria-hidden /></IconButton>}>
                <MenuItem icon={<Eraser size={16} />} danger disabled={sessions === 0} onSelect={() => setClearAll(true)}>Clear all sessions</MenuItem>
              </DropdownMenu>
            </PanelBar>
          )}
          {s.list.length === 0 ? (
            !adding && (
              <Empty title="No saved logins." action={<Button icon={<KeyRound size={16} />} onClick={() => setAdding(true)}>Add a login</Button>}>
                Add one by hand, or sign in through the Browser tab and press &quot;Save this session&quot;.
              </Empty>
            )
          ) : (
            <div className="pn-log">
              {s.list.map((c, i) => (
                <Entry key={c.id} time={c.last_used ? stampOf(c.last_used) : ""} i={Math.min(i, 6)} className="pn-entry">
                  {editing === c.id ? (
                    <VaultForm init={draftOf(c)} orig={c} onSave={save(c)} onCancel={() => setEditing(null)} />
                  ) : (
                    <Row c={c} onEdit={() => { setAdding(false); setEditing(c.id); }} onDelete={() => setConfirm(c)} onClear={() => void clearOne(c)} />
                  )}
                </Entry>
              ))}
            </div>
          )}
        </>
      )}
      <Dialog open={confirm !== null} onClose={() => setConfirm(null)} title="Delete this login?" confirmLabel="Delete" danger busy={busy} onConfirm={() => void remove()}>
        {confirm ? `"${clip(confirm.label, 60)}" and its saved session will be removed for good. Dot can no longer sign in with it.` : null}
      </Dialog>
      <Dialog open={clearAll} onClose={() => setClearAll(false)} title="Clear all sessions?" confirmLabel="Clear sessions" danger busy={busy} onConfirm={() => void clearEvery()}>
        {`${sessions === 1 ? "1 saved session" : `${sessions} saved sessions`} will be deleted. Logins and passwords stay; Dot signs in again next time.`}
      </Dialog>
    </Sheet>
  );
}

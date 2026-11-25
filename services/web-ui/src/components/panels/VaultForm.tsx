"use client";
import { useState } from "react";
import { Button, Checkbox, Field, Input, Textarea } from "@/components/ui";
import { draftProblem, type Credential, type VaultDraft } from "@/lib/api/vault";

export type FieldErrors = Partial<Record<"label" | "origins" | "totp" | "form", string>>;

interface Props {
  init: VaultDraft;
  /** The entry being edited; null when adding. */
  orig: Credential | null;
  /** Resolves to field errors (empty when saved). */
  onSave: (d: VaultDraft) => Promise<FieldErrors>;
  onCancel: () => void;
}

const KEEP = "Leave empty to keep the stored one.";

/** Add or edit a saved login. Secret fields always start empty: stored secrets are never shown or fetched. */
export function VaultForm({ init, orig, onSave, onCancel }: Props) {
  const [d, setD] = useState(init);
  const [err, setErr] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof VaultDraft>(k: K, v: VaultDraft[K]) => {
    setD((p) => ({ ...p, [k]: v }));
    setErr((e) => ({ ...e, [k === "totp" || k === "dropTotp" ? "totp" : k]: undefined, form: undefined }));
  };
  const submit = async () => {
    const local = draftProblem(d);
    if (local) { setErr({ [local.field]: local.text }); return; }
    setBusy(true);
    setErr(await onSave(d));
    setBusy(false);
  };
  const edit = orig !== null;
  const pwHelp = edit ? (orig.has_password ? KEEP : "No password stored. Type one to add it.") : "Optional for a session-only login.";
  const totpHelp = edit && orig.has_totp ? KEEP : "Base32 secret from the site's 2FA setup. Optional.";
  return (
    <form className="pn-form vault-form" autoComplete="off" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <Field label="Name" error={err.label}>
        {(p) => <Input {...p} dir="auto" value={d.label} maxLength={80} required autoComplete="off" placeholder="GitHub" onChange={(e) => set("label", e.target.value)} />}
      </Field>
      <Field label="Sites" help="One origin per line, like https://github.com. List every host the sign-in touches." error={err.origins}>
        {(p) => <Textarea {...p} className="mono" rows={2} value={d.origins} spellCheck={false} autoCapitalize="off" autoComplete="off" placeholder="https://github.com" onChange={(e) => set("origins", e.target.value)} />}
      </Field>
      <Field label="Username">
        {(p) => <Input {...p} value={d.username} maxLength={500} autoCapitalize="off" spellCheck={false} autoComplete="off" onChange={(e) => set("username", e.target.value)} />}
      </Field>
      <Field label={edit ? "New password" : "Password"} help={pwHelp}>
        {(p) => <Input {...p} type="password" value={d.password} maxLength={1000} autoComplete="new-password" onChange={(e) => set("password", e.target.value)} />}
      </Field>
      <Field label={edit && orig.has_totp ? "New TOTP secret" : "TOTP secret"} help={totpHelp} error={err.totp}>
        {(p) => <Input {...p} type="password" className="mono" value={d.totp} maxLength={200} autoComplete="off" spellCheck={false} disabled={d.dropTotp} onChange={(e) => set("totp", e.target.value)} />}
      </Field>
      {edit && orig.has_totp && (
        <Checkbox className="pn-check" checked={d.dropTotp} onChange={(e) => { set("dropTotp", e.target.checked); if (e.target.checked) set("totp", ""); }}>Remove the stored TOTP secret</Checkbox>
      )}
      <Field label="Notes">
        {(p) => <Textarea {...p} dir="auto" rows={2} value={d.notes} maxLength={1000} onChange={(e) => set("notes", e.target.value)} />}
      </Field>
      {edit && orig.has_session && <p className="pn-desc">Changing the sites deletes the saved session.</p>}
      {err.form && <p className="pn-note" role="alert">{err.form}</p>}
      <div className="pn-actions">
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" variant="solid" loading={busy} disabled={!d.label.trim() || !d.origins.trim()}>{edit ? "Save changes" : "Save login"}</Button>
      </div>
    </form>
  );
}

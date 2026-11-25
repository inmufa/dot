import { request } from "./client";

/** The only shape the vault returns. Secrets are write-only: never in any response. */
export interface Credential {
  id: string;
  label: string;
  origins: string[];
  username: string;
  notes: string;
  has_password: boolean;
  has_totp: boolean;
  has_session: boolean;
  session_saved_at: string | null;
  session_expires_at: string | null;
  last_used: string | null;
  created_at: string;
  updated_at: string;
}

export interface CredentialCreate {
  label: string;
  origins: string[];
  username?: string;
  password?: string;
  totp_secret?: string;
  notes?: string;
}
export type CredentialPatch = Partial<CredentialCreate>;

export const VAULT_OFF = 4140;
export const VAULT_LABEL_TAKEN = 4142;
export const VAULT_BAD_ORIGIN = 4149;
export const VAULT_NO_PAGE = 4150;
export const VAULT_NO_SESSION = 4151;

const enc = encodeURIComponent;
const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const vaultApi = {
  status: () => request<{ enabled: boolean }>("/v1/vault/status"),
  list: () => request<Credential[]>("/v1/vault"),
  create: (d: CredentialCreate) => request<Credential>("/v1/vault", post(d)),
  update: (id: string, d: CredentialPatch) => request<Credential>(`/v1/vault/${enc(id)}`, { method: "PATCH", body: JSON.stringify(d) }),
  remove: (id: string) => request<{ ok: boolean }>(`/v1/vault/${enc(id)}?confirm=${enc(id)}`, { method: "DELETE" }),
  saveSession: (sessionId: string, target: { credential: string } | { label: string }) =>
    request<Credential>("/v1/vault/save-session", post({ session_id: sessionId, ...target })),
  clearSession: (id: string) => request<{ ok: boolean }>(`/v1/vault/${enc(id)}/session`, { method: "DELETE" }),
  clearAllSessions: () => request<{ cleared: number }>("/v1/vault/sessions?confirm=all", { method: "DELETE" }),
};

/** Form state. Secret fields start empty and are sent only when typed. */
export interface VaultDraft {
  label: string;
  origins: string;
  username: string;
  notes: string;
  password: string;
  totp: string;
  /** Edit only: remove the stored TOTP secret. */
  dropTotp: boolean;
}

export const EMPTY_DRAFT: VaultDraft = { label: "", origins: "", username: "", notes: "", password: "", totp: "", dropTotp: false };

export const draftOf = (c: Credential): VaultDraft => ({ ...EMPTY_DRAFT, label: c.label, origins: c.origins.join("\n"), username: c.username, notes: c.notes });

/** One origin per line or comma separated; blanks and repeats dropped. The server normalises. */
export function splitOrigins(text: string): string[] {
  return [...new Set(text.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean))];
}

const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((x, i) => x === b[i]);

export function createBody(d: VaultDraft): CredentialCreate {
  const out: CredentialCreate = { label: d.label.trim(), origins: splitOrigins(d.origins) };
  if (d.username.trim()) out.username = d.username.trim();
  if (d.password) out.password = d.password;
  const totp = d.totp.replace(/\s+/g, "");
  if (totp) out.totp_secret = totp;
  if (d.notes.trim()) out.notes = d.notes.trim();
  return out;
}

/** Only what changed; empty secret fields keep the stored value. */
export function patchBody(orig: Credential, d: VaultDraft): CredentialPatch {
  const out: CredentialPatch = {};
  const label = d.label.trim();
  if (label !== orig.label) out.label = label;
  const origins = splitOrigins(d.origins);
  if (!sameList(origins, orig.origins)) out.origins = origins;
  if (d.username.trim() !== orig.username) out.username = d.username.trim();
  if (d.notes.trim() !== orig.notes) out.notes = d.notes.trim();
  if (d.password) out.password = d.password;
  const totp = d.totp.replace(/\s+/g, "");
  if (totp) out.totp_secret = totp;
  else if (d.dropTotp && orig.has_totp) out.totp_secret = "";
  return out;
}

/** Local checks before sending; mirrors the server limits. */
export function draftProblem(d: VaultDraft): { field: "label" | "origins" | "totp"; text: string } | null {
  const label = d.label.trim();
  if (!label) return { field: "label", text: "Give it a name." };
  if (label.length > 80) return { field: "label", text: "80 characters at most." };
  const o = splitOrigins(d.origins);
  if (o.length === 0) return { field: "origins", text: "Add at least one site, like https://example.com." };
  if (o.length > 10) return { field: "origins", text: "10 sites at most." };
  const totp = d.totp.replace(/\s+/g, "");
  if (totp && !/^[A-Za-z2-7]+=*$/.test(totp)) return { field: "totp", text: "A TOTP secret is base32: letters A-Z and digits 2-7." };
  return null;
}

/** Which form field a server error belongs to. */
export function fieldForCode(code: number | null): "label" | "origins" | null {
  if (code === VAULT_LABEL_TAKEN) return "label";
  if (code === VAULT_BAD_ORIGIN) return "origins";
  return null;
}

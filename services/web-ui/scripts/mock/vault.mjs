// Credential vault mock (docs/api-contract.md "Credential vault"). Secrets are accepted and dropped: never echoed.
// Control: /__vault?mode=on|off|missing&empty=1 (off answers enabled:false and 4140, missing answers 404 like an old backend).
import { st, json, readBody, sleep } from "./core.mjs";

const iso = (min = 0) => new Date(Date.now() + min * 60_000).toISOString();
export const vaultMode = { v: "on" };

function cred(o) {
  return { id: o.id, label: o.label, origins: o.origins, username: o.username ?? "", notes: o.notes ?? "", has_password: o.has_password ?? true, has_totp: o.has_totp ?? false, has_session: o.has_session ?? false, session_saved_at: o.has_session ? iso(-600) : null, session_expires_at: o.has_session ? iso(60 * 24 * 13) : null, last_used: o.last_used ?? null, created_at: iso(-9000), updated_at: iso(-900) };
}

export function seedVault(empty = false) {
  st.vault = empty ? [] : [
    cred({ id: "VA1B2C3D41", label: "GitHub", origins: ["https://github.com"], username: "dev-user", has_totp: true, has_session: true, last_used: iso(-45) }),
    cred({ id: "VA1B2C3D42", label: "Grafana (home)", origins: ["https://grafana.home.arpa:3443"], username: "admin", notes: "Read-only dashboards. Dot may look, not edit.", last_used: iso(-60 * 30) }),
    cred({ id: "VA1B2C3D43", label: "Hetzner Console", origins: ["https://console.hetzner.cloud", "https://accounts.hetzner.com"], username: "owner@example.org", has_totp: true }),
    cred({ id: "VA1B2C3D44", label: "news.example.org", origins: ["https://news.example.org"], has_password: false, has_session: true, last_used: iso(-60 * 50) }),
  ];
}
seedVault();

export function vaultControl(url, res) {
  vaultMode.v = url.searchParams.get("mode") ?? "on";
  if (url.searchParams.has("empty")) seedVault(url.searchParams.get("empty") === "1");
  return json(res, 200, { mode: vaultMode.v, n: st.vault.length });
}

const sorted = () => [...st.vault].sort((a, b) => a.label.localeCompare(b.label));
const ORIGIN = /^https:\/\/[a-z0-9.-]+(:\d+)?$/;
/** Full URL to origin; null when not https://host[:port]. */
function origin(raw) {
  try {
    const u = new URL(String(raw).trim());
    const o = u.origin.toLowerCase();
    return ORIGIN.test(o) ? o : null;
  } catch { return null; }
}

export async function vaultRoutes(req, res, p, url, fail) {
  if (!p.startsWith("/v1/vault")) return false;
  if (vaultMode.v === "missing") return fail(1002, "Not found", 404), true;
  if (p === "/v1/vault/status") return json(res, 200, { enabled: vaultMode.v === "on" }), true;
  if (vaultMode.v !== "on") return fail(4140, "The credential vault is off: set DOT_VAULT_KEY (make vault-key)", 503), true;
  await sleep(120);
  const m = req.method;
  if (p === "/v1/vault" && m === "GET") return json(res, 200, sorted()), true;
  const checkOrigins = (list) => {
    if (!Array.isArray(list) || list.length < 1 || list.length > 10) return fail(4149, "Add between 1 and 10 sites", 422), null;
    const out = list.map(origin);
    const bad = list.find((_, i) => out[i] === null);
    if (bad !== undefined) return fail(4149, `Not a valid https origin: ${String(bad).slice(0, 80)}`, 422), null;
    return [...new Set(out)];
  };
  const taken = (label, id) => st.vault.some((c) => c.label.toLowerCase() === String(label).toLowerCase() && c.id !== id);
  if (p === "/v1/vault" && m === "POST") {
    const b = await readBody(req);
    if (!b.label) return fail(1003, "Label is required", 422), true;
    if (taken(b.label)) return fail(4142, `A login named '${b.label}' already exists`, 409), true;
    const origins = checkOrigins(b.origins);
    if (!origins) return true;
    const c = cred({ id: `V${Date.now().toString(36).toUpperCase().slice(-9)}`, label: b.label, origins, username: b.username, notes: b.notes, has_password: !!b.password, has_totp: !!b.totp_secret });
    st.vault.push(c);
    return json(res, 201, c), true;
  }
  if (p === "/v1/vault/sessions" && m === "DELETE") {
    if (url.searchParams.get("confirm") !== "all") return fail(4143, "Confirm with ?confirm=all", 400), true;
    let n = 0;
    for (const c of st.vault) if (c.has_session) { n++; Object.assign(c, { has_session: false, session_saved_at: null, session_expires_at: null }); }
    return json(res, 200, { cleared: n }), true;
  }
  if (p === "/v1/vault/save-session" && m === "POST") {
    const b = await readBody(req);
    const bs = st.browser?.get(b.session_id);
    const tab = bs?.tabs.find((t) => t.tab === bs.active);
    if (!tab || !/^https?:/.test(tab.url)) return fail(4150, "No page is open in this chat's browser", 409), true;
    const o = new URL(tab.url).origin;
    if (/example\.com/.test(o)) return fail(4151, `Nothing is signed in on ${o}`, 409), true;
    let c;
    if (b.credential) {
      c = st.vault.find((x) => x.id === b.credential);
      if (!c) return fail(4141, "Saved login not found", 404), true;
      if (!c.origins.includes(o)) c.origins.push(o);
    } else {
      if (!b.label) return fail(1003, "Label is required", 422), true;
      if (taken(b.label)) return fail(4142, `A login named '${b.label}' already exists`, 409), true;
      c = cred({ id: `V${Date.now().toString(36).toUpperCase().slice(-9)}`, label: b.label, origins: [o], has_password: false });
      st.vault.push(c);
    }
    Object.assign(c, { has_session: true, session_saved_at: iso(), session_expires_at: iso(60 * 24 * 14), updated_at: iso() });
    return json(res, 200, c), true;
  }
  const one = /^\/v1\/vault\/([^/]+)(\/session)?$/.exec(p);
  if (!one) return false;
  const c = st.vault.find((x) => x.id === one[1]);
  if (!c) return fail(4141, "Saved login not found", 404), true;
  if (one[2] && m === "DELETE") { Object.assign(c, { has_session: false, session_saved_at: null, session_expires_at: null }); return json(res, 200, { ok: true }), true; }
  if (m === "DELETE") {
    if (url.searchParams.get("confirm") !== c.id) return fail(4143, "Confirm the delete with ?confirm=<id>", 400), true;
    st.vault = st.vault.filter((x) => x !== c);
    return json(res, 200, { ok: true }), true;
  }
  if (m === "PATCH") {
    const b = await readBody(req);
    st.lastVaultPatch = Object.keys(b);
    if (b.label !== undefined && taken(b.label, c.id)) return fail(4142, `A login named '${b.label}' already exists`, 409), true;
    if (b.origins !== undefined) {
      const origins = checkOrigins(b.origins);
      if (!origins) return true;
      c.origins = origins;
      Object.assign(c, { has_session: false, session_saved_at: null, session_expires_at: null });
    }
    for (const k of ["label", "username", "notes"]) if (b[k] !== undefined) c[k] = b[k];
    if (b.password) c.has_password = true;
    if (b.totp_secret !== undefined) c.has_totp = b.totp_secret !== "";
    c.updated_at = iso();
    return json(res, 200, c), true;
  }
  return false;
}

/** "sign in" prompt: BrowserLogin with its plain-text approval card. */
export async function loginScenario(c) {
  const g = st.vault.find((x) => x.label === "GitHub") ?? st.vault[0];
  await c.tok("I will sign in with the saved login.\n");
  const args = { credential: g?.label ?? "GitHub", url: "https://github.com/login" };
  const diff = `Sign in to ${(g?.origins ?? ["https://github.com"]).join(", ")}\nUsername: ${g?.username ?? ""}\nSaved login: ${g?.label ?? "GitHub"}`;
  const ok = await c.tool("BrowserLogin", args, "logged in (saved session restored)\nPage: https://github.com/\nTitle: GitHub", { diff, reason: "signs in with a saved login" }, true);
  if (g && ok) g.last_used = iso();
  await c.tok(ok ? "Signed in." : "Not signed in: you rejected it.");
  return true;
}

// Mock of the Dot backend (contract shapes in docs/api-contract.md and docs/ui-contract.md). No external deps.
// Prompt triggers: browse [docs], edit, bash, ask [multi], agent, plan, compact, web, code, long, form, research, think,
// write page, table|chart [bar|line|area|pie]|stats|steps|checklist|cards|callout|tabs|accordion|choices|widgets|badwidget.
// Control: /__seed[?worst=1], /__reset[?worst=1], /__caps?off=search,files,... (see mock/features.mjs). Browser view: /__browser?mode=down|ok. Voice: /__voice?mode=ok|down|fail.
// Vault: /__vault?mode=on|off|missing[&empty=1]; prompt "sign in" asks for BrowserLogin.
import http from "node:http";
import { seed } from "./mock-data.mjs";
import { PORT, TOKEN, st, json, envelope } from "./mock/core.mjs";
import { seedSessions, addWorst, dropWorst } from "./mock/seed.mjs";
import { browserControl } from "./mock/browser.mjs";
import { voiceControl, voiceRoutes } from "./mock/voice.mjs";
import { capFor, capsRoute, featureRoutes, resetFeatures } from "./mock/features.mjs";
import { contentRoute } from "./mock/files.mjs";
import { legacyRoutes } from "./mock/legacy.mjs";
import { formRoutes } from "./mock/forms.mjs";
import { sessionRoutes } from "./mock/sessions.mjs";
import { seedVault, vaultControl, vaultMode, vaultRoutes } from "./mock/vault.mjs";

const handlers = [contentRoute, vaultRoutes, voiceRoutes, legacyRoutes, formRoutes, featureRoutes, sessionRoutes];
seedSessions();

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const p = url.pathname;
  const worst = url.searchParams.get("worst") === "1";
  if (p === "/__seed") { st.data = seed(worst); dropWorst(); if (worst) addWorst(); return json(res, 200, { ok: true }); }
  if (p === "/__reset") {
    for (const s of st.sessions.values()) s.cancel = true;
    st.approvals.clear(); st.answers.clear(); st.audit.length = 0;
    st.data = seed(worst); seedSessions(); resetFeatures(); seedVault(); vaultMode.v = "on";
    if (worst) addWorst();
    return json(res, 200, { ok: true });
  }
  if (p === "/__caps") return capsRoute(url, res);
  if (p === "/__browser") return browserControl(url, res);
  if (p === "/__voice") return voiceControl(url, res);
  if (p === "/__vault") return vaultControl(url, res);
  if (req.headers.authorization !== `Bearer ${TOKEN}` && p !== "/health") return json(res, 401, envelope(1001, "Invalid token", 401).body);
  const lang = (req.headers["accept-language"] ?? "en").slice(0, 2);
  const fail = (code, text, status) => { const e = envelope(code, lang === "ru" ? `[ru] ${text}` : text, status); json(res, e.status, e.body); };
  if (p === "/ready" || p === "/health") return json(res, 200, { ok: true });
  const cap = capFor(req.method, p);
  if (cap && st.caps.has(cap)) return fail(1002, "Not found", 404);
  try {
    for (const h of handlers) if (p.startsWith("/v1/") && (await h(req, res, p, url, fail)) === true) return;
  } catch (e) {
    console.error(e);
    if (!res.headersSent) return fail(1000, "Mock error", 500);
    return res.end();
  }
  fail(1002, "Not found", 404);
});

server.listen(PORT, "127.0.0.1", () => console.log(`mock backend on http://127.0.0.1:${PORT} token=${TOKEN}`));

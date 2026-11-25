// Browser view mock: per-session fake pages drawn as SVG frames (the real worker sends JPEG).
// Control: /__browser?mode=down|ok|empty (down answers 4015 like a stopped worker).
import { st, json, readBody, sleep } from "./core.mjs";

const DW = 1280, DH = 800;
const NAV_MS = Number(process.env.MOCK_NAV_MS ?? 400);
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const PAGES = {
  "example.com": ["Example Domain", "This domain is for use in illustrative examples."],
  "docs.dot.local": ["Dot documentation", "Self-hosted agent. Read the architecture and security notes."],
  "news.example.org": ["Daily briefing", "Three stories today. The first one is about local models."],
};
const BAD = /(^|\/\/)(localhost|127\.|10\.|192\.168\.|169\.254\.)/;

export const browserMode = { v: "ok" };
export const browserControl = (url, res) => (browserMode.v = url.searchParams.get("mode") ?? "ok", json(res, 200, { mode: browserMode.v }));

const bs = (s) => {
  if (!st.browser) st.browser = new Map();
  if (!st.browser.has(s.id)) st.browser.set(s.id, { tabs: [], active: null, n: 0, acting: false, seq: 0, blocked: null, click: null, typed: "", loadingUntil: 0, vp: null });
  return st.browser.get(s.id);
};
const cur = (b) => b.tabs.find((t) => t.tab === b.active);
const titleOf = (url) => (PAGES[new URL(url).hostname]?.[0] ?? new URL(url).hostname);

function go(b, raw, tab = cur(b)) {
  const url = /^[a-z]+:\/\//i.test(raw) ? raw : `https://${raw}`;
  if (BAD.test(url)) { b.blocked = "private address"; return false; }
  b.blocked = null;
  if (!tab) { tab = { tab: `t${++b.n}`, url: "", title: "", hist: [], pos: -1 }; b.tabs.push(tab); b.active = tab.tab; }
  tab.hist = [...tab.hist.slice(0, tab.pos + 1), url]; tab.pos++;
  tab.url = url; tab.title = titleOf(url); b.loadingUntil = Date.now() + 700;
  return true;
}
const snapshot = (s) => {
  const b = bs(s), t = cur(b), open = b.tabs.length > 0;
  return { open, tabs: b.tabs.map(({ tab, url, title }) => ({ tab, url, title })), active: b.active, url: t?.url ?? "", title: t?.title ?? "", loading: Date.now() < b.loadingUntil, can_back: !!t && t.pos > 0, can_forward: !!t && t.pos < t.hist.length - 1, viewport: open ? (b.vp ?? { width: DW, height: DH }) : b.vp, blocked: b.blocked, agent_acting: b.acting, agent_seq: b.seq, status: null };
};
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, Math.floor(Number(v) || 0)));

function frame(s) {
  const b = bs(s), t = cur(b), { width: W, height: H } = b.vp ?? { width: DW, height: DH };
  const [h, p] = PAGES[new URL(t.url).hostname] ?? [t.title, "Mock page content."];
  // narrow page: the input wraps under the links, like a responsive site
  const wide = W >= 1000, ix = wide ? 560 : 80, iy = wide ? 340 : 570, iw = wide ? 520 : Math.max(120, W - 160);
  const dot = b.click ? `<circle cx="${b.click[0]}" cy="${b.click[1]}" r="14" fill="none" stroke="#e11d48" stroke-width="3"/>` : "";
  const links = ["Getting started", "Reference", "Changelog"].map((l, i) => `<rect x="80" y="${340 + i * 70}" width="360" height="48" rx="8" fill="#eef2ff"/><text x="104" y="${371 + i * 70}" font-size="22" fill="#3730a3" font-family="sans-serif">${l}</text>`).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="${W}" height="${H}" fill="#fff"/><text x="80" y="140" font-size="56" font-weight="700" fill="#111" font-family="sans-serif">${esc(h)}</text><text x="80" y="210" font-size="26" fill="#444" font-family="sans-serif">${esc(p)}</text><text x="80" y="270" font-size="20" fill="#888" font-family="monospace">${esc(t.url)}  ${new Date().toLocaleTimeString()}</text>${links}<rect x="${ix}" y="${iy}" width="${iw}" height="52" rx="6" fill="#fff" stroke="#999"/><text x="${ix + 16}" y="${iy + 34}" font-size="22" fill="#111" font-family="sans-serif">${esc(b.typed)}</text>${dot}</svg>`;
}

/** Agent browser tool in a scripted turn: marks the session busy while it runs. */
export async function agentBrowse(c, url) {
  const b = bs(c.s);
  b.acting = true;
  await sleep(500);
  go(b, url);
  await c.tool("BrowserNavigate", { url }, `Opened (HTTP 200).\nPage: ${url}\nTitle: ${titleOf(/^[a-z]+:\/\//.test(url) ? url : `https://${url}`)}`, undefined, true);
  await sleep(900);
  await c.tool("BrowserRead", { view: "snapshot" }, `Page: ${url}\nElements:\n[1] link "Getting started"\n[2] link "Reference"`, undefined, true);
  b.acting = false; b.seq += 2;
}

export async function browserRoutes(req, res, s, sub, url, fail) {
  if (browserMode.v === "down") return fail(4015, "Browser is unavailable (start the 'browser' compose profile)", 502), true;
  const b = bs(s), act = sub.slice("browser/".length), post = req.method === "POST";
  if (act === "state") return json(res, 200, snapshot(s)), true;
  if (act === "frame" && post) {
    if (!cur(b)) return res.writeHead(204).end(), true;
    const body = Buffer.from(frame(s));
    return res.writeHead(200, { "Content-Type": "image/svg+xml", "Content-Length": body.length }), res.end(body), true;
  }
  if (!post) return false;
  const body = await readBody(req);
  if (b.acting) return fail(4017, "Dot is using the browser right now. Try again in a moment", 409), true;
  const t = cur(b);
  if (act === "navigate" || act === "reload") await sleep(NAV_MS); // server answering (worker returns at commit)
  if (act === "viewport") b.vp = { width: clamp(body.width, 320, 1920), height: clamp(body.height, 320, 1600) };
  else if (act === "navigate") { if (!go(b, String(body.url ?? ""))) return fail(4018, "The browser blocked this address (private or disallowed)", 403), true; }
  else if (act === "tabs/new") { if (body.url) { b.active = null; if (!go(b, body.url, null)) return fail(4018, "The browser blocked this address (private or disallowed)", 403), true; } else { b.tabs.push({ tab: `t${++b.n}`, url: "https://example.com/", title: "Example Domain", hist: ["https://example.com/"], pos: 0 }); b.active = `t${b.n}`; } }
  else if (act === "tabs/switch") b.active = body.tab;
  else if (act === "tabs/close") { b.tabs = b.tabs.filter((x) => x.tab !== body.tab); b.active = b.tabs.at(-1)?.tab ?? null; }
  else if (t && act === "back" && t.pos > 0) { t.url = t.hist[--t.pos]; t.title = titleOf(t.url); }
  else if (t && act === "forward" && t.pos < t.hist.length - 1) { t.url = t.hist[++t.pos]; t.title = titleOf(t.url); }
  else if (act === "reload") b.loadingUntil = Date.now() + 500;
  else if (act === "click") { b.click = [Math.round(body.x), Math.round(body.y)]; if (body.x > 80 && body.x < 440 && body.y > 340 && body.y < 550 && t) go(b, "docs.dot.local"); }
  else if (act === "type") b.typed = (b.typed + String(body.text ?? "")).slice(-40);
  else if (act === "press" && body.key === "Backspace") b.typed = b.typed.slice(0, -1);
  return json(res, 200, snapshot(s)), true;
}

// Per-session file store: files/list + content routes and the "write page" scenario.
import fs from "node:fs";
import zlib from "node:zlib";
import { st, json, sleep } from "./core.mjs";

const MIME = { html: "text/html; charset=utf-8", md: "text/markdown; charset=utf-8", csv: "text/csv; charset=utf-8", svg: "image/svg+xml", png: "image/png", py: "text/x-python; charset=utf-8", js: "text/javascript; charset=utf-8", ts: "text/plain; charset=utf-8", json: "application/json", txt: "text/plain; charset=utf-8" };
const ext = (p) => p.split(".").pop().toLowerCase();
export const mimeOf = (p) => MIME[ext(p)] ?? "application/octet-stream";
export function kindOf(p) {
  const e = ext(p);
  if (e === "html" || e === "htm") return "html";
  if (e === "md") return "md";
  if (e === "csv") return "csv";
  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(e)) return "image";
  return ["py", "js", "ts", "json", "sh", "css", "yaml", "yml", "toml"].includes(e) ? "code" : "other";
}

export function putFile(sid, path, content) {
  if (!st.files.has(sid)) st.files.set(sid, new Map());
  const buf = Buffer.isBuffer(content) ? content : Buffer.from(content);
  st.files.get(sid).set(path, { buf, mtime: new Date().toISOString() });
  return buf;
}

const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc = (b) => { let c = 0xffffffff; for (const x of b) c = crcTable[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
const chunk = (type, data) => { const t = Buffer.from(type); const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const c = Buffer.alloc(4); c.writeUInt32BE(crc(Buffer.concat([t, data]))); return Buffer.concat([len, t, data, c]); };
/** Small valid RGB PNG (a 24x24 gradient). */
export function tinyPng(size = 24) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4); ihdr[8] = 8; ihdr[9] = 2;
  const raw = Buffer.alloc((size * 3 + 1) * size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) { const o = y * (size * 3 + 1) + 1 + x * 3; raw[o] = (x * 255) / size; raw[o + 1] = (y * 255) / size; raw[o + 2] = 160; }
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

const HTML = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Dot demo</title><style>body{font:16px system-ui;margin:2rem}button{padding:.5rem 1rem}</style></head><body><h1>Dot demo page</h1><p>Sandboxed HTML written by the agent.</p><button onclick="document.querySelector('p').textContent='clicked '+new Date().toLocaleTimeString()">Click me</button></body></html>`;
const SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 60" width="240" height="120"><rect width="120" height="60" rx="8" fill="#1f2937"/><circle cx="30" cy="30" r="16" fill="#34d399"/><text x="56" y="36" fill="#fff" font-size="16" font-family="sans-serif">Dot</text></svg>`;
const CSV = "id,name,score\n1,Alice,92\n2,Bob,78\n3,Zafar,85\n4,Мария,91\n5,Oʻtkir,67\n";
const MD = "# Notes\n\n- Self-hosted agent\n- Files are served from the session workspace\n\n| key | value |\n|---|---|\n| port | 8765 |\n";

export const seedFiles = (sid) => {
  putFile(sid, "README.md", MD);
  putFile(sid, "index.html", HTML);
  putFile(sid, "data/scores.csv", CSV);
  putFile(sid, "assets/logo.svg", SVG);
  putFile(sid, "assets/preview.png", tinyPng());
  putFile(sid, "src/app.py", "import logging\n\n\ndef main() -> int:\n    logging.basicConfig(level=logging.INFO)\n    return 0\n");
};

export async function writePageScenario(c) {
  await c.tok("I'll write a small page with some assets.\n");
  const files = [["page.html", HTML], ["report.md", MD], ["scores.csv", CSV], ["logo.svg", SVG], ["chart.png", tinyPng()]];
  for (const [path, content] of files) {
    putFile(c.s.id, path, content);
    await c.tool("Write", { file_path: path, content: Buffer.isBuffer(content) ? `<binary png, ${content.length} bytes>` : content }, `Wrote ${path} (${Buffer.byteLength(content)} bytes)`);
    await sleep(60);
  }
  await c.tok("Done. Open the Files panel to preview `page.html`, `report.md`, `scores.csv`, `logo.svg` and `chart.png`.");
  return true;
}

export function fileRoutes(s, sub, res, url, fail) {
  const store = st.files.get(s.id) ?? new Map();
  if (sub === "files") return json(res, 200, [...store].map(([path, f]) => ({ path, size: f.buf.length, mtime: f.mtime, kind: kindOf(path) }))), true;
  const f = store.get(url.searchParams.get("path") ?? "");
  if (!f) return fail(4010, "File not found", 404), true;
  const path = url.searchParams.get("path");
  res.writeHead(200, { "Content-Type": mimeOf(path), "Content-Length": f.buf.length, "X-Content-Type-Options": "nosniff", ...(kindOf(path) === "html" || ext(path) === "svg" ? { "Content-Security-Policy": "sandbox" } : {}) });
  res.end(f.buf);
  return true;
}

// Rendered html, same rules as backend/sessions/services/workspace/preview.py (CSP, chart tag, reporter).
const ASSETS = new URL("../../../../backend/backend/sessions/assets/", import.meta.url);
const asset = (n) => fs.readFileSync(new URL(n, ASSETS), "utf8").replaceAll("</script", "<\\/script");
const RENDER_CSP = "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'; frame-src 'none'; frame-ancestors 'self'; form-action 'none'; base-uri 'none'";
const CHART_TAG = /<script\b[^>]*\bsrc\s*=\s*["']?(?:\.\/)?dot-chart\.js["']?[^>]*>\s*<\/script>/gi;
function prepare(html) {
  const t = html.replace(CHART_TAG, () => `<script>${asset("chart.umd.js")}</script>`);
  const rt = `<script>${asset("artifact_runtime.js")}</script>`;
  const m = /<head\b[^>]*>/i.exec(t);
  return m ? t.slice(0, m.index + m[0].length) + rt + t.slice(m.index + m[0].length) : rt + t;
}

/** GET /v1/files/content?path=&render= : the real route (not session scoped). */
export function contentRoute(req, res, p, url, fail) {
  if (p !== "/v1/files/content") return false;
  const path = url.searchParams.get("path") ?? "";
  const rel = path.replace(/^\/workspace\//, "");
  let f = null;
  for (const store of st.files.values()) f ??= store.get(path) ?? store.get(rel) ?? null;
  if (!f) return fail(4110, "File not found", 404), true;
  const kind = kindOf(path);
  if (url.searchParams.get("render") === "1" && kind === "html") {
    const body = Buffer.from(prepare(f.buf.toString("utf8")));
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Content-Length": body.length, "X-Content-Type-Options": "nosniff", "Content-Security-Policy": RENDER_CSP, "X-Frame-Options": "SAMEORIGIN" });
    return res.end(body), true;
  }
  const text = ["html", "md", "csv", "code"].includes(kind);
  res.writeHead(200, { "Content-Type": text ? "text/plain; charset=utf-8" : mimeOf(path), "Content-Length": f.buf.length, "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox" });
  return res.end(f.buf), true;
}

const CHART_PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>Sales</title><style>body{font:16px system-ui;margin:1rem}.box{height:260px}</style></head><body><h1>Sales by month</h1><div class="box"><canvas id="c"></canvas></div><button id="b">Add month</button><script src="dot-chart.js"></script><script>const d=[3,5,4];const ch=new Chart(document.getElementById("c"),{type:"bar",data:{labels:["Jan","Feb","Mar"],datasets:[{label:"Sales",data:d}]},options:{responsive:true,maintainAspectRatio:false}});document.getElementById("b").onclick=()=>{d.push(7);ch.data.labels.push("Apr");ch.update()};window.__chart=typeof Chart;</script></body></html>`;
const BROKEN_PAGE = `<!doctype html><html><body><p id="s">broken</p><script>console.warn("careful now");undefinedFunction();</script></body></html>`;
// Tries every way out; reports each result to the parent (postMessage is the one allowed channel).
const PROBE_PAGE = `<!doctype html><html><body><script>
const out = {};
const done = (k, v) => { out[k] = v; };
const tryit = async (k, fn) => { try { await fn(); done(k, "REACHED"); } catch (e) { done(k, "blocked"); } };
(async () => {
  await tryit("fetch", () => fetch("/api/dot/v1/sessions"));
  await tryit("fetch-remote", () => fetch("https://example.com/"));
  await tryit("xhr", () => new Promise((ok, no) => { const x = new XMLHttpRequest(); x.open("GET", "/health"); x.onload = ok; x.onerror = no; x.send(); }));
  await tryit("websocket", () => new Promise((ok, no) => { const w = new WebSocket("ws://127.0.0.1:1/"); w.onopen = ok; w.onerror = no; }));
  await tryit("image-remote", () => new Promise((ok, no) => { const i = new Image(); i.onload = ok; i.onerror = no; i.src = "https://example.com/x.png"; }));
  await tryit("parent-document", () => parent.document.title);
  await tryit("top-location", () => top.location.href);
  await tryit("local-storage", () => localStorage.getItem("x"));
  await tryit("cookie", () => document.cookie);
  out.origin = String(window.origin);
  parent.postMessage({ probe: out }, "*");
})();
<\/script></body></html>`;

export async function writeArtifactScenario(c) {
  await c.tok("I'll build an interactive chart and a broken page for testing.\n");
  for (const [path, content] of [["chart.html", CHART_PAGE], ["broken.html", BROKEN_PAGE], ["probe.html", PROBE_PAGE]]) {
    putFile(c.s.id, path, content);
    await c.tool("Write", { file_path: path, content }, `Wrote ${path} (${Buffer.byteLength(content)} bytes)`);
    await sleep(60);
  }
  await c.tok("Done. Open `chart.html` in the Preview tab.");
  return true;
}

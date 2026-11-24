// Tiny mock of the Dot backend with the real contract shapes (docs/api-contract.md). No external deps.
// Prompts: "edit" -> approval with a diff; "bash" -> approval with a command; "code" -> markdown + code;
// "long" -> worst-case output; anything else -> thinking + a read tool + answer.
import http from "node:http";
import { seed } from "./mock-data.mjs";
import { scenario } from "./mock-scenarios.mjs";

const PORT = Number(process.env.MOCK_PORT ?? 8765);
const TOKEN = process.env.MOCK_TOKEN ?? "mock-token";
const SLOW = Number(process.env.MOCK_DELAY ?? 25);
const sessions = new Map();
const approvals = new Map();
const answers = new Map();
let data = seed(false);
const audit = [];
let n = 0;
const id = () => `S${String(++n).padStart(5, "0")}ABCD`.slice(0, 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const envelope = (code, text, status = 400) => ({ status, body: [{ key: null, code, show: true, icon_type: "error", type: "domain_error", messages: [text] }] });

function newSession(mode = "default", title = null) {
  const s = { id: id(), mode, title, created_at: new Date().toISOString(), messages: [], seq: 0, running: false, cancel: false };
  sessions.set(s.id, s);
  return s;
}
const pub = (s) => ({ id: s.id, mode: s.mode, title: s.title, created_at: s.created_at });
const add = (s, m) => s.messages.push({ seq: ++s.seq, tool_calls: null, tool_call_id: null, rewound: false, created_at: new Date().toISOString(), ...m });

function json(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}
const readBody = (req) => new Promise((r) => { let d = ""; req.on("data", (c) => (d += c)); req.on("end", () => { try { r(JSON.parse(d || "{}")); } catch { r({}); } }); });

const DIFF = `--- a/src/app.py
+++ b/src/app.py
@@ -10,7 +10,8 @@ def main():
     args = parse()
-    run(args)
+    setup_logging(args.verbose)
+    run(args)
     return 0
`;
const LONG_UNBROKEN = "x".repeat(6000);

async function turn(s, text, res) {
  const send = (e) => !res.writableEnded && res.write(`data: ${JSON.stringify(e)}\n\n`);
  const tok = async (t, thinking = false) => { for (const part of t.match(t.length > 500 ? /[\s\S]{1,400}/g : /[\s\S]{1,12}/g) ?? []) { if (s.cancel) return; send({ type: "token", text: part, thinking }); await sleep(SLOW); } };
  add(s, { role: "user", content: text });
  if (!s.title) s.title = text.slice(0, 60);
  const usage = (k) => send({ type: "usage", context_tokens: 1200 * k, context_limit: 16384 });
  const tool = async (name, args, output, ask, tainted = false) => {
    const call_id = `call_${++n}`;
    send({ type: "tool_call", invocation: { call_id, name, arguments: args } });
    audit.unshift({ id: `A${n}`, session: s.id, mode: s.mode, tool: name, args, decision: ask ? "ask" : "allow", source: ask ? "classifier" : "rule", reason: ask ? "mutating call" : "read-only", created_at: new Date().toISOString() });
    if (ask) {
      const approval_id = `ap_${n}`;
      send({ type: "approval_required", approval_id, invocation: { call_id, name, arguments: args }, diff: ask.diff ?? null, verdict: { decision: "ask", stage: "B", reason: ask.reason } });
      const decision = await new Promise((r) => approvals.set(approval_id, r));
      audit.unshift({ id: `U${n}`, session: s.id, mode: s.mode, tool: name, args, decision: decision === "reject" ? "deny" : "allow", source: "user", reason: `answered ${decision}`, created_at: new Date().toISOString() });
      if (decision === "reject") { send({ type: "tool_result", result: { call_id, output: "Denied (error 3000): rejected by user", is_error: true, tainted: false, spill_path: null } }); return false; }
    }
    send({ type: "tool_result", result: { call_id, output, is_error: false, tainted, spill_path: null } });
    return true;
  };
  usage(1);
  const approve = (approval_id) => new Promise((r) => approvals.set(approval_id, r));
  if (await scenario(text, { s, send, tok, tool, usage, sleep, answers, approve, id: () => ++n, add: (m) => add(s, m) })) {
    /* handled by a scenario */
  } else if (/long/i.test(text)) {
    await tok("Worst case output follows.\n\n" + LONG_UNBROKEN + "\n\nعربي نص طويل للاختبار 🙂 Привет, мир! Oʻzbekcha: gʻoya, oʻrik.\n");
    await tool("Bash", { command: "cat big.log " + LONG_UNBROKEN.slice(0, 300) }, Array.from({ length: 400 }, (_, i) => `line ${i} ${"y".repeat(60)}`).join("\n") + "\n" + LONG_UNBROKEN);
  } else if (/code/i.test(text)) {
    await tok("Here is a **fix**:\n\n```python\ndef add(a: int, b: int) -> int:\n    return a + b  # simple\n```\n\n- first point with `inline code`\n- second point\n\n| name | value |\n|---|---|\n| alpha | 1 |\n| beta | 2 |\n\nSee [docs](https://example.com).");
  } else if (/edit|bash/i.test(text)) {
    await tok("I need to change a file.", true);
    await tok("Let me update the entry point.");
    usage(2);
    const edit = /edit/i.test(text);
    const ok = await tool(edit ? "Edit" : "Bash", edit ? { file_path: "src/app.py", old: "run(args)", new: "setup_logging(args.verbose)\nrun(args)" } : { command: "rm -rf build && npm run build" }, edit ? "Edited src/app.py (1 replacement)" : "build ok", edit ? { diff: DIFF, reason: "edits a tracked file" } : { reason: "destructive shell command" });
    if (!s.cancel) await tok(ok ? "Done. The entry point now configures logging." : "Understood, I left the file alone.");
  } else {
    await tok("The user wants a summary. I should read the readme first.", true);
    await tok("Reading the project overview.\n");
    usage(2);
    await tool("Read", { file_path: "README.md" }, "     1\t# Dot\n     2\tSelf-hosted coding agent.");
    await tok("Dot is a self-hosted coding and research agent.");
  }
  add(s, { role: "assistant", content: "(reply)" });
  usage(3);
  send({ type: "done", stop_reason: s.cancel ? "cancelled" : "end_turn" });
  res.end();
}

const SKILLS = [
  { name: "review", description: "Review the current diff for bugs.", source: "bundled", available: true, reason: null, model_invocable: true },
  { name: "commit", description: "Write a conventional commit message.", source: "user", available: true, reason: null, model_invocable: false },
  { name: "browse", description: "Drive the browser worker.", source: "bundled", available: false, reason: "missing tool: browser", model_invocable: true },
];

const TIERS = { prefix: 2100, global: 400, user: 120, workspace: 900, memory: 260 };
const readJson = readBody;

async function extra(req, res, p, url, fail) {
  let m;
  const get = req.method === "GET";
  if ((m = /^\/v1\/questions\/([^/]+)\/answer$/.exec(p))) {
    const q = answers.get(m[1]);
    if (!q) return fail(2003, "Question not found", 404);
    const { selected = [], other = null } = await readJson(req);
    if ((!selected.length && !other) || selected.some((x) => !q.options.includes(x)) || (!q.multi && selected.length > 1)) return fail(2005, "Answer is not valid", 400);
    answers.delete(m[1]); q.r([...selected, ...(other ? [other] : [])].join(", "));
    return json(res, 200, { ok: true });
  }
  if ((m = /^\/v1\/sessions\/([^/]+)\/(tasks|context|compact)$/.exec(p))) {
    const s = sessions.get(m[1]);
    if (!s) return fail(2000, "Session not found", 404);
    if (m[2] === "tasks") return json(res, 200, data.tasks);
    if (m[2] === "context") return json(res, 200, { limit: 16384, threshold: 12288, used: 7200, source: "reported", tiers: TIERS, messages: { user: 600, assistant: 2400, tool: 1800, summary: s.compacted ? 900 : 0 }, compactions: s.compacted ? [{ id: 1, trigger: "auto", stages: ["summary"], tokens_before: 12100, tokens_after: 4300, summary_seq: 9, undone: false, created_at: new Date().toISOString() }] : [] });
    if (s.running) return fail(2001, "Session is busy", 409);
    s.compacted = true;
    return json(res, 200, { compacted: true, reason: null, tokens_before: 7200, tokens_after: 2600, stages: ["summary"] });
  }
  if (p === "/v1/tools") return json(res, 200, data.tools);
  if (p === "/v1/mcp/servers") return json(res, 200, data.mcp);
  if ((m = /^\/v1\/mcp\/servers\/([^/]+)\/(reconnect|trust)$/.exec(p))) {
    const sv = data.mcp.find((x) => x.name === decodeURIComponent(m[1]));
    if (!sv) return fail(4030, "MCP server not found", 404);
    if (m[2] === "trust") sv.trusted = true;
    sv.status = "connecting"; sv.error = null;
    setTimeout(() => { sv.status = "connected"; sv.tool_count ||= 4; }, 1200);
    return json(res, 200, sv);
  }
  if (p === "/v1/memory" && get) { const q = (url.searchParams.get("q") ?? "").toLowerCase(); return json(res, 200, data.memory.filter((f) => !q || `${f.name} ${f.body}`.toLowerCase().includes(q))); }
  if (p === "/v1/memory") { const b = await readJson(req); if (!b.name || !b.body) return fail(2022, "Invalid memory fact", 400); const f = { id: `M${String(++n).padStart(9, "0")}`, description: "", kind: "project", ...b, updated_at: new Date().toISOString() }; data.memory.unshift(f); return json(res, 201, f); }
  if ((m = /^\/v1\/memory\/([^/]+)$/.exec(p))) {
    const f = data.memory.find((x) => x.id === m[1]);
    if (!f) return fail(2021, "Memory fact not found", 404);
    if (req.method === "DELETE") { data.memory = data.memory.filter((x) => x !== f); return json(res, 200, { ok: true }); }
    Object.assign(f, await readJson(req), { updated_at: new Date().toISOString() }); return json(res, 200, f);
  }
  if (p === "/v1/schedules" && get) return json(res, 200, data.schedules);
  if (p === "/v1/schedules") {
    const b = await readJson(req);
    if (String(b.cron ?? "").trim().split(/\s+/).length !== 5 && !/^@/.test(b.cron ?? "")) return fail(4035, "Invalid cron expression", 400);
    const j = { id: `JU${String(++n).padStart(8, "0")}`, kind: "user", cron: b.cron, prompt: b.prompt, enabled: true, created_at: new Date().toISOString(), last_run_at: null, next_run_at: new Date(Date.now() + 3_600_000).toISOString(), last_status: null, runs: [] };
    data.schedules.push(j); return json(res, 201, j);
  }
  if ((m = /^\/v1\/schedules\/([^/]+)$/.exec(p)) && req.method === "DELETE") {
    const j = data.schedules.find((x) => x.id === m[1]);
    if (!j) return fail(4036, "Schedule not found", 404);
    if (j.kind === "builtin") return fail(4038, "Built-in jobs cannot be deleted", 409);
    data.schedules = data.schedules.filter((x) => x !== j); return json(res, 200, { ok: true });
  }
  return false;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const p = url.pathname;
  if (p === "/__seed") { data = seed(url.searchParams.get("worst") === "1"); return json(res, 200, { ok: true }); }
  if (p === "/__reset") { sessions.clear(); approvals.clear(); answers.clear(); audit.length = 0; data = seed(url.searchParams.get("worst") === "1"); return json(res, 200, { ok: true }); }
  if (req.headers.authorization !== `Bearer ${TOKEN}` && p !== "/health") return json(res, 401, envelope(1001, "Invalid token", 401).body);
  const lang = (req.headers["accept-language"] ?? "en").slice(0, 2);
  const fail = (code, text, status) => { const e = envelope(code, lang === "ru" ? `[ru] ${text}` : text, status); json(res, e.status, e.body); };
  let m;
  if (p === "/ready" || p === "/health") return json(res, 200, { ok: true });
  if (p === "/v1/skills") return json(res, 200, SKILLS);
  if (p.startsWith("/v1/") && (await extra(req, res, p, url, fail)) !== false) return;
  if (p === "/v1/audit") return json(res, 200, { items: audit.filter((a) => !url.searchParams.get("session") || a.session === url.searchParams.get("session")).slice(0, 50), next_cursor: null });
  if (p === "/v1/sessions" && req.method === "GET") return json(res, 200, [...sessions.values()].reverse().map(pub));
  if (p === "/v1/sessions" && req.method === "POST") { const b = await readBody(req); return json(res, 201, pub(newSession(b.mode, b.title))); }
  if ((m = /^\/v1\/approvals\/([^/]+)\/resolve$/.exec(p))) {
    const r = approvals.get(m[1]);
    if (!r) return fail(3003, "Unknown approval", 404);
    approvals.delete(m[1]); r((await readBody(req)).decision); return json(res, 200, { ok: true });
  }
  if ((m = /^\/v1\/sessions\/([^/]+)(\/[a-z]+)?$/.exec(p))) {
    const s = sessions.get(m[1]);
    if (!s) return fail(2000, "Session not found", 404);
    if (m[2] === "/messages") return json(res, 200, s.messages.filter((x) => !x.rewound));
    if (m[2] === "/mode") { s.mode = (await readBody(req)).mode; return json(res, 200, pub(s)); }
    if (m[2] === "/stop") { s.cancel = true; for (const r of approvals.values()) r("reject"); for (const q of answers.values()) q.r("(cancelled)"); return json(res, 200, { ok: true, stopped: s.running }); }
    if (m[2] === "/rewind") {
      const to = (await readBody(req)).to_seq; let k = 0;
      s.messages.forEach((x) => { if (x.seq > to) { x.rewound = true; k++; } });
      return json(res, 200, { kept_through_seq: to, rewound_messages: k, restored: [{ path: "src/app.py", action: "restored" }] });
    }
    if (m[2] === "/chat") {
      if (s.running) return fail(2001, "Session is busy", 409);
      const text = (await readBody(req)).message ?? "";
      s.running = true; s.cancel = false;
      res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" });
      req.on("close", () => { if (!res.writableEnded) s.cancel = true; });
      try { await turn(s, text, res); } finally { s.running = false; }
      return;
    }
  }
  fail(1002, "Not found", 404);
});

server.listen(PORT, "127.0.0.1", () => console.log(`mock backend on http://127.0.0.1:${PORT} token=${TOKEN}`));

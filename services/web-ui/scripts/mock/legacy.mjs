// Older routes: skills, audit, approvals, tasks/context/compact, tools, MCP, memory, schedules.
import { st, nid, json, readBody } from "./core.mjs";

const SKILLS = [
  { name: "review", description: "Review the current diff for bugs.", source: "bundled", available: true, reason: null, model_invocable: true },
  { name: "commit", description: "Write a conventional commit message.", source: "user", available: true, reason: null, model_invocable: false },
  { name: "browse", description: "Drive the browser worker.", source: "bundled", available: false, reason: "missing tool: browser", model_invocable: true },
];
const TIERS = { prefix: 2100, global: 400, user: 120, workspace: 900, memory: 260 };
const T = true;

export async function legacyRoutes(req, res, p, url, fail) {
  let m;
  const get = req.method === "GET";
  const d = st.data;
  if (p === "/v1/skills") return json(res, 200, SKILLS), T;
  if (p === "/v1/audit") return json(res, 200, { items: st.audit.filter((a) => !url.searchParams.get("session") || a.session === url.searchParams.get("session")).slice(0, 50), next_cursor: null }), T;
  if ((m = /^\/v1\/approvals\/([^/]+)\/resolve$/.exec(p))) {
    const r = st.approvals.get(m[1]);
    if (!r) return fail(3003, "Unknown approval", 404), T;
    st.approvals.delete(m[1]); r((await readBody(req)).decision);
    return json(res, 200, { ok: true }), T;
  }
  if ((m = /^\/v1\/sessions\/([^/]+)\/(tasks|context|compact)$/.exec(p))) {
    const s = st.sessions.get(m[1]);
    if (!s) return fail(2000, "Session not found", 404), T;
    if (m[2] === "tasks") return json(res, 200, d.tasks), T;
    if (m[2] === "context") return json(res, 200, { limit: 16384, threshold: 12288, used: 7200, source: "reported", tiers: TIERS, messages: { user: 600, assistant: 2400, tool: 1800, summary: s.compacted ? 900 : 0 }, compactions: s.compacted ? [{ id: 1, trigger: "auto", stages: ["summary"], tokens_before: 12100, tokens_after: 4300, summary_seq: 9, undone: false, created_at: new Date().toISOString() }] : [] }), T;
    if (s.running) return fail(2001, "Session is busy", 409), T;
    s.compacted = true;
    return json(res, 200, { compacted: true, reason: null, tokens_before: 7200, tokens_after: 2600, stages: ["summary"] }), T;
  }
  if (p === "/v1/tools") return json(res, 200, d.tools), T;
  if (p === "/v1/mcp/servers") return json(res, 200, d.mcp), T;
  if ((m = /^\/v1\/mcp\/servers\/([^/]+)\/(reconnect|trust)$/.exec(p))) {
    const sv = d.mcp.find((x) => x.name === decodeURIComponent(m[1]));
    if (!sv) return fail(4030, "MCP server not found", 404), T;
    if (m[2] === "trust") sv.trusted = true;
    sv.status = "connecting"; sv.error = null;
    setTimeout(() => { sv.status = "connected"; sv.tool_count ||= 4; }, 1200);
    return json(res, 200, sv), T;
  }
  if (p === "/v1/memory" && get) { const q = (url.searchParams.get("q") ?? "").toLowerCase(); return json(res, 200, d.memory.filter((f) => !q || `${f.name} ${f.body}`.toLowerCase().includes(q))), T; }
  if (p === "/v1/memory") {
    const b = await readBody(req);
    if (!b.name || !b.body) return fail(2022, "Invalid memory fact", 400), T;
    const f = { id: `M${String(nid()).padStart(9, "0")}`, description: "", kind: "project", ...b, updated_at: new Date().toISOString() };
    d.memory.unshift(f);
    return json(res, 201, f), T;
  }
  if ((m = /^\/v1\/memory\/([^/]+)$/.exec(p))) {
    const f = d.memory.find((x) => x.id === m[1]);
    if (!f) return fail(2021, "Memory fact not found", 404), T;
    if (req.method === "DELETE") { d.memory = d.memory.filter((x) => x !== f); return json(res, 200, { ok: true }), T; }
    Object.assign(f, await readBody(req), { updated_at: new Date().toISOString() });
    return json(res, 200, f), T;
  }
  if (p === "/v1/schedules" && get) return json(res, 200, d.schedules), T;
  if (p === "/v1/schedules") {
    const b = await readBody(req);
    if (String(b.cron ?? "").trim().split(/\s+/).length !== 5 && !/^@/.test(b.cron ?? "")) return fail(4035, "Invalid cron expression", 400), T;
    const j = { id: `JU${String(nid()).padStart(8, "0")}`, kind: "user", cron: b.cron, prompt: b.prompt, enabled: true, created_at: new Date().toISOString(), last_run_at: null, next_run_at: new Date(Date.now() + 3_600_000).toISOString(), last_status: null, runs: [] };
    d.schedules.push(j);
    return json(res, 201, j), T;
  }
  if ((m = /^\/v1\/schedules\/([^/]+)$/.exec(p)) && req.method === "DELETE") {
    const j = d.schedules.find((x) => x.id === m[1]);
    if (!j) return fail(4036, "Schedule not found", 404), T;
    if (j.kind === "builtin") return fail(4038, "Built-in jobs cannot be deleted", 409), T;
    d.schedules = d.schedules.filter((x) => x !== j);
    return json(res, 200, { ok: true }), T;
  }
  return false;
}

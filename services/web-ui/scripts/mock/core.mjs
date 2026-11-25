// Shared state, ids, session model and HTTP helpers for the mock backend.
import { seed } from "../mock-data.mjs";

export const PORT = Number(process.env.MOCK_PORT ?? 8765);
export const TOKEN = process.env.MOCK_TOKEN ?? "mock-token";
export const SLOW = Number(process.env.MOCK_DELAY ?? 25);
export const EFFORTS = ["off", "low", "medium", "high", "max"];

export const st = {
  sessions: new Map(), approvals: new Map(), answers: new Map(), audit: [],
  caps: new Set(), data: seed(false), n: 0,
  files: new Map(), uploads: new Map(), projects: [], model: "qwen3-coder-30b", loadingUntil: 0,
};

export const nid = () => ++st.n;
export const newId = () => `S${String(nid()).padStart(5, "0")}ABCD`.slice(0, 10);
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const envelope = (code, text, status = 400) => ({ status, body: [{ key: null, code, show: true, icon_type: "error", type: "domain_error", messages: [text] }] });

export function json(res, status, body, headers = {}) {
  res.writeHead(status, { "Content-Type": "application/json", ...headers });
  res.end(JSON.stringify(body));
}

/** Raw request body; resolves null when it exceeds `limit` bytes. */
export const readRaw = (req, limit = 25 * 1024 * 1024) =>
  new Promise((resolve) => {
    const parts = [];
    let size = 0;
    req.on("data", (c) => { size += c.length; if (size <= limit) parts.push(c); });
    req.on("end", () => resolve(size > limit ? null : Buffer.concat(parts)));
    req.on("error", () => resolve(null));
  });

export async function readBody(req) {
  const b = await readRaw(req, 8 * 1024 * 1024);
  try { return JSON.parse(b?.toString() || "{}"); } catch { return {}; }
}

export function newSession(o = {}) {
  const now = new Date().toISOString();
  const s = { id: newId(), mode: o.mode ?? "default", title: o.title ?? null, created_at: now, updated_at: now, messages: [], seq: 0, running: false, cancel: false, blocked: 0, pinned: false, archived: false, project: o.project ?? null, state: "idle", parent_id: null, effort: "medium" };
  st.sessions.set(s.id, s);
  if (s.project) ensureProject(s.project);
  return s;
}

export function ensureProject(name) {
  if (!st.projects.some((p) => p.name === name)) st.projects.push({ id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `p${nid()}`, name, instructions: "" });
}

export const stateOf = (s) => (s.running ? (s.blocked > 0 ? "waiting" : "running") : s.state);
export const pub = (s) => ({ id: s.id, mode: s.mode, title: s.title, created_at: s.created_at, pinned: s.pinned, archived: s.archived, project: s.project, state: stateOf(s), parent_id: s.parent_id, updated_at: s.updated_at, effort: s.effort });

export function add(s, m) {
  const now = new Date().toISOString();
  s.updated_at = now;
  const msg = { seq: ++s.seq, tool_calls: null, tool_call_id: null, rewound: false, created_at: now, ...m };
  s.messages.push(msg);
  return msg;
}

/** Store one finished assistant turn: assistant message (text, thinking, calls, meta) plus tool results. */
export function persistTurn(s, acc) {
  const meta = {};
  if (acc.thinking) meta.thinking = acc.thinking;
  if (acc.widgets?.length) meta.widgets = acc.widgets;
  if (acc.sources) meta.sources = acc.sources;
  if (acc.effort) meta.effort = acc.effort;
  add(s, {
    role: "assistant", content: acc.text, ...(acc.thinking ? { thinking: acc.thinking } : {}),
    tool_calls: acc.calls.length ? acc.calls.map((c) => ({ id: c.call_id, type: "function", function: { name: c.name, arguments: c.args } })) : null,
    ...(Object.keys(meta).length ? { meta } : {}),
  });
  for (const c of acc.calls) if (c.output !== undefined) add(s, { role: "tool", content: c.output, tool_call_id: c.call_id, tainted: !!c.tainted });
}

/** Shift a session (and its messages) to `minAgo` minutes in the past. */
export function age(s, minAgo) {
  const t = new Date(Date.now() - minAgo * 60_000).toISOString();
  s.created_at = s.updated_at = t;
  s.messages.forEach((m) => { m.created_at = t; });
}

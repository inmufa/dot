// Session routes: list/create/patch/delete, search, export, regenerate, branch, effort, chat, and the older session actions.
import { st, json, readBody, newSession, pub, EFFORTS } from "./core.mjs";
import { turn } from "./turn.mjs";
import { attachmentRoutes } from "./attachments.mjs";
import { fileRoutes } from "./files.mjs";
import { browserRoutes } from "./browser.mjs";

const live = (s) => s.messages.filter((x) => !x.rewound);

function search(q) {
  const out = [];
  for (const s of st.sessions.values()) {
    let hits = 0;
    if ((s.title ?? "").toLowerCase().includes(q)) { out.push({ session_id: s.id, title: s.title, snippet: s.title, seq: 0 }); hits++; }
    for (const m of live(s)) {
      if ((m.role !== "user" && m.role !== "assistant") || hits >= 4) continue;
      const i = (m.content ?? "").toLowerCase().indexOf(q);
      if (i === -1) continue;
      out.push({ session_id: s.id, title: s.title, snippet: m.content.slice(Math.max(0, i - 40), i + q.length + 60), seq: m.seq });
      hits++;
    }
    if (out.length >= 60) break;
  }
  return out;
}

function exportSession(s, fmt, res) {
  const name = `session-${s.id}.${fmt === "json" ? "json" : "md"}`;
  const headers = { "Content-Disposition": `attachment; filename="${name}"` };
  if (fmt === "json") {
    res.writeHead(200, { "Content-Type": "application/json", ...headers });
    return res.end(JSON.stringify({ session: pub(s), messages: live(s) }, null, 2));
  }
  const body = [`# ${s.title ?? "Untitled"}`, "", ...live(s).filter((m) => m.role === "user" || m.role === "assistant").flatMap((m) => [`### ${m.role === "user" ? "You" : "Dot"}`, "", m.content, ""])].join("\n");
  res.writeHead(200, { "Content-Type": "text/markdown; charset=utf-8", ...headers });
  res.end(body);
}

async function stream(s, res, req, text, body, opts) {
  s.running = true; s.cancel = false; s.state = "running";
  res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" });
  res.on("close", () => { if (!res.writableEnded) s.cancel = true; });
  try { await turn(s, text, res, body, opts); } finally { s.running = false; s.blocked = 0; if (!res.writableEnded) res.end(); }
}

export async function sessionRoutes(req, res, p, url, fail) {
  const get = req.method === "GET";
  if (p === "/v1/search") {
    const q = (url.searchParams.get("q") ?? "").trim().toLowerCase();
    return json(res, 200, q ? search(q) : []), true;
  }
  if (p === "/v1/sessions" && get) {
    const all = ["1", "true"].includes(url.searchParams.get("include_archived") ?? "");
    const list = [...st.sessions.values()].filter((s) => all || !s.archived).sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return json(res, 200, list.map(pub)), true;
  }
  if (p === "/v1/sessions" && req.method === "POST") {
    const b = await readBody(req);
    return json(res, 201, pub(newSession({ mode: b.mode, title: b.title, project: typeof b.project === "string" && b.project ? (st.projects.find((x) => x.id === b.project)?.name ?? b.project) : null }))), true;
  }
  const m = /^\/v1\/sessions\/([^/]+)(?:\/(.+))?$/.exec(p);
  if (!m) return false;
  const s = st.sessions.get(m[1]);
  if (!s) return fail(2000, "Session not found", 404), true;
  const sub = m[2] ?? "";

  if (sub === "" && req.method === "PATCH") {
    const b = await readBody(req);
    if (typeof b.title === "string") s.title = b.title.slice(0, 500);
    if (typeof b.pinned === "boolean") s.pinned = b.pinned;
    if (typeof b.archived === "boolean") s.archived = b.archived;
    s.updated_at = new Date().toISOString();
    return json(res, 200, pub(s)), true;
  }
  if (sub === "" && req.method === "DELETE") {
    if (s.running) s.cancel = true;
    st.sessions.delete(s.id); st.files.delete(s.id); st.uploads.delete(s.id);
    return json(res, 200, { ok: true }), true;
  }
  if (sub === "" && get) return json(res, 200, pub(s)), true;
  if (sub === "messages") return json(res, 200, live(s)), true;
  if (sub === "mode") { s.mode = (await readBody(req)).mode; return json(res, 200, pub(s)), true; }
  if (sub === "stop") {
    s.cancel = true;
    for (const r of st.approvals.values()) r("reject");
    for (const q of st.answers.values()) q.r("(cancelled)");
    return json(res, 200, { ok: true, stopped: s.running }), true;
  }
  if (sub === "rewind") {
    const to = (await readBody(req)).to_seq; let k = 0;
    s.messages.forEach((x) => { if (x.seq > to) { x.rewound = true; k++; } });
    return json(res, 200, { kept_through_seq: to, rewound_messages: k, restored: [{ path: "src/app.py", action: "restored" }] }), true;
  }
  if (sub === "effort" && req.method === "PUT") {
    const { effort } = await readBody(req);
    if (!EFFORTS.includes(effort)) return fail(2005, "Invalid effort", 400), true;
    s.effort = effort;
    return json(res, 200, pub(s)), true;
  }
  if (sub === "export") {
    const f = url.searchParams.get("format") ?? "md";
    if (f !== "md" && f !== "json") return fail(2005, "format must be md or json", 400), true;
    return exportSession(s, f, res), true;
  }
  if (sub === "branch") {
    const to = Number((await readBody(req)).to_seq);
    if (!Number.isFinite(to) || to < 1 || to > s.seq) return fail(2005, "to_seq is out of range", 400), true;
    const b = newSession({ title: `${s.title ?? "Untitled"} (branch)`, project: s.project, mode: s.mode });
    b.parent_id = s.id; b.effort = s.effort;
    for (const msg of live(s).filter((x) => x.seq <= to)) { b.messages.push(structuredClone(msg)); b.seq = msg.seq; }
    if (st.files.has(s.id)) st.files.set(b.id, new Map(st.files.get(s.id)));
    return json(res, 201, pub(b)), true;
  }
  if (sub === "regenerate" || sub === "chat") {
    if (s.running) return fail(2001, "Session is busy", 409), true;
    if (sub === "chat") {
      const b = await readBody(req);
      return await stream(s, res, req, typeof b.message === "string" ? b.message : "", b, {}), true;
    }
    const lastUser = live(s).findLast((x) => x.role === "user");
    if (!lastUser) return fail(2005, "Nothing to regenerate", 400), true;
    s.messages = s.messages.filter((x) => x.seq <= lastUser.seq);
    s.seq = lastUser.seq;
    return await stream(s, res, req, lastUser.content, await readBody(req), { regen: true }), true;
  }
  if (sub === "attachments") return await attachmentRoutes(req, res, s, fail);
  if (sub === "files" || sub === "files/content") return fileRoutes(s, sub, res, url, fail);
  if (sub.startsWith("browser/")) return await browserRoutes(req, res, s, sub, url, fail);
  return false;
}

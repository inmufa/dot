// Feature routes: commands, telemetry, models, projects, plus the capability switch (/__caps).
import { st, json, readBody } from "./core.mjs";

/** Capability name for a request, or null when the route is not a switchable feature. */
export function capFor(method, p) {
  if (p === "/v1/search") return "search";
  if (p === "/v1/commands") return "commands";
  if (p === "/v1/telemetry") return "telemetry";
  if (p.startsWith("/v1/models")) return "models";
  if (p.startsWith("/v1/projects")) return "projects";
  if (p.startsWith("/v1/voice/")) return "voice";
  if (method === "PATCH" && /^\/v1\/sessions\/[^/]+$/.test(p)) return "pin";
  const m = /^\/v1\/sessions\/[^/]+\/(export|regenerate|branch|effort|attachments|files|browser)(\/|$)/.exec(p);
  return m ? m[1] : null;
}
export const CAPS = ["search", "export", "regenerate", "branch", "effort", "commands", "attachments", "files", "browser", "projects", "telemetry", "models", "pin", "voice"];

export function capsRoute(url, res) {
  const off = (url.searchParams.get("off") ?? "").split(",").map((x) => x.trim()).filter(Boolean);
  st.caps = new Set(off.filter((x) => CAPS.includes(x)));
  return json(res, 200, { off: [...st.caps], unknown: off.filter((x) => !CAPS.includes(x)), known: CAPS });
}

const C = (group, rows) => rows.map(([name, args, description, available = true, reason = null]) => ({ name, args, description, group, available, reason }));
const COMMANDS = [
  ...C("core", [["compact", "[focus]", "Summarize the conversation to free context"], ["clear", null, "Clear the transcript view"], ["effort", "[off|low|medium|high|max]", "Set the thinking effort"], ["model", "[name]", "Show or switch the model"], ["context", null, "Show context usage by tier"], ["plan", "[prompt]", "Plan before editing"], ["research", "<topic>", "Run a cited research pass"]]),
  ...C("session", [["resume", "[session]", "Open an earlier session"], ["rename", "<title>", "Rename this session"], ["export", "[md|json]", "Export this session"], ["retry", null, "Regenerate the last answer"], ["branch", "[seq]", "Branch from a message"], ["rewind", "[seq]", "Rewind to a message and restore files"], ["mode", "[plan|default|acceptEdits|auto|bypass]", "Set the permission mode"], ["stop", null, "Stop the running turn"], ["new", null, "Start a new session"], ["copy", null, "Copy the last answer"]]),
  ...C("tools", [["memory", "[query]", "Browse memory facts"], ["mcp", null, "Manage MCP servers"], ["skills", null, "List skills"], ["tasks", null, "Show the task list"], ["permissions", null, "Show permission rules"], ["hooks", null, "Show hooks"], ["agents", null, "Show subagents"], ["cron", null, "Manage scheduled prompts"], ["init", null, "Create project instructions"]]),
  ...C("extra", [["help", null, "Show all commands"], ["usage", null, "Show token usage"], ["voice", null, "Voice input", false, "Voice is not available yet: no speech model loaded"], ["theme", "[light|dark|system]", "Change the theme"], ["btw", "<question>", "Ask a side question without touching the context"]]),
];

const MODELS = [
  { id: "qwen3-coder-30b", name: "Qwen3 Coder 30B A3B", size_mb: 18200, note: "Q4_K_M, default coding model" },
  { id: "gemma-3-27b", name: "Gemma 3 27B", size_mb: 16400, note: "Q4_K_M, strong Russian and Uzbek" },
  { id: "qwen3-8b", name: "Qwen3 8B", size_mb: 5100, note: "Q4_K_M, fast and small" },
];
export const resetFeatures = () => { st.model = MODELS[0].id; st.loadingUntil = 0; st.caps = new Set(); };
export const seedProjects = () => { st.projects = [{ id: "dot", name: "Dot", instructions: "Self-hosted agent. Use uv, ruff, strict typing." }, { id: "kigo", name: "Kigo", instructions: "" }, { id: "docs", name: "Docs", instructions: "Write plain prose. No em dashes." }]; };

export async function featureRoutes(req, res, p, url, fail) {
  let m;
  if (p === "/v1/commands") return json(res, 200, COMMANDS), true;
  if (p === "/v1/telemetry") {
    const m0 = MODELS.find((x) => x.id === st.model);
    const busy = [...st.sessions.values()].filter((s) => s.running).length;
    // real backend shape (docs/api-contract.md); "loading" shows as llm_up false
    const slots = [0, 1, 2, 3].map((id) => ({ id, busy: id < busy, context_used: id === 0 ? 7200 : null, context_size: 16384 }));
    return json(res, 200, { llm_up: Date.now() >= st.loadingUntil, model: m0.name, context_size: 16384, slots, tokens_per_s: Number((34 + Math.random() * 8).toFixed(1)), prompt_tokens_per_s: null, vram_used_mb: m0.size_mb + 2400 + busy * 300, vram_total_mb: 24576, sandbox_up: true, voice_up: false, uptime_s: 100, reasoning_effort_levels: null, vision: false }), true;
  }
  if (p === "/v1/models" && req.method === "GET") {
    return json(res, 200, MODELS.map((x) => ({
      name: x.id, display_name: x.name, size_mb: x.size_mb, active: x.id === st.model, vision: x.id === "gemma-3-27b", listed: true,
      context_max: x.id === "qwen3-8b" ? 32768 : 16384, thinking: true, effort_levels: ["low", "medium", "high"], recommended_profile: null,
      switch_command: `make model M=${x.id}`,
    }))), true;
  }
  if (p === "/v1/models/select") return fail(5010, "Switch models on the host: make model M=<name>", 501), true;
  if (p === "/v1/projects" && req.method === "GET") return json(res, 200, st.projects.map((x) => ({ ...x, session_count: [...st.sessions.values()].filter((s) => s.project === x.name).length }))), true;
  if ((m = /^\/v1\/projects\/([^/]+)$/.exec(p)) && req.method === "PATCH") {
    const pr = st.projects.find((x) => x.id === m[1]);
    if (!pr) return fail(4041, "Project not found", 404), true;
    const b = await readBody(req);
    if (typeof b.name === "string" && b.name.trim()) {
      for (const s of st.sessions.values()) if (s.project === pr.name) s.project = b.name.trim();
      pr.name = b.name.trim();
    }
    if (typeof b.instructions === "string") pr.instructions = b.instructions;
    return json(res, 200, { ...pr, session_count: [...st.sessions.values()].filter((s) => s.project === pr.name).length }), true;
  }
  return false;
}

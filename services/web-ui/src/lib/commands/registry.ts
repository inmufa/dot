import type { CommandGroup, CommandInfo, SkillInfo } from "@/lib/api/types";

export interface CommandDef extends CommandInfo {
  kind: "command" | "skill";
}

const c = (name: string, args: string | null, description: string, group: CommandGroup = "core", available = true, reason: string | null = null): CommandDef => ({
  name, args, description, group, available, reason, kind: "command",
});

/** Built-in registry, used until (and merged with) `GET /v1/commands`. */
export const BUILTIN_COMMANDS: readonly CommandDef[] = [
  c("new", null, "Start a new chat"),
  c("clear", null, "Start a fresh chat in the same project, keep this one in history"),
  c("stop", null, "Stop the running turn"),
  c("retry", null, "Run the last turn again", "session"),
  c("branch", null, "Branch this chat from the last turn", "session"),
  c("rewind", null, "Open the rewind timeline", "session"),
  c("compact", "[focus]", "Summarize older context to free space", "session"),
  c("context", null, "Show what fills the context window", "session"),
  c("resume", null, "Open a previous chat", "session"),
  c("rename", "[title]", "Rename this chat", "session"),
  c("export", "[md|json]", "Download this chat", "session"),
  c("mode", "plan|default|acceptEdits|auto|bypass", "Switch permission mode"),
  c("effort", "instant|low|medium|high|max", "Set how hard the model thinks"),
  c("model", null, "Choose the model"),
  c("plan", null, "Toggle plan mode for the next message"),
  c("research", null, "Toggle research mode for the next message"),
  c("memory", null, "Open memory", "tools"),
  c("mcp", null, "Open MCP servers", "tools"),
  c("passwords", null, "Open saved logins for the browser", "tools"),
  c("skills", null, "Open skills", "tools"),
  c("tasks", null, "Open tasks", "tools"),
  c("help", null, "Show commands and shortcuts"),
  c("copy", null, "Copy the last answer", "extra"),
  c("init", null, "Create project instructions", "extra"),
  c("permissions", null, "Open permissions and the audit log", "extra"),
  c("hooks", null, "Show configured hooks", "extra"),
  c("agents", null, "Show sub-agents", "extra"),
  c("cron", null, "Open schedules", "extra"),
  c("usage", null, "Show token and speed usage", "extra"),
  c("voice", null, "Voice mode", "extra", false, "Voice is not available yet"),
  c("theme", "system|light|dark", "Change the theme", "extra"),
  c("btw", "<question>", "Ask a side question that does not enter the context", "extra"),
];

export const GROUP_ORDER: readonly CommandGroup[] = ["core", "session", "tools", "extra"];
export const GROUP_LABEL: Record<CommandGroup, string> = { core: "Commands", session: "This chat", tools: "Panels", extra: "More" };

/** Merge the backend registry over the built-ins (backend wins on text and availability), then add skills. */
export function mergeCommands(remote: CommandInfo[] | null, skills: SkillInfo[]): CommandDef[] {
  const byName = new Map<string, CommandDef>(BUILTIN_COMMANDS.map((x) => [x.name, x]));
  for (const r of remote ?? []) {
    if (typeof r.name !== "string" || !r.name) continue;
    byName.set(r.name, { ...(byName.get(r.name) ?? c(r.name, null, "")), ...r, kind: "command" });
  }
  for (const s of skills) {
    if (byName.has(s.name)) continue;
    byName.set(s.name, { name: s.name, args: null, description: s.description, group: "tools", available: s.available, reason: s.reason, kind: "skill" });
  }
  return [...byName.values()];
}

/** Active slash query: text after a leading "/" with no whitespace yet, else null. */
export function slashQuery(text: string): string | null {
  const m = /^\/([^\s/]*)$/.exec(text);
  return m ? (m[1] ?? "") : null;
}

export function filterCommands(items: CommandDef[], q: string, limit = 50): CommandDef[] {
  const needle = q.toLowerCase();
  const starts = items.filter((i) => i.name.toLowerCase().startsWith(needle));
  const rest = items.filter((i) => !i.name.toLowerCase().startsWith(needle) && (i.name.toLowerCase().includes(needle) || i.description.toLowerCase().includes(needle)));
  return [...starts, ...rest].slice(0, limit);
}

/** "/name rest" -> {name, arg}; null when the text is not a command line. */
export function parseCommandLine(text: string): { name: string; arg: string } | null {
  const m = /^\/([A-Za-z][\w.-]*)(?:\s+([\s\S]*))?$/.exec(text.trim());
  return m ? { name: m[1] ?? "", arg: (m[2] ?? "").trim() } : null;
}

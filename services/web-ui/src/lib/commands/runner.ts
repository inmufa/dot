import type { Effort } from "@/lib/api/types";
import { parseEffortArg } from "@/lib/effort/levels";
import { ALL_MODES, type PermissionMode } from "@/lib/stream/events";

export type PanelId = "skills" | "audit" | "rewind" | "tasks" | "memory" | "mcp" | "schedules" | "tools" | "settings" | "passwords";
export type CanvasTab = "preview" | "files" | "browser";

/** Everything a command can do; implemented once by the app provider (and by a fake in tests). */
export interface CommandHost {
  hasSession: boolean;
  stop(): void;
  newChat(): void;
  clearChat(): void;
  retry(): void;
  branch(): void;
  setMode(m: PermissionMode): void;
  setEffort(e: Effort): void;
  openEffort(): void;
  openModel(): void;
  openPanel(p: PanelId): void;
  openContext(): void;
  openPalette(scope?: "chats"): void;
  openHelp(): void;
  compact(focus: string): void;
  rename(title: string): void;
  exportChat(format: "md" | "json"): void;
  togglePlan(): void;
  toggleResearch(): void;
  copyLast(): void;
  setTheme(t: "system" | "light" | "dark"): void;
  /** Send the raw text to the backend (unknown or backend-only commands, /btw). */
  sendText(text: string): void;
  flash(text: string): void;
}

export type Runner = (arg: string, h: CommandHost) => void;

const RUNNERS: Record<string, Runner> = {
  new: (_a, h) => h.newChat(),
  clear: (_a, h) => h.clearChat(),
  stop: (_a, h) => h.stop(),
  retry: (_a, h) => h.retry(),
  branch: (_a, h) => h.branch(),
  rewind: (_a, h) => h.openPanel("rewind"),
  compact: (a, h) => h.compact(a),
  context: (_a, h) => h.openContext(),
  resume: (_a, h) => h.openPalette("chats"),
  rename: (a, h) => h.rename(a),
  export: (a, h) => h.exportChat(a.toLowerCase() === "json" ? "json" : "md"),
  mode: (a, h) => {
    const m = ALL_MODES.find((x) => x.toLowerCase() === a.toLowerCase());
    if (m) h.setMode(m);
    else h.flash(`Usage: /mode ${ALL_MODES.join("|")}`);
  },
  effort: (a, h) => {
    if (!a) { h.openEffort(); return; }
    const e = parseEffortArg(a);
    if (e) h.setEffort(e);
    else h.flash("Usage: /effort instant|low|medium|high|max");
  },
  model: (_a, h) => h.openModel(),
  plan: (_a, h) => h.togglePlan(),
  research: (_a, h) => h.toggleResearch(),
  memory: (_a, h) => h.openPanel("memory"),
  mcp: (_a, h) => h.openPanel("mcp"),
  passwords: (_a, h) => h.openPanel("passwords"),
  skills: (_a, h) => h.openPanel("skills"),
  tasks: (_a, h) => h.openPanel("tasks"),
  help: (_a, h) => h.openHelp(),
  copy: (_a, h) => h.copyLast(),
  permissions: (_a, h) => h.openPanel("audit"),
  cron: (_a, h) => h.openPanel("schedules"),
  theme: (a, h) => {
    const t = a.toLowerCase();
    if (t === "system" || t === "light" || t === "dark") h.setTheme(t);
    else h.flash("Usage: /theme system|light|dark");
  },
  voice: (_a, h) => h.flash("Voice is not available yet."),
};

/** Names with a local handler (the rest go to the backend as text). */
export const LOCAL_COMMANDS: readonly string[] = Object.keys(RUNNERS);

/** Run a parsed command. Returns false when it is not a local command (caller sends it as text). */
export function runCommand(name: string, arg: string, host: CommandHost, rawText: string): boolean {
  const r = RUNNERS[name.toLowerCase()];
  if (!r) {
    if (!host.hasSession) host.flash("Open a chat first.");
    else host.sendText(rawText);
    return false;
  }
  r(arg, host);
  return true;
}

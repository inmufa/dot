import type { SkillInfo } from "./api/client";

export interface SlashItem {
  name: string;
  hint: string;
  kind: "builtin" | "skill";
  available: boolean;
}

export const BUILTINS: SlashItem[] = [
  { name: "mode", hint: "Switch permission mode: /mode plan|default|acceptEdits|auto|bypass", kind: "builtin", available: true },
  { name: "stop", hint: "Stop the running turn", kind: "builtin", available: true },
  { name: "rewind", hint: "Open the rewind timeline", kind: "builtin", available: true },
  { name: "new", hint: "Start a new session", kind: "builtin", available: true },
];

export function slashItems(skills: SkillInfo[]): SlashItem[] {
  const names = new Set(BUILTINS.map((b) => b.name));
  const fromSkills = skills
    .filter((s) => !names.has(s.name))
    .map<SlashItem>((s) => ({ name: s.name, hint: s.description, kind: "skill", available: s.available }));
  return [...BUILTINS, ...fromSkills];
}

/** Active slash query: text after a leading "/" with no whitespace yet, else null. */
export function slashQuery(text: string): string | null {
  const m = /^\/([^\s/]*)$/.exec(text);
  return m ? (m[1] ?? "") : null;
}

export function filterSlash(items: SlashItem[], q: string): SlashItem[] {
  const needle = q.toLowerCase();
  const starts = items.filter((i) => i.name.toLowerCase().startsWith(needle));
  const rest = items.filter((i) => !i.name.toLowerCase().startsWith(needle) && i.name.toLowerCase().includes(needle));
  return [...starts, ...rest].slice(0, 50);
}

export type Command =
  | { type: "mode"; arg: string }
  | { type: "stop" }
  | { type: "rewind" }
  | { type: "new" }
  | null;

export function parseBuiltin(text: string): Command {
  const m = /^\/(mode|stop|rewind|new)(?:\s+(.*))?$/.exec(text.trim());
  if (!m) return null;
  const name = m[1];
  if (name === "mode") return { type: "mode", arg: (m[2] ?? "").trim() };
  return { type: name as "stop" | "rewind" | "new" };
}

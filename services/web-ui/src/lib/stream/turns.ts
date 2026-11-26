import type { Item } from "./reducer";

type UserItem = Extract<Item, { kind: "user" }>;

export interface ActivityGroup {
  kind: "activity";
  id: string;
  items: Item[];
  /** Tool calls and sub-agents in the group. */
  steps: number;
  /** Wall time in ms (null when unknown, e.g. history without timestamps). */
  ms: number | null;
  /** True while the turn this group belongs to is still running. */
  live: boolean;
  /** Short label of what is happening now (last running tool name). */
  current: string | null;
  needsYou: boolean;
}
export type TurnPart = ActivityGroup | { kind: "item"; item: Item };
export interface Turn {
  id: string;
  user: UserItem | null;
  parts: TurnPart[];
  live: boolean;
}

/** Tools whose output is shown as a dedicated block, not as an activity step. */
const HIDDEN_TOOLS = new Set(["Present", "AskUserQuestion", "Ask", "ExitPlanMode"]);

export const isStep = (i: Item): boolean => (i.kind === "tool" && !HIDDEN_TOOLS.has(i.name)) || i.kind === "subagent";

/** Activity content: steps, plus assistant text/thinking that comes before the last step of the turn. */
function inGroup(i: Item, idx: number, lastStep: number): boolean {
  if (isStep(i)) return true;
  return i.kind === "assistant" && idx < lastStep;
}

function span(items: Item[], live: boolean, now: number): number | null {
  const times = items.flatMap((i) => [i.kind === "tool" ? i.endedAt : undefined, "at" in i ? i.at : undefined]).filter((x): x is number => typeof x === "number");
  if (times.length < 2 && !live) return null;
  const start = Math.min(...times);
  const end = live ? now : Math.max(...times);
  return Number.isFinite(start) && end >= start ? end - start : null;
}

function buildTurn(user: UserItem | null, items: Item[], live: boolean, now: number): Turn {
  const lastStep = items.reduce((a, it, i) => (isStep(it) ? i : a), -1);
  const parts: TurnPart[] = [];
  let group: ActivityGroup | null = null;
  items.forEach((it, i) => {
    if (it.kind === "tool" && HIDDEN_TOOLS.has(it.name)) return;
    if (inGroup(it, i, lastStep)) {
      if (!group) {
        group = { kind: "activity", id: `g:${it.id}`, items: [], steps: 0, ms: null, live, current: null, needsYou: false };
        parts.push(group);
      }
      group.items.push(it);
      return;
    }
    parts.push({ kind: "item", item: it });
  });
  for (const p of parts) {
    if (p.kind !== "activity") continue;
    p.steps = p.items.filter(isStep).length;
    const startAt = user?.at;
    const all = startAt !== undefined ? [{ kind: "user", id: "", text: "", at: startAt } as Item, ...p.items] : p.items;
    p.ms = span(all, live, now);
    const running = [...p.items].reverse().find((x) => x.kind === "tool" && (x.status === "running" || x.status === "awaiting"));
    p.current = running?.kind === "tool" ? running.name : null;
    p.needsYou = p.items.some((x) => x.kind === "tool" && x.status === "awaiting");
  }
  return { id: user?.id ?? `t:${items[0]?.id ?? "0"}`, user, parts, live };
}

/**
 * Split a flat item list into turns (a user message and everything until the next one) and
 * fold the tool calls and sub-agents of each turn into one collapsible activity group.
 */
export function groupTurns(items: Item[], running: boolean, now: number = Date.now()): Turn[] {
  const turns: Turn[] = [];
  let user: UserItem | null = null;
  let cur: Item[] = [];
  const flush = (last: boolean) => {
    if (user || cur.length) turns.push(buildTurn(user, cur, last && running, now));
  };
  for (const it of items) {
    if (it.kind === "user") {
      flush(false);
      user = it;
      cur = [];
    } else cur.push(it);
  }
  flush(true);
  return turns;
}

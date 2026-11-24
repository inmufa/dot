import type { Item } from "./reducer";

export interface WireMessage {
  seq: number;
  role: string;
  content: string;
  tool_calls?: Record<string, unknown>[] | null;
  tool_call_id?: string | null;
  rewound?: boolean;
  tainted?: boolean;
}

type Rec = Record<string, unknown>;

function callParts(c: Rec): { id: string; name: string; args: Record<string, unknown> } {
  const fn = (typeof c.function === "object" && c.function ? c.function : c) as Rec;
  let args: unknown = fn.arguments;
  if (typeof args === "string") {
    try {
      args = JSON.parse(args);
    } catch {
      args = { raw: args };
    }
  }
  const id = typeof c.id === "string" ? c.id : typeof c.call_id === "string" ? c.call_id : "";
  return {
    id,
    name: typeof fn.name === "string" ? fn.name : "tool",
    args: typeof args === "object" && args && !Array.isArray(args) ? (args as Rec) : {},
  };
}

/** Rebuild transcript items from stored messages (thinking is not stored). */
export function itemsFromMessages(msgs: WireMessage[]): Item[] {
  const out: Item[] = [];
  const tools = new Map<string, Extract<Item, { kind: "tool" }>>();
  for (const m of msgs) {
    if (m.rewound) continue;
    if (m.role === "user") out.push({ kind: "user", id: `m${m.seq}`, text: m.content });
    else if (m.role === "plan") out.push({ kind: "plan", id: `m${m.seq}`, text: m.content });
    else if (m.role === "summary") out.push({ kind: "compaction", id: `m${m.seq}`, before: 0, after: 0, stages: ["summary"], summary: m.content });
    else if (m.role === "assistant") {
      if (m.content) out.push({ kind: "assistant", id: `m${m.seq}`, text: m.content, thinking: "", streaming: false });
      (m.tool_calls ?? []).forEach((c, i) => {
        const p = callParts(c);
        const id = p.id || `m${m.seq}-${i}`;
        const t: Extract<Item, { kind: "tool" }> = { kind: "tool", id, name: p.name, args: p.args, status: "done" };
        tools.set(id, t);
        out.push(t);
      });
    } else if (m.role === "tool" && m.tool_call_id) {
      const t = tools.get(m.tool_call_id);
      if (t) {
        t.output = m.content;
        if (m.tainted) t.tainted = true;
        if (/^Denied \(error \d+\)/.test(m.content)) t.status = "error";
      }
    }
  }
  return out;
}

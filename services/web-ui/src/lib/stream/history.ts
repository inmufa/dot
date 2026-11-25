import type { Item, UserAtt } from "./reducer";

export interface WireMessage {
  seq: number;
  role: string;
  content: string;
  tool_calls?: Record<string, unknown>[] | null;
  tool_call_id?: string | null;
  rewound?: boolean;
  tainted?: boolean;
  meta?: Record<string, unknown> | null;
  created_at?: string;
}

type Rec = Record<string, unknown>;

function attsFromMeta(meta: WireMessage["meta"]): UserAtt[] {
  const raw = meta?.attachments;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((a: unknown) => {
    const r = a as Rec;
    const kind = r.kind === "image" || r.kind === "text" ? r.kind : "doc";
    return typeof r.id === "string" ? [{ id: r.id, name: typeof r.name === "string" ? r.name : "file", kind }] : [];
  });
}

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
    const at = m.created_at ? Date.parse(m.created_at) || undefined : undefined;
    if (m.role === "user") {
      const atts = attsFromMeta(m.meta);
      out.push({ kind: "user", id: `m${m.seq}`, text: m.content, seq: m.seq, ...(at ? { at } : {}), ...(atts.length ? { atts } : {}) });
    }
    else if (m.role === "plan") out.push({ kind: "plan", id: `m${m.seq}`, text: m.content });
    else if (m.role === "summary") out.push({ kind: "compaction", id: `m${m.seq}`, before: 0, after: 0, stages: ["summary"], summary: m.content });
    else if (m.role === "assistant") {
      if (m.content) out.push({ kind: "assistant", id: `m${m.seq}`, text: m.content, thinking: "", streaming: false, seq: m.seq, ...(at ? { at } : {}) });
      (m.tool_calls ?? []).forEach((c, i) => {
        const p = callParts(c);
        const id = p.id || `m${m.seq}-${i}`;
        if (p.name === "Present" && typeof p.args.kind === "string") {
          out.push({ kind: "widget", id: `w:${id}`, wkind: p.args.kind, title: typeof p.args.title === "string" ? p.args.title : null, props: p.args.props });
          return;
        }
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
  const sources = msgs.flatMap((m) => (Array.isArray(m.meta?.sources) ? [{ seq: m.seq, items: m.meta.sources as never[] }] : []));
  for (const { seq, items } of sources) {
    const at = out.findIndex((i) => i.id === `m${seq}`);
    const entry: Item = { kind: "sources", id: `src${seq}`, items };
    if (at >= 0) out.splice(at + 1, 0, entry);
    else out.push(entry);
  }
  return out;
}

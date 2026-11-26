import type { Approval, ChatAction, ChatState, DotPhase, Item, SubagentState } from "./chatTypes";
import type { StreamEvent } from "./events";
import { initialChat, STEP_CAP } from "./chatTypes";

export { STEP_CAP, initialChat } from "./chatTypes";
export type {
  Approval, ChatAction, ChatState, DotPhase, Item, NoticeLevel, QueuedMessage, QuestionStatus, SubagentState, ToolStatus, UserAtt,
} from "./chatTypes";

export function phaseOf(s: ChatState): DotPhase {
  if (s.approval || s.question) return "waiting";
  return s.running ? "thinking" : "idle";
}

const STOP_NOTES: Record<string, string> = {
  cancelled: "Stopped.",
  max_iterations: "Stopped: reached the step limit for one turn.",
  approval_timeout: "Stopped: the approval request timed out.",
  blocked: "Blocked by a prompt hook.",
};

type NewItem = Item extends infer T ? (T extends Item ? Omit<T, "id"> & { id?: string } : never) : never;

function push(s: ChatState, item: NewItem, now?: number): ChatState {
  const id = item.id ?? `i${s.seq + 1}`;
  const at = now !== undefined && (item as { at?: number }).at === undefined ? { at: now } : {};
  return { ...s, seq: s.seq + 1, items: [...s.items, { ...at, ...item, id }] };
}

function replaceLast(s: ChatState, fn: (it: Item) => Item): ChatState {
  const items = s.items.slice();
  const last = items.length - 1;
  const it = items[last];
  if (!it) return s;
  items[last] = fn(it);
  return { ...s, items };
}

/** Close the thinking timer of an assistant item once something other than thinking arrives. */
function endThink(it: Extract<Item, { kind: "assistant" }>, now: number): Extract<Item, { kind: "assistant" }> {
  return it.thinkStartedAt !== undefined && it.thinkMs === undefined ? { ...it, thinkMs: Math.max(0, now - it.thinkStartedAt) } : it;
}

function onToken(s: ChatState, text: string, thinking: boolean, now: number): ChatState {
  const last = s.items[s.items.length - 1];
  if (last?.kind === "assistant" && last.streaming) {
    return replaceLast(s, (it) => {
      if (it.kind !== "assistant") return it;
      if (thinking) return { ...it, thinking: it.thinking + text, thinkStartedAt: it.thinkStartedAt ?? now };
      return { ...endThink(it, now), text: it.text + text };
    });
  }
  return push(s, {
    kind: "assistant",
    text: thinking ? "" : text,
    thinking: thinking ? text : "",
    streaming: true,
    at: now,
    ...(thinking ? { thinkStartedAt: now } : {}),
  }, now);
}

function patchTool(s: ChatState, id: string, patch: Partial<Extract<Item, { kind: "tool" }>>): ChatState {
  return {
    ...s,
    items: s.items.map((it) => (it.kind === "tool" && it.id === id ? { ...it, ...patch } : it)),
  };
}

function closeStreaming(s: ChatState, now = Date.now()): ChatState {
  if (!s.items.some((i) => i.kind === "assistant" && i.streaming)) return s;
  return {
    ...s,
    items: s.items.map((i) => (i.kind === "assistant" && i.streaming ? { ...endThink(i, now), streaming: false } : i)),
  };
}

const FINISH: Record<string, SubagentState> = { ok: "done", error: "error", cancelled: "cancelled" };

function onSubagent(s: ChatState, e: Extract<StreamEvent, { type: "subagent" }>, now: number): ChatState {
  const id = `sub:${e.label}`;
  const known = s.items.some((i) => i.id === id);
  const state: SubagentState = e.status === "queued" ? "queued" : e.status === "finished" ? (FINISH[e.detail] ?? "done") : "running";
  if (!known) return push(s, { kind: "subagent", id, label: e.label, type: e.subagent_type, status: state, steps: e.status === "step" && e.detail ? [e.detail] : [], stepCount: e.status === "step" ? 1 : 0 }, now);
  return {
    ...s,
    items: s.items.map((i) => {
      if (i.kind !== "subagent" || i.id !== id) return i;
      const step = e.status === "step";
      return { ...i, status: state, steps: step && e.detail ? [...i.steps, e.detail].slice(-STEP_CAP) : i.steps, stepCount: i.stepCount + (step ? 1 : 0) };
    }),
  };
}

/** Anything still open when the turn ends can no longer be answered. */
function settle(s: ChatState): ChatState {
  const items = s.items.map((i): Item => {
    if (i.kind === "question" && i.status === "open") return { ...i, status: "closed" };
    if (i.kind === "subagent" && (i.status === "running" || i.status === "queued")) return { ...i, status: "cancelled" };
    return i;
  });
  return { ...s, items, question: null };
}

export function applyEvent(s: ChatState, e: StreamEvent, now: number): ChatState {
  switch (e.type) {
    case "token":
      return onToken(s, e.text, e.thinking, now);
    case "tool_draft":
      // a tool call being written means the thinking is over
      return { ...s, items: s.items.map((i) => (i.kind === "assistant" && i.streaming ? endThink(i, now) : i)), draft: { name: e.name, target: e.target, chars: e.chars } };
    case "tool_call": {
      const closed = { ...closeStreaming(s, now), draft: null };
      if (closed.items.some((i) => i.kind === "tool" && i.id === e.invocation.call_id)) return closed;
      return push(closed, { kind: "tool", id: e.invocation.call_id, name: e.invocation.name, args: e.invocation.arguments, status: "running" }, now);
    }
    case "approval_required": {
      const n = patchTool(closeStreaming(s, now), e.invocation.call_id, { status: "awaiting" });
      const ap: Approval = { id: e.approval_id, invocation: e.invocation, diff: e.diff, verdict: e.verdict, subagent: e.subagent, at: now };
      return { ...n, approval: ap };
    }
    case "tool_result": {
      const r = e.result;
      const n = patchTool(s, r.call_id, { status: r.is_error ? "error" : "done", output: r.output, tainted: r.tainted, spillPath: r.spill_path, endedAt: now });
      const done = n.approval?.invocation.call_id === r.call_id ? { ...n, approval: null } : n;
      const call = done.items.find((i) => i.kind === "tool" && i.id === r.call_id);
      const plan = call?.kind === "tool" && call.name === "ExitPlanMode" ? call.args.plan : undefined;
      return !r.is_error && typeof plan === "string" && plan ? push(done, { kind: "plan", text: plan }, now) : done;
    }
    case "question": {
      const n = push(closeStreaming(s, now), { kind: "question", id: e.question_id, text: e.question, options: e.options, multi: e.multi_select, fields: e.fields, status: "open", at: now });
      return { ...n, question: e.question_id };
    }
    case "widget":
      return push(closeStreaming(s, now), { kind: "widget", id: e.call_id ? `w:${e.call_id}` : undefined, wkind: e.kind, title: e.title, props: e.props }, now);
    case "sources":
      return push(s, { kind: "sources", items: e.items }, now);
    case "subagent":
      return onSubagent(closeStreaming(s, now), e, now);
    case "compaction":
      return push(s, { kind: "compaction", before: e.tokens_before, after: e.tokens_after, stages: e.stages }, now);
    case "injected": {
      const at = s.queue.findIndex((q) => q.text === e.text);
      const queue = at < 0 ? s.queue : s.queue.filter((_, i) => i !== at);
      return push({ ...closeStreaming(s, now), queue }, { kind: "user", text: e.text }, now);
    }
    case "usage":
      return { ...s, usage: { tokens: e.context_tokens, limit: e.context_limit } };
    case "error":
      return push(closeStreaming(s, now), { kind: "notice", level: "error", code: e.code, text: e.message }, now);
    case "done": {
      const n = settle({ ...closeStreaming(s, now), running: false, approval: null, turnStartedAt: null });
      // cancelled with a queue: send-now interrupted it, the queue drains next
      const note = e.stop_reason === "cancelled" && s.queue.length > 0 ? "Interrupted - sending the next message." : STOP_NOTES[e.stop_reason];
      return note ? push(n, { kind: "notice", level: "info", text: note }, now) : n;
    }
  }
}

export function chatReducer(s: ChatState, a: ChatAction): ChatState {
  switch (a.type) {
    case "send": {
      const now = a.now ?? Date.now();
      return push({ ...s, running: true, turnStartedAt: now }, { kind: "user", text: a.text, ...(a.atts?.length ? { atts: a.atts } : {}) }, now);
    }
    case "regenerate": {
      const lastUser = s.items.map((i) => i.kind).lastIndexOf("user");
      return lastUser < 0 ? s : { ...s, running: true, turnStartedAt: a.now, items: s.items.slice(0, lastUser + 1) };
    }
    case "enqueue":
      return { ...s, queue: [...s.queue, { id: a.id, text: a.text }] };
    case "dequeue":
      return { ...s, queue: s.queue.filter((q) => q.id !== a.id) };
    case "event":
      return applyEvent(s, a.event, a.now);
    case "load":
      return { ...initialChat, items: a.items, seq: a.items.length + 1000, queue: s.queue };
    case "approval_sent":
      return s.approval
        ? { ...patchTool(s, s.approval.invocation.call_id, { status: "running" }), approval: null }
        : s;
    case "question_sent":
      return { ...s, question: s.question === a.id ? null : s.question, items: s.items.map((i) => (i.kind === "question" && i.id === a.id ? { ...i, status: "answered", answer: a.answer } : i)) };
    case "question_expired":
      return { ...s, question: s.question === a.id ? null : s.question, items: s.items.map((i) => (i.kind === "question" && i.id === a.id && i.status === "open" ? { ...i, status: "expired" } : i)) };
    case "end": {
      let n: ChatState = settle({ ...closeStreaming(s), running: false, approval: null, turnStartedAt: null, draft: null });
      if (a.error) n = push(n, { kind: "notice", level: "error", code: a.error.code, text: a.error.text });
      // A turn that ended with tools still open: mark them so the UI stops spinning.
      return { ...n, items: n.items.map((i) => (i.kind === "tool" && (i.status === "running" || i.status === "awaiting") ? { ...i, status: "error" as const, output: i.output ?? "No result." } : i)) };
    }
  }
}

import type { ClassifierVerdict, QuestionOption, StreamEvent, ToolInvocation } from "./events";

export type ToolStatus = "running" | "awaiting" | "done" | "error";
export type NoticeLevel = "error" | "info";

export type Item =
  | { kind: "user"; id: string; text: string }
  | { kind: "assistant"; id: string; text: string; thinking: string; streaming: boolean }
  | {
      kind: "tool";
      id: string;
      name: string;
      args: Record<string, unknown>;
      status: ToolStatus;
      output?: string;
      tainted?: boolean;
      spillPath?: string | null;
    }
  | { kind: "notice"; id: string; level: NoticeLevel; code?: number; text: string }
  | {
      kind: "question";
      id: string;
      text: string;
      options: QuestionOption[];
      multi: boolean;
      status: QuestionStatus;
      answer?: string;
      at: number;
    }
  | { kind: "subagent"; id: string; label: string; type: string; status: SubagentState; steps: string[]; stepCount: number }
  | { kind: "compaction"; id: string; before: number; after: number; stages: string[]; summary?: string }
  | { kind: "plan"; id: string; text: string };

export type QuestionStatus = "open" | "answered" | "expired" | "closed";
export type SubagentState = "queued" | "running" | "done" | "error" | "cancelled";
export const STEP_CAP = 40;

export interface Approval {
  id: string;
  invocation: ToolInvocation;
  diff: string | null;
  verdict: ClassifierVerdict | null;
  at: number;
  subagent: string | null;
}

export type DotPhase = "idle" | "thinking" | "waiting";

export interface ChatState {
  items: Item[];
  running: boolean;
  approval: Approval | null;
  /** Id of the question item the turn is blocked on. */
  question: string | null;
  usage: { tokens: number; limit: number } | null;
  seq: number;
}

export const initialChat: ChatState = { items: [], running: false, approval: null, question: null, usage: null, seq: 0 };

export type ChatAction =
  | { type: "send"; text: string }
  | { type: "event"; event: StreamEvent; now: number }
  | { type: "load"; items: Item[] }
  | { type: "end"; error?: { code?: number; text: string } }
  | { type: "approval_sent" }
  | { type: "question_sent"; id: string; answer: string }
  | { type: "question_expired"; id: string };

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

function push(s: ChatState, item: NewItem): ChatState {
  const id = item.id ?? `i${s.seq + 1}`;
  return { ...s, seq: s.seq + 1, items: [...s.items, { ...item, id }] };
}

function replaceLast(s: ChatState, fn: (it: Item) => Item): ChatState {
  const items = s.items.slice();
  const last = items.length - 1;
  const it = items[last];
  if (!it) return s;
  items[last] = fn(it);
  return { ...s, items };
}

function onToken(s: ChatState, text: string, thinking: boolean): ChatState {
  const last = s.items[s.items.length - 1];
  if (last?.kind === "assistant" && last.streaming) {
    return replaceLast(s, (it) =>
      it.kind === "assistant"
        ? { ...it, text: thinking ? it.text : it.text + text, thinking: thinking ? it.thinking + text : it.thinking }
        : it,
    );
  }
  return push(s, {
    kind: "assistant",
    text: thinking ? "" : text,
    thinking: thinking ? text : "",
    streaming: true,
  });
}

function patchTool(s: ChatState, id: string, patch: Partial<Extract<Item, { kind: "tool" }>>): ChatState {
  return {
    ...s,
    items: s.items.map((it) => (it.kind === "tool" && it.id === id ? { ...it, ...patch } : it)),
  };
}

function closeStreaming(s: ChatState): ChatState {
  if (!s.items.some((i) => i.kind === "assistant" && i.streaming)) return s;
  return {
    ...s,
    items: s.items.map((i) => (i.kind === "assistant" && i.streaming ? { ...i, streaming: false } : i)),
  };
}

const FINISH: Record<string, SubagentState> = { ok: "done", error: "error", cancelled: "cancelled" };

function onSubagent(s: ChatState, e: Extract<StreamEvent, { type: "subagent" }>): ChatState {
  const id = `sub:${e.label}`;
  const known = s.items.some((i) => i.id === id);
  const state: SubagentState = e.status === "queued" ? "queued" : e.status === "finished" ? (FINISH[e.detail] ?? "done") : "running";
  if (!known) return push(s, { kind: "subagent", id, label: e.label, type: e.subagent_type, status: state, steps: e.status === "step" && e.detail ? [e.detail] : [], stepCount: e.status === "step" ? 1 : 0 });
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
      return onToken(s, e.text, e.thinking);
    case "tool_call": {
      const closed = closeStreaming(s);
      if (closed.items.some((i) => i.kind === "tool" && i.id === e.invocation.call_id)) return closed;
      return push(closed, {
        kind: "tool",
        id: e.invocation.call_id,
        name: e.invocation.name,
        args: e.invocation.arguments,
        status: "running",
      });
    }
    case "approval_required": {
      const n = patchTool(closeStreaming(s), e.invocation.call_id, { status: "awaiting" });
      const ap: Approval = {
        id: e.approval_id,
        invocation: e.invocation,
        diff: e.diff,
        verdict: e.verdict,
        subagent: e.subagent,
        at: now,
      };
      return { ...n, approval: ap };
    }
    case "tool_result": {
      const r = e.result;
      const n = patchTool(s, r.call_id, {
        status: r.is_error ? "error" : "done",
        output: r.output,
        tainted: r.tainted,
        spillPath: r.spill_path,
      });
      const done = n.approval?.invocation.call_id === r.call_id ? { ...n, approval: null } : n;
      const call = done.items.find((i) => i.kind === "tool" && i.id === r.call_id);
      const plan = call?.kind === "tool" && call.name === "ExitPlanMode" ? call.args.plan : undefined;
      return !r.is_error && typeof plan === "string" && plan ? push(done, { kind: "plan", text: plan }) : done;
    }
    case "question": {
      const n = push(closeStreaming(s), { kind: "question", id: e.question_id, text: e.question, options: e.options, multi: e.multi_select, status: "open", at: now });
      return { ...n, question: e.question_id };
    }
    case "subagent":
      return onSubagent(closeStreaming(s), e);
    case "compaction":
      return push(s, { kind: "compaction", before: e.tokens_before, after: e.tokens_after, stages: e.stages });
    case "usage":
      return { ...s, usage: { tokens: e.context_tokens, limit: e.context_limit } };
    case "error":
      return push(closeStreaming(s), { kind: "notice", level: "error", code: e.code, text: e.message });
    case "done": {
      const n = settle({ ...closeStreaming(s), running: false, approval: null });
      const note = STOP_NOTES[e.stop_reason];
      return note ? push(n, { kind: "notice", level: "info", text: note }) : n;
    }
  }
}

export function chatReducer(s: ChatState, a: ChatAction): ChatState {
  switch (a.type) {
    case "send":
      return push({ ...s, running: true }, { kind: "user", text: a.text });
    case "event":
      return applyEvent(s, a.event, a.now);
    case "load":
      return { ...initialChat, items: a.items, seq: a.items.length + 1000 };
    case "approval_sent":
      return s.approval
        ? { ...patchTool(s, s.approval.invocation.call_id, { status: "running" }), approval: null }
        : s;
    case "question_sent":
      return { ...s, question: s.question === a.id ? null : s.question, items: s.items.map((i) => (i.kind === "question" && i.id === a.id ? { ...i, status: "answered", answer: a.answer } : i)) };
    case "question_expired":
      return { ...s, question: s.question === a.id ? null : s.question, items: s.items.map((i) => (i.kind === "question" && i.id === a.id && i.status === "open" ? { ...i, status: "expired" } : i)) };
    case "end": {
      let n: ChatState = settle({ ...closeStreaming(s), running: false, approval: null });
      if (a.error) n = push(n, { kind: "notice", level: "error", code: a.error.code, text: a.error.text });
      // A turn that ended with tools still open: mark them so the UI stops spinning.
      return { ...n, items: n.items.map((i) => (i.kind === "tool" && (i.status === "running" || i.status === "awaiting") ? { ...i, status: "error" as const, output: i.output ?? "No result." } : i)) };
    }
  }
}

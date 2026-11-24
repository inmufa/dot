// Mirror of packages/dot-contracts events + DTOs (hand-written, validated at the edge).
export type PermissionMode = "plan" | "default" | "acceptEdits" | "auto" | "bypass";
export const MODES: readonly PermissionMode[] = ["plan", "default", "acceptEdits", "auto", "bypass"];

export type Decision = "allow" | "ask" | "deny";
export interface ToolInvocation {
  call_id: string;
  name: string;
  arguments: Record<string, unknown>;
}
export interface ToolResult {
  call_id: string;
  output: string;
  is_error: boolean;
  tainted: boolean;
  spill_path: string | null;
}
export interface ClassifierVerdict {
  decision: Decision;
  stage: string;
  reason: string;
}

export interface QuestionOption {
  label: string;
  description: string;
}
export type SubagentStatus = "queued" | "started" | "step" | "finished";

export type StreamEvent =
  | { type: "token"; text: string; thinking: boolean }
  | { type: "tool_call"; invocation: ToolInvocation }
  | { type: "tool_result"; result: ToolResult }
  | {
      type: "approval_required";
      approval_id: string;
      invocation: ToolInvocation;
      diff: string | null;
      verdict: ClassifierVerdict | null;
      subagent: string | null;
    }
  | { type: "question"; question_id: string; question: string; options: QuestionOption[]; multi_select: boolean }
  | { type: "subagent"; label: string; subagent_type: string; status: SubagentStatus; detail: string }
  | { type: "compaction"; tokens_before: number; tokens_after: number; stages: string[] }
  | { type: "usage"; context_tokens: number; context_limit: number }
  | { type: "done"; stop_reason: string }
  | { type: "error"; code: number; message: string };

type Rec = Record<string, unknown>;
const isRec = (v: unknown): v is Rec => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown, d = ""): string => (typeof v === "string" ? v : d);
const num = (v: unknown, d = 0): number => (typeof v === "number" && Number.isFinite(v) ? v : d);

function invocation(v: unknown): ToolInvocation | null {
  if (!isRec(v) || typeof v.call_id !== "string" || typeof v.name !== "string") return null;
  return { call_id: v.call_id, name: v.name, arguments: isRec(v.arguments) ? v.arguments : {} };
}

function verdict(v: unknown): ClassifierVerdict | null {
  if (!isRec(v)) return null;
  const d = v.decision;
  if (d !== "allow" && d !== "ask" && d !== "deny") return null;
  return { decision: d, stage: str(v.stage), reason: str(v.reason) };
}

/** Validate one decoded SSE payload; unknown or malformed events return null. */
export function parseEvent(v: unknown): StreamEvent | null {
  if (!isRec(v)) return null;
  switch (v.type) {
    case "token":
      return { type: "token", text: str(v.text), thinking: v.thinking === true };
    case "tool_call": {
      const inv = invocation(v.invocation);
      return inv ? { type: "tool_call", invocation: inv } : null;
    }
    case "tool_result": {
      const r = v.result;
      if (!isRec(r) || typeof r.call_id !== "string") return null;
      return {
        type: "tool_result",
        result: {
          call_id: r.call_id,
          output: str(r.output),
          is_error: r.is_error === true,
          tainted: r.tainted === true,
          spill_path: typeof r.spill_path === "string" ? r.spill_path : null,
        },
      };
    }
    case "approval_required": {
      const inv = invocation(v.invocation);
      if (!inv || typeof v.approval_id !== "string") return null;
      return {
        type: "approval_required",
        approval_id: v.approval_id,
        invocation: inv,
        diff: typeof v.diff === "string" ? v.diff : null,
        verdict: verdict(v.verdict),
        subagent: typeof v.subagent === "string" && v.subagent ? v.subagent : null,
      };
    }
    case "question": {
      if (typeof v.question_id !== "string" || !Array.isArray(v.options)) return null;
      const options = v.options.flatMap((o): QuestionOption[] =>
        isRec(o) && typeof o.label === "string" ? [{ label: o.label, description: str(o.description) }] : [],
      );
      if (options.length === 0) return null;
      return { type: "question", question_id: v.question_id, question: str(v.question), options: options.slice(0, 4), multi_select: v.multi_select === true };
    }
    case "subagent": {
      const st = v.status;
      if (st !== "queued" && st !== "started" && st !== "step" && st !== "finished") return null;
      if (typeof v.label !== "string") return null;
      return { type: "subagent", label: v.label, subagent_type: str(v.subagent_type, "agent"), status: st, detail: str(v.detail) };
    }
    case "compaction":
      return {
        type: "compaction",
        tokens_before: num(v.tokens_before),
        tokens_after: num(v.tokens_after),
        stages: Array.isArray(v.stages) ? v.stages.filter((x): x is string => typeof x === "string") : [],
      };
    case "usage":
      return { type: "usage", context_tokens: num(v.context_tokens), context_limit: num(v.context_limit) };
    case "done":
      return { type: "done", stop_reason: str(v.stop_reason, "end_turn") };
    case "error":
      return { type: "error", code: num(v.code, 1000), message: str(v.message) };
    default:
      return null;
  }
}

export function parseEventJson(data: string): StreamEvent | null {
  try {
    return parseEvent(JSON.parse(data));
  } catch {
    return null;
  }
}

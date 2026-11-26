import type { SourceItem } from "../api/types";
import type { ClassifierVerdict, QuestionOption, StreamEvent, ToolInvocation } from "./events";

export type ToolStatus = "running" | "awaiting" | "done" | "error";
export type NoticeLevel = "error" | "info";

export type Item =
  | { kind: "user"; id: string; text: string; at?: number; seq?: number; queued?: boolean; atts?: UserAtt[] }
  | {
      kind: "assistant";
      id: string;
      text: string;
      thinking: string;
      streaming: boolean;
      at?: number;
      seq?: number;
      /** Wall time of the thinking phase, set once the first answer token or a tool call arrives. */
      thinkStartedAt?: number;
      thinkMs?: number;
    }
  | {
      kind: "tool";
      id: string;
      at?: number;
      endedAt?: number;
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
      fields?: unknown[] | null;
      status: QuestionStatus;
      answer?: string;
      at: number;
    }
  | { kind: "subagent"; id: string; label: string; type: string; status: SubagentState; steps: string[]; stepCount: number }
  | { kind: "compaction"; id: string; before: number; after: number; stages: string[]; summary?: string }
  | { kind: "plan"; id: string; text: string }
  | { kind: "widget"; id: string; wkind: string; title: string | null; props: unknown; at?: number }
  | { kind: "sources"; id: string; items: SourceItem[] };

export interface QueuedMessage {
  id: string;
  text: string;
}

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
  /** Messages typed while a turn runs; sent one by one when it ends. */
  queue: QueuedMessage[];
  turnStartedAt: number | null;
  /** A tool call the model is still writing (no visible text streams meanwhile). */
  draft: { name: string; target: string; chars: number } | null;
}

export const initialChat: ChatState = { items: [], running: false, approval: null, question: null, usage: null, seq: 0, queue: [], turnStartedAt: null, draft: null };

export type ChatAction =
  | { type: "send"; text: string; now?: number; atts?: UserAtt[] }
  | { type: "regenerate"; now: number }
  | { type: "enqueue"; id: string; text: string }
  | { type: "dequeue"; id: string }
  | { type: "event"; event: StreamEvent; now: number }
  | { type: "load"; items: Item[] }
  | { type: "end"; error?: { code?: number; text: string } }
  | { type: "approval_sent" }
  | { type: "question_sent"; id: string; answer: string }
  | { type: "question_expired"; id: string };

/** Attachment shown on a sent message (thumbnail for images, tile for files). */
export interface UserAtt {
  id: string;
  name: string;
  kind: "image" | "doc" | "text";
}

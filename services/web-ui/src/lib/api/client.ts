import { DotApiError, describeError } from "./errors";
import type { PermissionMode } from "../stream/events";
import type { AuditPage, CompactOut, ContextInfo, MemoryDraft, MemoryFact, McpServer, RewindOut, ScheduleInfo, SessionInfo, SkillInfo, TaskInfo, ToolInfo } from "./types";
import type { WireMessage } from "../stream/history";

export type * from "./types";

export const BASE = "/api/dot";

let lang = "en";
export const setApiLang = (l: string): void => {
  lang = l;
};

export function apiHeaders(extra?: Record<string, string>): Record<string, string> {
  return { "Accept-Language": lang, ...extra };
}

async function parseBody(res: Response): Promise<unknown> {
  try {
    return (await res.json()) as unknown;
  } catch {
    return null;
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...init,
      headers: apiHeaders(init.body ? { "Content-Type": "application/json" } : undefined),
      cache: "no-store",
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new DotApiError(describeError(0, null));
  }
  if (!res.ok) throw new DotApiError(describeError(res.status, await parseBody(res)));
  return (await res.json()) as T;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
const enc = encodeURIComponent;

export const api = {
  sessions: () => request<SessionInfo[]>("/v1/sessions"),
  createSession: (mode?: PermissionMode) => request<SessionInfo>("/v1/sessions", post(mode ? { mode } : {})),
  messages: (id: string) => request<WireMessage[]>(`/v1/sessions/${enc(id)}/messages`),
  setMode: (id: string, mode: PermissionMode) => request<SessionInfo>(`/v1/sessions/${enc(id)}/mode`, post({ mode })),
  stop: (id: string) => request<{ ok: boolean; stopped: boolean }>(`/v1/sessions/${enc(id)}/stop`, { method: "POST" }),
  resolve: (approvalId: string, decision: "allow" | "always" | "reject") =>
    request<{ ok: boolean }>(`/v1/approvals/${enc(approvalId)}/resolve`, post({ decision })),
  rewind: (id: string, toSeq: number) => request<RewindOut>(`/v1/sessions/${enc(id)}/rewind`, post({ to_seq: toSeq })),
  skills: () => request<SkillInfo[]>("/v1/skills"),
  audit: (cursor?: string | null, session?: string) => {
    const q = new URLSearchParams({ limit: "50" });
    if (cursor) q.set("cursor", cursor);
    if (session) q.set("session", session);
    return request<AuditPage>(`/v1/audit?${q.toString()}`);
  },
  answer: (qid: string, selected: string[], other: string | null) =>
    request<{ ok: boolean }>(`/v1/questions/${enc(qid)}/answer`, post({ selected, other })),
  tasks: (id: string) => request<TaskInfo[]>(`/v1/sessions/${enc(id)}/tasks`),
  context: (id: string) => request<ContextInfo>(`/v1/sessions/${enc(id)}/context`),
  compact: (id: string) => request<CompactOut>(`/v1/sessions/${enc(id)}/compact`, { method: "POST" }),
  memory: (q = "") => request<MemoryFact[]>(`/v1/memory?limit=200${q ? `&q=${enc(q)}` : ""}`),
  memoryAdd: (d: MemoryDraft) => request<MemoryFact>("/v1/memory", post(d)),
  memoryUpdate: (id: string, d: Partial<MemoryDraft>) => request<MemoryFact>(`/v1/memory/${enc(id)}`, { method: "PUT", body: JSON.stringify(d) }),
  memoryDelete: (id: string) => request<{ ok: boolean }>(`/v1/memory/${enc(id)}`, { method: "DELETE" }),
  tools: () => request<ToolInfo[]>("/v1/tools"),
  mcp: () => request<McpServer[]>("/v1/mcp/servers"),
  mcpAct: (name: string, act: "reconnect" | "trust") => request<McpServer>(`/v1/mcp/servers/${enc(name)}/${act}`, { method: "POST" }),
  schedules: () => request<ScheduleInfo[]>("/v1/schedules"),
  scheduleAdd: (cron: string, prompt: string) => request<ScheduleInfo>("/v1/schedules", post({ cron, prompt, enabled: true })),
  scheduleDelete: (id: string) => request<{ ok: boolean }>(`/v1/schedules/${enc(id)}`, { method: "DELETE" }),
  config: () => request<{ backend: string | null; configured: boolean }>("/config"),
  ready: () => request<unknown>("/ready"),
};

export function chatUrl(id: string): string {
  return `${BASE}/v1/sessions/${enc(id)}/chat`;
}

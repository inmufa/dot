import { DotApiError, describeError } from "./errors";
import type { PermissionMode } from "@/lib/stream/events";
import type { AttachmentInfo, AuditPage, CommandInfo, CompactOut, Effort, FileEntry, ModelInfo, ProjectInfo, SearchHit, Telemetry, ContextInfo, MemoryDraft, MemoryFact, McpServer, RewindOut, ScheduleInfo, SessionInfo, SkillInfo, TaskInfo, ToolInfo } from "./types";
import type { WireMessage } from "@/lib/stream/history";
import { toTelemetry } from "./telemetry";
import { fileContentPath, toFileEntries } from "./files";

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

async function requestText(path: string): Promise<string> {
  let res: Response;
  try {
    res = await fetch(BASE + path, { headers: apiHeaders(), cache: "no-store" });
  } catch {
    throw new DotApiError(describeError(0, null));
  }
  if (!res.ok) throw new DotApiError(describeError(res.status, await parseBody(res)));
  return res.text();
}

export const api = {
  sessions: (archived = false) => request<SessionInfo[]>(`/v1/sessions${archived ? "?include_archived=1" : ""}`),
  createSession: (mode?: PermissionMode, project?: string | null) =>
    request<SessionInfo>("/v1/sessions", post({ ...(mode ? { mode } : {}), ...(project ? { project } : {}) })),
  patchSession: (id: string, patch: { title?: string; pinned?: boolean; archived?: boolean }) =>
    request<SessionInfo>(`/v1/sessions/${enc(id)}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteSession: (id: string) => request<{ ok: boolean }>(`/v1/sessions/${enc(id)}?confirm=${enc(id)}`, { method: "DELETE" }),
  search: (q: string) => request<SearchHit[]>(`/v1/search?q=${enc(q)}`),
  exportSession: (id: string, format: "md" | "json") => requestText(`/v1/sessions/${enc(id)}/export?format=${format}`),
  branch: (id: string, toSeq: number) => request<SessionInfo>(`/v1/sessions/${enc(id)}/branch`, post({ to_seq: toSeq })),
  setEffort: (id: string, effort: Effort) => request<SessionInfo>(`/v1/sessions/${enc(id)}/effort`, { method: "PUT", body: JSON.stringify({ effort }) }),
  commands: () => request<CommandInfo[]>("/v1/commands"),
  files: async (id: string): Promise<FileEntry[]> => toFileEntries(await request<Parameters<typeof toFileEntries>[0]>(`/v1/sessions/${enc(id)}/files`)),
  fileUrl: (_id: string, path: string, render = false) => `${BASE}${fileContentPath(path, render)}`,
  fileText: (_id: string, path: string) => requestText(fileContentPath(path)),
  projects: () => request<ProjectInfo[]>("/v1/projects"),
  patchProject: (id: string, patch: { name?: string; instructions?: string }) =>
    request<ProjectInfo>(`/v1/projects/${enc(id)}`, { method: "PATCH", body: JSON.stringify(patch) }),
  inject: (id: string, message: string) =>
    request<{ queued: boolean }>(`/v1/sessions/${enc(id)}/inject`, { method: "POST", body: JSON.stringify({ message }) }),
  injectCancel: (id: string, message: string) =>
    request<{ removed: boolean }>(`/v1/sessions/${enc(id)}/inject/cancel`, { method: "POST", body: JSON.stringify({ message }) }),
  telemetry: async (): Promise<Telemetry> => toTelemetry(await request<Parameters<typeof toTelemetry>[0]>("/v1/telemetry")),
  models: () => request<ModelInfo[]>("/v1/models"),
  upload: async (sessionId: string, file: File): Promise<AttachmentInfo> => {
    const fd = new FormData();
    fd.append("files", file);
    let res: Response;
    try {
      res = await fetch(`${BASE}/v1/sessions/${enc(sessionId)}/attachments`, { method: "POST", body: fd, headers: apiHeaders(), cache: "no-store" });
    } catch {
      throw new DotApiError(describeError(0, null));
    }
    if (!res.ok) throw new DotApiError(describeError(res.status, await parseBody(res)));
    const list = (await res.json()) as AttachmentInfo[];
    const first = list[0];
    if (!first) throw new DotApiError(describeError(500, null));
    return first;
  },
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
  answerForm: (qid: string, fields: Record<string, unknown>) =>
    request<{ ok: boolean }>(`/v1/questions/${enc(qid)}/answer`, post({ fields })),
  tasks: (id: string) => request<TaskInfo[]>(`/v1/sessions/${enc(id)}/tasks`),
  context: (id: string) => request<ContextInfo>(`/v1/sessions/${enc(id)}/context`),
  compact: (id: string, focus?: string) =>
    request<CompactOut>(`/v1/sessions/${enc(id)}/compact`, focus ? post({ focus }) : { method: "POST" }),
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
export function regenerateUrl(id: string): string {
  return `${BASE}/v1/sessions/${enc(id)}/regenerate`;
}

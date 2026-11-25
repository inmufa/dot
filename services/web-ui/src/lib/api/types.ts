import type { PermissionMode } from "@/lib/stream/events";

export type Effort = "off" | "low" | "medium" | "high" | "max";
export interface SessionInfo {
  id: string;
  mode: PermissionMode;
  title: string | null;
  created_at: string;
  pinned?: boolean;
  archived?: boolean;
  project?: string | null;
  state?: "idle" | "running" | "waiting";
  parent_id?: string | null;
  updated_at?: string;
  effort?: Effort;
  message_count?: number;
}
export interface SkillInfo {
  name: string;
  description: string;
  source: "workspace" | "user" | "bundled";
  available: boolean;
  reason: string | null;
  model_invocable: boolean;
}
export interface AuditEntry {
  id: string;
  session: string;
  mode: string;
  tool: string;
  args: Record<string, unknown>;
  decision: "allow" | "ask" | "deny";
  source: string;
  reason: string;
  created_at: string;
}
export interface AuditPage {
  items: AuditEntry[];
  next_cursor: string | null;
}
export interface RewindOut {
  kept_through_seq: number;
  rewound_messages: number;
  restored: { path: string; action: string }[];
}
export interface TaskInfo {
  id: string;
  subject: string;
  description: string;
  status: "pending" | "in_progress" | "completed";
  blocked_by: string[];
  created_at: string;
  updated_at: string;
}
export interface MemoryFact {
  id: string;
  name: string;
  description: string;
  kind: "user" | "feedback" | "project" | "reference";
  body: string;
  updated_at: string;
}
export type MemoryDraft = Pick<MemoryFact, "name" | "description" | "kind" | "body">;
export interface ToolInfo {
  name: string;
  description: string;
  deferred: boolean;
  mutating: boolean;
  needs_approval?: boolean;
  source: "builtin" | "mcp";
  input_schema: Record<string, unknown>;
}
export interface McpServer {
  name: string;
  transport: "stdio" | "http" | "sse";
  scope: "user" | "project";
  status: "connecting" | "connected" | "failed" | "needs_trust" | "stopped";
  tool_count: number;
  trusted: boolean;
  error: string | null;
}
export interface ScheduleRun {
  started_at: string;
  finished_at: string | null;
  status: "ok" | "failed" | "missed" | "running";
  session_id: string | null;
  detail: string;
}
export interface ScheduleInfo {
  id: string;
  kind: "user" | "builtin";
  cron: string;
  prompt: string;
  enabled: boolean;
  created_at: string;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string | null;
  runs: ScheduleRun[];
}
export interface ContextInfo {
  limit: number;
  threshold: number;
  used: number;
  source: "reported" | "estimated";
  tiers: Record<string, number>;
  messages: Record<string, number>;
  compactions: {
    id: number;
    trigger: string;
    stages: string[];
    tokens_before: number;
    tokens_after: number;
    summary_seq: number | null;
    undone: boolean;
    created_at: string;
  }[];
}
export interface CompactOut {
  compacted: boolean;
  reason: string | null;
  tokens_before: number;
  tokens_after: number;
  stages: string[];
}

export interface SearchHit {
  session_id: string;
  title: string | null;
  snippet: string;
  seq: number;
}
export type CommandGroup = "core" | "session" | "tools" | "extra";
export interface CommandInfo {
  name: string;
  args: string | null;
  description: string;
  group: CommandGroup;
  available: boolean;
  reason: string | null;
}
export interface AttachmentInfo {
  id: string;
  name: string;
  mime: string;
  size: number;
  kind: "image" | "doc" | "text";
}
export interface FileEntry {
  path: string;
  size: number;
  mtime: string;
  kind: "html" | "md" | "image" | "csv" | "code" | "other";
}
export interface ProjectInfo {
  id: string;
  name: string;
  instructions: string;
  session_count: number;
}
export interface Telemetry {
  model: string;
  state: "ready" | "loading" | "down";
  ctx_used: number;
  ctx_limit: number;
  vram_used_mb: number;
  vram_total_mb: number;
  tok_s: number;
  slots: { busy: number; total: number };
  vision: boolean;
  voice: boolean;
}
export interface ModelInfo {
  name: string;
  size_mb: number;
  active: boolean;
  vision: boolean;
  display_name: string;
  listed: boolean;
  context_max: number;
  thinking: boolean;
  effort_levels: string[];
  recommended_profile: string | null;
  /** Shell command that switches to this model (the UI cannot switch). */
  switch_command: string;
}
export interface SourceItem {
  n: number;
  title: string;
  url: string;
  snippet?: string;
}

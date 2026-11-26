import type { RefObject } from "react";
import type { useConnection } from "@/hooks/useConnection";
import type { SessionsApi } from "@/hooks/useSessions";
import type { Settings } from "@/hooks/useSettings";
import type { UiState } from "@/hooks/useUiState";
import type { Effort, SkillInfo, Telemetry } from "@/lib/api/client";
import type { DotErrorInfo } from "@/lib/api/errors";
import type { CommandDef } from "@/lib/commands/registry";
import type { CommandHost } from "@/lib/commands/runner";
import type { PermissionMode } from "@/lib/stream/events";
import type { ChatState, DotPhase, UserAtt } from "@/lib/stream/reducer";

export interface ComposerHandle {
  focus: () => void;
  setText: (t: string) => void;
}
export interface BackendCfg {
  backend: string | null;
  configured: boolean;
}
export type Decision = "allow" | "always" | "reject";

export interface AppApi {
  settings: Settings;
  setSettings: (p: Partial<Settings>) => void;
  conn: ReturnType<typeof useConnection>;
  cfg: BackendCfg | null;
  S: SessionsApi;
  id: string | null;
  chat: ChatState;
  phase: DotPhase;
  phases: Record<string, DotPhase>;
  skills: SkillInfo[] | null;
  skillsErr: DotErrorInfo | null;
  loadSkills: () => void;
  commands: CommandDef[];
  telemetry: Telemetry | null;
  ui: UiState;
  composer: RefObject<ComposerHandle | null>;
  flash: string | null;
  notify: (text: string) => void;
  effort: Effort;
  setEffort: (e: Effort) => void;
  /** Deeper thinking on/off: max effort (ultrathink) vs the default. */
  toggleDeep: () => void;
  planOn: boolean;
  researchOn: boolean;
  togglePlan: () => void;
  toggleResearch: () => void;
  changeMode: (m: PermissionMode) => Promise<void>;
  /** Plain text or a /command line. Returns true when the text was consumed. */
  send: (text: string, opts?: { attachments?: string[]; attInfo?: UserAtt[] }) => boolean;
  stop: () => void;
  decide: (d: Decision) => void;
  regenerate: () => void;
  /** Branch (and optionally prefill the composer to edit) from the nth user message. */
  branchFromUser: (userItemId: string, edit?: boolean) => Promise<void>;
  rewindToUser: (userItemId: string) => Promise<void>;
  compact: (focus?: string) => Promise<void>;
  host: CommandHost;
}

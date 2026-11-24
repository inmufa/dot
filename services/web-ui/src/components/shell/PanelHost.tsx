"use client";
import type { SkillInfo } from "@/lib/api/client";
import type { DotErrorInfo } from "@/lib/api/errors";
import type { Settings } from "@/hooks/useSettings";
import { AuditPanel } from "../panels/AuditPanel";
import { McpPanel } from "../panels/McpPanel";
import { MemoryPanel } from "../panels/MemoryPanel";
import { RewindPanel } from "../panels/RewindPanel";
import { SchedulesPanel } from "../panels/SchedulesPanel";
import { SkillsPanel } from "../panels/SkillsPanel";
import { TasksPanel } from "../panels/TasksPanel";
import { ToolsPanel } from "../panels/ToolsPanel";
import type { PanelId } from "./Rail";
import { SettingsSheet } from "./SettingsSheet";

interface Props {
  panel: PanelId | null;
  onClose: () => void;
  sessionId: string | null;
  running: boolean;
  skills: { list: SkillInfo[] | null; error: DotErrorInfo | null; retry: () => void; pick: (name: string) => void };
  settings: { value: Settings; set: (p: Partial<Settings>) => void; backend: string | null; configured: boolean | null };
}

/** Every side sheet, mounted once; each is a closed <dialog> until its id matches. */
export function PanelHost({ panel, onClose, sessionId, running, skills, settings }: Props) {
  const is = (p: PanelId) => panel === p;
  return (
    <>
      <SkillsPanel open={is("skills")} onClose={onClose} skills={skills.list} error={skills.error} onRetry={skills.retry} onPick={skills.pick} />
      <AuditPanel open={is("audit")} onClose={onClose} sessionId={sessionId} />
      <RewindPanel open={is("rewind")} onClose={onClose} sessionId={sessionId} running={running} />
      <TasksPanel open={is("tasks")} onClose={onClose} sessionId={sessionId} running={running} />
      <MemoryPanel open={is("memory")} onClose={onClose} />
      <ToolsPanel open={is("tools")} onClose={onClose} />
      <McpPanel open={is("mcp")} onClose={onClose} />
      <SchedulesPanel open={is("schedules")} onClose={onClose} />
      <SettingsSheet open={is("settings")} onClose={onClose} settings={settings.value} onChange={settings.set} backend={settings.backend} configured={settings.configured} />
    </>
  );
}

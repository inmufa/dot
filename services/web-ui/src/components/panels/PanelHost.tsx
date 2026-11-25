"use client";
import type { SkillInfo } from "@/lib/api/client";
import type { DotErrorInfo } from "@/lib/api/errors";
import type { Settings } from "@/hooks/useSettings";
import { AuditPanel } from "@/components/panels/AuditPanel";
import { McpPanel } from "@/components/panels/McpPanel";
import { PasswordsPanel } from "@/components/panels/PasswordsPanel";
import { MemoryPanel } from "@/components/panels/MemoryPanel";
import { RewindPanel } from "@/components/panels/RewindPanel";
import { SchedulesPanel } from "@/components/panels/SchedulesPanel";
import { SkillsPanel } from "@/components/panels/SkillsPanel";
import { TasksPanel } from "@/components/panels/TasksPanel";
import { ToolsPanel } from "@/components/panels/ToolsPanel";
import type { PanelId } from "@/lib/commands/runner";
import { SettingsSheet } from "@/components/shell/SettingsSheet";
import { useApp } from "@/lib/state/app";

interface Props {
  panel: PanelId | null;
  onClose: () => void;
  sessionId: string | null;
  running: boolean;
  skills: { list: SkillInfo[] | null; error: DotErrorInfo | null; retry: () => void; pick: (name: string) => void };
  settings: { value: Settings; set: (p: Partial<Settings>) => void; backend: string | null; configured: boolean | null };
}

/** Every side sheet, mounted once; each is a closed <dialog> until its id matches. */
function PanelHostView({ panel, onClose, sessionId, running, skills, settings }: Props) {
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
      <PasswordsPanel open={is("passwords")} onClose={onClose} />
      <SettingsSheet open={is("settings")} onClose={onClose} settings={settings.value} onChange={settings.set} backend={settings.backend} configured={settings.configured} />
    </>
  );
}

export function PanelHost() {
  const { ui, id, chat, skills, skillsErr, loadSkills, composer, settings, setSettings, cfg } = useApp();
  return (
    <PanelHostView
      panel={ui.panel}
      onClose={() => ui.setPanel(null)}
      sessionId={id}
      running={chat.running}
      skills={{ list: skills, error: skillsErr, retry: loadSkills, pick: (n) => composer.current?.setText(`/${n} `) }}
      settings={{ value: settings, set: setSettings, backend: cfg?.backend ?? null, configured: cfg?.configured ?? null }}
    />
  );
}

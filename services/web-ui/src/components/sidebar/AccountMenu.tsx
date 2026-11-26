"use client";
import { BookOpen, Brain, CalendarClock, KeyRound, ListChecks, Plug, ScrollText, Settings, Wrench } from "lucide-react";
import { DropdownMenu, MenuItem, MenuSeparator, StateDot, Tooltip } from "@/components/ui";
import { shortModel } from "@/components/composer/ControlRow";
import type { PanelId } from "@/lib/commands/runner";
import { useApp } from "@/lib/state/app";

type Entry = { id: PanelId; label: string; Icon: typeof Brain };
/** Everyday tools: rows above the chat list, icons in the rail. */
export const NAV: Entry[] = [
  { id: "tasks", label: "Tasks", Icon: ListChecks },
  { id: "schedules", label: "Schedules", Icon: CalendarClock },
  { id: "memory", label: "Memory", Icon: Brain },
  { id: "skills", label: "Skills", Icon: BookOpen },
];
/** Setup and admin live in the account menu. */
const MORE: Entry[] = [
  { id: "passwords", label: "Passwords", Icon: KeyRound },
  { id: "mcp", label: "MCP", Icon: Plug },
  { id: "tools", label: "Tools", Icon: Wrench },
  { id: "audit", label: "Audit log", Icon: ScrollText },
];

/** Account row; opens settings and admin tools upward. `compact` is the dot-only rail form. */
export function AccountMenu({ compact, onPick }: { compact?: boolean; onPick: (id: PanelId) => void }) {
  const { phase, telemetry } = useApp();
  const model = telemetry?.model ? shortModel(telemetry.model) : "";
  return (
    <DropdownMenu
      side="top"
      align="start"
      label="Settings and tools"
      trigger={(p) => {
        const btn = (
          <button type="button" {...p} className={compact ? "sb-account sb-account-rail" : "sb-account"} aria-label={compact ? "Dot: settings and tools" : undefined}>
            <span className="sb-account-dot"><StateDot state={phase} /></span>
            {!compact && (
              <span className="sb-account-text">
                <span className="sb-account-name">Dot</span>
                {model && <span className="sb-account-model rec" title={telemetry?.model}>{model}</span>}
              </span>
            )}
          </button>
        );
        return compact ? <Tooltip text="Settings and tools" side="top">{btn}</Tooltip> : btn;
      }}
    >
      <MenuItem icon={<Settings size={16} />} onSelect={() => onPick("settings")}>Settings</MenuItem>
      <MenuSeparator />
      {MORE.map(({ id, label, Icon }) => (
        <MenuItem key={id} icon={<Icon size={16} />} onSelect={() => onPick(id)}>{label}</MenuItem>
      ))}
    </DropdownMenu>
  );
}

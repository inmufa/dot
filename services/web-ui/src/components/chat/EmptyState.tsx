import { MODE_INFO } from "../shell/ModeSwitcher";
import type { PermissionMode } from "@/lib/stream/events";
import { StateDot } from "../ui/StateDot";

export function EmptyState({ hasSession, mode, onNew }: { hasSession: boolean; mode: PermissionMode | null; onNew: () => void }) {
  return (
    <div className="empty">
      <StateDot state="idle" large />
      {hasSession ? (
        <>
          <h2>Ready when you are</h2>
          <p>Describe a task for the workspace: read code, edit files, run commands, search the web.</p>
          {mode && (
            <p className="muted">
              Mode is <strong>{MODE_INFO[mode].label}</strong>. {MODE_INFO[mode].desc}
            </p>
          )}
          <p className="muted">
            Type <kbd>/</kbd> for commands and skills.
          </p>
        </>
      ) : (
        <>
          <h2>No session open</h2>
          <p>A session keeps one conversation, its permission mode and its rewind history.</p>
          <button type="button" className="btn btn-primary" onClick={onNew}>
            New session
          </button>
        </>
      )}
    </div>
  );
}

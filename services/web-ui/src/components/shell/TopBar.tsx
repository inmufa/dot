import { History, Menu } from "lucide-react";
import type { SessionInfo } from "@/lib/api/client";
import { sessionTitle } from "@/lib/format";
import type { DotPhase } from "@/lib/stream/reducer";
import type { PermissionMode } from "@/lib/stream/events";
import { PHASE_LABEL } from "@/hooks/useDotState";
import { StateDot } from "../ui/StateDot";
import { ContextMeter } from "./ContextMeter";
import { ModeSwitcher } from "./ModeSwitcher";

interface Props {
  session: SessionInfo | null;
  phase: DotPhase;
  usage: { tokens: number; limit: number } | null;
  running: boolean;
  onMenu: () => void;
  onMode: (m: PermissionMode) => void;
  onRewind: () => void;
}

export function TopBar({ session, phase, usage, running, onMenu, onMode, onRewind }: Props) {
  return (
    <header className="topbar">
      <button type="button" className="btn btn-ghost btn-icon menu-toggle" onClick={onMenu} aria-label="Open sessions">
        <Menu size={20} aria-hidden />
      </button>
      <div className="topbar-state" role="status">
        <StateDot state={phase} />
        <span className="topbar-label">{PHASE_LABEL[phase]}</span>
      </div>
      <h1 className="topbar-title">{session ? sessionTitle(session.title) : "No session"}</h1>
      <div className="topbar-tools">
        <ContextMeter usage={usage} sessionId={session?.id ?? null} running={running} />
        <ModeSwitcher mode={session?.mode ?? null} disabled={running} onChange={onMode} />
        <button type="button" className="btn btn-ghost btn-icon" onClick={onRewind} disabled={!session} aria-label="Rewind" title="Rewind">
          <History size={18} aria-hidden />
        </button>
      </div>
    </header>
  );
}

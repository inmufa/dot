"use client";
import { History, Menu, PanelRight } from "lucide-react";
import "./Shell.css";
import { IconButton, StateDot } from "@/components/ui";
import { PHASE_LABEL } from "@/hooks/useDotState";
import { useApp } from "@/lib/state/app";
import { sessionTitle } from "@/lib/util/format";
import { indexTime } from "@/lib/util/indexTime";
import { useTyped } from "@/lib/util/useTyped";

/** Top bar on the log's grid: started-at time in the gutter, the dot on the rail, the title in the body column. */
export function TopBar() {
  const { S, phase, ui } = useApp();
  const name = S.active ? sessionTitle(S.active.title) : "No session";
  const title = useTyped(name);
  return (
    <header className="topbar">
      <span className="menu-toggle"><IconButton label="Open sessions" onClick={() => ui.setDrawer(true)}><Menu size={20} aria-hidden /></IconButton></span>
      <div className="topbar-log" role="status">
        <span className="topbar-time rec" title={S.active?.created_at ? `Started ${new Date(S.active.created_at).toLocaleString()}` : undefined}>{S.active ? indexTime(S.active.created_at) : ""}</span>
        <span data-flight-target className="flight-target"><StateDot state={phase} /></span>
        <h1 className="topbar-title" dir="auto" title={name}>{title}</h1>
        {phase !== "idle" && <span className="topbar-label rec">{PHASE_LABEL[phase].toLowerCase()}</span>}
      </div>
      <div className="topbar-tools">
        <IconButton label="Canvas" pressed={ui.canvas.open} onClick={() => (ui.canvas.open ? ui.closeCanvas() : ui.openCanvas())}><PanelRight size={18} aria-hidden /></IconButton>
        <IconButton label="Rewind" onClick={() => ui.setPanel("rewind")} disabled={!S.active}><History size={18} aria-hidden /></IconButton>
      </div>
    </header>
  );
}

"use client";
import { PanelLeftOpen, Search, SquarePen } from "lucide-react";
import { AccountMenu, NAV } from "./AccountMenu";
import { IconButton } from "@/components/ui";
import type { PanelId } from "@/lib/commands/runner";
import { useApp } from "@/lib/state/app";

interface Props { onNew: () => void; onSearch: (e: { detail: number }) => void; onPick: (id: PanelId) => void }

/** Closed desktop sidebar: the same icons in one column, a dotted line running down to the account dot. */
export function SidebarRail({ onNew, onSearch, onPick }: Props) {
  const { ui } = useApp();
  return (
    <nav className="sb-rail" aria-label="Sidebar">
      <IconButton label="Expand sidebar" onClick={ui.toggleSidebar}><PanelLeftOpen size={18} aria-hidden /></IconButton>
      <IconButton label="New chat" onClick={onNew}><SquarePen size={18} aria-hidden /></IconButton>
      <IconButton label="Search (Ctrl K)" onClick={onSearch}><Search size={18} aria-hidden /></IconButton>
      <div className="sb-rail-nav">
        {NAV.map(({ id, label, Icon }) => <IconButton key={id} label={label} onClick={() => onPick(id)}><Icon size={18} aria-hidden /></IconButton>)}
      </div>
      <span className="sb-rail-line" aria-hidden />
      <AccountMenu compact onPick={onPick} />
    </nav>
  );
}

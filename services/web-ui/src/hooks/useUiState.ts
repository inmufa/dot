"use client";
import { useCallback, useEffect, useState } from "react";
import type { CanvasTab, PanelId } from "@/lib/commands/runner";

export type SidebarMode = "open" | "rail";
export type OverlayId = "palette" | "help" | "model" | null;

export interface UiState {
  sidebar: SidebarMode;
  toggleSidebar: () => void;
  /** Mobile drawer (sidebar as overlay). */
  drawer: boolean;
  setDrawer: (o: boolean) => void;
  panel: PanelId | null;
  setPanel: (p: PanelId | null) => void;
  canvas: { open: boolean; tab: CanvasTab; width: number; path: string | null };
  /** Open the canvas; `path` selects a file for the preview tab. */
  openCanvas: (tab?: CanvasTab, path?: string) => void;
  closeCanvas: () => void;
  setCanvasTab: (t: CanvasTab) => void;
  setCanvasWidth: (w: number) => void;
  sidebarWidth: number;
  setSidebarWidth: (w: number) => void;
  overlay: OverlayId;
  paletteScope: "all" | "chats";
  openOverlay: (o: Exclude<OverlayId, null>, scope?: "all" | "chats") => void;
  closeOverlay: () => void;
}

const ls = {
  get: (k: string): string | null => {
    try {
      return window.localStorage.getItem(k);
    } catch {
      return null;
    }
  },
  set: (k: string, v: string): void => {
    try {
      window.localStorage.setItem(k, v);
    } catch {
      /* storage unavailable */
    }
  },
};

export const CANVAS_MIN = 380;
export const CANVAS_MAX = 1400;
export const SIDEBAR_MIN = 220;
export const SIDEBAR_MAX = 520;

export function useUiState(): UiState {
  const [sidebar, setSidebar] = useState<SidebarMode>("open");
  const [drawer, setDrawer] = useState(false);
  const [panel, setPanel] = useState<PanelId | null>(null);
  const [canvas, setCanvas] = useState<UiState["canvas"]>({ open: false, tab: "preview", width: 520, path: null });
  const [sidebarWidth, setSbw] = useState(260);
  const [overlay, setOverlay] = useState<OverlayId>(null);
  const [paletteScope, setScope] = useState<"all" | "chats">("all");

  useEffect(() => {
    if (ls.get("dot.sidebar") === "rail") setSidebar("rail");
    const w = Number(ls.get("dot.canvasW"));
    if (w >= CANVAS_MIN && w <= CANVAS_MAX) setCanvas((c) => ({ ...c, width: w }));
    const sw = Number(ls.get("dot.sidebarW"));
    if (sw >= SIDEBAR_MIN && sw <= SIDEBAR_MAX) setSbw(sw);
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebar((s) => {
      const n = s === "open" ? "rail" : "open";
      ls.set("dot.sidebar", n);
      return n;
    });
  }, []);
  const openCanvas = useCallback((tab?: CanvasTab, path?: string) => setCanvas((c) => ({ ...c, open: true, tab: tab ?? c.tab, path: path ?? c.path })), []);
  const closeCanvas = useCallback(() => setCanvas((c) => ({ ...c, open: false })), []);
  const setCanvasTab = useCallback((tab: CanvasTab) => setCanvas((c) => ({ ...c, tab })), []);
  const setCanvasWidth = useCallback((w: number) => {
    const v = Math.max(CANVAS_MIN, Math.min(CANVAS_MAX, Math.round(w)));
    ls.set("dot.canvasW", String(v));
    setCanvas((c) => ({ ...c, width: v }));
  }, []);
  const setSidebarWidth = useCallback((w: number) => {
    const v = Math.max(SIDEBAR_MIN, Math.min(SIDEBAR_MAX, Math.round(w)));
    ls.set("dot.sidebarW", String(v));
    setSbw(v);
  }, []);
  const openOverlay = useCallback((o: Exclude<OverlayId, null>, scope: "all" | "chats" = "all") => {
    setScope(scope);
    setOverlay(o);
  }, []);
  const closeOverlay = useCallback(() => setOverlay(null), []);

  return { sidebar, toggleSidebar, drawer, setDrawer, panel, setPanel, canvas, openCanvas, closeCanvas, setCanvasTab, setCanvasWidth, sidebarWidth, setSidebarWidth, overlay, paletteScope, openOverlay, closeOverlay };
}

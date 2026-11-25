"use client";
import dynamic from "next/dynamic";
import { useEffect, useRef, type CSSProperties } from "react";
import { PreviewOffer } from "@/components/canvas/PreviewOffer";
import { PendingDock } from "@/components/activity/PendingDock";
import { Transcript } from "@/components/chat/Transcript";
import { Composer } from "@/components/composer/Composer";
import { Home } from "@/components/home/Home";
import { PanelHost } from "@/components/panels/PanelHost";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { useToast } from "@/components/ui";
import { AppProvider, useApp } from "@/lib/state/app";
import { Banner } from "./Banner";
import { HelpSheet } from "./HelpSheet";
import { ModelPicker } from "@/components/home/ModelPicker";
import { TopBar } from "./TopBar";
import { usePaneSlide } from "./usePaneSlide";

const Canvas = dynamic(() => import("@/components/canvas/Canvas"), { ssr: false });
const Palette = dynamic(() => import("@/components/sidebar/Palette"), { ssr: false });

/** Bare `notify`/flash strings from anywhere in the app surface as toasts. */
function useFlashToast(flash: string | null) {
  const toast = useToast();
  useEffect(() => {
    if (!flash) return;
    const bad = /^(could not|usage|failed)|not available|unreachable/i.test(flash);
    toast({ title: flash, tone: bad ? "warn" : "neutral" });
  }, [flash, toast]);
}

function Shell() {
  const { S, conn, cfg, chat, id, ui, flash, composer, toggleDeep } = useApp();
  const home = !id || chat.items.length === 0;
  const app = useRef<HTMLDivElement>(null);
  useFlashToast(flash);
  usePaneSlide(app, ui.sidebar);

  // Global keys: "/" focuses the composer, Ctrl+K palette, Ctrl+Shift+E effort. Never animated.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && !e.shiftKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        ui.openOverlay("palette");
      } else if (mod && e.shiftKey && e.key.toLowerCase() === "e") {
        e.preventDefault();
        toggleDeep();
      } else if (e.key === "/" && !mod && !e.altKey && !(e.target as HTMLElement).closest("input, textarea, select, dialog, [contenteditable]")) {
        e.preventDefault();
        composer.current?.setText("/");
      } else if (e.key === "Escape" && ui.drawer) ui.setDrawer(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ui, composer, toggleDeep]);

  return (
    <div
      ref={app}
      className="app"
      data-sidebar={ui.sidebar}
      data-canvas={ui.canvas.open ? "open" : "closed"}
      data-mode={S.active?.mode ?? "default"}
      style={{ "--canvas-w": `${ui.canvas.width}px`, "--sb-open-w": `${ui.sidebarWidth}px` } as CSSProperties}
    >
      <a className="skip" href="#composer">Skip to message box</a>
      <div className="sidebar-wrap" data-open={ui.drawer}>
        <Sidebar />
      </div>
      {ui.drawer && <button type="button" className="scrim" aria-label="Close sessions" onClick={() => ui.setDrawer(false)} />}
      <div className="main" data-home={home}>
        <Banner link={conn.link} error={conn.error} backend={cfg?.backend ?? null} onRetry={() => { conn.recheck(); void S.reload(); }} />
        <TopBar />
        <div className="stage">
          {home ? <Home /> : <Transcript />}
          <div className="dock" id="dock">
            <div className="column">
              <PreviewOffer />
              <PendingDock />
              <Composer />
            </div>
          </div>
        </div>
      </div>
      <Canvas />
      <PanelHost />
      <HelpSheet />
      {ui.overlay === "palette" && <Palette />}
      <ModelPicker />
    </div>
  );
}

export function AppShell() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}

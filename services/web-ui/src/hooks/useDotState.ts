"use client";
import { useEffect } from "react";
import type { DotPhase } from "@/lib/stream/reducer";

export const PHASE_LABEL: Record<DotPhase, string> = {
  idle: "Idle",
  thinking: "Thinking",
  waiting: "Needs approval",
};

/** The dot is also the tab icon and title. */
export function useDotFavicon(phase: DotPhase, chatTitle?: string | null): void {
  useEffect(() => {
    let link = document.querySelector<HTMLLinkElement>('link[rel="icon"][data-dot]');
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      link.type = "image/svg+xml";
      link.dataset.dot = "1";
      document.head.appendChild(link);
    }
    link.href = `/dot-${phase === "waiting" ? "waiting" : phase}.svg?v=2`; // same version as app/layout.tsx icons
    const t = chatTitle?.trim();
    document.title = [phase === "idle" ? null : PHASE_LABEL[phase], t, "Dot"].filter(Boolean).join(" - ");
  }, [phase, chatTitle]);
}

"use client";
import { useEffect } from "react";
import type { DotPhase } from "@/lib/stream/reducer";

export const PHASE_LABEL: Record<DotPhase, string> = {
  idle: "Idle",
  thinking: "Thinking",
  waiting: "Needs approval",
};

/** The dot is also the tab icon and title. */
export function useDotFavicon(phase: DotPhase): void {
  useEffect(() => {
    let link = document.querySelector<HTMLLinkElement>('link[rel="icon"][data-dot]');
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      link.type = "image/svg+xml";
      link.dataset.dot = "1";
      document.head.appendChild(link);
    }
    link.href = `/dot-${phase === "waiting" ? "waiting" : phase}.svg`;
    document.title = phase === "idle" ? "Dot" : `${PHASE_LABEL[phase]} - Dot`;
  }, [phase]);
}

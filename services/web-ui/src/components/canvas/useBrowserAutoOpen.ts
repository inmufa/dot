"use client";
import { useEffect, useRef } from "react";
import { useApp } from "@/lib/state/app";
import { isBrowserTool } from "./useBrowser";

/** True while the owner is typing a message: never pop a panel over that. */
function composing(): boolean {
  const el = document.activeElement;
  return el instanceof HTMLTextAreaElement && !!el.closest(".composer") && el.value.trim() !== "";
}

/** First approved or unasked Browser* tool call of a turn opens the canvas on the Browser tab, once per turn. */
export function useBrowserAutoOpen(): void {
  const { chat, ui } = useApp();
  const done = useRef(-1);
  const lastUser = chat.items.findLastIndex((i) => i.kind === "user");
  const turn = chat.items.filter((i) => i.kind === "user").length;
  // a call still waiting for approval does not count: the canvas would cover the card on phones
  const pending = chat.approval?.invocation.call_id;
  const called = chat.items.slice(lastUser + 1).some((i) => i.kind === "tool" && isBrowserTool(i.name) && i.id !== pending);
  useEffect(() => {
    if (!called || !chat.running || done.current === turn) return;
    done.current = turn;
    if (!composing()) ui.openCanvas("browser");
  }, [called, chat.running, turn, ui]);
}

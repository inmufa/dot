"use client";
import { useEffect, useRef } from "react";
import { useApp } from "@/lib/state/app";
import { useBuddyAnim } from "@/lib/buddy/prefs";
import { Buddy, BuddyMark, type BuddyHandle } from "./Buddy";
import type { Emote, Mood } from "./rig";

/** Dot's situation as a looping mood; transitions call `onEmote` once. */
export function useBuddyMood(onEmote: (e: Emote) => void): Mood {
  const { chat, id } = useApp();
  const toolRunning = chat.items.some((i) => i.kind === "tool" && i.status === "running");
  const plan = chat.approval?.invocation.name === "ExitPlanMode";
  const was = useRef({ running: chat.running, plan, id });
  const emit = useRef(onEmote);
  useEffect(() => { emit.current = onEmote; });

  useEffect(() => {
    const w = was.current;
    if (id !== w.id) emit.current("wink");
    else if (chat.running && !w.running) emit.current("nod");
    else if (!chat.running && w.running) {
      const last = [...chat.items].reverse().find((i) => i.kind === "notice" || i.kind === "assistant");
      const notice = last?.kind === "notice" ? last : null;
      emit.current(notice?.level === "error" ? "error" : notice?.text.startsWith("Stopped") ? "squint" : "done");
    } else if (plan && !w.plan) emit.current("wonder");
    was.current = { running: chat.running, plan, id };
  }, [chat.running, chat.items, plan, id]);

  return chat.approval || chat.question ? "waiting" : chat.running ? (toolRunning ? "working" : "thinking") : "idle";
}

/** A buddy wired to what Dot is doing right now. Click it and it jumps. */
export function LiveBuddy({ size, follow = false, className }: { size: number; follow?: boolean; className?: string }) {
  const buddy = useRef<BuddyHandle>(null);
  const mood = useBuddyMood((e) => buddy.current?.play(e));
  const animate = useBuddyAnim();
  if (!animate) return <BuddyMark size={size} />;
  return <Buddy ref={buddy} size={size} mood={mood} follow={follow} className={`bd-click${className ? ` ${className}` : ""}`} onClick={() => buddy.current?.play("jump")} />;
}

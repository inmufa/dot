"use client";
import { useEffect, useSyncExternalStore } from "react";
import { feature, getCaps } from "@/lib/api/caps";
import { voiceApi } from "@/lib/api/voice";

/** unknown: not asked yet; missing: backend has no voice routes (404); down: worker not running. */
export type VoiceState = "unknown" | "up" | "down" | "missing";
export interface VoiceSnap { state: VoiceState; stt: boolean; tts: boolean }

let snap: VoiceSnap = { state: "unknown", stt: false, tts: false };
let inflight: Promise<void> | null = null;
const listeners = new Set<() => void>();
const set = (s: VoiceSnap) => { snap = s; listeners.forEach((l) => l()); };

/** Ask the backend whether the worker is up (404 flips the `voice` capability off). */
export function refreshVoice(): Promise<void> {
  inflight ??= feature("voice", voiceApi.status)
    .then((r) => {
      if (r === null) set({ state: "missing", stt: false, tts: false });
      else set({ state: r.available ? "up" : "down", stt: r.stt, tts: r.tts });
    })
    .catch(() => set({ state: "down", stt: false, tts: false }))
    .finally(() => { inflight = null; });
  return inflight;
}

/** Voice worker state; checks once on first use and again every 30 s while it is down. */
export function useVoice(): VoiceSnap {
  const s = useSyncExternalStore((fn) => (listeners.add(fn), () => listeners.delete(fn)), () => snap, () => snap);
  useEffect(() => {
    if (getCaps().voice === "no") return;
    if (snap.state === "unknown") void refreshVoice();
    if (s.state !== "down") return;
    const t = window.setInterval(() => void refreshVoice(), 30_000);
    return () => window.clearInterval(t);
  }, [s.state]);
  return s;
}

"use client";
import { useSyncExternalStore } from "react";

export interface VoicePrefs { voice: string; speed: number; autoStop: boolean }
const KEY = "dot.voice";
const DEFAULTS: VoicePrefs = { voice: "", speed: 1, autoStop: true };
export const SPEEDS = [0.85, 1, 1.25, 1.5] as const;

let prefs: VoicePrefs = DEFAULTS;
let loaded = false;
const listeners = new Set<() => void>();

function load(): void {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    const v = JSON.parse(window.localStorage.getItem(KEY) ?? "null") as Partial<VoicePrefs> | null;
    if (v) prefs = { voice: typeof v.voice === "string" ? v.voice.slice(0, 32) : "", speed: typeof v.speed === "number" && v.speed >= 0.5 && v.speed <= 2 ? v.speed : 1, autoStop: v.autoStop !== false };
  } catch {
    /* storage unavailable */
  }
}

export const getPrefs = (): VoicePrefs => (load(), prefs);
export function setPrefs(patch: Partial<VoicePrefs>): void {
  prefs = { ...getPrefs(), ...patch };
  try {
    window.localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* ignore */
  }
  listeners.forEach((l) => l());
}
export const useVoicePrefs = (): VoicePrefs =>
  useSyncExternalStore((fn) => (listeners.add(fn), () => listeners.delete(fn)), getPrefs, () => DEFAULTS);

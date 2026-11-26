"use client";
import { useSyncExternalStore } from "react";

export const BUDDY_COLORS = [
  { name: "Tangerine", hex: "#F59A4E" },
  { name: "Mint", hex: "#7FD1B9" },
  { name: "Periwinkle", hex: "#9FA8F0" },
  { name: "Sakura", hex: "#F4A9C0" },
  { name: "Matcha", hex: "#B5CC7A" },
  { name: "Mochi white", hex: "#EEE9DF" },
] as const;
export const DEFAULT_BUDDY = BUDDY_COLORS[0].hex;

const KEY = "dot.buddy";
let color: string = DEFAULT_BUDDY;
let loaded = false;
const listeners = new Set<() => void>();

function load(): void {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    const v = window.localStorage.getItem(KEY);
    if (v && BUDDY_COLORS.some((c) => c.hex === v)) color = v;
  } catch {
    /* storage unavailable */
  }
}

export const getBuddyColor = (): string => (load(), color);
export function setBuddyColor(hex: string): void {
  color = hex;
  try {
    window.localStorage.setItem(KEY, hex);
  } catch {
    /* ignore */
  }
  listeners.forEach((l) => l());
}
export const useBuddyColor = (): string =>
  useSyncExternalStore((fn) => (listeners.add(fn), () => listeners.delete(fn)), getBuddyColor, () => DEFAULT_BUDDY);

// animation on/off: off shows the still logo pose everywhere
const ANIM_KEY = "dot.buddy.anim";
let anim = true;
let animLoaded = false;
const animListeners = new Set<() => void>();
export function getBuddyAnim(): boolean {
  if (!animLoaded && typeof window !== "undefined") {
    animLoaded = true;
    try { anim = window.localStorage.getItem(ANIM_KEY) !== "0"; } catch { /* storage unavailable */ }
  }
  return anim;
}
export function setBuddyAnim(on: boolean): void {
  anim = on;
  try { window.localStorage.setItem(ANIM_KEY, on ? "1" : "0"); } catch { /* ignore */ }
  animListeners.forEach((l) => l());
}
export const useBuddyAnim = (): boolean =>
  useSyncExternalStore((fn) => (animListeners.add(fn), () => animListeners.delete(fn)), getBuddyAnim, () => true);

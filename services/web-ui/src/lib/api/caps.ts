"use client";
import { useSyncExternalStore } from "react";
import { DotApiError } from "./errors";

/** Optional backend features. "no" means the endpoint answered 404/405 (not available yet). */
export const CAP_IDS = [
  "search", "export", "regenerate", "branch", "effort", "commands", "attachments",
  "files", "browser", "projects", "telemetry", "models", "pin", "voice", "vision",
] as const;
export type CapId = (typeof CAP_IDS)[number];
export type CapState = "unknown" | "yes" | "no";

let caps: Record<CapId, CapState> = Object.fromEntries(CAP_IDS.map((c) => [c, "unknown"])) as Record<CapId, CapState>;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function setCap(id: CapId, state: CapState): void {
  if (caps[id] === state) return;
  caps = { ...caps, [id]: state };
  emit();
}
export const getCaps = (): Record<CapId, CapState> => caps;

/** Route missing (not "session not found"): 404/405/501 with no domain code or the generic 1002. */
export const isMissing = (e: unknown): boolean =>
  e instanceof DotApiError && [404, 405, 501].includes(e.info.status) && (e.info.code === null || e.info.code === 1002);

/** Run a feature call: 404/405 marks it unsupported and returns null; other errors rethrow. */
export async function feature<T>(id: CapId, fn: () => Promise<T>): Promise<T | null> {
  if (caps[id] === "no") return null;
  try {
    const r = await fn();
    setCap(id, "yes");
    return r;
  } catch (e) {
    if (isMissing(e)) {
      setCap(id, "no");
      return null;
    }
    throw e;
  }
}

export const useCaps = (): Record<CapId, CapState> =>
  useSyncExternalStore((fn) => (listeners.add(fn), () => listeners.delete(fn)), getCaps, getCaps);
/** True unless the backend said "not available" (unknown counts as available so controls show). */
export const useCap = (id: CapId): boolean => useCaps()[id] !== "no";

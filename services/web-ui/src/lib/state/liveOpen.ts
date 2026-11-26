import { useSyncExternalStore } from "react";

/** Whether the running turn's steps are expanded under the live line (one turn runs at a time). */
let open = false;
const subs = new Set<() => void>();
export const setLiveOpen = (v: boolean): void => { if (v !== open) { open = v; subs.forEach((f) => f()); } };
export const useLiveOpen = (): boolean =>
  useSyncExternalStore((f) => (subs.add(f), () => subs.delete(f)), () => open, () => false);

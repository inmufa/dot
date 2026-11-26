import type { Effort } from "@/lib/api/types";

export interface EffortMeta {
  id: Effort;
  label: string;
  short: string;
  desc: string;
  /** Measured or expected latency hint shown in the picker. */
  speed: string;
  /** Filled bars out of 5. */
  bars: number;
  key: string;
}

export const EFFORTS: readonly EffortMeta[] = [
  { id: "off", label: "Instant", short: "Instant", desc: "No thinking", speed: "about 1 s", bars: 1, key: "1" },
  { id: "low", label: "Low", short: "Low", desc: "Brief thinking", speed: "a few seconds", bars: 2, key: "2" },
  { id: "medium", label: "Medium", short: "Med", desc: "Balanced default", speed: "5 to 20 s", bars: 3, key: "3" },
  { id: "high", label: "High", short: "High", desc: "Careful, double-checks", speed: "20 to 60 s", bars: 4, key: "4" },
  { id: "max", label: "Max", short: "Max", desc: "Ultrathink plus a check", speed: "a minute or more", bars: 5, key: "5" },
] as const;

export const DEFAULT_EFFORT: Effort = "medium";
export const isEffort = (v: unknown): v is Effort => EFFORTS.some((e) => e.id === v);

const ULTRA = /\bultrathink\b/i;
export const hasUltrathink = (text: string): boolean => ULTRA.test(text);

/** Effort for one turn: the keyword raises it to max for that turn only; voice mode forces instant. */
export function effectiveEffort(session: Effort, text: string, voice = false): Effort {
  if (voice) return "off";
  return hasUltrathink(text) ? "max" : session;
}

/** Parse "/effort <arg>": level id, label, or digit 1-5. */
export function parseEffortArg(arg: string): Effort | null {
  const a = arg.trim().toLowerCase();
  if (!a) return null;
  const hit = EFFORTS.find((e) => e.id === a || e.label.toLowerCase() === a || e.key === a || (a === "normal" && e.id === "medium") || (a === "ultra" && e.id === "max"));
  return hit?.id ?? null;
}

/** Split text around "ultrathink" so the input overlay can shimmer the word. */
export function splitUltrathink(text: string): { text: string; hot: boolean }[] {
  const out: { text: string; hot: boolean }[] = [];
  let last = 0;
  for (const m of text.matchAll(/\bultrathink\b/gi)) {
    if (m.index > last) out.push({ text: text.slice(last, m.index), hot: false });
    out.push({ text: m[0], hot: true });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), hot: false });
  return out;
}

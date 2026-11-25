import type { VoiceInfo } from "@/lib/api/voice";

/** Pre-recorded clips in public/voice-samples (scripts/voice-samples.py writes them). */
export const SAMPLES_BASE = "/voice-samples/";
export interface SampleManifest { text: string; clips: Record<string, string> }

/** Validates the manifest; unknown shapes give an empty set (no play buttons). */
export function parseManifest(raw: unknown): SampleManifest {
  const m = raw as { text?: unknown; voices?: unknown } | null;
  const clips: Record<string, string> = {};
  if (m && Array.isArray(m.voices)) {
    for (const v of m.voices as ({ id?: unknown; file?: unknown } | null)[]) {
      if (typeof v?.id === "string" && typeof v.file === "string" && /^[\w-]+\.(ogg|mp3|opus|webm)$/.test(v.file)) clips[v.id] = SAMPLES_BASE + v.file;
    }
  }
  return { text: typeof m?.text === "string" ? m.text : "", clips };
}

let cached: Promise<SampleManifest> | null = null;
export function loadSamples(): Promise<SampleManifest> {
  cached ??= fetch(SAMPLES_BASE + "manifest.json")
    .then((r) => (r.ok ? r.json() : null))
    .then(parseManifest, () => parseManifest(null));
  return cached;
}

/** "af_heart" -> "Heart". */
export const voiceName = (id: string): string => {
  const n = id.includes("_") ? id.slice(id.indexOf("_") + 1) : id;
  return n.charAt(0).toUpperCase() + n.slice(1);
};

const ACCENT: Record<string, string> = { US: "American", UK: "British" };
const GENDER: Record<string, string> = { female: "Female", male: "Male" };
export const groupLabel = (v: VoiceInfo): string => `${ACCENT[v.accent] ?? v.accent}, ${(GENDER[v.gender] ?? v.gender).toLowerCase()}`;

/** Voices grouped by accent and gender, groups in first-seen order, names sorted inside a group. */
export function groupVoices(list: VoiceInfo[]): { label: string; voices: VoiceInfo[] }[] {
  const groups = new Map<string, VoiceInfo[]>();
  for (const v of list) {
    const k = groupLabel(v);
    groups.set(k, [...(groups.get(k) ?? []), v]);
  }
  return [...groups].map(([label, voices]) => ({ label, voices: voices.sort((a, b) => voiceName(a.id).localeCompare(voiceName(b.id))) }));
}

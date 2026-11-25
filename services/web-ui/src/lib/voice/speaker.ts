"use client";
import { useSyncExternalStore } from "react";
import { voiceApi } from "@/lib/api/voice";
import { getPrefs } from "./prefs";

export type SpeakPhase = "idle" | "loading" | "playing";
export interface SpeakSnap { phase: SpeakPhase; key: string | null }

let snap: SpeakSnap = { phase: "idle", key: null };
const listeners = new Set<() => void>();
const set = (s: SpeakSnap) => { snap = s; listeners.forEach((l) => l()); };

let ctx: AudioContext | null = null;
let abort: AbortController | null = null;
let sources: AudioBufferSourceNode[] = [];
let run = 0;
let clip: HTMLAudioElement | null = null;

/** Int16 little-endian bytes to float samples; `carry` holds a dangling odd byte. */
export function pcmToFloat(bytes: Uint8Array, carry: number | null): { samples: Float32Array<ArrayBuffer>; carry: number | null } {
  const joined = carry === null ? bytes : Uint8Array.from([carry, ...bytes]);
  const n = joined.length >> 1;
  const view = new DataView(joined.buffer, joined.byteOffset, n * 2);
  const samples = new Float32Array(n);
  for (let i = 0; i < n; i++) samples[i] = view.getInt16(i * 2, true) / 32768;
  return { samples, carry: joined.length & 1 ? (joined[joined.length - 1] ?? null) : null };
}

/** Stop playback and cancel the stream (barge-in). */
export function stopSpeaking(): void {
  run++;
  abort?.abort();
  abort = null;
  sources.forEach((s) => { s.onended = null; try { s.stop(); } catch { /* already ended */ } });
  sources = [];
  if (clip) { clip.onplaying = clip.onended = clip.onerror = null; clip.pause(); clip = null; }
  if (snap.phase !== "idle") set({ phase: "idle", key: null });
  document.removeEventListener("keydown", onKey, true);
}

function onKey(e: KeyboardEvent): void {
  if (e.key !== "Escape") return;
  e.stopPropagation();
  stopSpeaking();
}

/** Stream /v1/voice/speak and play it gap-free, sentence by sentence. Rejects before playback on API errors. */
export async function speak(key: string, text: string): Promise<void> {
  stopSpeaking();
  const my = run;
  const ac = new AbortController();
  abort = ac;
  ctx ??= new AudioContext();
  void ctx.resume();
  set({ phase: "loading", key });
  document.addEventListener("keydown", onKey, true);
  const { voice, speed } = getPrefs();
  try {
    const { body, rate } = await voiceApi.speak(text, { voice, speed }, ac.signal);
    const reader = body.getReader();
    let carry: number | null = null;
    let at = 0;
    let started = false;
    for (;;) {
      const { done, value } = await reader.read();
      if (my !== run) return;
      if (done) break;
      const r = pcmToFloat(value, carry);
      carry = r.carry;
      if (!r.samples.length) continue;
      const buf = ctx.createBuffer(1, r.samples.length, rate);
      buf.copyToChannel(r.samples, 0);
      const src = ctx.createBufferSource();
      src.buffer = buf;
      src.connect(ctx.destination);
      at = Math.max(at, ctx.currentTime + 0.06);
      src.start(at);
      at += buf.duration;
      sources.push(src);
      src.onended = () => {
        sources = sources.filter((s) => s !== src);
        if (my === run && !sources.length && !abort) stopSpeaking();
      };
      if (!started) { started = true; set({ phase: "playing", key }); }
    }
    abort = null;
    if (!sources.length && my === run) stopSpeaking();
  } catch (e) {
    if (my === run) stopSpeaking();
    if (!(e instanceof DOMException && e.name === "AbortError")) throw e;
  }
}

/** Play a pre-recorded clip (static file). Shares state with speak(), so only one sound plays at a time. */
export function playClip(key: string, url: string): void {
  stopSpeaking();
  const my = run;
  const a = new Audio(url);
  clip = a;
  set({ phase: "loading", key });
  document.addEventListener("keydown", onKey, true);
  const done = () => { if (my === run) stopSpeaking(); };
  a.onplaying = () => { if (my === run) set({ phase: "playing", key }); };
  a.onended = done;
  a.onerror = done;
  a.play().catch(done);
}

/** Toggle a clip: stop it if it is the one playing, else play it. */
export function toggleClip(key: string, url: string): void {
  if (snap.key === key && snap.phase !== "idle") stopSpeaking();
  else playClip(key, url);
}

export const getSpeaker = (): SpeakSnap => snap;
export const useSpeaker = (): SpeakSnap =>
  useSyncExternalStore((fn) => (listeners.add(fn), () => listeners.delete(fn)), () => snap, () => snap);

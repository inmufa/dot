/** Synthesised UI sounds (Web Audio, no asset files): soft glass-like tones with a short room tail. */
export type Cue = "send" | "done" | "research" | "approval" | "error" | "micOn" | "micOff" | "newChat" | "copy";

let ctx: AudioContext | null = null;
let out: GainNode | null = null;
let room: ConvolverNode | null = null;
let enabled = false;

export const setSoundsEnabled = (on: boolean): void => {
  enabled = on;
};

/** Browsers start audio suspended: unlock on the first real gesture. */
export function unlockSound(): void {
  if (ctx || typeof window === "undefined") return;
  const Ctor = window.AudioContext;
  ctx = new Ctor();
  out = ctx.createGain();
  out.gain.value = 0.22;
  const lp = ctx.createBiquadFilter();
  lp.type = "lowpass";
  lp.frequency.value = 5200;
  lp.Q.value = 0.3;
  out.connect(lp);
  lp.connect(ctx.destination);
  room = ctx.createConvolver();
  room.buffer = impulse(ctx, 0.9, 3.2);
  const wet = ctx.createGain();
  wet.gain.value = 0.28;
  room.connect(wet);
  wet.connect(lp);
}

/** Exponentially decaying noise as a small, soft room. */
function impulse(c: AudioContext, seconds: number, decay: number): AudioBuffer {
  const n = Math.floor(c.sampleRate * seconds);
  const buf = c.createBuffer(2, n, c.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch);
    for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, decay);
  }
  return buf;
}

/** One bell-like note: sine body + quiet octave partial, fast attack, exponential release. */
function note(freq: number, at: number, dur: number, gain: number, bright = 0.16): void {
  if (!ctx || !out || !room) return;
  const t = ctx.currentTime + at;
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(gain, t + 0.012);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  g.connect(out);
  g.connect(room);
  const body = ctx.createOscillator();
  body.type = "sine";
  body.frequency.value = freq;
  body.connect(g);
  body.start(t);
  body.stop(t + dur + 0.05);
  const part = ctx.createOscillator();
  part.type = "sine";
  part.frequency.value = freq * 2.01;
  const pg = ctx.createGain();
  pg.gain.setValueAtTime(bright, t);
  pg.gain.exponentialRampToValueAtTime(0.0001, t + dur * 0.4);
  part.connect(pg);
  pg.connect(g);
  part.start(t);
  part.stop(t + dur);
}

// Pitches (Hz): a calm pentatonic set so every cue sits well together
const E5 = 659.25;
const G5 = 783.99;
const A5 = 880;
const B5 = 987.77;
const D6 = 1174.66;
const E6 = 1318.51;
const A4 = 440;
const E4 = 329.63;
const D4 = 293.66;
const B3 = 246.94;

const CUES: Record<Cue, () => void> = {
  send: () => { note(E5, 0, 0.16, 0.5); note(B5, 0.05, 0.2, 0.34); },
  done: () => { note(E5, 0, 0.5, 0.5); note(B5, 0.11, 0.8, 0.42); note(E6, 0.24, 0.9, 0.2, 0.08); },
  research: () => { note(E5, 0, 0.55, 0.48); note(G5, 0.12, 0.6, 0.4); note(B5, 0.24, 0.8, 0.4); note(E6, 0.4, 1.3, 0.3, 0.1); },
  approval: () => { note(A4, 0, 0.35, 0.5); note(E5, 0.14, 0.45, 0.46); note(A5, 0.3, 0.7, 0.34); },
  error: () => { note(D4, 0, 0.4, 0.55, 0.05); note(B3, 0.13, 0.65, 0.5, 0.04); note(E4, 0.04, 0.3, 0.12, 0.02); },
  micOn: () => { note(G5, 0, 0.12, 0.42); note(D6, 0.06, 0.18, 0.34); },
  micOff: () => { note(D6, 0, 0.12, 0.34); note(G5, 0.06, 0.2, 0.4); },
  newChat: () => { note(A5, 0, 0.14, 0.3, 0.1); },
  copy: () => { note(E6, 0, 0.09, 0.22, 0.05); },
};

export function playSound(cue: Cue): void {
  if (!enabled) return;
  unlockSound();
  if (!ctx) return;
  if (ctx.state === "suspended") void ctx.resume();
  CUES[cue]();
}

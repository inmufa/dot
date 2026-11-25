/** Average channels to mono. */
export function downmix(channels: Float32Array[]): Float32Array {
  const first = channels[0];
  if (!first) return new Float32Array(0);
  if (channels.length === 1) return first;
  const out = new Float32Array(first.length);
  for (const ch of channels) for (let i = 0; i < out.length; i++) out[i] = (out[i] ?? 0) + (ch[i] ?? 0) / channels.length;
  return out;
}

/** Box-filter resample (enough for speech; avoids aliasing when going down). */
export function resample(x: Float32Array, from: number, to: number): Float32Array {
  if (from === to) return x;
  const n = Math.floor((x.length * to) / from);
  const out = new Float32Array(n);
  const step = from / to;
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * step);
    const b = Math.min(x.length, Math.max(a + 1, Math.floor((i + 1) * step)));
    let sum = 0;
    for (let j = a; j < b; j++) sum += x[j] ?? 0;
    out[i] = sum / (b - a);
  }
  return out;
}

/** 16-bit mono PCM WAV. */
export function encodeWav(samples: Float32Array, rate: number): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const str = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, "RIFF");
  v.setUint32(4, 36 + samples.length * 2, true);
  str(8, "WAVEfmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, rate, true);
  v.setUint32(28, rate * 2, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  str(36, "data");
  v.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => v.setInt16(44 + i * 2, Math.round(Math.max(-1, Math.min(1, s)) * 32767), true));
  return new Blob([buf], { type: "audio/wav" });
}

export const TARGET_RATE = 16000;

/** Decoded audio (any rate, any channels) to a 16 kHz mono WAV. */
export function toWav16k(channels: Float32Array[], rate: number): Blob {
  return encodeWav(resample(downmix(channels), rate, TARGET_RATE), TARGET_RATE);
}

/** Seconds of speech in a 16 kHz WAV blob (44-byte header). */
export const wavSeconds = (b: Blob): number => Math.max(0, b.size - 44) / 2 / TARGET_RATE;

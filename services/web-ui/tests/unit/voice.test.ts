import { describe, expect, it } from "vitest";
import { levelOf, silentTooLong } from "@/lib/voice/dictation";
import { pcmToFloat } from "@/lib/voice/speaker";
import { downmix, encodeWav, resample, toWav16k, wavSeconds } from "@/lib/voice/wav";

const bytes = async (b: Blob) => new DataView(await b.arrayBuffer());

describe("wav", () => {
  it("writes a 16 kHz mono 16-bit header", async () => {
    const v = await bytes(encodeWav(new Float32Array([0, 1, -1, 0.5]), 16000));
    expect(String.fromCharCode(v.getUint8(0), v.getUint8(1), v.getUint8(2), v.getUint8(3))).toBe("RIFF");
    expect(v.getUint16(22, true)).toBe(1);
    expect(v.getUint32(24, true)).toBe(16000);
    expect(v.getUint16(34, true)).toBe(16);
    expect(v.getUint32(40, true)).toBe(8);
    expect([v.getInt16(46, true), v.getInt16(48, true)]).toEqual([32767, -32767]);
  });
  it("downmixes and resamples 48 kHz stereo to 16 kHz", () => {
    expect(Array.from(downmix([new Float32Array([1, 0]), new Float32Array([0, 1])]))).toEqual([0.5, 0.5]);
    const one = new Float32Array(48000).fill(0.25);
    expect(resample(one, 48000, 16000)).toHaveLength(16000);
    const blob = toWav16k([one, one], 48000);
    expect(blob.size).toBe(44 + 32000);
    expect(wavSeconds(blob)).toBeCloseTo(1, 3);
  });
});

describe("pcmToFloat", () => {
  it("keeps a dangling odd byte for the next chunk", () => {
    const a = pcmToFloat(new Uint8Array([0x00, 0x40, 0x00]), null);
    expect(a.samples[0]).toBeCloseTo(0.5, 3);
    expect(a.carry).toBe(0);
    const b = pcmToFloat(new Uint8Array([0xc0]), a.carry);
    expect(b.samples[0]).toBeCloseTo(-0.5, 3);
    expect(b.carry).toBeNull();
  });
});

describe("auto-stop", () => {
  it("stops 3 s after the last voice, or 8 s if nothing was said", () => {
    expect(silentTooLong(true, 2900, 20000)).toBe(false);
    expect(silentTooLong(true, 3000, 20000)).toBe(true);
    expect(silentTooLong(false, 9000, 7900)).toBe(false);
    expect(silentTooLong(false, 9000, 8000)).toBe(true);
  });
  it("maps raw loudness to 0..1", () => {
    expect(levelOf(0)).toBe(0);
    expect(levelOf(0.1)).toBeCloseTo(0.5);
    expect(levelOf(0.9)).toBe(1);
  });
});

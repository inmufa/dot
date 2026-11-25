import { apiHeaders, BASE, request } from "./client";
import { DotApiError, describeError } from "./errors";

export interface VoiceStatus { available: boolean; stt: boolean; tts: boolean }
export interface VoiceInfo { id: string; accent: string; gender: string }
export interface VoiceList { default: string; sample_rate: number; voices: VoiceInfo[] }

/** Worker not running (compose profile `voice`, DOT_VOICE=on). */
export const VOICE_DOWN = 4130;

async function fail(res: Response): Promise<never> {
  throw new DotApiError(describeError(res.status, await res.json().catch(() => null)));
}

async function send(path: string, init: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, cache: "no-store" });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new DotApiError(describeError(0, null));
  }
  if (!res.ok) await fail(res);
  return res;
}

export const voiceApi = {
  status: () => request<VoiceStatus>("/v1/voice/status"),
  voices: () => request<VoiceList>("/v1/voice/voices"),
  /** 16 kHz mono WAV in, text out. */
  async transcribe(wav: Blob, signal?: AbortSignal): Promise<{ text: string; duration_s: number | null }> {
    const res = await send("/v1/voice/transcribe", { method: "POST", body: wav, signal, headers: apiHeaders({ "Content-Type": "audio/wav" }) });
    return (await res.json()) as { text: string; duration_s: number | null };
  },
  /** Raw s16le mono stream, one sentence at a time. */
  async speak(text: string, o: { voice?: string; speed?: number }, signal: AbortSignal): Promise<{ body: ReadableStream<Uint8Array>; rate: number }> {
    const res = await send("/v1/voice/speak", {
      method: "POST",
      signal,
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ text, format: "pcm", ...(o.voice ? { voice: o.voice } : {}), speed: o.speed ?? 1 }),
    });
    if (!res.body) throw new DotApiError(describeError(502, null));
    return { body: res.body, rate: Number(res.headers.get("x-sample-rate")) || 24000 };
  },
};

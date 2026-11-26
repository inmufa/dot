"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { DotApiError } from "@/lib/api/errors";
import { voiceApi, VOICE_DOWN } from "@/lib/api/voice";
import { playSound } from "@/lib/sound/engine";
import { getPrefs } from "./prefs";
import { stopSpeaking } from "./speaker";
import { refreshVoice } from "./status";
import { toWav16k } from "./wav";

export type DictationPhase = "idle" | "recording" | "transcribing";
/** denied: mic permission; unsupported: no mic API; down: worker off; failed: other error; quiet: nothing heard. */
export type DictationIssue = { kind: "denied" | "unsupported" | "down" | "failed" | "quiet"; text: string } | null;

const MAX_S = 110; // worker refuses over 120 s
const MIN_S = 0.4;
const SILENCE_MS = 3000; // auto-stop after this long without voice
const NO_SPEECH_MS = 8000; // ...or this long if nothing was said at all
export const VOICE_RMS = 0.015; // above this raw level counts as voice

/** Mic loudness 0..1 for drawing (raw RMS 0.2 is already loud speech). */
export const levelOf = (rms: number): number => Math.min(1, rms * 5);

/** True once the mic has been quiet long enough to stop on its own. */
export function silentTooLong(heard: boolean, quietMs: number, elapsedMs: number): boolean {
  return heard ? quietMs >= SILENCE_MS : elapsedMs >= NO_SPEECH_MS;
}

async function decode(blob: Blob): Promise<Blob> {
  const ac = new AudioContext();
  try {
    const audio = await ac.decodeAudioData(await blob.arrayBuffer());
    const chans = Array.from({ length: audio.numberOfChannels }, (_, i) => audio.getChannelData(i));
    return toWav16k(chans, audio.sampleRate);
  } finally {
    void ac.close();
  }
}

const isMonitor = (label: string) => /monitor|loopback|stereo mix|what u hear|system audio/i.test(label);

/** Open the chosen microphone; if the browser's default is a monitor (system sound), switch to a real input. */
async function openMic(): Promise<MediaStream> {
  const md = navigator.mediaDevices;
  const base = { channelCount: 1, echoCancellation: true, noiseSuppression: true };
  const want = getPrefs().micId;
  let s = await md.getUserMedia({ audio: want ? { ...base, deviceId: { exact: want } } : base }).catch((e: unknown) => {
    if (want && e instanceof DOMException && e.name === "OverconstrainedError") return md.getUserMedia({ audio: base });
    throw e;
  });
  const label = s.getAudioTracks()[0]?.label ?? "";
  if (!want && isMonitor(label)) {
    const real = (await md.enumerateDevices()).find((d) => d.kind === "audioinput" && d.deviceId !== "default" && !isMonitor(d.label));
    if (real) {
      s.getTracks().forEach((t) => t.stop());
      s = await md.getUserMedia({ audio: { ...base, deviceId: { exact: real.deviceId } } });
    }
  }
  return s;
}

export interface Dictation {
  phase: DictationPhase;
  issue: DictationIssue;
  seconds: number;
  start: () => void;
  stop: () => void;
  cancel: () => void;
  /** Live mic loudness 0..1 (0 when not recording). Read it from an animation frame; it does not re-render. */
  level: () => number;
  toggle: () => void;
  clearIssue: () => void;
}

/** Record with MediaRecorder, convert to 16 kHz mono WAV, transcribe. The text goes to `onText`; nothing is sent. */
export function useDictation(onText: (t: string) => void): Dictation {
  const [phase, setPhase] = useState<DictationPhase>("idle");
  const [issue, setIssue] = useState<DictationIssue>(null);
  const [seconds, setSeconds] = useState(0);
  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const t0 = useRef(0);
  const live = useRef(false);
  const pending = useRef(false);
  const discard = useRef(false);
  const abort = useRef<AbortController | null>(null);
  const meter = useRef<{ ac: AudioContext; an: AnalyserNode; buf: Uint8Array<ArrayBuffer> } | null>(null);
  const heard = useRef(false);
  const lastVoice = useRef(0);
  const onTextRef = useRef(onText);
  useEffect(() => { onTextRef.current = onText; });

  const release = () => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (meter.current) { void meter.current.ac.close(); meter.current = null; }
  };
  const rms = useCallback(() => {
    const m = meter.current;
    if (!m) return 0;
    m.an.getByteTimeDomainData(m.buf);
    let sum = 0;
    for (const v of m.buf) { const x = (v - 128) / 128; sum += x * x; }
    return Math.sqrt(sum / m.buf.length);
  }, []);
  const level = useCallback(() => levelOf(rms()), [rms]);

  const finish = useCallback(async (blob: Blob, secs: number) => {
    if (secs < MIN_S) { setPhase("idle"); setIssue({ kind: "quiet", text: "Too short. Hold the button a little longer." }); return; }
    const ac = new AbortController();
    abort.current = ac;
    try {
      const wav = await decode(blob);
      const r = await voiceApi.transcribe(wav, ac.signal);
      if (r.text.trim()) onTextRef.current(r.text.trim());
      else setIssue({ kind: "quiet", text: "Nothing heard. Try again closer to the microphone." });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      if (e instanceof DotApiError && e.info.code === VOICE_DOWN) { void refreshVoice(); setIssue({ kind: "down", text: e.info.title }); }
      else setIssue({ kind: "failed", text: e instanceof DotApiError ? e.info.title : "Could not read that recording." });
    } finally {
      abort.current = null;
      setPhase("idle");
    }
  }, []);

  const stop = useCallback(() => {
    pending.current = false;
    if (rec.current?.state === "recording") rec.current.stop();
  }, []);

  const cancel = useCallback(() => {
    if (abort.current) { abort.current.abort(); return; } // transcribing: drop the result
    discard.current = true;
    stop();
  }, [stop]);

  const start = useCallback(() => {
    if (live.current) return;
    discard.current = false;
    setIssue(null);
    // mediaDevices is undefined on insecure origins
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setIssue({ kind: "unsupported", text: "This browser cannot record audio here." });
      return;
    }
    live.current = true;
    pending.current = true;
    stopSpeaking();
    openMic().then((s) => {
      stream.current = s;
      try {
        const ac = new AudioContext();
        const an = ac.createAnalyser();
        an.fftSize = 1024;
        ac.createMediaStreamSource(s).connect(an);
        void ac.resume();
        meter.current = { ac, an, buf: new Uint8Array(an.fftSize) };
      } catch {
        meter.current = null; // no level: waveform stays flat, auto-stop is off
      }
      heard.current = false;
      lastVoice.current = performance.now();
      const r = new MediaRecorder(s);
      rec.current = r;
      chunks.current = [];
      r.ondataavailable = (e) => { if (e.data.size) chunks.current.push(e.data); };
      r.onstop = () => {
        const secs = (performance.now() - t0.current) / 1000;
        const blob = new Blob(chunks.current, { type: r.mimeType || "audio/webm" });
        chunks.current = [];
        release();
        rec.current = null;
        live.current = false;
        if (discard.current) { discard.current = false; setPhase("idle"); return; }
        setPhase("transcribing");
        playSound("micOff");
        void finish(blob, secs);
      };
      t0.current = performance.now();
      setSeconds(0);
      r.start();
      setPhase("recording");
      playSound("micOn");
      // released before the permission prompt resolved
      if (!pending.current) r.stop();
    }, (e: unknown) => {
      live.current = false;
      const name = e instanceof DOMException ? e.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") setIssue({ kind: "denied", text: "Microphone access is blocked." });
      else if (name === "NotFoundError") setIssue({ kind: "failed", text: "No microphone found." });
      else setIssue({ kind: "failed", text: "Could not open the microphone." });
    });
  }, [finish]);

  useEffect(() => {
    if (phase !== "recording") return;
    const t = window.setInterval(() => {
      const now = performance.now();
      const s = (now - t0.current) / 1000;
      setSeconds(Math.floor(s));
      if (s >= MAX_S) stop();
      if (!meter.current || !getPrefs().autoStop) return;
      if (rms() > VOICE_RMS) { heard.current = true; lastVoice.current = now; }
      else if (silentTooLong(heard.current, now - lastVoice.current, now - t0.current)) stop();
    }, 100);
    return () => window.clearInterval(t);
  }, [phase, stop, rms]);

  useEffect(() => () => {
    abort.current?.abort();
    if (rec.current) { rec.current.onstop = null; if (rec.current.state === "recording") rec.current.stop(); }
    release();
  }, []);

  const toggle = useCallback(() => (rec.current?.state === "recording" ? stop() : start()), [start, stop]);
  return { phase, issue, seconds, start, stop, cancel, level, toggle, clearIssue: () => setIssue(null) };
}


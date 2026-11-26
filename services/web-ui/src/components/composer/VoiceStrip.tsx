"use client";
import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { IconButton } from "@/components/ui";
import type { Dictation } from "@/lib/voice/dictation";
import "./Voice.css";

const BAR = 3;
const GAP = 3;
const STEP_MS = 50; // one new bar per step: the wave scrolls left

export const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** Recording strip that replaces the text box: cancel, live waveform (frozen + shimmer while transcribing), timer. */
export function VoiceStrip({ d }: { d: Dictation }) {
  const cv = useRef<HTMLCanvasElement>(null);
  const bars = useRef<number[]>([]);
  const live = useRef(d);
  const smooth = useRef(0);
  useEffect(() => { live.current = d; });
  const busy = d.phase === "transcribing";

  useEffect(() => {
    const canvas = cv.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const root = canvas.closest<HTMLElement>(".composer");
    let raf = 0;
    let last = 0;
    const draw = (now: number) => {
      const cur = live.current;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
      const n = Math.max(1, Math.floor(w / (BAR + GAP)));
      if (cur.phase === "recording") {
        const raw = cur.level();
        smooth.current += (raw - smooth.current) * (raw > smooth.current ? 0.5 : 0.18); // quick attack, slow release
        const lvl = smooth.current;
        root?.style.setProperty("--voice-lvl", lvl.toFixed(2));
        if (now - last >= STEP_MS) { last = now; bars.current.push(lvl); }
      }
      if (bars.current.length > n) bars.current.splice(0, bars.current.length - n);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = getComputedStyle(canvas).color;
      const data = bars.current;
      const slide = cur.phase === "recording" ? Math.min(1, (now - last) / STEP_MS) * (BAR + GAP) : 0; // glide between steps
      for (let i = 0; i < n; i++) {
        const v = data[data.length - n + i] ?? 0; // newest bar on the right
        const x = w - (n - i) * (BAR + GAP) + GAP - slide;
        if (v < 0.04) { ctx.globalAlpha = 0.45; ctx.fillRect(x, h / 2 - 1, BAR, 2); ctx.globalAlpha = 1; continue; } // dotted baseline
        const bh = Math.max(4, Math.min(h, v * h * 1.1));
        ctx.beginPath();
        ctx.roundRect(x, (h - bh) / 2, BAR, bh, BAR / 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); root?.style.removeProperty("--voice-lvl"); };
  }, []);

  return (
    <div className="vstrip" data-busy={busy || undefined}>
      <IconButton label={busy ? "Cancel transcription" : "Cancel recording"} className="vs-cancel" onClick={d.cancel}><X size={18} aria-hidden /></IconButton>
      <div className="vs-wave" role="img" aria-label={busy ? "Transcribing" : "Microphone level"}>
        <canvas ref={cv} />
      </div>
      <span className="vs-time" role="status" aria-live="off">{busy ? "Transcribing" : clock(d.seconds)}</span>
    </div>
  );
}

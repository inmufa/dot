"use client";
import { useRef, useState } from "react";
import { Button, Popover } from "@/components/ui";
import { shortModel } from "@/components/composer/ControlRow";
import { useCap } from "@/lib/api/caps";
import { useApp } from "@/lib/state/app";
import { compactTokens, percent } from "@/lib/util/format";

const num = (n: unknown): number => (typeof n === "number" && Number.isFinite(n) ? n : 0);
const gb = (mb: unknown) => (num(mb) / 1024).toFixed(1);

/** Quiet trust cue under the greeting: short model name, details in a popover. */
export function ModelChip() {
  const { telemetry: t, ui, chat } = useApp();
  const known = useCap("telemetry");
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);

  if (!known) return <p className="model-line rec">local</p>;
  if (!t) return <p className="model-line rec" aria-busy="true">local model</p>;
  const name = shortModel(t.model) || "Local model";
  const status = t.state === "ready" ? null : t.state === "loading" ? "loading" : "offline";
  const vramTotal = num(t.vram_total_mb);
  const ctxLimit = num(t.ctx_limit);
  // same figure as the composer's Context meter (prompt + history), not the idle slot's 0
  const ctxUsed = chat.usage && chat.usage.limit > 0 ? chat.usage.tokens : num(t.ctx_used);
  return (
    <>
      <button ref={btn} type="button" className="model-line model-btn rec" aria-expanded={open} aria-haspopup="dialog" onClick={() => setOpen((v) => !v)}>
        <span className="model-led" data-tone={t.state === "ready" ? "ok" : t.state === "loading" ? "warn" : "bad"} aria-hidden />
        <span className="model-name" title={t.model}>{name}</span>
        {ctxLimit > 0 && <span>{compactTokens(ctxLimit)} context</span>}
        <span className={status ? "model-status" : undefined}>{status ?? "local"}</span>
      </button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={btn} side="bottom" align="start" label="Local model details">
        <div className="model-pop">
          <p className="model-pop-title">{t.state === "ready" ? "Ready on this machine" : t.state === "loading" ? "Loading the model" : "Model server is down"}</p>
          <dl className="model-stats">
            {vramTotal > 0 && <div><dt>GPU memory</dt><dd className="tnum">{gb(t.vram_used_mb)} of {gb(vramTotal)} GB ({percent(num(t.vram_used_mb), vramTotal)}%)</dd></div>}
            {ctxLimit > 0 && <div><dt>Context</dt><dd className="tnum">{compactTokens(ctxUsed)} of {compactTokens(ctxLimit)} ({percent(ctxUsed, ctxLimit)}%)</dd></div>}
            <div><dt>Speed</dt><dd className="tnum">{num(t.tok_s) > 0 ? `${num(t.tok_s).toFixed(1)} tok/s` : "idle"}</dd></div>
            <div><dt>Slots</dt><dd className="tnum">{num(t.slots.busy)} of {num(t.slots.total)} busy</dd></div>
          </dl>
          <Button size="sm" onClick={() => { setOpen(false); ui.openOverlay("model"); }}>Change model</Button>
        </div>
      </Popover>
    </>
  );
}

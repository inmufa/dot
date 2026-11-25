import type { Telemetry } from "./types";

// Backend wire shape (docs/api-contract.md, GET /v1/telemetry).
interface WireSlot { busy?: boolean; context_used?: number | null; context_size?: number | null }
interface WireTelemetry {
  llm_up?: boolean;
  model?: string | null;
  context_size?: number | null;
  slots?: WireSlot[] | null;
  tokens_per_s?: number | null;
  vram_used_mb?: number | null;
  vram_total_mb?: number | null;
  voice_up?: boolean;
  vision?: boolean;
}

const n = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) ? v : 0);

/** Map the backend payload to the UI model; llm_up false is "down". */
export function toTelemetry(w: WireTelemetry): Telemetry {
  const slots = Array.isArray(w.slots) ? w.slots : [];
  return {
    model: w.model ?? "",
    state: w.llm_up ? "ready" : "down",
    ctx_used: Math.max(0, ...slots.map((s) => n(s.context_used))),
    ctx_limit: n(w.context_size),
    vram_used_mb: n(w.vram_used_mb),
    vram_total_mb: n(w.vram_total_mb),
    tok_s: n(w.tokens_per_s),
    slots: { busy: slots.filter((s) => s.busy).length, total: slots.length },
    vision: Boolean(w.vision),
    voice: Boolean(w.voice_up),
  };
}

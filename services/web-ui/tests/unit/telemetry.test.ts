import { describe, expect, it } from "vitest";
import { toTelemetry } from "@/lib/api/telemetry";

describe("toTelemetry", () => {
  it("maps the real backend payload", () => {
    const t = toTelemetry({
      llm_up: true, model: "Qwen.gguf", context_size: 32768, tokens_per_s: 27.4,
      slots: [{ busy: true, context_used: 3971, context_size: 32768 }, { busy: false, context_used: null, context_size: 32768 }],
      vram_used_mb: 7524, vram_total_mb: 8192, voice_up: true, vision: true,
    });
    expect(t).toEqual({ model: "Qwen.gguf", state: "ready", ctx_used: 3971, ctx_limit: 32768, vram_used_mb: 7524, vram_total_mb: 8192, tok_s: 27.4, slots: { busy: 1, total: 2 }, vision: true, voice: true });
  });

  it("treats llm_up false with nulls as down", () => {
    const t = toTelemetry({ llm_up: false, model: null, context_size: null, slots: null, tokens_per_s: null });
    expect(t.state).toBe("down");
    expect(t.slots).toEqual({ busy: 0, total: 0 });
    expect(t.ctx_limit).toBe(0);
  });
});

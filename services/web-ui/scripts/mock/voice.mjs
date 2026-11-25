// Voice mock: status, transcribe, speak (sine tones, one sentence per burst), voices.
// Control: /__voice?mode=ok|down|fail (down answers 4130 like a stopped worker, fail answers 4135).
import { json, readRaw, readBody, sleep } from "./core.mjs";

export const voiceMode = { v: "ok" };
export const voiceControl = (url, res) => (voiceMode.v = url.searchParams.get("mode") ?? "ok", json(res, 200, { mode: voiceMode.v }));

const RATE = 24000;
const NAMES = "af_alloy af_aoede af_bella af_heart af_jessica af_kore af_nicole af_nova af_river af_sarah af_sky am_adam am_echo am_eric am_fenrir am_liam am_michael am_onyx am_puck am_santa bf_alice bf_emma bf_isabella bf_lily bm_daniel bm_fable bm_george bm_lewis".split(" ");

const tone = (seconds, hz) => {
  const n = Math.floor(seconds * RATE);
  const b = Buffer.alloc(n * 2);
  for (let i = 0; i < n; i++) b.writeInt16LE(Math.round(Math.sin((2 * Math.PI * hz * i) / RATE) * 3000 * Math.min(1, i / 400, (n - i) / 400)), i * 2);
  return b;
};

export async function voiceRoutes(req, res, p, url, fail) {
  if (!p.startsWith("/v1/voice/")) return false;
  const sub = p.slice("/v1/voice/".length);
  if (sub === "status") return json(res, 200, { available: voiceMode.v !== "down", stt: voiceMode.v !== "down", tts: voiceMode.v !== "down" }), true;
  if (voiceMode.v === "down") return fail(4130, "Voice is not running (set DOT_VOICE=on and run: make up-voice)", 503), true;
  if (voiceMode.v === "fail" && sub !== "voices") return fail(4135, "Voice service failed", 502), true;
  if (sub === "voices") return json(res, 200, { default: "af_heart", sample_rate: RATE, voices: NAMES.map((id) => ({ id, accent: id[0] === "a" ? "US" : "UK", gender: id[1] === "f" ? "female" : "male" })) }), true;
  if (sub === "transcribe" && req.method === "POST") {
    const raw = await readRaw(req, 4_000_000);
    if (!raw) return fail(4131, "Audio is too large", 413), true;
    await sleep(900);
    return json(res, 200, { text: "Summarize the failing tests in the billing module.", duration_s: Math.max(0, raw.length - 44) / 32000 }), true;
  }
  if (sub === "speak" && req.method === "POST") {
    const body = await readBody(req);
    const sentences = String(body.text ?? "").split(/(?<=[.!?])\s+/).filter(Boolean).slice(0, 20);
    if (!sentences.length) return fail(4134, "Nothing to read aloud", 422), true;
    res.writeHead(200, { "Content-Type": "audio/L16", "X-Sample-Rate": String(RATE), "Cache-Control": "no-store" });
    let open = true;
    res.on("close", () => { open = false; });
    for (const [i, s] of sentences.entries()) {
      if (!open) return true;
      await sleep(i ? 150 : 400);
      res.write(tone(Math.min(2.5, 0.4 + s.length / 40), 330 + (i % 3) * 55));
    }
    res.end();
    return true;
  }
  return false;
}

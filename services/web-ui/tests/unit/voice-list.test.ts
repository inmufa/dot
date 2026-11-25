import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { groupVoices, parseManifest, voiceName } from "@/lib/voice/samples";
import { getSpeaker, playClip, stopSpeaking, toggleClip } from "@/lib/voice/speaker";

const V = (id: string, accent: string, gender: string) => ({ id, accent, gender });

describe("voice list helpers", () => {
  it("names and groups voices by accent and gender, sorted inside a group", () => {
    expect(voiceName("af_heart")).toBe("Heart");
    const g = groupVoices([V("af_sky", "US", "female"), V("bm_lewis", "UK", "male"), V("af_alloy", "US", "female")]);
    expect(g.map((x) => x.label)).toEqual(["American, female", "British, male"]);
    expect(g[0]?.voices.map((v) => v.id)).toEqual(["af_alloy", "af_sky"]);
  });
  it("reads clip URLs from the manifest and drops unsafe or malformed entries", () => {
    const m = parseManifest({ text: "Hi", voices: [{ id: "af_heart", file: "af_heart.ogg" }, { id: "x", file: "../secret.ogg" }, { id: 3, file: "a.ogg" }] });
    expect(m).toEqual({ text: "Hi", clips: { af_heart: "/voice-samples/af_heart.ogg" } });
    expect(parseManifest(null).clips).toEqual({});
  });
});

class FakeAudio {
  static all: FakeAudio[] = [];
  paused = true;
  onplaying: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public src: string) { FakeAudio.all.push(this); }
  static at(i: number): FakeAudio { const a = FakeAudio.all[i]; if (!a) throw new Error(`no audio ${i}`); return a; }
  play() { this.paused = false; return Promise.resolve(); }
  pause() { this.paused = true; }
}

describe("clip previews", () => {
  beforeEach(() => {
    FakeAudio.all = [];
    vi.stubGlobal("Audio", FakeAudio);
    vi.stubGlobal("document", { addEventListener: vi.fn(), removeEventListener: vi.fn() });
  });
  afterEach(() => { stopSpeaking(); vi.unstubAllGlobals(); });

  it("plays one clip at a time: starting another stops the first", () => {
    playClip("clip:a", "/a.ogg");
    const a = FakeAudio.at(0);
    a.onplaying?.();
    expect(getSpeaker()).toEqual({ phase: "playing", key: "clip:a" });
    playClip("clip:b", "/b.ogg");
    expect(a.paused).toBe(true);
    expect(getSpeaker()).toEqual({ phase: "loading", key: "clip:b" });
    a.onplaying?.(); // stale events from the stopped clip are ignored
    expect(getSpeaker().key).toBe("clip:b");
  });
  it("toggle stops the playing clip; the end of a clip resets state", () => {
    toggleClip("clip:a", "/a.ogg");
    FakeAudio.at(0).onplaying?.();
    toggleClip("clip:a", "/a.ogg");
    expect(FakeAudio.at(0).paused).toBe(true);
    expect(getSpeaker().phase).toBe("idle");
    toggleClip("clip:b", "/b.ogg");
    FakeAudio.at(1).onended?.();
    expect(getSpeaker()).toEqual({ phase: "idle", key: null });
  });
});

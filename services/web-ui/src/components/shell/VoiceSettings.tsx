"use client";
import { useEffect, useState } from "react";
import { Play, Square } from "lucide-react";
import { Button, Segmented, Skeletons, Switch } from "@/components/ui";
import { useCap } from "@/lib/api/caps";
import { voiceApi, type VoiceInfo } from "@/lib/api/voice";
import { SPEEDS, setPrefs, useVoicePrefs } from "@/lib/voice/prefs";
import { loadSamples, voiceName, groupLabel } from "@/lib/voice/samples";
import { getSpeaker, speak, stopSpeaking, useSpeaker } from "@/lib/voice/speaker";
import { refreshVoice, useVoice } from "@/lib/voice/status";
import { CopyCmd } from "./CopyCmd";
import { SettingGroup, SettingRow } from "./SettingRow";
import { VoiceList } from "./VoiceList";

const SAMPLE = "Hi, this is how I sound. Pick the voice and pace you like.";
const SAMPLE_KEY = "voice-test";
const INTRO = "Dictation and Read aloud run offline on this machine.";

/** Settings section: voice list with per-voice previews, speed and a live test, or the "not running" state with the command to start it. */
export function VoiceSettings({ open }: { open: boolean }) {
  const cap = useCap("voice");
  const v = useVoice();
  const prefs = useVoicePrefs();
  const sp = useSpeaker();
  const testing = sp.key === SAMPLE_KEY && sp.phase !== "idle";
  const play = () => { speak(SAMPLE_KEY, SAMPLE).catch(() => undefined); };
  const test = () => { if (testing) stopSpeaking(); else play(); };
  const [voices, setVoices] = useState<{ list: VoiceInfo[]; def: string } | null>(null);
  const [clips, setClips] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!open || !cap) return;
    void refreshVoice();
  }, [open, cap]);
  useEffect(() => {
    if (!open || v.state !== "up" || !v.tts || voices) return;
    voiceApi.voices().then((r) => setVoices({ list: r.voices, def: r.default }), () => undefined);
    loadSamples().then((m) => setClips(m.clips), () => undefined);
  }, [open, v.state, v.tts, voices]);
  // closing Settings silences its previews, not Read aloud elsewhere
  useEffect(() => {
    if (open) return;
    const k = getSpeaker().key;
    if (k === SAMPLE_KEY || k?.startsWith("clip:")) stopSpeaking();
  }, [open]);
  if (!cap || v.state === "missing") return null;
  if (v.state === "down") {
    return (
      <SettingGroup title="Voice" intro={INTRO}>
        <SettingRow label="Voice is not running" hint="Set DOT_VOICE=on and DOT_VOICE_TOKEN in .env, then run this in the project folder." layout="block">
          <div className="st-voice-off">
            <CopyCmd cmd="make up-voice" />
            <Button variant="ghost" size="sm" onClick={() => void refreshVoice()}>Check again</Button>
          </div>
        </SettingRow>
      </SettingGroup>
    );
  }
  const speed = SPEEDS.find((s) => s === prefs.speed) ?? 1;
  const current = voices ? (voices.list.find((x) => x.id === (prefs.voice || voices.def)) ?? null) : null;
  return (
    <SettingGroup title="Voice" intro={INTRO}>
      <SettingRow label="Speed" hint="Reading pace. Changing it plays the test sample.">
        <Segmented label="Speech speed" value={String(speed)} options={SPEEDS.map((s) => ({ value: String(s), label: `${s}x` }))} onChange={(x) => { setPrefs({ speed: Number(x) }); setTimeout(play, 0); }} />
      </SettingRow>
      <SettingRow label="Test voice" hint="Reads a sample live with the chosen voice and speed.">
        <Button size="sm" variant="soft" onClick={test} disabled={!voices}>
          {testing ? <><Square size={12} fill="currentColor" aria-hidden /> Stop</> : <><Play size={12} fill="currentColor" aria-hidden /> {sp.phase === "loading" && sp.key === SAMPLE_KEY ? "Loading" : "Play sample"}</>}
        </Button>
      </SettingRow>
      <SettingRow label="Stop on silence" htmlFor="voice-autostop" layout="inline" hint="Dictation finishes by itself after about 3 seconds without speech.">
        <Switch id="voice-autostop" checked={prefs.autoStop} onChange={(e) => setPrefs({ autoStop: e.target.checked })} />
      </SettingRow>
      <SettingRow
        label={current ? <>Read aloud voice <span className="st-current">{voiceName(current.id)} ({groupLabel(current)})</span></> : "Read aloud voice"}
        hint="Press play next to any voice to hear it. Choosing a voice does not play it."
        layout="block"
      >
        {voices ? (
          <VoiceList voices={voices.list} value={prefs.voice || voices.def} def={voices.def} clips={clips} onChange={(id) => setPrefs({ voice: id })} />
        ) : (
          <Skeletons n={3} />
        )}
      </SettingRow>
    </SettingGroup>
  );
}

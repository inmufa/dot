"use client";
import { Square, Volume2 } from "lucide-react";
import { IconButton } from "@/components/ui";
import { useCap } from "@/lib/api/caps";
import { DotApiError } from "@/lib/api/errors";
import { useApp } from "@/lib/state/app";
import { speak, stopSpeaking, useSpeaker } from "@/lib/voice/speaker";
import "@/components/composer/Voice.css";
import { useVoice } from "@/lib/voice/status";

/** Stable key per message text, so only the playing message shows Stop. */
const keyOf = (t: string): string => `${t.length}:${t.slice(0, 48)}`;

/** Read aloud (hover action). Streams sentence by sentence; click again, or Esc, to stop. */
export function ReadAloud({ text }: { text: string }) {
  const app = useApp();
  const cap = useCap("voice");
  const v = useVoice();
  const sp = useSpeaker();
  const key = keyOf(text);
  const mine = sp.key === key && sp.phase !== "idle";
  if (!cap || v.state === "missing") return null;
  const off = v.state === "down" || (v.state === "up" && !v.tts);
  const click = () => {
    if (mine) { stopSpeaking(); return; }
    if (off) { app.notify("Voice is not running. Set DOT_VOICE=on and run make up-voice."); return; }
    speak(key, text).catch((e: unknown) => app.notify(e instanceof DotApiError ? e.info.title : "Could not read this aloud."));
  };
  return (
    <IconButton size="sm" label={mine ? "Stop reading (Esc)" : "Read aloud"} className="say" data-on={mine || undefined} aria-disabled={off || undefined} aria-busy={mine && sp.phase === "loading" ? true : undefined} onClick={click}>
      {mine ? <Square size={14} fill="currentColor" aria-hidden /> : <Volume2 size={16} aria-hidden />}
    </IconButton>
  );
}

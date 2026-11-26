"use client";
import { Mic, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, IconButton, Kbd, Popover } from "@/components/ui";
import { useCap } from "@/lib/api/caps";
import type { Dictation } from "@/lib/voice/dictation";
import { useApp } from "@/lib/state/app";
import { refreshVoice, useVoice } from "@/lib/voice/status";
import "./Voice.css";

/** What the notice popover says for the current problem. */
function notice(down: boolean, issue: Dictation["issue"]): { title: string; body: React.ReactNode } | null {
  if (issue?.kind === "denied") return { title: "Microphone is blocked", body: "Allow the microphone for this site in the browser address bar, then try again." };
  if (issue?.kind === "unsupported") return { title: "Recording is not available", body: issue.text + " Open Dot on http://127.0.0.1 or over HTTPS." };
  if (issue) return { title: issue.kind === "quiet" ? "Nothing to transcribe" : "Voice input failed", body: issue.text };
  if (down) return { title: "Voice is not running", body: <>Set <code>DOT_VOICE=on</code> and <code>DOT_VOICE_TOKEN</code> in <code>.env</code>, then run <code>make up-voice</code>. Speech stays on this machine.</> };
  return null;
}

/** Click to record, click again to stop and transcribe into the composer. Esc cancels. */
export function MicButton({ d, disabled }: { d: Dictation; disabled?: boolean }) {
  const anchor = useRef<HTMLButtonElement>(null);
  const app = useApp();
  const cap = useCap("voice");
  const v = useVoice();
  const down = v.state === "down" || (v.state === "up" && !v.stt);
  const [asked, setAsked] = useState(false);
  const info = notice(down && asked, d.issue);
  const open = info !== null && d.phase === "idle";
  const rec = d.phase === "recording";
  const busy = d.phase === "transcribing";
  useEffect(() => {
    if (!rec && !busy) return;
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopPropagation(); d.cancel(); }
      else if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.stopPropagation(); if (rec) d.stop(); } // finish, never send
    };
    document.addEventListener("keydown", k, true);
    return () => document.removeEventListener("keydown", k, true);
  }, [rec, busy, d]);
  useEffect(() => { if (!down) setAsked(false); }, [down]);

  const click = () => {
    if (!cap || v.state === "missing") { app.notify("Voice is not available yet."); return; }
    if (down) { void refreshVoice(); d.clearIssue(); setAsked(true); return; }
    d.toggle();
  };
  const label = busy ? "Transcribing" : "Dictate";
  return (
    <>
      {rec && (
        <IconButton label="Stop and transcribe" className="mic mic-done" data-phase="recording" pressed={false} onClick={d.toggle}>
          <Square size={12} fill="currentColor" aria-hidden />
        </IconButton>
      )}
      {!rec && (
        <IconButton
          ref={anchor}
          label={label}
          className="mic"
          data-phase={d.phase}
          data-off={down || v.state === "missing" || undefined}
          aria-disabled={disabled || busy || undefined}
          pressed={false}
          onClick={disabled || busy ? undefined : click}
        >
          <Mic size={18} aria-hidden />
          {busy && <span className="mic-spin" aria-hidden />}
        </IconButton>
      )}
      <Popover open={open} onClose={() => { d.clearIssue(); setAsked(false); }} anchorRef={anchor} side="top" align="end" label="Voice" className="voice-pop">
        <h3>{info?.title}</h3>
        <p>{info?.body}</p>
        {d.issue?.kind === "denied" || d.issue?.kind === "unsupported" ? null : (
          <p>Hold <Kbd>Space</Kbd> in an empty message to talk.</p>
        )}
        <div className="row">
          {d.issue === null && <Button size="sm" onClick={() => void refreshVoice()}>Check again</Button>}
          <Button size="sm" variant="ghost" onClick={() => { d.clearIssue(); setAsked(false); }}>Close</Button>
        </div>
      </Popover>
    </>
  );
}

"use client";
import { useId } from "react";
import { Play, Square } from "lucide-react";
import { IconButton, Radio } from "@/components/ui";
import type { VoiceInfo } from "@/lib/api/voice";
import { groupVoices, voiceName } from "@/lib/voice/samples";
import { toggleClip, useSpeaker } from "@/lib/voice/speaker";

export const clipKey = (id: string) => `clip:${id}`;

interface Props {
  voices: VoiceInfo[];
  value: string;
  def: string;
  onChange: (id: string) => void;
  /** voice id -> clip URL; voices without one get no play button */
  clips: Record<string, string>;
}

/** Voice picker: native radios (arrow keys move the choice), grouped by accent; each row has its own preview button. Choosing never plays. */
export function VoiceList({ voices, value, def, onChange, clips }: Props) {
  const name = useId();
  const sp = useSpeaker();
  return (
    <div className="vl" role="radiogroup" aria-label="Read aloud voice">
      {groupVoices(voices).map((g) => (
        <div key={g.label} className="vl-group" role="group" aria-label={g.label}>
          <div className="vl-group-label" aria-hidden>{g.label}</div>
          <ul className="vl-items">
            {g.voices.map((v) => {
              const n = voiceName(v.id);
              const on = sp.key === clipKey(v.id) && sp.phase !== "idle";
              const url = clips[v.id];
              return (
                <li key={v.id} className="vl-item" data-selected={value === v.id || undefined} data-playing={on || undefined}>
                  <Radio className="vl-pick" name={name} value={v.id} checked={value === v.id} onChange={() => onChange(v.id)}>
                    <span className="vl-name">{n}{v.id === def && <span className="vl-def"> default</span>}</span>
                  </Radio>
                  {url && (
                    <IconButton size="sm" className="vl-play" label={on ? `Stop ${n} sample` : `Play ${n} sample`} onClick={() => toggleClip(clipKey(v.id), url)}>
                      {on ? <Square size={12} fill="currentColor" aria-hidden /> : <Play size={13} fill="currentColor" aria-hidden />}
                    </IconButton>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

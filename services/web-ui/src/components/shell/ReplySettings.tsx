"use client";
import { useEffect, useState } from "react";
import { Segmented } from "@/components/ui";
import { request } from "@/lib/api/client";
import { SettingGroup, SettingRow } from "./SettingRow";

type Tone = "supportive" | "balanced" | "blunt";
type Emoji = "normal" | "less" | "none";
interface Style { tone: Tone; emoji: Emoji }

const TONES: { value: Tone; label: string }[] = [
  { value: "supportive", label: "Supportive" },
  { value: "balanced", label: "Balanced" },
  { value: "blunt", label: "Blunt" },
];
const EMOJIS: { value: Emoji; label: string }[] = [
  { value: "normal", label: "Normal" },
  { value: "less", label: "Less" },
  { value: "none", label: "None" },
];

/** Reply tone and emoji use, stored by the backend and applied from the next message. */
export function ReplySettings({ open }: { open: boolean }) {
  const [style, setStyle] = useState<Style | null>(null);
  useEffect(() => {
    if (!open) return;
    request<Style>("/v1/preferences").then(setStyle, () => setStyle(null));
  }, [open]);
  const save = (patch: Partial<Style>) => {
    if (!style) return;
    const next = { ...style, ...patch };
    setStyle(next);
    request<Style>("/v1/preferences", { method: "PUT", body: JSON.stringify(next) }).then(setStyle, () => setStyle(style));
  };
  if (!style) return null;
  return (
    <SettingGroup title="Replies" intro="Applies from your next message. Dot always says when you are wrong and suggests better options, in any tone.">
      <SettingRow label="Tone" hint="Supportive is warm, Blunt skips the softening.">
        <Segmented label="Tone" value={style.tone} options={TONES} onChange={(tone) => save({ tone })} />
      </SettingRow>
      <SettingRow label="Emojis" hint="How often answers use them.">
        <Segmented label="Emojis" value={style.emoji} options={EMOJIS} onChange={(emoji) => save({ emoji })} />
      </SettingRow>
    </SettingGroup>
  );
}

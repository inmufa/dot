import { useId } from "react";
import { Segmented, Select, Sheet, Switch } from "@/components/ui";
import type { Lang, Settings, Theme } from "@/hooks/useSettings";
import { PalettePicker } from "./PalettePicker";
import { SettingGroup, SettingRow } from "./SettingRow";
import { BuddySettings } from "./BuddySettings";
import { ReplySettings } from "./ReplySettings";
import { VoiceSettings } from "./VoiceSettings";
import "./settings.css";

interface Props {
  open: boolean;
  onClose: () => void;
  settings: Settings;
  onChange: (p: Partial<Settings>) => void;
  backend: string | null;
  configured: boolean | null;
}

const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];
const DENSITY = [
  { value: "roomy", label: "Roomy" },
  { value: "compact", label: "Compact" },
] as const;
const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "ru", label: "Русский" },
  { id: "uz", label: "O‘zbekcha" },
];

type Flag = "showThinking" | "verbose" | "sounds";
const FLAGS: { key: Flag; label: string; hint: string }[] = [
  { key: "showThinking", label: "Show thinking while streaming", hint: "Off: a quiet line with a timer you can open." },
  { key: "verbose", label: "Verbose view", hint: "Expand tool calls with their full input and output." },
  { key: "sounds", label: "Sounds", hint: "A short tone for approvals and finished runs." },
];

export function SettingsSheet({ open, onClose, settings, onChange, backend, configured }: Props) {
  const id = useId();
  return (
    <Sheet open={open} onClose={onClose} title="Settings" wide>
      <div className="st">
        <SettingGroup title="Appearance">
          <SettingRow label="Theme" hint="System follows your OS.">
            <Segmented label="Theme" value={settings.theme} options={THEMES} onChange={(theme) => onChange({ theme })} />
          </SettingRow>
          <SettingRow label="Density" hint="Compact tightens spacing and text.">
            <Segmented label="Density" value={settings.density} options={[...DENSITY]} onChange={(density) => onChange({ density })} />
          </SettingRow>
          <SettingRow label="Palette" hint="Accent and surface tones. Works in light and dark." layout="block">
            <PalettePicker value={settings.palette} onChange={(palette) => onChange({ palette })} />
          </SettingRow>
        </SettingGroup>

        <BuddySettings />

        <ReplySettings open={open} />

        <SettingGroup title="Chat">
          {FLAGS.map((f) => (
            <SettingRow key={f.key} label={f.label} hint={f.hint} htmlFor={`${id}-${f.key}`} layout="inline">
              <Switch id={`${id}-${f.key}`} aria-describedby={`${id}-${f.key}-hint`} checked={settings[f.key]} onChange={(e) => onChange({ [f.key]: e.target.checked })} />
            </SettingRow>
          ))}
        </SettingGroup>

        <VoiceSettings open={open} />

        <SettingGroup title="Language">
          <SettingRow label="Backend messages" hint="Sent as Accept-Language. Error texts follow it." htmlFor={`${id}-lang`}>
            <Select id={`${id}-lang`} aria-describedby={`${id}-lang-hint`} value={settings.lang} onChange={(e) => onChange({ lang: e.target.value as Lang })}>
              {LANGS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
            </Select>
          </SettingRow>
        </SettingGroup>

        <SettingGroup title="Connection" intro={configured === false ? "DOT_API_TOKEN is missing on the web UI server." : "The token stays on the web UI server. The browser never sees it."}>
          <SettingRow label="Backend">
            <span className="st-value rec" title={backend ?? undefined}>{backend ?? "invalid DOT_URL"}</span>
          </SettingRow>
          <SettingRow label="API token">
            <span className="st-value rec" data-warn={configured === false || undefined}>{configured === false ? "not set" : "set on the server"}</span>
          </SettingRow>
        </SettingGroup>
      </div>
    </Sheet>
  );
}

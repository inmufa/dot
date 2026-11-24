import type { Lang, Settings, Theme } from "@/hooks/useSettings";
import { Sheet } from "../ui/Sheet";

interface Props {
  open: boolean;
  onClose: () => void;
  settings: Settings;
  onChange: (p: Partial<Settings>) => void;
  backend: string | null;
  configured: boolean | null;
}

const THEMES: Theme[] = ["system", "light", "dark"];
const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "ru", label: "Русский" },
  { id: "uz", label: "O‘zbekcha" },
];

export function SettingsSheet({ open, onClose, settings, onChange, backend, configured }: Props) {
  return (
    <Sheet open={open} onClose={onClose} title="Settings">
      <div className="field">
        <span className="label" id="theme-label">Theme</span>
        <div className="seg" role="radiogroup" aria-labelledby="theme-label">
          {THEMES.map((t) => (
            <label key={t}>
              <input type="radio" name="theme" checked={settings.theme === t} onChange={() => onChange({ theme: t })} />
              {t[0]?.toUpperCase()}
              {t.slice(1)}
            </label>
          ))}
        </div>
        <span className="help">System follows your OS setting.</span>
      </div>
      <div className="field">
        <label htmlFor="lang">Backend message language</label>
        <select id="lang" className="input" value={settings.lang} onChange={(e) => onChange({ lang: e.target.value as Lang })}>
          {LANGS.map((l) => (
            <option key={l.id} value={l.id}>{l.label}</option>
          ))}
        </select>
        <span className="help">Sent as Accept-Language. Error texts from the backend follow it.</span>
      </div>
      <div className="field">
        <span className="label">Backend</span>
        <code className="plain">{backend ?? "invalid DOT_URL"}</code>
        <span className="help">
          {configured === false
            ? "DOT_API_TOKEN is not set on the web UI server."
            : "The API token stays on the web UI server. The browser never sees it."}
        </span>
      </div>
      <div className="field">
        <span className="label">Keys</span>
        <dl className="keys">
          <dt><kbd>Enter</kbd></dt><dd>send</dd>
          <dt><kbd>Shift</kbd> <kbd>Enter</kbd></dt><dd>new line</dd>
          <dt><kbd>/</kbd></dt><dd>focus composer, open commands</dd>
          <dt><kbd>Esc</kbd></dt><dd>stop the running turn (in the composer)</dd>
          <dt><kbd>a</kbd> <kbd>s</kbd> <kbd>r</kbd></dt><dd>allow once, allow for session, reject</dd>
        </dl>
      </div>
    </Sheet>
  );
}
